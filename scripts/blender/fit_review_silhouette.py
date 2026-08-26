#!/usr/bin/env python3
"""Apply a reference-conditioned silhouette fit to a review-only Blender asset.

This is a conservative geometry experiment for AI candidates.  It reads the
locked reference image, estimates a height-binned lateral silhouette profile,
and deforms existing mesh vertices toward that profile.  It does not create
facial landmarks, textures, rig data, sockets, or production status.  The
result is always kept behind the AI candidate and Gate B locks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "CH101_REFERENCE_SILHOUETTE_PROFILE_FIT_V001"
DEFAULT_BIN_COUNT = 96


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--reference-image", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--front-axis",
        choices=("pos_x", "neg_x", "pos_y", "neg_y"),
        default="neg_x",
        help="Camera-facing axis used to choose the lateral screen coordinate.",
    )
    parser.add_argument("--strength", type=float, default=0.72)
    parser.add_argument("--bin-count", type=int, default=DEFAULT_BIN_COUNT)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mesh_objects() -> list[bpy.types.Object]:
    objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not objects:
        raise ValueError("blend contains no mesh objects")
    return objects


def world_vertex(obj: bpy.types.Object, vertex: bpy.types.MeshVertex) -> Vector:
    return obj.matrix_world @ vertex.co


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [world_vertex(obj, vertex) for obj in objects for vertex in obj.data.vertices]
    if not points:
        raise ValueError("mesh objects contain no vertices")
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def read_reference_profile(
    path: Path, bin_count: int
) -> tuple[list[tuple[float, float] | None], dict[str, object]]:
    """Read a silhouette profile without PIL or external Python packages."""
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    if width < 8 or height < 8:
        raise ValueError("reference image is too small")
    pixels = list(image.pixels[:])
    border: list[tuple[float, float, float]] = []
    step_x = max(1, width // 96)
    step_y = max(1, height // 96)
    for x in range(0, width, step_x):
        for y in (0, height - 1):
            index = (y * width + x) * 4
            border.append(tuple(float(pixels[index + channel]) for channel in range(3)))
    for y in range(0, height, step_y):
        for x in (0, width - 1):
            index = (y * width + x) * 4
            border.append(tuple(float(pixels[index + channel]) for channel in range(3)))
    background = tuple(sum(sample[channel] for sample in border) / len(border) for channel in range(3))

    def active(x: int, y: int) -> bool:
        index = (y * width + x) * 4
        rgba = pixels[index : index + 4]
        if len(rgba) < 4 or rgba[3] < 0.05:
            return False
        rgb = rgba[:3]
        distance = math.sqrt(sum((rgb[channel] - background[channel]) ** 2 for channel in range(3)))
        return distance >= 0.055 or min(rgb) <= 0.82

    active_points = [(x, y) for y in range(height) for x in range(width) if active(x, y)]
    if not active_points:
        raise ValueError("reference silhouette mask is empty")
    left = min(point[0] for point in active_points)
    right = max(point[0] for point in active_points)
    top = min(point[1] for point in active_points)
    bottom = max(point[1] for point in active_points)
    reference_width = max(right - left, 1)
    reference_height = max(bottom - top, 1)
    reference_center = (left + right) * 0.5
    reference_half = reference_width * 0.5
    bins: list[list[tuple[float, float]]] = [[] for _ in range(bin_count)]
    for y in range(top, bottom + 1):
        row = [x for x in range(left, right + 1) if active(x, y)]
        if not row:
            continue
        normalized_z = 1.0 - (y - top) / reference_height
        slot = max(0, min(bin_count - 1, int(round(normalized_z * (bin_count - 1)))))
        row_min = min(row)
        row_max = max(row)
        bins[slot].append(
            (
                ((row_min + row_max) * 0.5 - reference_center) / reference_half,
                max((row_max - row_min) * 0.5 / reference_half, 0.01),
            )
        )
    profile: list[tuple[float, float] | None] = []
    for values in bins:
        if values:
            profile.append(
                (
                    sum(value[0] for value in values) / len(values),
                    sum(value[1] for value in values) / len(values),
                )
            )
        else:
            profile.append(None)
    # Fill rows that were blank because of anti-aliasing or white clothing.
    known = [index for index, value in enumerate(profile) if value is not None]
    if not known:
        raise ValueError("reference silhouette profile has no populated rows")
    for index, value in enumerate(profile):
        if value is not None:
            continue
        nearest = min(known, key=lambda candidate: abs(candidate - index))
        profile[index] = profile[nearest]
    # Smooth only the target profile; this prevents adjacent mesh rings from
    # receiving large discontinuous scales from an aliased reference edge.
    smoothed: list[tuple[float, float]] = []
    for index in range(bin_count):
        window = profile[max(0, index - 2) : min(bin_count, index + 3)]
        smoothed.append(
            (
                sum(value[0] for value in window if value is not None) / len(window),
                sum(value[1] for value in window if value is not None) / len(window),
            )
        )
    return smoothed, {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "size": [width, height],
        "maskBounds": [left, top, right, bottom],
        "backgroundColor": [round(value, 6) for value in background],
        "algorithm": ALGORITHM,
    }


def profile_value(profile: list[tuple[float, float]], normalized_z: float) -> tuple[float, float]:
    position = max(0.0, min(1.0, normalized_z)) * (len(profile) - 1)
    lower = int(math.floor(position))
    upper = min(len(profile) - 1, lower + 1)
    fraction = position - lower
    return tuple(
        profile[lower][axis] * (1.0 - fraction) + profile[upper][axis] * fraction
        for axis in range(2)
    )


def lateral_coordinate(point: Vector, front_axis: str) -> float:
    return point.y if front_axis in {"pos_x", "neg_x"} else point.x


def deform_to_profile(
    objects: list[bpy.types.Object],
    profile: list[tuple[float, float]],
    front_axis: str,
    strength: float,
) -> dict[str, object]:
    minimum, maximum = world_bounds(objects)
    height = max(maximum.z - minimum.z, 1e-6)
    lateral_minimum = min(lateral_coordinate(world_vertex(obj, vertex), front_axis) for obj in objects for vertex in obj.data.vertices)
    lateral_maximum = max(lateral_coordinate(world_vertex(obj, vertex), front_axis) for obj in objects for vertex in obj.data.vertices)
    lateral_center = (lateral_minimum + lateral_maximum) * 0.5
    lateral_half = max((lateral_maximum - lateral_minimum) * 0.5, 1e-6)
    bin_count = len(profile)
    current_bins: list[list[float]] = [[] for _ in range(bin_count)]
    for obj in objects:
        for vertex in obj.data.vertices:
            point = world_vertex(obj, vertex)
            normalized_z = (point.z - minimum.z) / height
            slot = max(0, min(bin_count - 1, int(round(normalized_z * (bin_count - 1)))))
            current_bins[slot].append((lateral_coordinate(point, front_axis) - lateral_center) / lateral_half)
    current_profile: list[tuple[float, float]] = []
    for values in current_bins:
        if values:
            current_profile.append((0.0, max((max(values) - min(values)) * 0.5, 0.01)))
        else:
            current_profile.append((0.0, 0.01))
    for index, current in enumerate(current_profile):
        if current[1] > 0.011:
            continue
        nearest = min(
            (candidate for candidate, value in enumerate(current_profile) if value[1] > 0.011),
            key=lambda candidate: abs(candidate - index),
            default=index,
        )
        current_profile[index] = current_profile[nearest]

    changed_vertices = 0
    scale_values: list[float] = []
    center_values: list[float] = []
    strength = max(0.0, min(1.0, strength))
    for obj in objects:
        inverse = obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            point = world_vertex(obj, vertex)
            normalized_z = (point.z - minimum.z) / height
            slot = max(0, min(bin_count - 1, int(round(normalized_z * (bin_count - 1)))))
            target_center, target_half = profile_value(profile, normalized_z)
            current_center, current_half = current_profile[slot]
            ratio = max(0.55, min(1.65, target_half / max(current_half, 0.01)))
            factor = 1.0 + strength * (ratio - 1.0)
            target_center_world = lateral_center + target_center * lateral_half
            current_center_world = lateral_center + current_center * lateral_half
            old_lateral = lateral_coordinate(point, front_axis)
            new_lateral = target_center_world + (old_lateral - current_center_world) * factor
            if front_axis in {"pos_x", "neg_x"}:
                point.y = new_lateral
            else:
                point.x = new_lateral
            vertex.co = inverse @ point
            changed_vertices += 1
            scale_values.append(factor)
            center_values.append(target_center - current_center)
        obj.data.update()
    bpy.context.view_layer.update()
    return {
        "changedVertexCount": changed_vertices,
        "strength": round(strength, 6),
        "lateralAxis": "Y" if front_axis in {"pos_x", "neg_x"} else "X",
        "scaleRange": [round(min(scale_values), 6), round(max(scale_values), 6)] if scale_values else [1.0, 1.0],
        "meanAbsoluteCenterShiftNormalized": round(
            sum(abs(value) for value in center_values) / max(len(center_values), 1), 6
        ),
    }


def enforce_review_gate() -> None:
    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["review_silhouette_fit_algorithm"] = ALGORITHM


def export_glb(path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_apply=True)


def main() -> int:
    args = parse_args()
    blend = args.blend.resolve()
    reference = args.reference_image.resolve()
    if not blend.is_file() or not reference.is_file():
        raise FileNotFoundError(f"missing input: blend={blend}, reference={reference}")
    if args.strength < 0.0 or args.strength > 1.0:
        raise ValueError("strength must be between 0 and 1")
    if args.bin_count < 16:
        raise ValueError("bin-count must be at least 16")
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if output_blend == blend:
        raise ValueError("output blend must not overwrite the input review asset")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(blend)
    reference_sha256 = sha256_file(reference)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    objects = mesh_objects()
    profile, reference_report = read_reference_profile(reference, args.bin_count)
    deformation = deform_to_profile(objects, profile, args.front_axis, args.strength)
    enforce_review_gate()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_glb(output_glb)
    report = {
        "algorithm": ALGORITHM,
        "status": "REVIEW_SILHOUETTE_FIT_APPLIED",
        "sourceBlend": str(blend),
        "sourceBlendSha256": source_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb),
        "reference": reference_report,
        "referenceSha256": reference_sha256,
        "frontAxis": args.front_axis,
        "deformation": deformation,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "This is a review-only geometry deformation, not a Production Mesh.",
            "The reference silhouette does not transfer semantic face, hair, clothing, or equipment landmarks.",
            "Human Gate B review remains required and Unity input remains disabled.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
