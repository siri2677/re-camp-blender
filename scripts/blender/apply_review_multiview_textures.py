#!/usr/bin/env python3
"""Apply review-only front/back/right textures to a normalized Blender scene."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True, type=Path)
    parser.add_argument("--front-image", required=True, type=Path)
    parser.add_argument("--back-image", required=True, type=Path)
    parser.add_argument("--right-image", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--smooth-level", type=int, default=0)
    return parser.parse_args(raw)


def _texture_material(name: str, image_path: Path) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(str(image_path), check_existing=True)
    image.interpolation = "Linear"
    image.extension = "CLIP"
    shader.inputs["Roughness"].default_value = 0.72
    links.new(image.outputs["Color"], shader.inputs["Base Color"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def _apply_textures(args: argparse.Namespace) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    front = _texture_material("CH101_REVIEW_TEXTURE_FRONT", args.front_image.resolve())
    back = _texture_material("CH101_REVIEW_TEXTURE_BACK", args.back_image.resolve())
    right = _texture_material("CH101_REVIEW_TEXTURE_RIGHT", args.right_image.resolve())
    mesh_count = 0
    for obj in (item for item in bpy.context.scene.objects if item.type == "MESH"):
        mesh_count += 1
        mesh = obj.data
        if mesh.uv_layers.active is None:
            uv_layer = mesh.uv_layers.new(name="UVMap")
        else:
            uv_layer = mesh.uv_layers.active
        minimum = Vector(
            (min(vertex.co.x for vertex in mesh.vertices), min(vertex.co.y for vertex in mesh.vertices), min(vertex.co.z for vertex in mesh.vertices))
        )
        maximum = Vector(
            (max(vertex.co.x for vertex in mesh.vertices), max(vertex.co.y for vertex in mesh.vertices), max(vertex.co.z for vertex in mesh.vertices))
        )
        dx = max(maximum.x - minimum.x, 1e-6)
        dy = max(maximum.y - minimum.y, 1e-6)
        dz = max(maximum.z - minimum.z, 1e-6)
        mesh.materials.clear()
        for material in (front, back, right):
            mesh.materials.append(material)
        for polygon in mesh.polygons:
            if polygon.normal.y >= 0.30:
                polygon.material_index = 0
            elif polygon.normal.y <= -0.30:
                polygon.material_index = 1
            elif polygon.normal.x >= 0.30:
                polygon.material_index = 2
            else:
                polygon.material_index = 0 if polygon.normal.y >= 0.0 else 1
        loop_material: dict[int, int] = {}
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                loop_material[loop_index] = polygon.material_index
        for loop in mesh.loops:
            coordinate = mesh.vertices[loop.vertex_index].co
            material_index = loop_material[loop.index]
            u = (
                (coordinate.y - minimum.y) / dy
                if material_index == 2
                else (coordinate.x - minimum.x) / dx
            )
            v = (coordinate.z - minimum.z) / dz
            uv_layer.data[loop.index].uv = (max(0.0, min(1.0, u)), max(0.0, min(1.0, v)))
        if args.smooth_level > 0:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new("AI3D_REVIEW_SUBDIVISION", "SUBSURF")
            modifier.subdivision_type = "CATMULL_CLARK"
            modifier.levels = args.smooth_level
            modifier.render_levels = args.smooth_level
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
        obj["texture_projection_status"] = "MULTIVIEW_REFERENCE_TEXTURE_PROJECTION_REVIEW_ONLY"
        obj["source_status"] = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
        obj["gate_b"] = "PENDING_HUMAN_REVIEW"
        obj["unity_input_allowed"] = False
        obj["production_promotion_allowed"] = False
    scene = bpy.context.scene
    scene["source_status"] = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
    scene["gate_b"] = "PENDING_HUMAN_REVIEW"
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    glb_status = "NOT_REQUESTED"
    if args.output_glb:
        args.output_glb.parent.mkdir(parents=True, exist_ok=True)
        try:
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.export_scene.gltf(
                filepath=str(args.output_glb.resolve()),
                export_format="GLB",
                export_image_format="AUTO",
                export_materials="EXPORT",
            )
            glb_status = "EXPORTED"
        except Exception as error:  # Blender-version-specific exporter failure is recorded, not hidden.
            glb_status = f"FAILED:{type(error).__name__}:{error}"
    return {
        "status": "REVIEW_TEXTURES_APPLIED",
        "meshCount": mesh_count,
        "outputBlend": str(args.output_blend.resolve()),
        "outputGlb": str(args.output_glb.resolve()) if args.output_glb else None,
        "glbExportStatus": glb_status,
        "smoothLevel": args.smooth_level,
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = _apply_textures(args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
