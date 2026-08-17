#!/usr/bin/env python3
"""Build a CH101-A organic connected-body WIP with voxel remesh.

The pass is intentionally visual-only.  It provides a better starting surface
than disconnected cylinders while keeping the final status WIP/NOT APPROVED.
"""

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

from build_ch101_base_mesh_wip import (  # noqa: E402
    clear,
    curve,
    face,
    hair,
    look_at,
    mat,
    panel,
    ring_mesh,
    rounded_cube,
    set_parent,
    sphere,
)


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def create_body_volume(root: bpy.types.Object, skin_material: bpy.types.Material) -> bpy.types.Object:
    parts: list[bpy.types.Object] = []

    def add(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        sphere(name, location, scale, skin_material, root, segments=48)
        obj = bpy.context.object
        obj.rotation_euler = rotation
        parts.append(obj)

    # Taller adult proportions: pelvis, waist, torso, shoulder/arm, and long
    # legs are all overlapping volumes before the voxel merge.
    add("BodyPelvis", (0.0, 0.0, 1.42), (0.36, 0.23, 0.30))
    add("BodyWaist", (0.0, 0.0, 1.78), (0.25, 0.19, 0.28))
    add("BodyTorso", (0.0, 0.0, 2.08), (0.33, 0.20, 0.38))
    add("BodyShoulderL", (-0.27, 0.0, 2.22), (0.17, 0.16, 0.19))
    add("BodyShoulderR", (0.27, 0.0, 2.22), (0.17, 0.16, 0.19))
    add("BodyUpperArmL", (-0.39, -0.01, 1.98), (0.12, 0.11, 0.24), (0.0, 0.0, -0.22))
    add("BodyUpperArmR", (0.39, -0.01, 1.98), (0.12, 0.11, 0.24), (0.0, 0.0, 0.22))
    add("BodyForeArmL", (-0.53, -0.05, 1.72), (0.095, 0.09, 0.21), (0.0, 0.0, -0.12))
    add("BodyForeArmR", (0.53, -0.05, 1.72), (0.095, 0.09, 0.21), (0.0, 0.0, 0.12))
    add("BodyThighL", (-0.17, 0.0, 1.08), (0.16, 0.15, 0.42), (0.0, 0.0, -0.02))
    add("BodyThighR", (0.17, 0.0, 1.08), (0.16, 0.15, 0.42), (0.0, 0.0, 0.02))
    add("BodyCalfL", (-0.18, 0.0, 0.52), (0.105, 0.10, 0.35))
    add("BodyCalfR", (0.18, 0.0, 0.52), (0.105, 0.10, 0.35))

    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = "CH101_A_HighResBody_VoxelWIP"
    body.data.materials.clear()
    body.data.materials.append(skin_material)
    remesh = body.modifiers.new(name="OrganicVoxelRemesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.045
    remesh.use_smooth_shade = True
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    smooth = body.modifiers.new(name="OrganicSurfaceSubdivision", type="SUBSURF")
    smooth.levels = 1
    smooth.render_levels = 1
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body["status"] = "WIP / VOXEL CONNECTED BODY / NOT APPROVED"
    body["topology"] = "voxel remesh review surface; retopology required"
    return body


def add_outfit(root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    ring_mesh("CropTop", 0.0, [(1.91, 0.25, 0.17), (2.08, 0.31, 0.19), (2.26, 0.28, 0.18)], m["graphite"], root, segments=40)
    ring_mesh("ShortsWaist", 0.0, [(1.23, 0.34, 0.22), (1.40, 0.36, 0.22), (1.52, 0.31, 0.20)], m["graphite"], root, segments=40)
    for side in (-1, 1):
        ring_mesh("ShortsLeg", side * 0.17, [(1.16, 0.14, 0.18), (1.31, 0.16, 0.18), (1.43, 0.14, 0.17)], m["graphite"], root, segments=28)
        panel("JacketPanel", (side * 0.22, -0.23, 2.15), 0.15, 0.22, 0.58, 0.075, m["white"], root)
        rounded_cube("ThighStrap", (side * 0.18, -0.19, 1.05), (0.11, 0.022, 0.027), m["gold"], root, 0.012)
        sphere("BootUpper", (side * 0.18, -0.08, 0.20), (0.13, 0.14, 0.22), m["graphite"], root)
        sphere("BootToe", (side * 0.18, -0.25, 0.12), (0.16, 0.24, 0.11), m["white"], root)
    curve("JacketHem", [(-0.28, -0.24, 1.90), (0.0, -0.25, 1.87), (0.28, -0.24, 1.90)], 0.018, m["cyan"], root)


def add_equipment(root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    rounded_cube("SaberGrip", (0.68, -0.25, 1.68), (0.035, 0.035, 0.16), m["graphite"], root, 0.018)
    panel("SaberBlade", (0.68, -0.25, 2.05), 0.075, 0.045, 0.58, 0.025, m["cyan"], root)
    curve("SignalRibbon", [(-0.39, -0.18, 2.38), (-0.70, -0.08, 2.86), (-0.45, 0.0, 3.30), (0.20, 0.0, 3.42), (0.72, -0.12, 2.80), (0.46, -0.17, 2.30)], 0.038, m["cyan"], root)
    curve("RibbonAccent", [(-0.39, -0.20, 2.38), (-0.46, -0.01, 3.30), (0.20, -0.01, 3.42)], 0.009, m["gold"], root)


def setup_scene(out: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.015, 0.018, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.7, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("VoxelReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.45, -10.2, 2.15))
    camera = bpy.context.object
    camera.data.lens = 64
    look_at(camera, Vector((0, 0, 1.95)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_VoxelBody_WIP_3q.png")
    for location, energy, color in (((-4.0, -5.0, 6.5), 1200, (1.0, 0.80, 0.70)), ((4.0, -3.0, 4.0), 700, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 950, (0.10, 0.60, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.8)))


def main() -> None:
    options = parse_args()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    materials = {
        "skin": mat("MAT_VOXEL_Skin", (0.86, 0.58, 0.54, 1), 0.55),
        "skin_shadow": mat("MAT_VOXEL_SkinShadow", (0.70, 0.38, 0.38, 1), 0.64),
        "eye": mat("MAT_VOXEL_EyeWhite", (0.96, 0.98, 1.0, 1), 0.22),
        "iris": mat("MAT_VOXEL_Iris", (0.04, 0.40, 0.62, 1), 0.18, metallic=0.05),
        "pupil": mat("MAT_VOXEL_Pupil", (0.004, 0.006, 0.015, 1), 0.10),
        "eye_highlight": mat("MAT_VOXEL_Highlight", (1.0, 1.0, 1.0, 1), 0.06, emission=True),
        "lip": mat("MAT_VOXEL_Lip", (0.46, 0.08, 0.12, 1), 0.30),
        "hair": mat("MAT_VOXEL_Hair", (0.008, 0.012, 0.025, 1), 0.22),
        "white": mat("MAT_VOXEL_White", (0.88, 0.88, 0.84, 1), 0.42),
        "graphite": mat("MAT_VOXEL_Graphite", (0.018, 0.026, 0.046, 1), 0.36),
        "gold": mat("MAT_VOXEL_Gold", (0.78, 0.38, 0.06, 1), 0.25, metallic=0.7),
        "cyan": mat("MAT_VOXEL_Cyan", (0.01, 0.42, 0.64, 1), 0.24, metallic=0.12, emission=True),
    }
    root = bpy.data.objects.new("CH101_A_VoxelBody_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    create_body_volume(root, materials["skin"])
    add_outfit(root, materials)
    face(0.0, root, materials)
    hair(0.0, root, materials, hood=False)
    add_equipment(root, materials)
    root.scale.z = 1.12
    root["status"] = "WIP / VOXEL BODY REVIEW / NOT APPROVED"
    root["target_heads"] = "5.3-5.4"
    root["next"] = "retopology, UV, rig binding, human visual Gate A"
    setup_scene(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / VOXEL BODY REVIEW / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    blend = out / "CH101_A_VoxelBody_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "status": "WIP / VOXEL BODY REVIEW / NOT APPROVED",
        "blend": str(blend),
        "body_method": "overlapping anatomical volumes joined and voxel-remeshed",
        "target_heads": "5.3-5.4",
        "gate_a": "PENDING",
        "gate_b": "BLOCKED",
        "unity": "BLOCKED",
        "notes": ["Visual WIP only", "Retopology/UV/rigging not complete", "Human approval required"],
    }
    (out / "reports" / "CH101_A_VoxelBody_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / voxel body review / not approved")


if __name__ == "__main__":
    main()
