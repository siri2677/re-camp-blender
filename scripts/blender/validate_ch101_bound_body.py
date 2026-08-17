#!/usr/bin/env python3
"""Validate a CH101 body mesh bound to the rig template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


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
    body = bpy.data.objects.get("CH101_A_MPFBody_CC0_WIP") or bpy.data.objects.get("CH101_A_TargetedBody_WIP")
    errors = []
    if armature is None or armature.type != "ARMATURE":
        errors.append("missing CH101 rig template")
    if body is None or body.type != "MESH":
        errors.append("missing MPFB body mesh")
    modifier_bound = bool(body and armature and any(mod.type == "ARMATURE" and mod.object == armature for mod in body.modifiers))
    if not modifier_bound:
        errors.append("body missing Armature modifier bound to CH101 rig")
    weighted_vertices = sum(1 for vertex in body.data.vertices if vertex.groups) if body else 0
    if body and weighted_vertices != len(body.data.vertices):
        errors.append(f"unweighted vertices: {len(body.data.vertices) - weighted_vertices}")
    socket_errors = []
    for name, bone in SOCKET_BONES.items():
        socket = bpy.data.objects.get(name)
        if socket is None or socket.parent != armature or socket.parent_type != "BONE" or socket.parent_bone != bone:
            socket_errors.append(f"{name}->{bone}")
    if socket_errors:
        errors.append(f"socket errors: {', '.join(socket_errors)}")
    actions = {action.name for action in bpy.data.actions}
    missing_actions = sorted(REQUIRED_ACTIONS - actions)
    if missing_actions:
        errors.append(f"missing actions: {', '.join(missing_actions)}")
    report = {
        "blend": str(blend),
        "status": "PASS" if not errors else "FAIL",
        "scene_status": bpy.context.scene.get("re_camp_status", ""),
        "body_vertices": len(body.data.vertices) if body else 0,
        "weighted_vertices": weighted_vertices,
        "armature_modifier_bound": modifier_bound,
        "socket_count": len(SOCKET_BONES) - len(socket_errors),
        "socket_errors": socket_errors,
        "action_count": len(REQUIRED_ACTIONS - set(missing_actions)),
        "missing_actions": missing_actions,
        "gate_b": "BLOCKED / body only; CH101 styling and pose proof incomplete",
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
