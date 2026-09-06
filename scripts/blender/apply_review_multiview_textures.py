#!/usr/bin/env python3
"""Apply review-only front/back/right textures to a normalized Blender scene."""

from __future__ import annotations

import argparse
import json
import math
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
    parser.add_argument("--background-threshold", type=float, default=0.08)
    return parser.parse_args(raw)


def _foreground_texture(name: str, image_path: Path, threshold: float) -> tuple[bpy.types.Image, dict[str, object]]:
    """Pack a reference image with only the border-connected canvas removed."""
    source = bpy.data.images.load(str(image_path), check_existing=False)
    width, height = source.size
    if width < 8 or height < 8:
        raise ValueError(f"reference texture is too small: {image_path}")
    pixels = list(source.pixels[:])
    border: list[tuple[float, float, float]] = []
    sample_step = max(1, min(width, height) // 128)
    for x in range(0, width, sample_step):
        for y in (0, height - 1):
            offset = (y * width + x) * 4
            border.append(tuple(float(pixels[offset + channel]) for channel in range(3)))
    for y in range(0, height, sample_step):
        for x in (0, width - 1):
            offset = (y * width + x) * 4
            border.append(tuple(float(pixels[offset + channel]) for channel in range(3)))
    background = tuple(sum(sample[channel] for sample in border) / len(border) for channel in range(3))

    def is_background(index: int) -> bool:
        offset = index * 4
        if pixels[offset + 3] <= 0.01:
            return True
        distance = math.sqrt(
            sum((float(pixels[offset + channel]) - background[channel]) ** 2 for channel in range(3))
        )
        return distance <= threshold

    # Flood-fill only canvas-connected near-background. This preserves white
    # jacket pixels enclosed by the character silhouette.
    visited = bytearray(width * height)
    queue: list[int] = []
    for x in range(width):
        queue.extend((x, (height - 1) * width + x))
    for y in range(height):
        queue.extend((y * width, y * width + width - 1))
    head = 0
    while head < len(queue):
        index = queue[head]
        head += 1
        if visited[index] or not is_background(index):
            continue
        visited[index] = 1
        x = index % width
        y = index // width
        if x > 0:
            queue.append(index - 1)
        if x + 1 < width:
            queue.append(index + 1)
        if y > 0:
            queue.append(index - width)
        if y + 1 < height:
            queue.append(index + width)

    masked_pixels = pixels[:]
    background_pixels = 0
    for index in range(width * height):
        if visited[index]:
            masked_pixels[index * 4 + 3] = 0.0
            background_pixels += 1
        else:
            masked_pixels[index * 4 + 3] = max(masked_pixels[index * 4 + 3], 1.0)
    masked = bpy.data.images.new(f"{name}_FOREGROUND_MASKED", width, height, alpha=True)
    masked.pixels = masked_pixels
    try:
        masked.colorspace_settings.name = "sRGB"
    except (AttributeError, TypeError):
        pass
    masked.pack()
    source.user_clear()
    bpy.data.images.remove(source)
    return masked, {
        "algorithm": "BORDER_CONNECTED_CANVAS_FLOOD_FILL_V001",
        "threshold": threshold,
        "backgroundColor": [round(value, 6) for value in background],
        "size": [width, height],
        "backgroundPixelRatio": round(background_pixels / max(width * height, 1), 6),
        "foregroundPixelRatio": round(1.0 - background_pixels / max(width * height, 1), 6),
    }


def _base_color(material: bpy.types.Material | None) -> tuple[float, float, float, float]:
    if material and material.use_nodes:
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader is not None and shader.inputs.get("Base Color") is not None:
            return tuple(float(value) for value in shader.inputs["Base Color"].default_value)
    return (0.38, 0.42, 0.48, 1.0)


def _texture_material(
    name: str,
    image_path: Path,
    base_color: tuple[float, float, float, float],
    background_threshold: float,
) -> tuple[bpy.types.Material, dict[str, object]]:
    masked_image, mask_report = _foreground_texture(name, image_path, background_threshold)
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    base_shader = nodes.new("ShaderNodeBsdfPrincipled")
    base_shader.inputs["Base Color"].default_value = base_color
    base_shader.inputs["Roughness"].default_value = 0.80
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    image = nodes.new("ShaderNodeTexImage")
    image.image = masked_image
    image.interpolation = "Linear"
    image.extension = "CLIP"
    shader.inputs["Roughness"].default_value = 0.72
    mix = nodes.new("ShaderNodeMixShader")
    links.new(image.outputs["Color"], shader.inputs["Base Color"])
    links.new(image.outputs["Alpha"], mix.inputs[0])
    links.new(base_shader.outputs["BSDF"], mix.inputs[1])
    links.new(shader.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    material["review_texture_background_mask"] = mask_report["algorithm"]
    material["review_texture_foreground_ratio"] = mask_report["foregroundPixelRatio"]
    return material, mask_report


def _apply_textures(args: argparse.Namespace) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    source_material = next(
        (obj.data.materials[0] for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.data.materials),
        None,
    )
    base_color = _base_color(source_material)
    if sum(base_color[:3]) / 3.0 > 0.92:
        # A white provider material would make removed canvas pixels invisible
        # against the old failure mode. Use a neutral review underlay instead.
        base_color = (0.22, 0.25, 0.30, 1.0)
    front, front_report = _texture_material(
        "CH101_REVIEW_TEXTURE_FRONT", args.front_image.resolve(), base_color, args.background_threshold
    )
    back, back_report = _texture_material(
        "CH101_REVIEW_TEXTURE_BACK", args.back_image.resolve(), base_color, args.background_threshold
    )
    right, right_report = _texture_material(
        "CH101_REVIEW_TEXTURE_RIGHT", args.right_image.resolve(), base_color, args.background_threshold
    )
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
        "baseUnderlayColor": [round(value, 6) for value in base_color],
        "backgroundMask": {
            "front": front_report,
            "back": back_report,
            "right": right_report,
        },
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
