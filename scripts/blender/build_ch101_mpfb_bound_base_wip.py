#!/usr/bin/env python3
"""Bind the CC0 MPFB body to the validated CH101 rig template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_mpfb_base_wip import clear, look_at, make_material, normalize_body  # noqa: E402
from build_ch101_rig_template_wip import build_armature, collection, create_actions, socket  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


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
    floor.data.materials.append(make_material("BoundReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.35, -6.9, 2.0))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0, 0, 1.9)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_MPFBase_Bound_WIP_3q.png")
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
        raise RuntimeError("MPFB base.obj import did not expose body")
    for obj in imported:
        if obj != body:
            bpy.data.objects.remove(obj, do_unlink=True)
    normalize_body(body, target_height=3.65)
    body.name = "CH101_A_MPFBody_CC0_WIP"
    body.data.materials.append(make_material("MAT_CH101_Skin", (0.82, 0.50, 0.47, 1), 0.54))
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body_collection = collection("MODEL_HIGH_BODY")
    for owner in list(body.users_collection):
        owner.objects.unlink(body)
    body_collection.objects.link(body)
    rig_collection = collection("TECH_RIG_TEMPLATE")
    socket_collection = collection("TECH_SOCKETS_TEMPLATE")
    armature = build_armature(rig_collection)
    actions = create_actions(armature)
    socket_specs = {
        "Socket_Weapon_R": (0.60, -0.08, 1.62, "RightHand"),
        "Socket_Ribbon_L": (-0.38, 0.0, 2.30, "Chest"),
        "Socket_Ribbon_R": (0.38, 0.0, 2.30, "Chest"),
        "Socket_Pouch_L": (-0.30, -0.16, 1.70, "Hips"),
        "Socket_Pouch_R": (0.30, -0.16, 1.70, "Hips"),
        "Socket_Hair_Ponytail": (0.22, 0.05, 2.70, "Head"),
        "Socket_CameraFocus": (0.0, -0.02, 2.78, "Head"),
    }
    for name, (x, y, z, bone) in socket_specs.items():
        socket(name, bone, (x, y, z), armature, socket_collection)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    bound = any(mod.type == "ARMATURE" and mod.object == armature for mod in body.modifiers)
    weighted_vertices = sum(1 for vertex in body.data.vertices if vertex.groups)
    body["status"] = "WIP / MPFB BODY RIG BOUND / NOT APPROVED"
    body["source_license"] = "CC0 1.0 Universal (MPFB base asset)"
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / MPFB BODY RIG BOUND / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    scene["re_camp_source_license"] = "CC0 1.0 Universal"
    setup_scene(out)
    blend = out / "CH101_A_MPFBody_RigBound_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    body.data.calc_loop_triangles()
    report = {
        "status": "WIP / MPFB BODY RIG BOUND / NOT APPROVED",
        "blend": str(blend),
        "source_obj": str(base_obj),
        "source_license": "CC0 1.0 Universal",
        "body_vertices": len(body.data.vertices),
        "body_triangles": len(body.data.loop_triangles),
        "armature": armature.name,
        "armature_modifier_bound": bound,
        "weighted_vertices": weighted_vertices,
        "bone_count": len(armature.data.bones),
        "socket_count": len(socket_specs),
        "actions": actions,
        "gate_a": "PENDING / styling not complete",
        "gate_b": "BLOCKED / outfit, hair, retopo and pose proof incomplete",
        "notes": ["Real body topology and automatic weights", "CH101 styling remains WIP", "Human review required"],
    }
    (out / "reports" / "CH101_A_MPFBody_RigBound_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print(f"Bound: {bound}; weighted vertices: {weighted_vertices}")
    print("Status: WIP / MPFB body rig bound / not approved")


if __name__ == "__main__":
    main()
