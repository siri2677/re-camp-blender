#!/usr/bin/env python3
"""Import the CC0 MPFB/MakeHuman base mesh as CH101-A production input WIP."""

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
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection" and collection.users == 0:
            bpy.data.collections.remove(collection)


def make_material(name: str, color: tuple[float, float, float, float], roughness: float, metallic: float = 0.0) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = metallic
    return material


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def normalize_body(obj: bpy.types.Object, target_height: float = 3.65) -> None:
    # MPFB/MakeHuman OBJ is Y-up; Re:Camp Blender scenes are Z-up.
    obj.rotation_euler.x = math.radians(90.0)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.context.view_layer.update()
    scale = target_height / obj.dimensions.z
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    min_z = min(vertex.co.z for vertex in obj.data.vertices)
    obj.location.z -= min_z


def setup_scene(out: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.015, 0.018, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.4, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(make_material("MPFBReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.4, -6.9, 2.0))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0, 0, 1.9)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_MPFBase_WIP_3q.png")
    for location, energy, color in (((-4.0, -5.0, 6.0), 1000, (1.0, 0.80, 0.70)), ((4.0, -3.0, 4.0), 600, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 850, (0.10, 0.60, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.8)))


def main() -> None:
    options = parse_args()
    base_obj = Path(options.base_obj).resolve()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(base_obj), use_split_groups=True, import_vertex_groups=True, validate_meshes=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    body = next((obj for obj in imported if obj.name == "body"), None)
    if body is None:
        raise RuntimeError("MPFB base.obj import did not expose the expected body group")
    for obj in imported:
        if obj != body:
            obj.hide_render = True
            obj.hide_viewport = True
    body.name = "CH101_A_MPFBase_CC0_WIP"
    normalize_body(body)
    body.data.materials.append(make_material("MAT_MPFBase_SkinWIP", (0.62, 0.32, 0.30, 1), 0.58))
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body["status"] = "WIP / CC0 MPFB BASE / NOT APPROVED"
    body["source"] = "makehumancommunity/mpfb2 src/mpfb/data/3dobjs/base.obj"
    body["license"] = "CC0 1.0 Universal (per official MPFB license)"
    body["next"] = "CH101 face/hair/outfit sculpt and retopology"
    setup_scene(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / CC0 MPFB BASE / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    scene["re_camp_source_license"] = "CC0 1.0 Universal"
    blend = out / "CH101_A_MPFBase_CC0_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    body.data.calc_loop_triangles()
    report = {
        "status": "WIP / CC0 MPFB BASE / NOT APPROVED",
        "blend": str(blend),
        "source_obj": str(base_obj),
        "source_license": "CC0 1.0 Universal",
        "vertex_count": len(body.data.vertices),
        "triangle_count": len(body.data.loop_triangles),
        "target_height": "3.65 scene units",
        "gate_a": "PENDING",
        "gate_b": "BLOCKED / no CH101 outfit or rig bind",
        "notes": ["Actual human topology source", "No CH101 styling yet", "Human visual review required"],
    }
    (out / "reports" / "CH101_A_MPFBase_CC0_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / CC0 MPFB base / not approved")


if __name__ == "__main__":
    main()
