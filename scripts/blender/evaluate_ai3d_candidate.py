#!/usr/bin/env python3
"""Normalize and render an AI-generated model for automated visual review.

This script creates review evidence only. It never labels a candidate as a
production mesh and never enables Unity input.
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
CARDINAL_VIEWS = {
    "neg_y": Vector((0.0, -1.0, 0.0)),
    "pos_x": Vector((1.0, 0.0, 0.0)),
    "pos_y": Vector((0.0, 1.0, 0.0)),
    "neg_x": Vector((-1.0, 0.0, 0.0)),
}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--render-size", type=int, default=512)
    parser.add_argument("--normalized-blend", type=Path)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.armatures,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(data_collection):
            if block.users == 0:
                data_collection.remove(block)


def import_candidate(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        if hasattr(bpy.ops.wm, "fbx_import"):
            bpy.ops.wm.fbx_import(filepath=str(path))
        else:
            bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"unsupported candidate format: {suffix}")
    imported = [obj for obj in bpy.data.objects if obj not in before]
    for obj in list(imported):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
            imported.remove(obj)
    return imported


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        if obj.type == "MESH"
        for corner in obj.bound_box
    ]
    if not corners:
        raise ValueError("candidate contains no mesh bounds")
    minimum = Vector(tuple(min(point[index] for point in corners) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in corners) for index in range(3)))
    return minimum, maximum


def normalize_candidate(imported: list[bpy.types.Object], target_height: float = 1.68) -> bpy.types.Object:
    meshes = [obj for obj in imported if obj.type == "MESH"]
    minimum, maximum = world_bounds(meshes)
    height = maximum.z - minimum.z
    if height <= 1e-6:
        raise ValueError("candidate has zero height")
    center = (minimum + maximum) * 0.5
    root = bpy.data.objects.new("CH101_AI_Candidate_Root", None)
    bpy.context.scene.collection.objects.link(root)
    for obj in imported:
        if obj.parent is None:
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = world
    scale = target_height / height
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -minimum.z * scale)
    root["source_status"] = SOURCE_STATUS
    root["gate_b"] = GATE_B
    root["unity_input_allowed"] = False
    return root


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def detect_render_color_mode(meshes: list[bpy.types.Object]) -> str:
    """Use imported image textures when present, otherwise keep material colors."""
    for obj in meshes:
        for material in obj.data.materials:
            if not material or not material.node_tree:
                continue
            if any(
                node.type == "TEX_IMAGE" and getattr(node, "image", None) is not None
                for node in material.node_tree.nodes
            ):
                return "TEXTURE"
    return "MATERIAL"


def configure_render(size: int, color_mode: str) -> bpy.types.Object:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.color_type = color_mode
    camera_data = bpy.data.cameras.new("AI3D_Review_Camera")
    camera = bpy.data.objects.new("AI3D_Review_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 1.92
    scene.camera = camera
    return camera


def render_views(camera: bpy.types.Object, output_dir: Path) -> dict[str, str]:
    scene = bpy.context.scene
    target = Vector((0.0, 0.0, 0.84))
    distance = 4.0
    renders = {}
    views = dict(CARDINAL_VIEWS)
    views["three_quarter"] = Vector((1.0, -1.0, 0.0)).normalized()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, direction in views.items():
        camera.location = target + direction * distance
        look_at(camera, target)
        output_path = output_dir / f"{name}.png"
        scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
        renders[name] = str(output_path)
    return renders


def collect_metrics(meshes: list[bpy.types.Object]) -> dict[str, object]:
    triangle_count = 0
    vertex_count = 0
    material_names = set()
    uv_missing = []
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangle_count += len(obj.data.loop_triangles)
        vertex_count += len(obj.data.vertices)
        if not obj.data.uv_layers:
            uv_missing.append(obj.name)
        for material in obj.data.materials:
            if material:
                material_names.add(material.name)
    minimum, maximum = world_bounds(meshes)
    dimensions = maximum - minimum
    aspect = dimensions.z / max(dimensions.x, dimensions.y, 1e-6)
    technical_score = 0.25
    technical_score += 0.2 if not uv_missing else 0.0
    technical_score += 0.15 if material_names else 0.0
    technical_score += 0.2 if 1.2 <= aspect <= 4.5 else 0.05
    technical_score += 0.2 if 500 <= triangle_count <= 300000 else 0.05
    return {
        "meshCount": len(meshes),
        "vertexCount": vertex_count,
        "triangleCount": triangle_count,
        "materialCount": len(material_names),
        "materialNames": sorted(material_names),
        "uvMissing": sorted(uv_missing),
        "boundsMin": list(minimum),
        "boundsMax": list(maximum),
        "dimensions": list(dimensions),
        "heightToWidthAspect": round(aspect, 6),
        "technicalScore": round(min(technical_score, 1.0), 6),
    }


def main() -> int:
    args = parse_args()
    candidate = args.candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    output_dir = args.output_dir.resolve()
    report_path = args.report.resolve()
    clear_scene()
    imported = import_candidate(candidate)
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise ValueError("candidate contains no mesh objects")
    normalize_candidate(imported)
    bpy.context.view_layer.update()
    metrics = collect_metrics(meshes)
    render_color_mode = detect_render_color_mode(meshes)
    camera = configure_render(max(256, args.render_size), render_color_mode)
    renders = render_views(camera, output_dir / "renders")
    scene = bpy.context.scene
    scene["re_camp_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    if args.normalized_blend:
        normalized_blend = args.normalized_blend.resolve()
        normalized_blend.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(normalized_blend))
    else:
        normalized_blend = None
    report = {
        "character": "CH101",
        "candidateId": args.candidate_id,
        "candidatePath": str(candidate),
        "candidateSha256": sha256_file(candidate),
        "status": "EVALUATION_RENDERED",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "metrics": metrics,
        "renderColorMode": render_color_mode,
        "renders": renders,
        "cardinalViewOrder": list(CARDINAL_VIEWS),
        "normalizedBlend": str(normalized_blend) if normalized_blend else "",
        "warnings": [
            "Orientation is selected by silhouette scoring after rendering.",
            "This normalized scene is an AI review candidate, not a production mesh.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
