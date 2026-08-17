#!/usr/bin/env python3
"""Create a CH101-A rig/socket template without pretending a mesh is complete."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(raw)


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection" and collection.users == 0:
            bpy.data.collections.remove(collection)


def collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def build_armature(target: bpy.types.Collection) -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "CH101_A_RigTemplate_WIP"
    armature.data.name = "CH101_A_RigTemplate_Armature"
    move_to_collection(armature, target)
    edit = armature.data.edit_bones
    for bone in list(edit):
        edit.remove(bone)

    specs = {
        "Root": (0.0, 0.0, 0.0, None),
        "Hips": (0.0, 0.0, 1.28, "Root"),
        "Spine": (0.0, 0.0, 1.65, "Hips"),
        "Chest": (0.0, 0.0, 2.05, "Spine"),
        "Neck": (0.0, 0.0, 2.42, "Chest"),
        "Head": (0.0, 0.0, 2.72, "Neck"),
        "LeftShoulder": (-0.18, 0.0, 2.20, "Chest"),
        "LeftUpperArm": (-0.34, 0.0, 2.16, "LeftShoulder"),
        "LeftLowerArm": (-0.50, -0.02, 1.88, "LeftUpperArm"),
        "LeftHand": (-0.60, -0.05, 1.62, "LeftLowerArm"),
        "RightShoulder": (0.18, 0.0, 2.20, "Chest"),
        "RightUpperArm": (0.34, 0.0, 2.16, "RightShoulder"),
        "RightLowerArm": (0.50, -0.02, 1.88, "RightUpperArm"),
        "RightHand": (0.60, -0.05, 1.62, "RightLowerArm"),
        "LeftUpperLeg": (-0.17, 0.0, 1.28, "Hips"),
        "LeftLowerLeg": (-0.18, 0.0, 0.76, "LeftUpperLeg"),
        "LeftFoot": (-0.18, -0.06, 0.22, "LeftLowerLeg"),
        "LeftToes": (-0.18, -0.20, 0.08, "LeftFoot"),
        "RightUpperLeg": (0.17, 0.0, 1.28, "Hips"),
        "RightLowerLeg": (0.18, 0.0, 0.76, "RightUpperLeg"),
        "RightFoot": (0.18, -0.06, 0.22, "RightLowerLeg"),
        "RightToes": (0.18, -0.20, 0.08, "RightFoot"),
    }
    bones: dict[str, bpy.types.EditBone] = {}
    for name, (x, y, z, parent_name) in specs.items():
        bone = edit.new(name)
        bone.head = (x, y, z)
        bone.tail = (x, y, z + (0.18 if name not in {"Root", "Head", "LeftToes", "RightToes"} else 0.10))
        if parent_name:
            bone.parent = bones[parent_name]
            bone.use_connect = name not in {"LeftShoulder", "RightShoulder", "LeftUpperLeg", "RightUpperLeg"}
        bones[name] = bone
    bpy.ops.object.mode_set(mode="POSE")
    armature.show_in_front = True
    armature.data.display_type = "BBONE"
    armature["status"] = "WIP / RIG TEMPLATE / NO MESH"
    armature["character"] = "CH101-A Route Sprint"
    armature["gate"] = "Gate B blocked until visual mesh approval"
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def move_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def socket(name: str, bone: str, location: tuple[float, float, float], armature: bpy.types.Object, target: bpy.types.Collection) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.12
    obj.location = location
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj["status"] = "socket template"
    target.objects.link(obj)
    return obj


def create_actions(armature: bpy.types.Object) -> list[str]:
    names = ["CH101_Idle", "CH101_Run", "CH101_Attack", "CH101_A_Pose_Check"]
    for name in names:
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        action["status"] = "TEMPLATE / NO KEYED MESH PROOF"
        action["character"] = "CH101-A"
        action_slot = action.slots.new("OBJECT", armature.name)
    return names


def main() -> None:
    options = parse_args()
    out = Path(options.output_dir).resolve()
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    rig_collection = collection("TECH_RIG_TEMPLATE")
    socket_collection = collection("TECH_SOCKETS_TEMPLATE")
    animation_collection = collection("TECH_ANIMATION_TEMPLATE")
    armature = build_armature(rig_collection)
    sockets = {
        "Socket_Weapon_R": (0.60, -0.08, 1.62, "RightHand"),
        "Socket_Ribbon_L": (-0.38, 0.0, 2.30, "Chest"),
        "Socket_Ribbon_R": (0.38, 0.0, 2.30, "Chest"),
        "Socket_Pouch_L": (-0.30, -0.16, 1.70, "Hips"),
        "Socket_Pouch_R": (0.30, -0.16, 1.70, "Hips"),
        "Socket_Hair_Ponytail": (0.22, 0.05, 2.70, "Head"),
        "Socket_CameraFocus": (0.0, -0.02, 2.78, "Head"),
    }
    for name, (x, y, z, bone) in sockets.items():
        socket(name, bone, (x, y, z), armature, socket_collection)
    actions = create_actions(armature)
    animation_collection["actions"] = ",".join(actions)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / RIG TEMPLATE / NO MESH / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate B blocked / Gate C blocked"
    scene["re_camp_required_mesh"] = "High-resolution connected body and separate outfit/equipment meshes"
    blend = out / "CH101_A_RigTemplate_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "status": "WIP / RIG TEMPLATE / NO MESH / NOT APPROVED",
        "blend": str(blend),
        "armature": armature.name,
        "bone_count": len(armature.data.bones),
        "socket_names": sorted(sockets),
        "actions": actions,
        "mesh_objects": 0,
        "gate_b": "BLOCKED",
        "gate_c": "BLOCKED",
        "notes": ["Template only", "No weights or deformation proof", "Human Gate A and real mesh required"],
    }
    (out / "reports" / "CH101_A_RigTemplate_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / rig template / no mesh / not approved")


if __name__ == "__main__":
    main()
