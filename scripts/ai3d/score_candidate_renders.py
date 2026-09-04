#!/usr/bin/env python3
"""Score candidate render silhouettes against the locked CH101 turnaround."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        read_json,
        require_reference_manifest,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        read_json,
        require_reference_manifest,
        write_json,
    )


CARDINAL_CYCLE = ("neg_y", "pos_x", "pos_y", "neg_x")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--evaluation-report", required=True, type=Path)
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        help="Optional provider manifest carrying semantic component evidence.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    return parser.parse_args()


def _normalize_view(
    path: Path,
    candidate: bool,
    size: int = 256,
    vertical_flip: bool = False,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install pillow") from exc
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
    if vertical_flip:
        rgba = ImageOps.flip(rgba)
    if candidate:
        mask = rgba.getchannel("A").point(lambda value: 255 if value > 16 else 0)
    else:
        rgb = rgba.convert("RGB")
        background = Image.new("RGB", rgb.size, "white")
        difference = ImageChops.difference(rgb, background).convert("L")
        mask = difference.point(lambda value: 255 if value > 12 else 0)
        mask = mask.filter(ImageFilter.MaxFilter(5))
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError(f"empty silhouette mask: {path}")
    cropped_mask = mask.crop(bbox)
    cropped_rgba = rgba.crop(bbox)
    contained_mask = ImageOps.contain(
        cropped_mask, (size - 24, size - 16), Image.Resampling.LANCZOS
    )
    contained_rgba = ImageOps.contain(
        cropped_rgba, (size - 24, size - 16), Image.Resampling.LANCZOS
    )
    mask_canvas = Image.new("L", (size, size), 0)
    rgb_canvas = Image.new("RGB", (size, size), "white")
    offset = ((size - contained_mask.width) // 2, size - contained_mask.height - 8)
    mask_canvas.paste(contained_mask, offset)
    rgb_canvas.paste(contained_rgba.convert("RGB"), offset, contained_mask)
    solid = mask_canvas.copy()
    pixels = solid.load()
    for y in range(size):
        active = [x for x in range(size) if pixels[x, y] > 32]
        if active:
            for x in range(active[0], active[-1] + 1):
                pixels[x, y] = 255
    return {"mask": solid, "detailMask": mask_canvas, "rgb": rgb_canvas}


def _iou(left, right) -> float:
    from PIL import ImageChops

    intersection = ImageChops.logical_and(left.convert("1"), right.convert("1"))
    union = ImageChops.logical_or(left.convert("1"), right.convert("1"))
    intersection_count = sum(intersection.histogram()[1:])
    union_count = sum(union.histogram()[1:])
    return intersection_count / union_count if union_count else 0.0


def _edge_mask(view: dict[str, Any], face_only: bool = False):
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    edges = ImageOps.grayscale(view["rgb"]).filter(ImageFilter.FIND_EDGES)
    edges = edges.point(lambda value: 255 if value > 24 else 0)
    edges = ImageChops.logical_and(edges.convert("1"), view["detailMask"].convert("1")).convert("L")
    edges = edges.filter(ImageFilter.MaxFilter(5))
    if face_only:
        region = Image.new("L", edges.size, 0)
        face_bottom = int(edges.height * 0.38)
        region.paste(255, (0, 0, edges.width, face_bottom))
        edges = ImageChops.logical_and(edges.convert("1"), region.convert("1")).convert("L")
    return edges


def _color_histogram(view: dict[str, Any]) -> list[float]:
    rgb = view["rgb"]
    mask = view["detailMask"]
    bins = [0] * 64
    total = 0
    rgb_data = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata()
    mask_data = mask.get_flattened_data() if hasattr(mask, "get_flattened_data") else mask.getdata()
    for pixel, active in zip(rgb_data, mask_data):
        if active <= 32:
            continue
        red, green, blue = pixel
        index = (red // 64) * 16 + (green // 64) * 4 + (blue // 64)
        bins[min(index, 63)] += 1
        total += 1
    if not total:
        return [0.0] * 64
    return [value / total for value in bins]


def _histogram_intersection(left: list[float], right: list[float]) -> float:
    return sum(min(a, b) for a, b in zip(left, right))


def _mask_component_metrics(mask: Any) -> dict[str, Any]:
    """Measure detached visible regions on the unfilled alpha/detail mask."""
    binary = mask.convert("1")
    width, height = binary.size
    pixels = binary.load()
    visited = bytearray(width * height)
    component_areas: list[int] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or not pixels[x, y]:
                continue
            visited[index] = 1
            stack = [(x, y)]
            area = 0
            while stack:
                current_x, current_y = stack.pop()
                area += 1
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if visited[next_index] or not pixels[next_x, next_y]:
                        continue
                    visited[next_index] = 1
                    stack.append((next_x, next_y))
            component_areas.append(area)
    component_areas.sort(reverse=True)
    total_area = sum(component_areas)
    largest = component_areas[0] if component_areas else 0
    significant_minimum = max(8, math.ceil(total_area * 0.005))
    return {
        "visiblePixelCount": total_area,
        "connectedComponentCount": len(component_areas),
        "significantComponentCount": sum(
            1 for area in component_areas if area >= significant_minimum
        ),
        "significantComponentMinimumPixels": significant_minimum,
        "largestComponentPixelCount": largest,
        "largestComponentAreaRatio": round(largest / total_area, 8) if total_area else 0.0,
        "detachedAreaRatio": round((total_area - largest) / total_area, 8) if total_area else 0.0,
        "componentAreas": component_areas[:32],
    }


def build_render_integrity(
    selected: dict[str, Any], candidate_views: dict[str, Any]
) -> dict[str, Any]:
    selected_names = {
        "front": selected["front"],
        "right": selected["right"],
        "back": selected["back"],
    }
    views = {
        role: {
            "renderView": render_name,
            **_mask_component_metrics(candidate_views[render_name]["detailMask"]),
        }
        for role, render_name in selected_names.items()
    }
    ratios = [float(item["largestComponentAreaRatio"]) for item in views.values()]
    significant_counts = [int(item["significantComponentCount"]) for item in views.values()]
    return {
        "status": "RENDER_INTEGRITY_COLLECTED",
        "views": views,
        "minimumLargestComponentAreaRatio": round(min(ratios), 8),
        "maximumSignificantComponentCount": max(significant_counts),
    }


def evaluate_quality_hard_gates(
    evaluation: dict[str, Any],
    render_integrity: dict[str, Any],
    thresholds: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    policy = thresholds.get("geometryHardGates")
    failures: list[str] = []
    geometry = evaluation.get("metrics", {}).get("geometryIntegrity")
    if not isinstance(policy, dict):
        failures.append("GEOMETRY_HARD_GATE_POLICY_MISSING")
        policy = {}
    if not isinstance(geometry, dict) or geometry.get("status") != "GEOMETRY_INTEGRITY_COLLECTED":
        failures.append("GEOMETRY_INTEGRITY_REPORT_MISSING")
        geometry = {}

    checks = (
        (
            float(geometry.get("largestComponentVertexRatio", 0.0))
            >= float(policy.get("minimumLargestComponentVertexRatio", 1.0)),
            "LARGEST_CONNECTED_COMPONENT_BELOW_MINIMUM",
        ),
        (
            int(geometry.get("significantComponentCount", 10**9))
            <= int(policy.get("maximumSignificantComponentCount", 0)),
            "SIGNIFICANT_COMPONENT_COUNT_ABOVE_MAXIMUM",
        ),
        (
            float(geometry.get("looseVertexRatio", 1.0))
            <= float(policy.get("maximumLooseVertexRatio", 0.0)),
            "LOOSE_VERTEX_RATIO_ABOVE_MAXIMUM",
        ),
        (
            float(geometry.get("nonManifoldEdgeRatio", 1.0))
            <= float(policy.get("maximumNonManifoldEdgeRatio", 0.0)),
            "NON_MANIFOLD_EDGE_RATIO_ABOVE_MAXIMUM",
        ),
        (
            float(geometry.get("degenerateTriangleRatio", 1.0))
            <= float(policy.get("maximumDegenerateTriangleRatio", 0.0)),
            "DEGENERATE_TRIANGLE_RATIO_ABOVE_MAXIMUM",
        ),
        (
            float(render_integrity.get("minimumLargestComponentAreaRatio", 0.0))
            >= float(policy.get("minimumVisiblePrimaryComponentAreaRatio", 1.0)),
            "VISIBLE_PRIMARY_COMPONENT_RATIO_BELOW_MINIMUM",
        ),
        (
            int(render_integrity.get("maximumSignificantComponentCount", 10**9))
            <= int(policy.get("maximumVisibleSignificantComponentCount", 0)),
            "VISIBLE_SIGNIFICANT_COMPONENT_COUNT_ABOVE_MAXIMUM",
        ),
    )
    for passed, reason in checks:
        if not passed and reason not in failures:
            failures.append(reason)
    audit = {
        "status": "PASS" if not failures else "FAIL",
        "policy": policy,
        "geometryIntegrity": geometry,
        "renderIntegrity": render_integrity,
        "failureReasons": failures,
    }
    return not failures, failures, audit


def _view_metrics(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    from PIL import ImageOps

    candidate_edges = _edge_mask(candidate)
    candidate_face_edges = _edge_mask(candidate, face_only=True)
    candidate_histogram = _color_histogram(candidate)
    options = []
    for mirrored in (False, True):
        current = {
            key: ImageOps.mirror(value) if mirrored and hasattr(value, "size") else value
            for key, value in reference.items()
        }
        silhouette = _iou(current["mask"], candidate["mask"])
        edge = _iou(_edge_mask(current), candidate_edges)
        face = _iou(_edge_mask(current, face_only=True), candidate_face_edges)
        color = _histogram_intersection(_color_histogram(current), candidate_histogram)
        appearance = 0.5 * edge + 0.35 * color + 0.15 * face
        options.append(
            {
                "silhouette": silhouette,
                "edge": edge,
                "color": color,
                "face": face,
                "appearance": appearance,
                "combined": 0.6 * silhouette + 0.4 * appearance,
            }
        )
    return max(options, key=lambda item: item["combined"])

def score_orientation(
    reference_views: dict[str, Any], candidate_views: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts = []
    for front_index, front_name in enumerate(CARDINAL_CYCLE):
        back_name = CARDINAL_CYCLE[(front_index + 2) % 4]
        side_names = (
            CARDINAL_CYCLE[(front_index + 1) % 4],
            CARDINAL_CYCLE[(front_index - 1) % 4],
        )
        front_metrics = _view_metrics(reference_views["front"], candidate_views[front_name])
        back_metrics = _view_metrics(reference_views["back"], candidate_views[back_name])
        side_options = [
            (_view_metrics(reference_views["right"], candidate_views[name]), name)
            for name in side_names
        ]
        right_metrics, right_name = max(side_options, key=lambda item: item[0]["combined"])

        def aggregate(metric: str) -> float:
            return (
                0.45 * front_metrics[metric]
                + 0.3 * back_metrics[metric]
                + 0.25 * right_metrics[metric]
            )

        silhouette_score = aggregate("silhouette")
        appearance_score = aggregate("appearance")
        color_score = aggregate("color")
        orientation_score = 0.6 * silhouette_score + 0.4 * appearance_score
        attempts.append(
            {
                "front": front_name,
                "back": back_name,
                "right": right_name,
                "frontMetrics": {key: round(value, 6) for key, value in front_metrics.items()},
                "backMetrics": {key: round(value, 6) for key, value in back_metrics.items()},
                "rightMetrics": {key: round(value, 6) for key, value in right_metrics.items()},
                "silhouetteScore": round(silhouette_score, 6),
                "appearanceScore": round(appearance_score, 6),
                "colorScore": round(color_score, 6),
                "faceDetailScore": round(front_metrics["face"], 6),
                "orientationScore": round(orientation_score, 6),
            }
        )
    return max(attempts, key=lambda item: item["orientationScore"]), attempts


def assess_vertical_polarity(
    selected: dict[str, Any],
    vertically_flipped: dict[str, Any],
    minimum_improvement: float,
) -> dict[str, Any]:
    normal_score = float(selected["orientationScore"])
    flipped_score = float(vertically_flipped["orientationScore"])
    improvement = flipped_score - normal_score
    correction_required = improvement >= minimum_improvement
    return {
        "status": "UPSIDE_DOWN_DETECTED" if correction_required else "UPRIGHT_CONFIRMED",
        "correctionRequired": correction_required,
        "minimumImprovement": round(minimum_improvement, 6),
        "normalOrientationScore": round(normal_score, 6),
        "verticallyFlippedOrientationScore": round(flipped_score, 6),
        "scoreImprovement": round(improvement, 6),
    }


def _acceptance_result(
    selected: dict[str, Any],
    technical_score: float,
    triangle_count: int,
    thresholds: dict[str, Any],
) -> tuple[float, bool, list[str]]:
    silhouette_score = float(selected["silhouetteScore"])
    appearance_score = float(selected["appearanceScore"])
    color_score = float(selected["colorScore"])
    face_detail_score = float(selected["faceDetailScore"])
    overall_score = 0.65 * silhouette_score + 0.25 * appearance_score + 0.1 * technical_score
    failures = []
    checks = (
        (silhouette_score, thresholds["minimumSilhouetteScore"], "SILHOUETTE_SCORE_BELOW_MINIMUM"),
        (appearance_score, thresholds["minimumAppearanceScore"], "APPEARANCE_SCORE_BELOW_MINIMUM"),
        (color_score, thresholds["minimumColorScore"], "COLOR_SCORE_BELOW_MINIMUM"),
        (face_detail_score, thresholds["minimumFaceDetailScore"], "FACE_DETAIL_SCORE_BELOW_MINIMUM"),
        (overall_score, thresholds["minimumOverallScore"], "OVERALL_SCORE_BELOW_MINIMUM"),
    )
    for actual, minimum, reason in checks:
        if actual < minimum:
            failures.append(reason)
    if triangle_count > thresholds["maximumSourceTriangles"]:
        failures.append("SOURCE_TRIANGLE_COUNT_ABOVE_MAXIMUM")
    return overall_score, not failures, failures


def build_score_report(
    contract: dict[str, Any],
    references: dict[str, Any],
    evaluation: dict[str, Any],
    candidate_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if evaluation.get("character") != contract["character"]:
        raise ValueError("evaluation report character mismatch")
    if evaluation.get("sourceStatus") != contract["statusPolicy"]["sourceStatus"]:
        raise ValueError("evaluation report source status mismatch")
    if evaluation.get("unityInputAllowed") is not False:
        raise ValueError("evaluation report cannot enable Unity input")
    reference_views = {
        name: _normalize_view(Path(references["views"][name]["path"]), candidate=False)
        for name in ("front", "right", "back")
    }
    candidate_render_paths = {
        name: Path(evaluation["renders"][name])
        for name in CARDINAL_CYCLE
    }
    candidate_views = {
        name: _normalize_view(path, candidate=True)
        for name, path in candidate_render_paths.items()
    }
    vertically_flipped_views = {
        name: _normalize_view(path, candidate=True, vertical_flip=True)
        for name, path in candidate_render_paths.items()
    }
    selected, attempts = score_orientation(reference_views, candidate_views)
    vertically_flipped_selected, vertically_flipped_attempts = score_orientation(
        reference_views, vertically_flipped_views
    )
    thresholds = contract["candidateAcceptance"]
    render_integrity = build_render_integrity(selected, candidate_views)
    hard_gates_passed, hard_gate_failures, quality_audit = evaluate_quality_hard_gates(
        evaluation, render_integrity, thresholds
    )
    polarity = assess_vertical_polarity(
        selected,
        vertically_flipped_selected,
        float(thresholds.get("minimumVerticalPolarityImprovement", 0.02)),
    )
    technical_score = float(evaluation.get("metrics", {}).get("technicalScore", 0.0))
    triangle_count = int(evaluation.get("metrics", {}).get("triangleCount", 0))
    silhouette_score = float(selected["silhouetteScore"])
    appearance_score = float(selected["appearanceScore"])
    color_score = float(selected["colorScore"])
    face_detail_score = float(selected["faceDetailScore"])
    overall_score, scores_eligible, failure_reasons = _acceptance_result(
        selected, technical_score, triangle_count, thresholds
    )
    if polarity["correctionRequired"]:
        failure_reasons.insert(0, "UPSIDE_DOWN_ORIENTATION")
    for reason in hard_gate_failures:
        if reason not in failure_reasons:
            failure_reasons.append(reason)
    eligible = scores_eligible and not polarity["correctionRequired"] and hard_gates_passed
    corrected_overall, corrected_scores_eligible, corrected_failures = _acceptance_result(
        vertically_flipped_selected, technical_score, triangle_count, thresholds
    )
    polarity["verticalFlipPreview"] = {
        "status": (
            "CORRECTION_PREVIEW_REQUIRES_RERENDER"
            if polarity["correctionRequired"]
            else "CONTROL_VERTICAL_FLIP_REJECTED"
        ),
        "overallScore": round(corrected_overall, 6),
        "silhouetteScore": vertically_flipped_selected["silhouetteScore"],
        "appearanceScore": vertically_flipped_selected["appearanceScore"],
        "colorScore": vertically_flipped_selected["colorScore"],
        "faceDetailScore": vertically_flipped_selected["faceDetailScore"],
        "scoresMeetThresholds": corrected_scores_eligible,
        "failureReasons": corrected_failures,
        "selectedOrientation": vertically_flipped_selected,
        "orientationAttempts": vertically_flipped_attempts,
    }
    report = {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "candidateId": evaluation["candidateId"],
        "strategyId": evaluation.get("strategyId", ""),
        "candidatePath": evaluation["candidatePath"],
        "candidateSha256": evaluation["candidateSha256"],
        "status": "AUTO_REVIEW_CANDIDATE" if eligible else "REGENERATE_REQUIRED",
        "eligibleForHumanReview": eligible,
        "overallScore": round(overall_score, 6),
        "silhouetteScore": round(silhouette_score, 6),
        "appearanceScore": round(appearance_score, 6),
        "colorScore": round(color_score, 6),
        "faceDetailScore": round(face_detail_score, 6),
        "technicalScore": round(technical_score, 6),
        "failureReasons": failure_reasons,
        "selectedOrientation": selected,
        "orientationAttempts": attempts,
        "orientationValidation": polarity,
        "qualityHardGateAudit": quality_audit,
        "metricLimitations": {
            "faceDetailScore": "UPPER_IMAGE_EDGE_OVERLAP_NOT_SEMANTIC_FACE_IDENTITY",
            "automaticAcceptance": "ALPHA_REVIEW_ROUTING_ONLY_NOT_GATE_B_APPROVAL",
            "geometryHardGates": "TOPOLOGY_AND_RENDER_FRAGMENTATION_ONLY_NOT_SEMANTIC_DESIGN_MATCH",
        },
        "thresholds": thresholds,
        "artCommit": contract["artLock"]["commit"],
        "evaluationReport": evaluation,
        **candidate_gate_fields(contract),
    }
    if isinstance(candidate_manifest, dict):
        candidates = candidate_manifest.get("candidates", [])
        if isinstance(candidates, list):
            matching = next(
                (
                    entry
                    for entry in candidates
                    if isinstance(entry, dict)
                    and entry.get("candidateId") == evaluation.get("candidateId")
                ),
                None,
            )
            if isinstance(matching, dict) and isinstance(matching.get("semanticComponentAudit"), dict):
                report["semanticComponentAudit"] = matching["semanticComponentAudit"]
    return report


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    references = require_reference_manifest(args.reference_manifest.resolve(), contract)
    evaluation = read_json(args.evaluation_report.resolve())
    candidate_manifest = (
        read_json(args.candidate_manifest.resolve()) if args.candidate_manifest else None
    )
    report = build_score_report(contract, references, evaluation, candidate_manifest)
    write_json(args.output.resolve(), report)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
