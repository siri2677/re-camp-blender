#!/usr/bin/env python3
"""Bind the target-applied MPFB body WIP to the CH101 rig template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_rig_template_wip import build_armature, collection, create_actions, socket  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(raw)


def main() -> None:
    options = parse_args()
    input_blend = Path(options.input_blend).resolve()
    out = Path(options.output_dir).resolve()
    (out / "reports").mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(input_blend))
    body = bpy.data.objects.get("CH101_A_TargetedBody_WIP")
    root = bpy.data.objects.get("CH101_A_TargetedObj_WIP_Root")
    if body is None:
        raise RuntimeError("Targeted body not found")
    if root:
        body.parent = None
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
    weighted = sum(1 for vertex in body.data.vertices if vertex.groups)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / TARGETED MPFB BODY RIG BOUND / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    blend = out / "CH101_A_TargetedBody_RigBound_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    body.data.calc_loop_triangles()
    report = {
        "status": "WIP / TARGETED MPFB BODY RIG BOUND / NOT APPROVED",
        "blend": str(blend),
        "input_blend": str(input_blend),
        "body_vertices": len(body.data.vertices),
        "body_triangles": len(body.data.loop_triangles),
        "weighted_vertices": weighted,
        "armature_modifier_bound": bound,
        "armature": armature.name,
        "bone_count": len(armature.data.bones),
        "socket_count": len(socket_specs),
        "actions": actions,
        "gate_a": "PENDING / styling incomplete",
        "gate_b": "BLOCKED / clothing, pose and deformation proof incomplete",
    }
    (out / "reports" / "CH101_A_TargetedBody_RigBound_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print(f"Bound: {bound}; weighted vertices: {weighted}")
    print("Status: WIP / targeted MPFB body rig bound / not approved")


if __name__ == "__main__":
    main()
