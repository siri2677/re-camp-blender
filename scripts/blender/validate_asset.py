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

REQUIRED_COLLIDERS = {
    "Collider_Hips",
    "Collider_Chest",
    "Collider_Head",
    "Collider_LeftHand",
    "Collider_RightHand",
    "Collider_LeftFoot",
    "Collider_RightFoot",
}

COLLIDER_BONE_MAP = {
    "Collider_Hips": "Hips",
    "Collider_Chest": "Chest",
    "Collider_Head": "Head",
    "Collider_LeftHand": "LeftHand",
    "Collider_RightHand": "RightHand",
    "Collider_LeftFoot": "LeftFoot",
    "Collider_RightFoot": "RightFoot",
}

FACE_BLENDSHAPE_NAMES = {
    "Blink_L",
    "Blink_R",
    "Viseme_A",
    "Viseme_I",
    "Viseme_U",
    "Viseme_E",
    "Viseme_O",
    "Face_Smile",
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
    missing_colliders = sorted(REQUIRED_COLLIDERS - names)
    root = next((obj for obj in objects if obj.name.endswith("_Blockout_Root")), None)
    all_meshes = [obj for obj in objects if obj.type == "MESH"]
    meshes = [obj for obj in all_meshes if not obj.get("lod_level")]
    lod_meshes = [obj for obj in all_meshes if obj.get("lod_level")]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    armature = next((obj for obj in armatures if obj.name == armature_name), None)
    errors: list[str] = []
    if missing:
        errors.append(f"missing sockets: {', '.join(missing)}")
    if missing_colliders:
        errors.append(f"missing colliders: {', '.join(missing_colliders)}")
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

    collider_bone_errors = []
    for collider_name, bone_name in COLLIDER_BONE_MAP.items():
        collider = bpy.data.objects.get(collider_name)
        if collider is None or collider.type != "EMPTY" or collider.parent != armature or collider.parent_type != "BONE" or collider.parent_bone != bone_name:
            collider_bone_errors.append(f"{collider_name}->{bone_name}")
    if collider_bone_errors:
        errors.append(f"collider bone parenting mismatch: {', '.join(collider_bone_errors)}")

    head = bpy.data.objects.get("Body_Head")
    face_blendshape_names = sorted(
        key.name for key in head.data.shape_keys.key_blocks
        if key.name != "Basis"
    ) if head and head.type == "MESH" and head.data.shape_keys else []
    missing_face_blendshapes = sorted(FACE_BLENDSHAPE_NAMES - set(face_blendshape_names))
    if missing_face_blendshapes:
        errors.append(f"missing face blendshape targets: {', '.join(missing_face_blendshapes)}")

    lod_levels = sorted({str(obj.get("lod_level")) for obj in lod_meshes})
    missing_lod_levels = sorted({"LOD1", "LOD2"} - set(lod_levels))
    if missing_lod_levels:
        errors.append(f"missing LOD proxies: {', '.join(missing_lod_levels)}")

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
        for obj in all_meshes:
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
    lod_uv_missing = sorted(obj.name for obj in lod_meshes if not obj.data.uv_layers)
    lod_materialless_meshes = sorted(obj.name for obj in lod_meshes if not obj.data.materials)
    triangle_count = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangle_count += len(obj.data.loop_triangles)
    if uv_missing:
        errors.append(f"missing UV maps: {', '.join(uv_missing)}")
    if materialless_meshes:
        errors.append(f"missing material slots: {', '.join(materialless_meshes)}")
    if lod_uv_missing:
        errors.append(f"missing LOD UV maps: {', '.join(lod_uv_missing)}")
    if lod_materialless_meshes:
        errors.append(f"missing LOD material slots: {', '.join(lod_materialless_meshes)}")
    lod_triangle_counts = {}
    for level in lod_levels:
        lod_triangle_counts[level] = sum(
            len(obj.data.loop_triangles)
            for obj in lod_meshes
            if obj.get("lod_level") == level
        )

    report = {
        "character": args.character,
        "blend": str(Path(args.blend).resolve()),
        "status": "PASS" if not errors else "FAIL",
        "technical_proof": "NOT TESTED",
        "revision": bpy.context.scene.get("re_camp_blockout_revision", ""),
        "mesh_object_count": len(meshes),
        "lod_mesh_object_count": len(lod_meshes),
        "triangle_count": triangle_count,
        "socket_count": len(REQUIRED_SOCKETS - set(missing)),
        "missing": missing,
        "uv_missing": uv_missing,
        "materialless_meshes": materialless_meshes,
        "lod_levels": lod_levels,
        "lod_triangle_counts": lod_triangle_counts,
        "lod_uv_missing": lod_uv_missing,
        "lod_materialless_meshes": lod_materialless_meshes,
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
        "collider_count": len(REQUIRED_COLLIDERS - set(missing_colliders)),
        "missing_colliders": missing_colliders,
        "collider_bone_map": COLLIDER_BONE_MAP,
        "collider_bone_errors": collider_bone_errors,
        "collider_status": bpy.context.scene.get("re_camp_collider_status", "NOT SET"),
        "face_blendshape_names": face_blendshape_names,
        "missing_face_blendshapes": missing_face_blendshapes,
        "face_blendshape_status": bpy.context.scene.get("re_camp_face_blendshape_status", "NOT SET"),
        "rig_status": bpy.context.scene.get("re_camp_rig_status", "NOT SET"),
        "deformation_status": bpy.context.scene.get("re_camp_deformation_status", "NOT SET"),
        "motion_status": bpy.context.scene.get("re_camp_motion_status", "NOT SET"),
        "rig_preparation": "PASS" if armature and not missing_rig_bones and not missing_motion_clips and not socket_bone_errors and not collider_bone_errors else "FAIL",
        "weighted_mesh_object_count": len(weighted_meshes),
        "skinning_errors": skinning_errors,
        "skinning_status": bpy.context.scene.get("re_camp_skinning_status", "NOT SET"),
        "pose_review_status": bpy.context.scene.get("re_camp_pose_review_status", "NOT RENDERED"),
        "pose_review_names": sorted(name for name in bpy.context.scene.get("re_camp_pose_review_names", "").split(",") if name),
        "skinning_preparation": "PASS" if armature and not skinning_errors else "FAIL",
        "lod_preparation": "PASS" if not missing_lod_levels and not lod_uv_missing and not lod_materialless_meshes else "FAIL",
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
