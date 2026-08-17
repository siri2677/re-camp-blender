#!/usr/bin/env python3
"""Validate the CH101-A rig/socket template contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


REQUIRED_BONES = {
    "Root", "Hips", "Spine", "Chest", "Neck", "Head",
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
    "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
}
SOCKET_BONES = {
    "Socket_Weapon_R": "RightHand",
    "Socket_Ribbon_L": "Chest",
    "Socket_Ribbon_R": "Chest",
    "Socket_Pouch_L": "Hips",
    "Socket_Pouch_R": "Hips",
    "Socket_Hair_Ponytail": "Head",
    "Socket_CameraFocus": "Head",
}
REQUIRED_ACTIONS = {"CH101_Idle", "CH101_Run", "CH101_Attack", "CH101_A_Pose_Check"}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def main() -> int:
    options = parse_args()
    blend = Path(options.blend).resolve()
    report_path = Path(options.report).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    armature = bpy.data.objects.get("CH101_A_RigTemplate_WIP")
    bones = {bone.name for bone in armature.data.bones} if armature and armature.type == "ARMATURE" else set()
    missing_bones = sorted(REQUIRED_BONES - bones)
    socket_errors = []
    for socket_name, bone_name in SOCKET_BONES.items():
        obj = bpy.data.objects.get(socket_name)
        if obj is None:
            socket_errors.append(f"{socket_name}: missing")
        elif obj.parent != armature or obj.parent_type != "BONE" or obj.parent_bone != bone_name:
            socket_errors.append(f"{socket_name}: expected {bone_name}")
    actions = {action.name for action in bpy.data.actions}
    missing_actions = sorted(REQUIRED_ACTIONS - actions)
    mesh_objects = sorted(obj.name for obj in bpy.data.objects if obj.type == "MESH")
    errors = []
    if armature is None:
        errors.append("missing CH101_A_RigTemplate_WIP armature")
    if missing_bones:
        errors.append(f"missing bones: {', '.join(missing_bones)}")
    if socket_errors:
        errors.append(f"socket errors: {'; '.join(socket_errors)}")
    if missing_actions:
        errors.append(f"missing actions: {', '.join(missing_actions)}")
    if mesh_objects:
        errors.append(f"template unexpectedly contains mesh objects: {', '.join(mesh_objects)}")
    report = {
        "blend": str(blend),
        "status": "PASS" if not errors else "FAIL",
        "template_status": bpy.context.scene.get("re_camp_status", ""),
        "armature": armature.name if armature else "",
        "bone_count": len(bones),
        "missing_bones": missing_bones,
        "socket_count": len(SOCKET_BONES) - len(socket_errors),
        "socket_errors": socket_errors,
        "action_count": len(REQUIRED_ACTIONS - set(missing_actions)),
        "missing_actions": missing_actions,
        "mesh_objects": mesh_objects,
        "gate_b": "BLOCKED / no mesh weights",
        "gate_c": "BLOCKED / no Unity import",
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
