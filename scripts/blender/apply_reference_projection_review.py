#!/usr/bin/env python3
"""Project the locked CH101 reference onto front-facing review polygons only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "CH101_REFERENCE_FRONT_PROJECTION_REVIEW_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--reference-image", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mask-bounds", required=True, help="x0,y0,x1,y1 in reference pixels")
    parser.add_argument("--front-axis", choices=("neg_x", "pos_x"), default="neg_x")
    parser.add_argument("--flip-lateral", action="store_true")
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    if not points:
        raise ValueError("mesh objects contain no vertices")
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def enforce_review_gate() -> None:
    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["reference_projection_algorithm"] = ALGORITHM


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    reference = args.reference_image.resolve()
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if not source.is_file() or not reference.is_file():
        raise FileNotFoundError(source if not source.is_file() else reference)
    if output_blend == source:
        raise ValueError("output blend must not overwrite the input")
    try:
        mask_bounds = [float(value.strip()) for value in args.mask_bounds.split(",")]
    except ValueError as exc:
        raise ValueError("mask-bounds must contain four comma-separated numbers") from exc
    if len(mask_bounds) != 4 or mask_bounds[2] <= mask_bounds[0] or mask_bounds[3] <= mask_bounds[1]:
        raise ValueError("mask-bounds must be x0,y0,x1,y1 with positive size")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source)
    reference_sha256 = sha256_file(reference)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise ValueError("reference projection requires exactly one mesh object")
    obj = meshes[0]
    minimum, maximum = world_bounds(meshes)
    height = max(maximum.z - minimum.z, 1e-6)
    lateral_min = minimum.y
    lateral_range = max(maximum.y - minimum.y, 1e-6)
    image = bpy.data.images.load(str(reference), check_existing=False)
    image.name = "CH101_Reference_Projection_Review"
    try:
        image.colorspace_settings.name = "sRGB"
    except (AttributeError, TypeError):
        pass
    image.pack()
    material_name = "CH101_REFERENCE_PROJECTION_REVIEW"
    material = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    if principled is None:
        raise RuntimeError("Principled BSDF node is unavailable")
    texture = nodes.get("CH101 Reference Projection") or nodes.new("ShaderNodeTexImage")
    texture.name = "CH101 Reference Projection"
    texture.image = image
    links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    principled.inputs["Roughness"].default_value = 0.58
    if obj.data.materials.get(material_name) is None:
        obj.data.materials.append(material)
    material_index = obj.data.materials.find(material_name)
    uv_layer = obj.data.uv_layers.get("CH101ReferenceProjectionUV") or obj.data.uv_layers.new(
        name="CH101ReferenceProjectionUV"
    )
    image_width, image_height = image.size
    x0, y0, x1, y1 = mask_bounds
    front_vector = Vector((-1.0, 0.0, 0.0)) if args.front_axis == "neg_x" else Vector((1.0, 0.0, 0.0))
    projected_faces = 0
    untouched_faces = 0
    for polygon in obj.data.polygons:
        world_normal = obj.matrix_world.to_3x3() @ polygon.normal
        front_facing = world_normal.normalized().dot(front_vector) >= 0.15
        if not front_facing:
            untouched_faces += 1
            continue
        polygon.material_index = material_index
        projected_faces += 1
        for loop_index in polygon.loop_indices:
            vertex_index = obj.data.loops[loop_index].vertex_index
            world = obj.matrix_world @ obj.data.vertices[vertex_index].co
            normalized_lateral = max(0.0, min(1.0, (world.y - lateral_min) / lateral_range))
            if args.flip_lateral:
                normalized_lateral = 1.0 - normalized_lateral
            normalized_vertical = max(0.0, min(1.0, (world.z - minimum.z) / height))
            pixel_x = x0 + normalized_lateral * (x1 - x0)
            pixel_y = y1 - normalized_vertical * (y1 - y0)
            uv_layer.data[loop_index].uv = (pixel_x / image_width, 1.0 - pixel_y / image_height)
    enforce_review_gate()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", export_apply=True)
    report = {
        "algorithm": ALGORITHM,
        "status": "REFERENCE_PROJECTION_REVIEW_APPLIED",
        "sourceBlend": str(source),
        "sourceBlendSha256": source_sha256,
        "referenceImage": str(reference),
        "referenceImageSha256": reference_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb),
        "frontAxis": args.front_axis,
        "flipLateral": args.flip_lateral,
        "maskBounds": mask_bounds,
        "projectedFaceCount": projected_faces,
        "untouchedFaceCount": untouched_faces,
        "materialName": material_name,
        "uvLayer": uv_layer.name,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "Reference projection is a front-view review aid, not final texture authoring.",
            "Back/side material appearance is not semantically transferred by this pass.",
            "Face landmarks, hair, clothing, equipment, and production UVs remain unapproved.",
            "Re-render, score, and human Gate B review remain mandatory.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
