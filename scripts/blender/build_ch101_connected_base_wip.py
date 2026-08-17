#!/usr/bin/env python3
"""Build a connected CH101-A body WIP for visual review.

This is the first pass that uses a connected Skin Modifier body instead of a
collection of separate rounded primitives.  It is still WIP and deliberately
does not claim Gate B readiness.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_base_mesh_wip import (  # noqa: E402
    args as base_args,
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
    capsule,
)
from mathutils import Vector  # noqa: E402


def parse() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def skin_body(x: float, root: bpy.types.Object, material: bpy.types.Material) -> bpy.types.Object:
    # torso and limb centerlines, one connected graph
    points = [
        (x, 0.0, 1.28), (x, 0.0, 1.62), (x, 0.0, 1.94), (x, 0.0, 2.25),
        (x, 0.0, 2.48),
        (x - 0.30, 0.0, 2.17), (x - 0.46, -0.01, 1.88), (x - 0.58, -0.06, 1.62),
        (x + 0.30, 0.0, 2.17), (x + 0.46, -0.01, 1.88), (x + 0.58, -0.06, 1.62),
        (x - 0.17, 0.0, 1.26), (x - 0.18, 0.0, 0.78), (x - 0.18, 0.0, 0.24),
        (x + 0.17, 0.0, 1.26), (x + 0.18, 0.0, 0.78), (x + 0.18, 0.0, 0.24),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (3, 5), (5, 6), (6, 7), (3, 8), (8, 9), (9, 10), (0, 11), (11, 12), (12, 13), (0, 14), (14, 15), (15, 16)]
    mesh = bpy.data.meshes.new("CH101_ConnectedBodyMesh")
    mesh.from_pydata(points, edges, [])
    mesh.update()
    obj = bpy.data.objects.new("CH101_A_ConnectedBody_WIP", mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    skin = obj.modifiers.new(name="OrganicBodySkin", type="SKIN")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.context.view_layer.update()
    radii = [0.24, 0.23, 0.20, 0.27, 0.10, 0.11, 0.085, 0.065, 0.11, 0.085, 0.065, 0.13, 0.105, 0.075, 0.13, 0.105, 0.075]
    skin_data = obj.data.skin_vertices[0].data
    for index, radius in enumerate(radii):
        skin_data[index].radius = (radius, radius)
    skin_data[0].use_root = True
    subdiv = obj.modifiers.new(name="OrganicBodySubdivision", type="SUBSURF")
    subdiv.levels = 2
    subdiv.render_levels = 2
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def build_character(root: bpy.types.Object, materials: dict[str, bpy.types.Material]) -> None:
    x = 0.0
    skin_body(x, root, materials["skin"])
    capsule("Neck", (x, 0.0, 2.34), (x, 0.0, 2.60), 0.095, materials["skin"], root)
    sphere("BustL", (x - 0.13, -0.17, 2.10), (0.155, 0.12, 0.155), materials["skin"], root)
    sphere("BustR", (x + 0.13, -0.17, 2.10), (0.155, 0.12, 0.155), materials["skin"], root)
    ring_mesh("CropTop", x, [(1.88, 0.24, 0.16), (2.08, 0.30, 0.18), (2.26, 0.27, 0.17)], materials["graphite"], root, segments=40)
    ring_mesh("ShortsWaist", x, [(1.23, 0.34, 0.22), (1.39, 0.35, 0.22), (1.52, 0.30, 0.19)], materials["graphite"], root, segments=40)
    for side in (-1, 1):
        ring_mesh("ShortsLeg", x + side * 0.17, [(1.16, 0.14, 0.17), (1.30, 0.15, 0.18), (1.42, 0.13, 0.16)], materials["graphite"], root, segments=28)
        capsule("Sleeve", (x + side * 0.31, 0.0, 2.15), (x + side * 0.48, -0.01, 1.87), 0.115, materials["graphite"], root)
        capsule("ForeSleeve", (x + side * 0.48, -0.01, 1.87), (x + side * 0.59, -0.06, 1.64), 0.088, materials["graphite"], root)
        sphere("Hand", (x + side * 0.60, -0.08, 1.56), (0.065, 0.055, 0.085), materials["skin"], root)
        capsule("BootUpper", (x + side * 0.18, -0.08, 0.18), (x + side * 0.18, -0.08, 0.43), 0.12, materials["graphite"], root)
        sphere("BootToe", (x + side * 0.18, -0.23, 0.12), (0.16, 0.24, 0.11), materials["white"], root)
        panel("JacketPanel", (x + side * 0.225, -0.23, 2.14), 0.14, 0.22, 0.56, 0.07, materials["white"], root)
        rounded_cube("ThighStrap", (x + side * 0.18, -0.19, 1.05), (0.11, 0.022, 0.027), materials["gold"], root, 0.012)
    curve("JacketHem", [(x - 0.28, -0.24, 1.89), (x, -0.25, 1.86), (x + 0.28, -0.24, 1.89)], 0.018, materials["cyan"], root)
    face(x, root, materials)
    hair(x, root, materials, hood=False)
    capsule("SaberGrip", (x + 0.68, -0.24, 1.52), (x + 0.68, -0.24, 1.82), 0.04, materials["graphite"], root)
    panel("SaberBlade", (x + 0.68, -0.24, 2.16), 0.07, 0.05, 0.62, 0.03, materials["cyan"], root)
    curve("SignalRibbon", [(x - 0.40, -0.18, 2.38), (x - 0.72, -0.08, 2.84), (x - 0.48, 0.0, 3.26), (x + 0.18, 0.0, 3.40), (x + 0.72, -0.12, 2.77), (x + 0.45, -0.17, 2.32)], 0.04, materials["cyan"], root)
    root.scale.z = 1.15
    root["status"] = "WIP / CONNECTED BODY REVIEW / NOT APPROVED"
    root["target_heads"] = "5.3-5.4"


def setup_scene(out: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.015, 0.018, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.6, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("ConnectedReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.55))
    bpy.ops.object.camera_add(location=(0.35, -10.0, 2.25))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0, 0, 1.95)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_ConnectedBase_WIP_3q.png")
    for loc, energy, color in (((-4.0, -5.5, 6.5), 1150, (1.0, 0.78, 0.68)), ((4.0, -3.0, 4.0), 650, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 900, (0.10, 0.60, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.8)))


def main() -> None:
    options = parse()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    clear()
    materials = {
        "skin": mat("MAT_CONN_Skin", (0.86, 0.58, 0.54, 1), 0.55),
        "skin_shadow": mat("MAT_CONN_SkinShadow", (0.70, 0.38, 0.38, 1), 0.64),
        "eye": mat("MAT_CONN_EyeWhite", (0.96, 0.98, 1.0, 1), 0.22),
        "iris": mat("MAT_CONN_Iris", (0.04, 0.40, 0.62, 1), 0.18, metallic=0.05),
        "pupil": mat("MAT_CONN_Pupil", (0.004, 0.006, 0.015, 1), 0.10),
        "eye_highlight": mat("MAT_CONN_Highlight", (1.0, 1.0, 1.0, 1), 0.06, emission=True),
        "lip": mat("MAT_CONN_Lip", (0.46, 0.08, 0.12, 1), 0.3),
        "hair": mat("MAT_CONN_Hair", (0.008, 0.012, 0.025, 1), 0.22),
        "white": mat("MAT_CONN_White", (0.88, 0.88, 0.84, 1), 0.42),
        "graphite": mat("MAT_CONN_Graphite", (0.018, 0.026, 0.046, 1), 0.36),
        "gold": mat("MAT_CONN_Gold", (0.78, 0.38, 0.06, 1), 0.25, metallic=0.7),
        "cyan": mat("MAT_CONN_Cyan", (0.01, 0.42, 0.64, 1), 0.24, metallic=0.12, emission=True),
    }
    root = bpy.data.objects.new("CH101_A_ConnectedBase_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    build_character(root, materials)
    setup_scene(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / CONNECTED BASE REVIEW / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    blend = out / "CH101_A_ConnectedBase_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "reports" / "CH101_A_ConnectedBase_WIP_v001.json").write_text(
        '{\n  "status": "WIP / CONNECTED BASE REVIEW / NOT APPROVED",\n  "body": "Skin Modifier connected torso and limbs",\n  "target_heads": "5.3-5.4",\n  "gate_a": "PENDING",\n  "gate_b": "BLOCKED",\n  "unity": "BLOCKED"\n}\n',
        encoding="utf-8",
    )
    print(f"Generated {blend}")
    print("Status: WIP / connected base review / not approved")


if __name__ == "__main__":
    main()
