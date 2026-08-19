#!/usr/bin/env python3
"""Refine an AI-generated candidate into a review-only normalized artifact.

This script performs conservative geometry cleanup and technical preparation. It
does not infer final facial topology, approve equipment sockets, or enable Unity
input. The output remains an AI review candidate until a human Gate B decision.
"""

from __future__ import annotations

import argparse
import json
import math
import hashlib
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
REVIEW_MATERIAL_NAME = "AI_REVIEW_NEUTRAL_AUTO"
PALETTE_MATERIALS = {
    "white": (0.957, 0.957, 0.933, 1.0),
    "graphite": (0.008, 0.008, 0.012, 1.0),
    "gold": (0.668, 0.391, 0.063, 1.0),
    "cyan": (0.0, 0.455, 0.672, 1.0),
    "skin": (0.957, 0.957, 0.933, 1.0),
    "hair": (0.008, 0.008, 0.012, 1.0),
}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--parent-sha256", default="")
    parser.add_argument(
        "--material-mode",
        choices=("neutral", "preserve"),
        default="neutral",
        help="Use a neutral review material or preserve imported material slots/colors.",
    )
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def import_candidate(path: Path) -> list[bpy.types.Object]:
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"unsupported candidate format: {suffix}")
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("candidate contains no mesh objects")
    return meshes


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = []
    for obj in objects:
        corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise ValueError("candidate contains no mesh bounds")
    return (
        Vector(tuple(min(point[index] for point in corners) for index in range(3))),
        Vector(tuple(max(point[index] for point in corners) for index in range(3))),
    )


def transform_candidate(objects: list[bpy.types.Object], target_height: float = 1.68) -> dict[str, object]:
    minimum, maximum = world_bounds(objects)
    dimensions = maximum - minimum
    source_axis_index = max(range(3), key=lambda axis: dimensions[axis])
    orientation_fix = "NONE"
    if source_axis_index == 1:
        rotation = Matrix.Rotation(math.radians(90.0), 4, "X")
        orientation_fix = "Y_TO_Z"
    elif source_axis_index == 0:
        rotation = Matrix.Rotation(math.radians(-90.0), 4, "Y")
        orientation_fix = "X_TO_Z"
    else:
        rotation = Matrix.Identity(4)

    for obj in objects:
        obj.matrix_world = rotation @ obj.matrix_world
    bpy.context.view_layer.update()

    minimum, maximum = world_bounds(objects)
    height = maximum.z - minimum.z
    if height <= 1e-6:
        raise ValueError("candidate has zero height after orientation normalization")
    center = (minimum + maximum) * 0.5
    scale = target_height / height
    transform = Matrix.Translation(Vector((-center.x * scale, -center.y * scale, -minimum.z * scale))) @ Matrix.Scale(scale, 4)
    for obj in objects:
        obj.matrix_world = transform @ obj.matrix_world
    bpy.context.view_layer.update()

    minimum, maximum = world_bounds(objects)
    return {
        "sourceUpAxis": "XYZ"[source_axis_index],
        "orientationFix": orientation_fix,
        "targetHeight": target_height,
        "dimensions": [round(value, 6) for value in (maximum - minimum)],
    }


def clean_mesh(obj: bpy.types.Object) -> dict[str, object]:
    mesh = obj.data
    mesh.calc_loop_triangles()
    before_vertices = len(mesh.vertices)
    before_triangles = len(mesh.loop_triangles)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    uv_generated = False
    if not mesh.uv_layers:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.03)
        bpy.ops.object.mode_set(mode="OBJECT")
        uv_generated = True

    mesh.calc_loop_triangles()
    return {
        "object": obj.name,
        "verticesBefore": before_vertices,
        "verticesAfter": len(mesh.vertices),
        "trianglesBefore": before_triangles,
        "trianglesAfter": len(mesh.loop_triangles),
        "uvGenerated": uv_generated,
        "uvLayers": len(mesh.uv_layers),
    }


def ensure_review_material(obj: bpy.types.Object, material_mode: str) -> list[str]:
    if material_mode == "preserve" and len(obj.data.materials) > 0:
        return [material.name for material in obj.data.materials if material is not None]

    if material_mode == "preserve":
        return apply_palette_review_materials(obj)

    material = bpy.data.materials.get(REVIEW_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(REVIEW_MATERIAL_NAME)
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = (0.32, 0.42, 0.50, 1.0)
            principled.inputs["Roughness"].default_value = 0.58
    if obj.data.materials.get(REVIEW_MATERIAL_NAME) is None:
        obj.data.materials.append(material)
    material_index = obj.data.materials.find(material.name)
    for polygon in obj.data.polygons:
        polygon.material_index = material_index
    return [material.name]


def apply_palette_review_materials(obj: bpy.types.Object) -> list[str]:
    """Apply a conservative CH101 palette approximation when textures are absent.

    This is a review aid for untextured AI meshes, not texture generation. The
    bands are deliberately coarse and the report labels the result as an
    approximation so it cannot be mistaken for final art.
    """
    materials = {}
    for key, rgba in PALETTE_MATERIALS.items():
        name = f"AI_REVIEW_PALETTE_{key.upper()}"
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material.use_nodes = True
        material.diffuse_color = rgba
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = rgba
            principled.inputs["Roughness"].default_value = 0.58
        materials[key] = material

    obj.data.materials.clear()
    ordered = [materials[key] for key in ("white", "graphite", "gold", "cyan", "skin", "hair")]
    for material in ordered:
        obj.data.materials.append(material)
    height = max(obj.dimensions.z, 1e-6)
    for polygon in obj.data.polygons:
        world_center = obj.matrix_world @ polygon.center
        normalized_z = max(0.0, min(1.0, (world_center.z - 0.0) / height))
        world_normal = obj.matrix_world.to_3x3() @ polygon.normal
        front_facing = world_normal.y < -0.2
        if normalized_z < 0.16:
            key = "white" if front_facing else "graphite"
        elif normalized_z < 0.56:
            key = "skin"
        elif normalized_z < 0.69:
            key = "graphite"
        elif normalized_z < 0.84:
            key = "white" if front_facing else "graphite"
        elif normalized_z < 0.92:
            key = "skin" if front_facing else "hair"
        else:
            key = "hair"
        # Keep small cyan/gold accents sparse and deterministic for review.
        if polygon.index % 37 == 0 and normalized_z > 0.20:
            key = "cyan"
        elif polygon.index % 53 == 0 and normalized_z > 0.30:
            key = "gold"
        polygon.material_index = ("white", "graphite", "gold", "cyan", "skin", "hair").index(key)
    return [material.name for material in ordered]


def main() -> int:
    args = parse_args()
    candidate = args.candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    args.output_glb.parent.mkdir(parents=True, exist_ok=True)
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    clear_scene()
    imported = import_candidate(candidate)
    transform = transform_candidate(imported)
    cleanup = [clean_mesh(obj) for obj in imported]
    had_imported_materials = any(
        material is not None
        for obj in imported
        for material in obj.data.materials
    )
    material_names = sorted(
        {
            material_name
            for obj in imported
            for material_name in ensure_review_material(obj, args.material_mode)
        }
    )
    palette_fallback_used = args.material_mode == "preserve" and not had_imported_materials
    minimum, maximum = world_bounds(imported)
    triangle_count = sum(len(obj.data.loop_triangles) for obj in imported)
    uv_missing = [obj.name for obj in imported if not obj.data.uv_layers]

    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["refinement_stage"] = "TECHNICAL_REVIEW_REFINEMENT"
    scene["face_driver_status"] = "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER"
    scene["socket_status"] = "AUTO_ESTIMATED_NOT_APPROVED"

    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend))
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(args.output_glb), export_format="GLB", export_apply=True)

    warnings = [
        (
            "Imported material slots and vertex colors were preserved for review scoring."
            if args.material_mode == "preserve"
            else "Neutral review material is automatic and not a final art material."
        ),
    ]
    if palette_fallback_used:
        warnings.append(
            "No imported material was present; CH101 palette was assigned by coarse geometry bands for review only."
        )
    warnings.extend([
        "The refined candidate is not a Production Mesh.",
        "Human Gate B review is required before any Unity input.",
    ])

    report = {
        "character": "CH101",
        "candidatePath": str(candidate),
        "candidateSha256": sha256_file(candidate),
        "refinedGlb": str(args.output_glb.resolve()),
        "refinedGlbSha256": sha256_file(args.output_glb),
        "normalizedBlend": str(args.output_blend.resolve()),
        "provider": args.provider,
        "attempt": args.attempt,
        "parentSha256": args.parent_sha256,
        "status": "REFINED_REVIEW_CANDIDATE",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "orientation": transform,
        "metrics": {
            "meshCount": len(imported),
            "triangleCount": triangle_count,
            "materialCount": len(material_names),
            "materialNames": material_names,
            "uvMissing": sorted(uv_missing),
            "boundsMin": list(minimum),
            "boundsMax": list(maximum),
            "dimensions": list(maximum - minimum),
        },
        "cleanup": cleanup,
        "faceDriver": {
            "status": "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER",
            "blendShapeCount": 0,
        },
        "socketStatus": "AUTO_ESTIMATED_NOT_APPROVED",
        "materialMode": args.material_mode,
        "paletteFallbackUsed": palette_fallback_used,
        "warnings": warnings,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
