#!/usr/bin/env python3
"""Build a documentation-only CH101-style Blender blockout.

This script is intentionally a neutral humanoid and equipment placeholder.
It does not claim a final character model, rig, animation, Unity import, or
Gate B approval. Run it inside Blender, for example:

    blender --background --python build_blockout.py -- \
        --character CH101 --output-dir /tmp/ch101_blockout --render
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SOCKETS = {
    "Socket_Equipment_Primary": (0.58, -0.12, 1.85),
    "Socket_Gauntlet_L": (-0.72, -0.02, 2.05),
    "Socket_Gauntlet_R": (0.72, -0.02, 2.05),
    "Socket_AnchorRing_Carry": (0.0, -0.48, 2.25),
    "Socket_AnchorRing_Active": (0.0, -0.64, 2.25),
    "Socket_LineAttach": (0.0, -0.70, 2.25),
    "Socket_VFXCenter": (0.0, -0.18, 1.85),
    "Socket_CameraFocus": (0.0, 0.0, 2.35),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", default="CH101")
    parser.add_argument("--source-asset", default="")
    parser.add_argument("--source-commit", default="418ef96")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--export-fbx", action="store_true")
    return parser.parse_args(script_args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.metallic = metallic
    mat.roughness = 0.58
    return mat


def apply_material(obj: bpy.types.Object, mat: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.append(mat)
    return obj


def add_uv_sphere(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return apply_material(obj, mat)


def add_cylinder_between(name: str, start: tuple[float, float, float], end: tuple[float, float, float], radius: float, mat: bpy.types.Material) -> bpy.types.Object:
    start_vec = Vector(start)
    end_vec = Vector(end)
    direction = end_vec - start_vec
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=direction.length, location=(start_vec + end_vec) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return apply_material(obj, mat)


def add_cube(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return apply_material(obj, mat)


def add_equipment(name: str, location: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (0.10, 0.16, 0.58)
    obj.rotation_euler[1] = math.radians(-18)
    return apply_material(obj, mat)


def add_socket(name: str, location: tuple[float, float, float], root: bpy.types.Object) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.12
    obj.location = location
    obj.parent = root
    bpy.context.collection.objects.link(obj)
    return obj


def add_camera(name: str, location: tuple[float, float, float], target: Vector) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 58
    return camera


def configure_render(scene: bpy.types.Scene, output_dir: Path) -> None:
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except (RuntimeError, TypeError, ValueError):
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.025, 0.035, 0.05)
    output_dir.mkdir(parents=True, exist_ok=True)


def build_scene(args: argparse.Namespace) -> tuple[bpy.types.Object, Path]:
    output_dir = Path(args.output_dir).resolve()
    clear_scene()

    body = material("MAT_Blockout_Body", (0.28, 0.42, 0.62, 1.0))
    hair = material("MAT_Blockout_Hair", (0.08, 0.10, 0.16, 1.0))
    outfit = material("MAT_Blockout_Outfit", (0.16, 0.19, 0.24, 1.0))
    equipment = material("MAT_Blockout_Equipment", (0.13, 0.58, 0.68, 1.0), metallic=0.35)
    ring = material("MAT_Blockout_Ring", (0.86, 0.48, 0.12, 1.0), metallic=0.55)

    root = bpy.data.objects.new(f"{args.character}_Blockout_Root", None)
    root.empty_display_type = "PLAIN_AXES"
    root["character_id"] = args.character
    root["source_asset"] = args.source_asset
    root["source_commit"] = args.source_commit
    root["blockout_status"] = "DOCUMENTATION ONLY / NOT GATE B APPROVED"
    bpy.context.collection.objects.link(root)

    torso = add_cylinder_between("Body_Torso", (0, 0, 1.55), (0, 0, 2.45), 0.34, outfit)
    torso.parent = root
    pelvis = add_uv_sphere("Body_Pelvis", (0, 0, 1.32), (0.38, 0.28, 0.22), outfit)
    pelvis.parent = root
    neck = add_cylinder_between("Body_Neck", (0, 0, 2.40), (0, 0, 2.58), 0.14, body)
    neck.parent = root
    head = add_uv_sphere("Body_Head", (0, -0.01, 2.92), (0.38, 0.34, 0.44), body)
    head.parent = root
    hair_obj = add_uv_sphere("Hair_Blockout", (0, 0.08, 3.08), (0.43, 0.38, 0.37), hair)
    hair_obj.parent = root

    parts = [
        ("Arm_L_Upper", (-0.30, 0, 2.30), (-0.62, -0.01, 1.98), 0.11),
        ("Arm_L_Lower", (-0.62, -0.01, 1.98), (-0.78, -0.03, 1.70), 0.09),
        ("Arm_R_Upper", (0.30, 0, 2.30), (0.62, -0.01, 1.98), 0.11),
        ("Arm_R_Lower", (0.62, -0.01, 1.98), (0.78, -0.03, 1.70), 0.09),
        ("Leg_L_Upper", (-0.18, 0, 1.30), (-0.23, 0, 0.72), 0.14),
        ("Leg_L_Lower", (-0.23, 0, 0.72), (-0.25, -0.04, 0.12), 0.11),
        ("Leg_R_Upper", (0.18, 0, 1.30), (0.23, 0, 0.72), 0.14),
        ("Leg_R_Lower", (0.23, 0, 0.72), (0.25, -0.04, 0.12), 0.11),
    ]
    for name, start, end, radius in parts:
        obj = add_cylinder_between(name, start, end, radius, body if "Arm" in name else outfit)
        obj.parent = root

    equipment_obj = add_equipment("Equipment_Primary_Blockout", SOCKETS["Socket_Equipment_Primary"], equipment)
    equipment_obj.parent = root

    for side, x in (("L", -0.78), ("R", 0.78)):
        gauntlet = add_cube(f"Gauntlet_{side}_Blockout", (x, -0.05, 1.70), (0.12, 0.13, 0.16), equipment)
        gauntlet.parent = root

    bpy.ops.mesh.primitive_torus_add(major_radius=0.26, minor_radius=0.045, major_segments=24, minor_segments=8, location=SOCKETS["Socket_AnchorRing_Carry"], rotation=(math.pi / 2, 0, 0))
    ring_obj = bpy.context.object
    ring_obj.name = "AnchorRing_Blockout"
    ring_obj.parent = root
    apply_material(ring_obj, ring)

    for socket_name, location in SOCKETS.items():
        add_socket(socket_name, location, root)

    scene = bpy.context.scene
    configure_render(scene, output_dir / "renders")
    scene["re_camp_gate"] = "Gate B preflight only"
    scene["re_camp_source_commit"] = args.source_commit
    scene["re_camp_source_asset"] = args.source_asset
    scene["re_camp_technical_proof"] = "NOT TESTED"

    blend_path = output_dir / f"{args.character}_Blockout_REVIEW_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    return root, blend_path


def render_views(output_dir: Path) -> None:
    scene = bpy.context.scene
    target = Vector((0, 0, 1.75))
    views = {
        "front": (0, -10.5, 2.1),
        "side": (10.5, 0, 2.1),
        "back": (0, 10.5, 2.1),
    }
    for view, location in views.items():
        camera = add_camera(f"RenderCamera_{view}", location, target)
        scene.camera = camera
        scene.render.filepath = str(output_dir / "renders" / f"{view}.png")
        bpy.ops.render.render(write_still=True)


def export_fbx(output_dir: Path, character: str) -> Path:
    fbx_path = output_dir / f"{character}_Blockout_REVIEW_v001.fbx"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=False,
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
    )
    return fbx_path


def write_report(output_dir: Path, args: argparse.Namespace, blend_path: Path, fbx_path: Path | None) -> None:
    objects = list(bpy.data.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    report = {
        "character": args.character,
        "source_asset": args.source_asset,
        "source_commit": args.source_commit,
        "status": "DOCUMENTATION ONLY / NOT GATE B APPROVED",
        "technical_proof": "NOT TESTED",
        "blend": str(blend_path),
        "fbx": str(fbx_path) if fbx_path else None,
        "mesh_object_count": len(meshes),
        "object_count": len(objects),
        "socket_names": sorted(name for name in SOCKETS if bpy.data.objects.get(name)),
        "material_names": sorted(mat.name for mat in bpy.data.materials if mat.name.startswith("MAT_Blockout_")),
        "render_views": ["front", "side", "back"] if args.render else [],
    }
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports" / f"{args.character}_Blockout_REVIEW_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    root, blend_path = build_scene(args)
    del root
    if args.render:
        render_views(output_dir)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    fbx_path = export_fbx(output_dir, args.character) if args.export_fbx else None
    write_report(output_dir, args, blend_path, fbx_path)
    print(f"Blockout generated: {blend_path}")
    print(f"Status: documentation-only / Gate B not approved / technical proof not tested")


if __name__ == "__main__":
    main()
