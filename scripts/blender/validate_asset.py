#!/usr/bin/env python3
"""Validate the non-production structure of a generated Blender blockout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


REQUIRED_SOCKETS = {
    "Socket_Equipment_Primary",
    "Socket_Gauntlet_L",
    "Socket_Gauntlet_R",
    "Socket_AnchorRing_Carry",
    "Socket_AnchorRing_Active",
    "Socket_LineAttach",
    "Socket_VFXCenter",
    "Socket_CameraFocus",
}

REQUIRED_RIG_BONES = {
    "Root",
    "Hips",
    "Spine",
    "Chest",
    "Neck",
    "Head",
    "LeftShoulder",
    "LeftUpperArm",
    "LeftLowerArm",
    "LeftHand",
    "RightShoulder",
    "RightUpperArm",
    "RightLowerArm",
    "RightHand",
    "LeftUpperLeg",
    "LeftLowerLeg",
    "LeftFoot",
    "LeftToes",
    "RightUpperLeg",
    "RightLowerLeg",
    "RightFoot",
    "RightToes",
}

MOTION_CLIP_SUFFIXES = ("Idle", "Run", "Attack", "A_Pose_Check")

SOCKET_BONE_MAP = {
    "Socket_Equipment_Primary": "RightHand",
    "Socket_Gauntlet_L": "LeftHand",
    "Socket_Gauntlet_R": "RightHand",
    "Socket_AnchorRing_Carry": "Chest",
    "Socket_AnchorRing_Active": "Chest",
    "Socket_LineAttach": "Chest",
    "Socket_VFXCenter": "Hips",
    "Socket_CameraFocus": "Head",
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--character", default="CH101")
    return parser.parse_args(script_args)


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    objects = list(bpy.data.objects)
    names = {obj.name for obj in objects}
    armature_name = f"{args.character}_Rig_Armature"
    required_motion_clips = {f"{args.character}_{suffix}" for suffix in MOTION_CLIP_SUFFIXES}
    missing = sorted(REQUIRED_SOCKETS - names)
    root = next((obj for obj in objects if obj.name.endswith("_Blockout_Root")), None)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    armature = next((obj for obj in armatures if obj.name == armature_name), None)
    errors: list[str] = []
    if missing:
        errors.append(f"missing sockets: {', '.join(missing)}")
    if root is None:
        errors.append("missing blockout root empty")
    if not meshes:
        errors.append("no mesh objects found")
    if armature is None:
        errors.append(f"missing {armature_name}")

    missing_rig_bones = sorted(REQUIRED_RIG_BONES - {bone.name for bone in armature.data.bones}) if armature else sorted(REQUIRED_RIG_BONES)
    if missing_rig_bones:
        errors.append(f"missing rig bones: {', '.join(missing_rig_bones)}")

    motion_clips = sorted(action.name for action in bpy.data.actions if action.name.startswith(f"{args.character}_"))
    missing_motion_clips = sorted(required_motion_clips - set(motion_clips))
    if missing_motion_clips:
        errors.append(f"missing motion clips: {', '.join(missing_motion_clips)}")

    socket_bone_errors = []
    for socket_name, bone_name in SOCKET_BONE_MAP.items():
        socket = bpy.data.objects.get(socket_name)
        if socket is None or socket.parent != armature or socket.parent_type != "BONE" or socket.parent_bone != bone_name:
            socket_bone_errors.append(f"{socket_name}->{bone_name}")
    if socket_bone_errors:
        errors.append(f"socket bone parenting mismatch: {', '.join(socket_bone_errors)}")

    skinning_errors = []
    weighted_meshes = []
    if armature:
        for obj in meshes:
            armature_modifiers = [
                modifier for modifier in obj.modifiers
                if modifier.type == "ARMATURE" and modifier.object == armature
            ]
            has_vertex_weights = any(bool(vertex.groups) for vertex in obj.data.vertices)
            if not armature_modifiers:
                skinning_errors.append(f"{obj.name}: missing armature modifier")
            if not has_vertex_weights:
                skinning_errors.append(f"{obj.name}: no vertex weights")
            if armature_modifiers and has_vertex_weights:
                weighted_meshes.append(obj.name)
    if skinning_errors:
        errors.append(f"skinning errors: {'; '.join(skinning_errors)}")

    uv_missing = sorted(obj.name for obj in meshes if not obj.data.uv_layers)
    materialless_meshes = sorted(obj.name for obj in meshes if not obj.data.materials)
    triangle_count = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangle_count += len(obj.data.loop_triangles)
    if uv_missing:
        errors.append(f"missing UV maps: {', '.join(uv_missing)}")
    if materialless_meshes:
        errors.append(f"missing material slots: {', '.join(materialless_meshes)}")

    report = {
        "character": args.character,
        "blend": str(Path(args.blend).resolve()),
        "status": "PASS" if not errors else "FAIL",
        "technical_proof": "NOT TESTED",
        "revision": bpy.context.scene.get("re_camp_blockout_revision", ""),
        "mesh_object_count": len(meshes),
        "triangle_count": triangle_count,
        "socket_count": len(REQUIRED_SOCKETS - set(missing)),
        "missing": missing,
        "uv_missing": uv_missing,
        "materialless_meshes": materialless_meshes,
        "uv_status": bpy.context.scene.get("re_camp_uv_status", "NOT SET"),
        "lod_status": bpy.context.scene.get("re_camp_lod_status", "NOT SET"),
        "technical_preparation": "PASS" if not uv_missing and not materialless_meshes else "FAIL",
        "armature_count": len(armatures),
        "armature_name": armature.name if armature else "",
        "bone_count": len(armature.data.bones) if armature else 0,
        "missing_rig_bones": missing_rig_bones,
        "motion_clips": motion_clips,
        "missing_motion_clips": missing_motion_clips,
        "socket_bone_map": SOCKET_BONE_MAP,
        "socket_bone_errors": socket_bone_errors,
        "rig_status": bpy.context.scene.get("re_camp_rig_status", "NOT SET"),
        "deformation_status": bpy.context.scene.get("re_camp_deformation_status", "NOT SET"),
        "motion_status": bpy.context.scene.get("re_camp_motion_status", "NOT SET"),
        "rig_preparation": "PASS" if armature and not missing_rig_bones and not missing_motion_clips and not socket_bone_errors else "FAIL",
        "weighted_mesh_object_count": len(weighted_meshes),
        "skinning_errors": skinning_errors,
        "skinning_status": bpy.context.scene.get("re_camp_skinning_status", "NOT SET"),
        "pose_review_status": bpy.context.scene.get("re_camp_pose_review_status", "NOT RENDERED"),
        "pose_review_names": sorted(name for name in bpy.context.scene.get("re_camp_pose_review_names", "").split(",") if name),
        "skinning_preparation": "PASS" if armature and not skinning_errors else "FAIL",
        "errors": errors,
        "source_commit": bpy.context.scene.get("re_camp_source_commit", ""),
        "gate": bpy.context.scene.get("re_camp_gate", "Gate B preflight only"),
    }
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
