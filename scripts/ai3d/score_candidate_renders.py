#!/usr/bin/env python3
"""Score candidate render silhouettes against the locked CH101 turnaround."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def _normalize_view(path: Path, candidate: bool, size: int = 256) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install pillow") from exc
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
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


def build_score_report(
    contract: dict[str, Any],
    references: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    if evaluation.get("sourceStatus") != contract["statusPolicy"]["sourceStatus"]:
        raise ValueError("evaluation report source status mismatch")
    if evaluation.get("unityInputAllowed") is not False:
        raise ValueError("evaluation report cannot enable Unity input")
    reference_views = {
        name: _normalize_view(Path(references["views"][name]["path"]), candidate=False)
        for name in ("front", "right", "back")
    }
    candidate_views = {
        name: _normalize_view(Path(evaluation["renders"][name]), candidate=True)
        for name in CARDINAL_CYCLE
    }
    selected, attempts = score_orientation(reference_views, candidate_views)
    technical_score = float(evaluation.get("metrics", {}).get("technicalScore", 0.0))
    silhouette_score = float(selected["silhouetteScore"])
    appearance_score = float(selected["appearanceScore"])
    color_score = float(selected["colorScore"])
    face_detail_score = float(selected["faceDetailScore"])
    overall_score = 0.65 * silhouette_score + 0.25 * appearance_score + 0.1 * technical_score
    thresholds = contract["candidateAcceptance"]
    eligible = (
        silhouette_score >= thresholds["minimumSilhouetteScore"]
        and appearance_score >= thresholds["minimumAppearanceScore"]
        and color_score >= thresholds["minimumColorScore"]
        and face_detail_score >= thresholds["minimumFaceDetailScore"]
        and overall_score >= thresholds["minimumOverallScore"]
        and int(evaluation.get("metrics", {}).get("triangleCount", 0))
        <= thresholds["maximumSourceTriangles"]
    )
    return {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "candidateId": evaluation["candidateId"],
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
        "selectedOrientation": selected,
        "orientationAttempts": attempts,
        "thresholds": thresholds,
        "artCommit": contract["artLock"]["commit"],
        "evaluationReport": evaluation,
        **candidate_gate_fields(contract),
    }


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract)
    references = require_reference_manifest(args.reference_manifest.resolve(), contract)
    evaluation = read_json(args.evaluation_report.resolve())
    report = build_score_report(contract, references, evaluation)
    write_json(args.output.resolve(), report)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
