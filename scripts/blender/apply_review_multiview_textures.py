#!/usr/bin/env python3
"""Apply review-only front/back/right textures to a normalized Blender scene."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ai3d'))
from reference_foreground import foreground_mask


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    rgba_bytes = bytes(max(0, min(255, round(value * 255))) for value in pixels)
    mask, mask_report = foreground_mask(rgba_bytes, width, height)
    masked_pixels = pixels[:]
    for index in range(width * height):
        masked_pixels[index * 4 + 3] = mask[index] / 255
    masked = bpy.data.images.new(f"{name}_FOREGROUND_MASKED", width, height, alpha=True)
    try:
        masked.colorspace_settings.name = "sRGB"
    except (AttributeError, TypeError):
        pass
    # Changing color space invalidates a generated image's pixel buffer in
    # Blender. Configure it BEFORE writing the foreground alpha, or pack()
    # silently stores an opaque image again.
    masked.pixels = masked_pixels
    masked.pack()
    source.user_clear()
    bpy.data.images.remove(source)
    return masked, {**mask_report, "legacyThresholdIgnored": threshold}


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
    if args.input_blend.resolve() == args.output_blend.resolve():
        raise ValueError("review output must not overwrite the source blend")
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    objects = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and len(obj.data.vertices) and not obj.name.startswith("ReviewFloor_")
    ]
    if not objects:
        raise ValueError("candidate contains no non-helper mesh objects")
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    minimum = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
    maximum = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
    dx, dy, dz = (max(maximum[axis] - minimum[axis], 1e-6) for axis in range(3))
    source_material = next(
        (obj.data.materials[0] for obj in objects if obj.data.materials),
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
    reference_reports = (front_report, back_report, right_report)
    mesh_count = 0
    for obj in objects:
        mesh_count += 1
        # UVs depend on each object's world transform, not shared datablocks.
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        mesh = obj.data
        if mesh.uv_layers.active is None:
            uv_layer = mesh.uv_layers.new(name="UVMap")
        else:
            uv_layer = mesh.uv_layers.active
        mesh.materials.clear()
        for material in (front, back, right):
            mesh.materials.append(material)
        for polygon in mesh.polygons:
            normal = obj.matrix_world.to_3x3().inverted_safe().transposed() @ polygon.normal
            normal.normalize()
            if normal.y <= -0.30:
                polygon.material_index = 0
            elif normal.y >= 0.30:
                polygon.material_index = 1
            elif normal.x >= 0.30:
                polygon.material_index = 2
            else:
                polygon.material_index = 0 if normal.y <= 0.0 else 1
        loop_material: dict[int, int] = {}
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                loop_material[loop_index] = polygon.material_index
        for loop in mesh.loops:
            coordinate = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
            material_index = loop_material[loop.index]
            u = (
                (coordinate.y - minimum.y) / dy
                if material_index == 2
                else (coordinate.x - minimum.x) / dx
            )
            # Camera +Y looks toward -Y: screen-right is world -X.
            if material_index == 1:
                u = 1.0 - u
            v = (coordinate.z - minimum.z) / dz
            # Map mesh extrema to the subject, not the square padded canvas.
            reference_report = reference_reports[material_index]
            left, bottom, right_edge, top = reference_report['foregroundBoundsInclusive']
            width, height = reference_report['size']
            u = (left + .5 + u * (right_edge - left)) / width
            v = (bottom + .5 + v * (top - bottom)) / height
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
            bpy.ops.object.select_all(action="DESELECT")
            for obj in objects:
                obj.select_set(True)
            bpy.ops.export_scene.gltf(
                filepath=str(args.output_glb.resolve()),
                export_format="GLB",
                export_image_format="AUTO",
                export_materials="EXPORT",
                use_selection=True,
            )
            glb_status = "EXPORTED"
        except Exception as error:  # Blender-version-specific exporter failure is recorded, not hidden.
            glb_status = f"FAILED:{type(error).__name__}:{error}"
    return {
        "status": "REVIEW_TEXTURES_APPLIED",
        "algorithm": "CH101_REVIEW_SUBJECT_BOUNDS_TEXTURE_V003",
        "inputBlendSha256": sha256_file(args.input_blend),
        "outputBlendSha256": sha256_file(args.output_blend),
        "referenceSha256": {
            view: sha256_file(path) for view, path in (
                ("front", args.front_image), ("back", args.back_image), ("right", args.right_image)
            )
        },
        "projection": {
            "frontAxis": "neg_y", "rightAxis": "pos_x", "backAxis": "pos_y",
            "boundsSpace": "SHARED_WORLD_SPACE",
            "boundsMin": list(minimum), "boundsMax": list(maximum),
            "objects": [obj.name for obj in objects],
        },
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
