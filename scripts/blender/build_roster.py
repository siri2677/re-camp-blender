#!/usr/bin/env python3
"""Build the CH102-CH105 current-roster pre-Unity blockout package.

The builder intentionally stays at the same documentation-grade level as the
CH101 v007 blockout: approved 2D sheets drive recognizable silhouettes,
equipment cues, sockets, a shared humanoid-aligned rig, rigid blockout
weights, review actions, and validation metadata. It is not final modeling,
production skinning, Unity import proof, or Gate B approval.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bpy
from mathutils import Vector

from build_blockout import (
    SOCKETS,
    SOCKET_BONE_MAP,
    add_area_light,
    add_camera,
    add_cube,
    add_cylinder_between,
    add_curve,
    add_socket,
    add_torus,
    add_uv_sphere,
    clear_scene,
    configure_render,
    export_fbx,
    material,
    mesh_triangle_count,
    motion_clip_names,
    prepare_blockout_skinning,
    prepare_pre_unity_review,
    prepare_rig_and_motion,
    prepare_technical_asset,
)


ROSTER_PROFILES = {
    "CH102": {
        "name": "Mao",
        "palette": {
            "skin": (0.78, 0.51, 0.43, 1.0),
            "base": (0.075, 0.085, 0.14, 1.0),
            "light": (0.86, 0.88, 0.92, 1.0),
            "hair": (0.56, 0.49, 0.78, 1.0),
            "primary": (0.65, 0.56, 0.92, 1.0),
            "accent": (0.84, 0.72, 0.98, 1.0),
            "glow": (0.72, 0.86, 1.0, 1.0),
        },
        "hair_style": "bob",
        "art_direction": "silver-lavender hair / compact tactical silhouette / single folding mechanical bow",
        "features": ["silver-lavender hair", "folding mechanical bow", "lavender signal accents", "compact tactical jacket"],
    },
    "CH103": {
        "name": "Nozomi",
        "palette": {
            "skin": (0.79, 0.48, 0.39, 1.0),
            "base": (0.12, 0.10, 0.16, 1.0),
            "light": (0.95, 0.90, 0.82, 1.0),
            "hair": (0.78, 0.23, 0.18, 1.0),
            "primary": (0.94, 0.42, 0.25, 1.0),
            "accent": (1.0, 0.72, 0.42, 1.0),
            "glow": (1.0, 0.72, 0.46, 1.0),
        },
        "hair_style": "braid",
        "art_direction": "coral braid / rescue-ready light layers / orb baton and controlled veil panels",
        "features": ["coral braid", "orb baton", "controlled rescue veil", "warm rescue accents"],
    },
    "CH104": {
        "name": "Shion",
        "palette": {
            "skin": (0.73, 0.43, 0.37, 1.0),
            "base": (0.045, 0.05, 0.12, 1.0),
            "light": (0.80, 0.84, 0.94, 1.0),
            "hair": (0.12, 0.10, 0.28, 1.0),
            "primary": (0.28, 0.24, 0.72, 1.0),
            "accent": (0.42, 0.72, 1.0, 1.0),
            "glow": (0.56, 0.78, 1.0, 1.0),
        },
        "hair_style": "long",
        "art_direction": "indigo vertical read / prism fan / one map ring",
        "features": ["indigo vertical read", "prism fan", "map ring", "cool navigation accents"],
    },
    "CH105": {
        "name": "Akari",
        "palette": {
            "skin": (0.76, 0.46, 0.39, 1.0),
            "base": (0.025, 0.045, 0.065, 1.0),
            "light": (0.74, 0.84, 0.86, 1.0),
            "hair": (0.018, 0.025, 0.035, 1.0),
            "primary": (0.02, 0.46, 0.50, 1.0),
            "accent": (0.20, 0.84, 0.78, 1.0),
            "glow": (0.35, 1.0, 0.88, 1.0),
        },
        "hair_style": "short",
        "art_direction": "black/teal hair / paired gauntlets / one anchor ring",
        "features": ["black-teal hair", "paired gauntlets", "anchor ring", "dense close-combat silhouette"],
    },
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", choices=sorted(ROSTER_PROFILES), required=True)
    parser.add_argument("--source-asset", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--export-fbx", action="store_true")
    return parser.parse_args(script_args)


def make_materials(character: str, profile: dict[str, object]) -> dict[str, bpy.types.Material]:
    palette = profile["palette"]
    return {
        key: material(f"MAT_{character}_{key.title()}", color, metallic=0.35 if key in {"primary", "accent"} else 0.0, roughness=0.48 if key in {"primary", "accent", "glow"} else 0.65)
        for key, color in palette.items()
    }


def parent_all(root: bpy.types.Object, objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        obj.parent = root


def add_common_body(root: bpy.types.Object, mats: dict[str, bpy.types.Material], profile: dict[str, object]) -> None:
    torso = add_cylinder_between("Body_Torso", (0, 0, 1.62), (0, 0, 2.42), 0.30, mats["base"])
    pelvis = add_uv_sphere("Body_Pelvis", (0, 0, 1.35), (0.37, 0.27, 0.23), mats["base"])
    neck = add_cylinder_between("Body_Neck", (0, 0, 2.40), (0, 0, 2.58), 0.13, mats["skin"])
    head = add_uv_sphere("Body_Head", (0, -0.01, 2.93), (0.36, 0.32, 0.43), mats["skin"])
    parent_all(root, [torso, pelvis, neck, head])

    panels = [
        ("Outfit_Chest_L", (-0.23, -0.27, 2.22), (0.12, 0.055, 0.29), mats["light"]),
        ("Outfit_Chest_R", (0.23, -0.27, 2.22), (0.12, 0.055, 0.29), mats["light"]),
        ("Outfit_Shoulder_L", (-0.34, -0.02, 2.38), (0.13, 0.15, 0.10), mats["light"]),
        ("Outfit_Shoulder_R", (0.34, -0.02, 2.38), (0.13, 0.15, 0.10), mats["light"]),
        ("Outfit_BackPanel", (0, 0.25, 2.22), (0.28, 0.05, 0.28), mats["base"]),
    ]
    parent_all(root, [add_cube(name, location, scale, mat, bevel=0.035) for name, location, scale, mat in panels])
    parent_all(root, [
        add_cube("Outfit_CenterAccent", (0, -0.335, 2.22), (0.018, 0.018, 0.27), mats["accent"], bevel=0.01),
        add_cube("Outfit_HemAccent", (0, -0.30, 1.94), (0.25, 0.045, 0.035), mats["primary"], bevel=0.015),
        add_cube("Outfit_BeltAccent", (0, -0.275, 1.49), (0.30, 0.018, 0.025), mats["primary"], bevel=0.008),
    ])

    arms = [
        ("L", -1, (-0.31, 0, 2.31), (-0.64, -0.01, 1.99), (-0.80, -0.07, 1.72)),
        ("R", 1, (0.31, 0, 2.31), (0.64, -0.01, 1.99), (0.80, -0.07, 1.72)),
    ]
    for side, sign, shoulder, elbow, wrist in arms:
        upper = add_cylinder_between(f"Sleeve_{side}_Upper", shoulder, elbow, 0.115, mats["base"])
        lower = add_cylinder_between(f"Sleeve_{side}_Lower", elbow, wrist, 0.095, mats["base"])
        cuff = add_cube(f"Cuff_{side}", wrist, (0.11, 0.12, 0.08), mats["light"], bevel=0.03)
        hand = add_uv_sphere(f"Hand_{side}", (wrist[0] + 0.01 * sign, wrist[1] - 0.01, wrist[2] - 0.10), (0.09, 0.08, 0.11), mats["skin"])
        piping = add_cylinder_between(f"Sleeve_{side}_Accent", shoulder, elbow, 0.018, mats["primary"])
        parent_all(root, [upper, lower, cuff, hand, piping])

    parent_all(root, [add_cube("Shorts_Waistband", (0, -0.02, 1.48), (0.34, 0.25, 0.10), mats["base"], bevel=0.04)])
    for side, x in (("L", -0.20), ("R", 0.20)):
        shorts = add_cube(f"Shorts_{side}_Leg", (x, -0.04, 1.28), (0.16, 0.22, 0.17), mats["base"], bevel=0.04)
        thigh = add_cylinder_between(f"Leg_{side}_Upper", (x, 0, 1.14), (x * 1.12, 0, 0.70), 0.12, mats["skin"])
        shin = add_cylinder_between(f"Leg_{side}_Lower", (x * 1.12, 0, 0.70), (x * 1.18, -0.04, 0.43), 0.10, mats["skin"])
        knee = add_cube(f"KneeGuard_{side}", (x * 1.12, -0.14, 0.64), (0.115, 0.07, 0.08), mats["primary"], bevel=0.025)
        boot = add_cube(f"Boot_{side}", (x * 1.18, -0.13, 0.17), (0.20, 0.28, 0.16), mats["light"], bevel=0.05)
        sole = add_cube(f"Boot_{side}_Sole", (x * 1.18, -0.18, 0.035), (0.22, 0.30, 0.035), mats["accent"], bevel=0.02)
        parent_all(root, [shorts, thigh, shin, knee, boot, sole])

    style = profile["hair_style"]
    hair_main = add_uv_sphere("Hair_Main", (0, 0.08, 3.10), (0.42, 0.36, 0.36), mats["hair"])
    parent_all(root, [hair_main])
    if style == "bob":
        parts = [
            add_uv_sphere("Hair_Bob_L", (-0.28, -0.03, 2.90), (0.18, 0.18, 0.40), mats["hair"]),
            add_uv_sphere("Hair_Bob_R", (0.28, -0.03, 2.90), (0.18, 0.18, 0.40), mats["hair"]),
        ]
    elif style == "braid":
        parts = [
            add_uv_sphere("Hair_Braid_1", (0.24, 0.10, 2.92), (0.16, 0.15, 0.22), mats["hair"]),
            add_uv_sphere("Hair_Braid_2", (0.34, 0.10, 2.68), (0.14, 0.13, 0.20), mats["hair"]),
            add_uv_sphere("Hair_Braid_3", (0.28, 0.08, 2.45), (0.12, 0.11, 0.18), mats["primary"]),
        ]
    elif style == "long":
        parts = [
            add_uv_sphere("Hair_Long_L", (-0.28, 0.08, 2.82), (0.18, 0.16, 0.52), mats["hair"]),
            add_uv_sphere("Hair_Long_R", (0.28, 0.08, 2.82), (0.18, 0.16, 0.52), mats["hair"]),
            add_curve("Hair_Long_Lock", [(0.28, 0.10, 3.10), (0.52, 0.12, 2.72), (0.42, 0.08, 2.30)], 0.045, mats["primary"]),
        ]
    else:
        parts = [
            add_uv_sphere("Hair_Short_L", (-0.30, 0.02, 3.00), (0.18, 0.16, 0.30), mats["hair"]),
            add_uv_sphere("Hair_Short_R", (0.30, 0.02, 3.00), (0.18, 0.16, 0.30), mats["hair"]),
            add_curve("Hair_Teal_Lock", [(0.28, 0.08, 3.10), (0.48, 0.08, 2.82), (0.38, 0.04, 2.62)], 0.04, mats["primary"]),
        ]
    parent_all(root, parts)

    bangs = [
        add_uv_sphere(f"Hair_Bang_{index}", (x, -0.28, z), (0.13, 0.08, 0.22), mats["hair"])
        for index, (x, z) in enumerate(((-0.18, 3.12), (0.0, 3.16), (0.18, 3.12)), start=1)
    ]
    eyes = [
        add_uv_sphere(f"Eye_{side}", (x, -0.315, 2.98), (0.035, 0.018, 0.055), mats["glow"])
        for side, x in (("L", -0.13), ("R", 0.13))
    ]
    face = [
        add_uv_sphere("Face_Chin", (0, -0.25, 2.78), (0.19, 0.08, 0.11), mats["skin"]),
        add_cube("Face_Mouth", (0, -0.337, 2.84), (0.055, 0.008, 0.012), mats["base"], bevel=0.006),
        add_cube("Face_Brow_L", (-0.13, -0.332, 3.08), (0.065, 0.008, 0.012), mats["hair"], bevel=0.006),
        add_cube("Face_Brow_R", (0.13, -0.332, 3.08), (0.065, 0.008, 0.012), mats["hair"], bevel=0.006),
    ]
    parent_all(root, bangs + eyes + face)


def add_equipment(root: bpy.types.Object, mats: dict[str, bpy.types.Material], character: str) -> None:
    x, y, z = SOCKETS["Socket_Equipment_Primary"]
    if character == "CH102":
        bow = [
            add_curve("Bow_Frame", [(x - 0.18, y, z + 0.55), (x + 0.16, y, z + 0.25), (x - 0.18, y, z - 0.25)], 0.045, mats["primary"]),
            add_curve("Bow_String", [(x - 0.18, y - 0.02, z + 0.55), (x + 0.03, y - 0.02, z), (x - 0.18, y - 0.02, z - 0.25)], 0.012, mats["accent"]),
            add_cube("Bow_Grip", (x + 0.03, y, z), (0.07, 0.05, 0.18), mats["base"], bevel=0.02),
            add_cube("Bow_FoldingJoint", (x + 0.05, y - 0.04, z + 0.27), (0.06, 0.035, 0.06), mats["glow"], bevel=0.015),
        ]
        parent_all(root, bow)
    elif character == "CH103":
        baton = add_cylinder_between("Baton_Handle", (x, y, z - 0.35), (x, y, z + 0.48), 0.055, mats["primary"])
        orb = add_uv_sphere("Baton_Orb", (x, y - 0.01, z + 0.64), (0.16, 0.16, 0.16), mats["glow"])
        orb_ring = add_torus("Baton_OrbRing", (x, y - 0.01, z + 0.64), 0.19, 0.025, mats["accent"], rotation=(math.pi / 2, 0, 0))
        veil = add_curve("Veil_ControlledPanel", [(-0.35, -0.33, 2.40), (-0.62, -0.35, 2.10), (-0.48, -0.30, 1.72), (-0.20, -0.27, 1.50)], 0.028, mats["accent"])
        parent_all(root, [baton, orb, orb_ring, veil])
    elif character == "CH104":
        fan_parts = []
        for index, angle in enumerate((-34, -17, 0, 17, 34), start=1):
            blade = add_cube(f"Fan_Prism_{index}", (x + 0.06 * index, y, z + 0.15), (0.035, 0.045, 0.34), mats["primary" if index % 2 else "accent"], bevel=0.018)
            blade.rotation_euler[1] = math.radians(angle)
            fan_parts.append(blade)
        ring = add_torus("MapRing", SOCKETS["Socket_AnchorRing_Carry"], 0.22, 0.035, mats["accent"], rotation=(math.pi / 2, 0, 0))
        parent_all(root, fan_parts + [ring])
    elif character == "CH105":
        left = add_cube("Gauntlet_L", SOCKETS["Socket_Gauntlet_L"], (0.16, 0.14, 0.20), mats["primary"], bevel=0.045)
        right = add_cube("Gauntlet_R", SOCKETS["Socket_Gauntlet_R"], (0.16, 0.14, 0.20), mats["primary"], bevel=0.045)
        left_core = add_cube("Gauntlet_Core_L", (-0.74, -0.17, 2.06), (0.06, 0.025, 0.08), mats["glow"], bevel=0.015)
        right_core = add_cube("Gauntlet_Core_R", (0.74, -0.17, 2.06), (0.06, 0.025, 0.08), mats["glow"], bevel=0.015)
        ring = add_torus("AnchorRing", SOCKETS["Socket_AnchorRing_Carry"], 0.25, 0.045, mats["accent"], rotation=(math.pi / 2, 0, 0))
        cable = add_curve("AnchorRing_Line", [(0.0, -0.52, 2.38), (0.28, -0.65, 2.05), (0.74, -0.20, 2.06)], 0.018, mats["glow"])
        parent_all(root, [left, right, left_core, right_core, ring, cable])


def roster_skinning_bone(name: str) -> str:
    if name.startswith(("Hair_", "Face_", "Eye_")) or name == "Body_Head":
        return "Head"
    if name == "Body_Neck":
        return "Neck"
    if name in {"Body_Pelvis", "Shorts_Waistband"}:
        return "Hips"
    if name == "Body_Torso" or name.startswith(("Outfit_", "Veil_", "AnchorRing", "MapRing")):
        return "Chest"
    if name.startswith(("Bow_", "Baton_", "Fan_", "Equipment_")):
        return "RightHand"
    if name.startswith(("Gauntlet_L", "Cuff_L", "Hand_L")):
        return "LeftHand"
    if name.startswith(("Gauntlet_R", "Cuff_R", "Hand_R")):
        return "RightHand"
    if name.startswith("Sleeve_L_Upper"):
        return "LeftUpperArm"
    if name.startswith("Sleeve_L_Lower"):
        return "LeftLowerArm"
    if name.startswith("Sleeve_R_Upper"):
        return "RightUpperArm"
    if name.startswith("Sleeve_R_Lower"):
        return "RightLowerArm"
    if name.startswith(("Shorts_L_", "Leg_L_")):
        return "LeftUpperLeg" if "Upper" in name or name.startswith("Shorts_") else "LeftLowerLeg"
    if name.startswith(("Shorts_R_", "Leg_R_")):
        return "RightUpperLeg" if "Upper" in name or name.startswith("Shorts_") else "RightLowerLeg"
    if name.startswith("KneeGuard_L"):
        return "LeftLowerLeg"
    if name.startswith("KneeGuard_R"):
        return "RightLowerLeg"
    if name.startswith("Boot_L"):
        return "LeftFoot"
    if name.startswith("Boot_R"):
        return "RightFoot"
    return "Hips"


def prepare_roster_skinning(root: bpy.types.Object, character: str) -> dict[str, object]:
    armature = bpy.data.objects.get(f"{character}_Rig_Armature")
    if armature is None:
        raise RuntimeError(f"{character}_Rig_Armature is required before skinning")
    weighted_meshes = 0
    assignment_counts: dict[str, int] = {}
    for obj in (item for item in bpy.context.scene.objects if item.type == "MESH"):
        bone_name = roster_skinning_bone(obj.name)
        group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        modifier_name = f"{character}_ArmatureDeform"
        modifier = obj.modifiers.get(modifier_name) or obj.modifiers.new(name=modifier_name, type="ARMATURE")
        modifier.object = armature
        obj["skinning_revision"] = "v007"
        obj["skinning_mode"] = "RIGID BLOCKOUT WEIGHT"
        obj["skinning_bone"] = bone_name
        weighted_meshes += 1
        assignment_counts[bone_name] = assignment_counts.get(bone_name, 0) + 1
    status = "RIGID BLOCKOUT WEIGHTS / DEFORMATION REVIEW"
    armature["skinning_revision"] = "v007"
    armature["skinning_status"] = status
    armature["deformation_status"] = "RIGID BLOCKOUT WEIGHTS / PROTOTYPE"
    armature["weighted_mesh_object_count"] = weighted_meshes
    root["skinning_prepared"] = True
    root["skinning_status"] = status
    root["deformation_status"] = "RIGID BLOCKOUT WEIGHTS / PROTOTYPE"
    root["weighted_mesh_object_count"] = weighted_meshes
    root["skinning_assignment_counts"] = json.dumps(assignment_counts, sort_keys=True)
    return {"weighted_mesh_object_count": weighted_meshes, "skinning_status": status, "assignment_counts": assignment_counts}


def build_scene(args: argparse.Namespace) -> tuple[bpy.types.Object, Path]:
    character = args.character
    profile = ROSTER_PROFILES[character]
    output_dir = Path(args.output_dir).resolve()
    clear_scene()
    mats = make_materials(character, profile)

    root = bpy.data.objects.new(f"{character}_Blockout_Root", None)
    root.empty_display_type = "PLAIN_AXES"
    root["character_id"] = character
    root["character_name"] = profile["name"]
    root["source_asset"] = args.source_asset
    root["source_commit"] = args.source_commit
    root["art_direction"] = profile["art_direction"]
    root["translation_proof_status"] = "2D APPROVED / 3D BLOCKOUT PROOF ONLY"
    root["blockout_revision"] = "v007"
    root["blockout_status"] = "DOCUMENTATION ONLY / NOT GATE B APPROVED"
    bpy.context.collection.objects.link(root)

    add_common_body(root, mats, profile)
    add_equipment(root, mats, character)
    for socket_name, location in SOCKETS.items():
        add_socket(socket_name, location, root)

    scene = bpy.context.scene
    configure_render(scene, output_dir / "renders")
    add_area_light("Key_Light", (4.5, -6.0, 7.0), Vector((0, 0, 1.9)), 850.0, (1.0, 0.92, 0.82), 5.0)
    add_area_light("Fill_Light", (-4.0, -3.0, 4.0), Vector((0, 0, 1.8)), 500.0, (0.55, 0.75, 1.0), 4.0)
    add_area_light("Back_Light", (0.0, 4.0, 5.5), Vector((0, 0, 2.2)), 700.0, (0.15, 0.75, 0.95), 3.5)
    scene["re_camp_gate"] = "Gate B preflight only"
    scene["re_camp_source_commit"] = args.source_commit
    scene["re_camp_source_asset"] = args.source_asset
    scene["re_camp_technical_proof"] = "NOT TESTED"
    technical_stats = prepare_technical_asset(root)
    rig_stats = prepare_rig_and_motion(root, character)
    skinning_stats = prepare_roster_skinning(root, character)
    pre_unity_stats = prepare_pre_unity_review(root, character)
    scene["re_camp_blockout_revision"] = "v007"
    scene["re_camp_uv_status"] = "PASS" if technical_stats["uv_missing_after_prepare"] == 0 else "FAIL"
    scene["re_camp_lod_status"] = pre_unity_stats["lod_status"]
    scene["re_camp_lod_object_counts"] = json.dumps({key: value["object_count"] for key, value in pre_unity_stats["lod_stats"].items()}, sort_keys=True)
    scene["re_camp_lod_triangle_counts"] = json.dumps({key: value["triangle_count"] for key, value in pre_unity_stats["lod_stats"].items()}, sort_keys=True)
    scene["re_camp_collider_status"] = pre_unity_stats["collider_status"]
    scene["re_camp_collider_names"] = ",".join(pre_unity_stats["collider_names"])
    scene["re_camp_face_blendshape_status"] = pre_unity_stats["face_blendshape_status"]
    scene["re_camp_face_blendshape_names"] = ",".join(pre_unity_stats["face_blendshape_names"])
    scene["re_camp_rig_status"] = "PROTOTYPE / RIGID BLOCKOUT WEIGHTS"
    scene["re_camp_deformation_status"] = skinning_stats["skinning_status"]
    scene["re_camp_motion_status"] = "IDLE RUN ATTACK REVIEW CLIPS"
    scene["re_camp_armature_name"] = rig_stats["armature_name"]
    scene["re_camp_bone_count"] = rig_stats["bone_count"]
    scene["re_camp_skinning_status"] = skinning_stats["skinning_status"]
    scene["re_camp_weighted_mesh_count"] = skinning_stats["weighted_mesh_object_count"]
    scene["re_camp_pose_review_status"] = "PENDING RENDER"

    blend_path = output_dir / f"{character}_Blockout_REVIEW_v007.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    return root, blend_path


def render_pose_previews(output_dir: Path, character: str) -> None:
    scene = bpy.context.scene
    armature = bpy.data.objects.get(f"{character}_Rig_Armature")
    if armature is None:
        raise RuntimeError(f"{character}_Rig_Armature is required for pose previews")
    clips = motion_clip_names(character)
    pose_frames = {clips["A_Pose_Check"]: 1, clips["Idle"]: 24, clips["Run"]: 12, clips["Attack"]: 16}
    camera = add_camera("RenderCamera_pose_review", (0, -11.4, 2.15), Vector((0, 0, 1.85)))
    scene.camera = camera
    pose_dir = output_dir / "renders" / "poses"
    pose_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []
    for action_name, frame in pose_frames.items():
        action = bpy.data.actions.get(action_name)
        if action is None:
            continue
        armature.animation_data.action = action
        scene.frame_set(frame)
        scene.render.filepath = str(pose_dir / f"{action_name}.png")
        bpy.ops.render.render(write_still=True)
        rendered.append(action_name)
    armature.animation_data.action = bpy.data.actions.get(clips["Idle"])
    scene.frame_set(1)
    scene["re_camp_pose_review_status"] = "PASS" if len(rendered) == len(pose_frames) else "PARTIAL"
    scene["re_camp_pose_review_names"] = ",".join(rendered)


def render_views(output_dir: Path) -> None:
    scene = bpy.context.scene
    camera = add_camera("RenderCamera_front", (0, -11.4, 2.15), Vector((0, 0, 1.85)))
    scene.camera = camera
    for view, location in {"front": (0, -11.4, 2.15), "side": (11.4, 0, 2.15), "back": (0, 11.4, 2.15)}.items():
        camera.location = location
        camera.rotation_euler = (Vector((0, 0, 1.85)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output_dir / "renders" / f"{view}.png")
        bpy.ops.render.render(write_still=True)


def write_report(output_dir: Path, args: argparse.Namespace, blend_path: Path, fbx_path: Path | None) -> None:
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.get("lod_level")]
    lod_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.get("lod_level")]
    lod_triangle_counts = {
        level: sum(mesh_triangle_count(obj.data) for obj in lod_meshes if obj.get("lod_level") == level)
        for level in sorted({str(obj.get("lod_level")) for obj in lod_meshes})
    }
    head = bpy.data.objects.get("Body_Head")
    report = {
        "character": args.character,
        "character_name": ROSTER_PROFILES[args.character]["name"],
        "revision": "v007",
        "source_asset": args.source_asset,
        "source_commit": args.source_commit,
        "status": "DOCUMENTATION ONLY / NOT GATE B APPROVED",
        "translation_proof_status": "2D APPROVED / 3D BLOCKOUT PROOF ONLY",
        "technical_proof": "NOT TESTED",
        "blend": str(blend_path),
        "fbx": str(fbx_path) if fbx_path else None,
        "mesh_object_count": len(meshes),
        "object_count": len(bpy.data.objects),
        "triangle_count": sum(mesh_triangle_count(obj.data) for obj in meshes),
        "uv_missing": sorted(obj.name for obj in meshes if not obj.data.uv_layers),
        "materialless_meshes": sorted(obj.name for obj in meshes if not obj.data.materials),
        "lod_status": bpy.context.scene.get("re_camp_lod_status", "NOT SET"),
        "lod_mesh_object_count": len(lod_meshes),
        "lod_triangle_counts": lod_triangle_counts,
        "armature_name": bpy.context.scene.get("re_camp_armature_name", ""),
        "bone_count": bpy.context.scene.get("re_camp_bone_count", 0),
        "rig_status": bpy.context.scene.get("re_camp_rig_status", "NOT SET"),
        "deformation_status": bpy.context.scene.get("re_camp_deformation_status", "NOT SET"),
        "skinning_status": bpy.context.scene.get("re_camp_skinning_status", "NOT SET"),
        "weighted_mesh_object_count": bpy.context.scene.get("re_camp_weighted_mesh_count", 0),
        "pose_review_status": bpy.context.scene.get("re_camp_pose_review_status", "NOT RENDERED"),
        "pose_review_names": sorted(name for name in bpy.context.scene.get("re_camp_pose_review_names", "").split(",") if name),
        "motion_status": bpy.context.scene.get("re_camp_motion_status", "NOT SET"),
        "motion_clips": sorted(action.name for action in bpy.data.actions if action.name.startswith(f"{args.character}_")),
        "socket_bone_map": SOCKET_BONE_MAP,
        "socket_names": sorted(name for name in SOCKETS if bpy.data.objects.get(name)),
        "collider_names": sorted(name for name in ("Collider_Hips", "Collider_Chest", "Collider_Head", "Collider_LeftHand", "Collider_RightHand", "Collider_LeftFoot", "Collider_RightFoot") if bpy.data.objects.get(name)),
        "collider_status": bpy.context.scene.get("re_camp_collider_status", "NOT SET"),
        "face_blendshape_names": sorted(key.name for key in head.data.shape_keys.key_blocks if key.name != "Basis") if head and head.data.shape_keys else [],
        "face_blendshape_status": bpy.context.scene.get("re_camp_face_blendshape_status", "NOT SET"),
        "material_names": sorted(mat.name for mat in bpy.data.materials if mat.name.startswith(f"MAT_{args.character}_")),
        "art_direction": ROSTER_PROFILES[args.character]["art_direction"],
        "art_features": ROSTER_PROFILES[args.character]["features"],
        "render_views": ["front", "side", "back"] if args.render else [],
    }
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{args.character}_Blockout_REVIEW_v007.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    _, blend_path = build_scene(args)
    if args.render:
        render_views(output_dir)
        render_pose_previews(output_dir, args.character)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    fbx_path = export_fbx(output_dir, args.character) if args.export_fbx else None
    write_report(output_dir, args, blend_path, fbx_path)
    print(f"Roster blockout generated: {blend_path}")
    print("Revision: v007 / current roster pre-Unity proof")
    print("Status: documentation-only / Gate B not approved / Unity proof pending")


if __name__ == "__main__":
    main()
