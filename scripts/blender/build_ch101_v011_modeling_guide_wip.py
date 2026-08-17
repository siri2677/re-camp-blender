#!/usr/bin/env python3
"""Create the CH101 v011 manual modeling handoff scene.

The scene combines the approved-in-principle 2D WIP anchor, a real MPFB body
shown as a non-rendering wire reference, and the CH101 rig/socket template.
It is intentionally a modeling guide, not a finished character asset.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_modeling_guide_wip import (  # noqa: E402
    collection,
    create_guides,
    empty,
    image_reference,
    move_to,
    clear_scene,
)
from build_ch101_mpfb_base_wip import normalize_body  # noqa: E402
from build_ch101_rig_template_wip import build_armature, create_actions, socket  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--turnaround")
    parser.add_argument("--readability")
    return parser.parse_args(raw)


def add_camera() -> bpy.types.Object:
    bpy.ops.object.camera_add(location=(0.45, -6.8, 2.25))
    camera = bpy.context.object
    camera.name = "CH101_V011_ModelingGuide_Camera"
    camera.data.lens = 60
    direction = Vector((0.0, 0.0, 1.95)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return camera


def main() -> None:
    options = parse_args()
    out = Path(options.output_dir).resolve()
    reference = Path(options.reference).resolve()
    base_obj = Path(options.base_obj).resolve()
    anchor_tag = "v012" if "v012" in reference.name.lower() else "v011"
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear_scene()

    refs = collection("REF_CH101_V011")
    body_collection = collection("MODEL_HIGH_BODY")
    cloth = collection("MODEL_CLOTH_OUTFIT")
    hair = collection("MODEL_HAIR")
    equipment = collection("MODEL_EQUIPMENT")
    rig_collection = collection("TECH_RIG_TEMPLATE")
    socket_collection = collection("TECH_SOCKETS_TEMPLATE")
    animation_collection = collection("TECH_ANIMATION_TEMPLATE")
    export = collection("EXPORT_READY_AFTER_GATE_B")

    reference_obj = image_reference(reference, refs, "REF_CH101_A_FaceBustStyleAnchor_WIP_v011", 4.0)
    reference_obj.location = (-1.35, 0.28, 2.72)
    reference_obj.rotation_euler = (math.radians(90.0), 0.0, math.radians(90.0))
    if options.turnaround:
        candidate = Path(options.turnaround).resolve()
        if candidate.exists():
            image_reference(candidate, refs, "REF_CH101_A_CanonicalTurnaround_v005", 3.2)
    if options.readability:
        candidate = Path(options.readability).resolve()
        if candidate.exists():
            image_reference(candidate, refs, "REF_CH101_A_Readability_v010", 3.0)

    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(base_obj), use_split_groups=True, import_vertex_groups=True, validate_meshes=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    body = next((obj for obj in imported if obj.name == "body"), None)
    if body is None:
        raise RuntimeError("MPFB base.obj import did not expose the body group")
    normalize_body(body, target_height=3.65)
    body.name = "CH101_A_MPFBody_CC0_WireReference_WIP"
    move_to(body, body_collection)
    body.display_type = "WIRE"
    body.show_in_front = True
    body.hide_render = True
    body["status"] = "WIP / WIRE REFERENCE ONLY / NOT APPROVED"
    body["source"] = base_obj.name
    for obj in imported:
        if obj != body:
            obj.hide_render = True
            obj.hide_viewport = True

    guide_names = create_guides(body_collection)
    # Face/bust landmarks derived from v011.  These are review points only;
    # an artist replaces them with sculpt/retopo geometry.
    face_guides = {
        "Guide_Face_Eye_L": (-0.115, -0.39, 3.22),
        "Guide_Face_Eye_R": (0.115, -0.39, 3.22),
        "Guide_Face_Hairline": (0.0, -0.10, 3.50),
        "Guide_Face_Chin": (0.0, -0.16, 3.00),
        "Guide_Hair_PonytailRoot": (0.28, 0.10, 3.52),
        "Guide_Jacket_Collar_L": (-0.28, -0.31, 2.48),
        "Guide_Jacket_Collar_R": (0.28, -0.31, 2.48),
        "Guide_CropTop_Center": (0.0, -0.34, 2.08),
    }
    for name, location in face_guides.items():
        point = empty(name, location, body_collection, 0.055)
        point["status"] = "v011 construction guide"
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
    camera = add_camera()
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_variant"] = "A / canonical"
    scene["re_camp_status"] = f"WIP / {anchor_tag.upper()} MODELING GUIDE / NOT APPROVED"
    scene["re_camp_reference"] = reference.name
    scene["re_camp_source_body"] = base_obj.name
    scene["re_camp_target_heads"] = "5.3-5.4"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    for target, purpose in (
        (cloth, "manual high-resolution jacket, crop top, shorts, straps and boots"),
        (hair, "manual scalp, bangs, side locks and ponytail masses from v011"),
        (equipment, "manual saber, ribbons, pouches and signal module"),
        (export, "only populated after Gate A/B visual and technical approval"),
    ):
        target["purpose"] = purpose
        target["status"] = "EMPTY / WAITING FOR MANUAL HIGH-RES MESH"
    blend = out / f"CH101_A_{anchor_tag.upper()}_ModelingGuide_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "character": "CH101-A",
        "status": f"WIP / {anchor_tag.upper()} MODELING GUIDE / NOT APPROVED",
        "reference": str(reference),
        "base_obj": str(base_obj),
        "blend": str(blend),
        "body": {"name": body.name, "display_type": body.display_type, "status": body["status"]},
        "guide_points": guide_names + sorted(face_guides),
        "sockets": sorted(sockets),
        "actions": actions,
        "empty_production_collections": ["MODEL_CLOTH_OUTFIT", "MODEL_HAIR", "MODEL_EQUIPMENT", "EXPORT_READY_AFTER_GATE_B"],
        "gate_a": "PENDING",
        "gate_b": "BLOCKED",
        "notes": ["v011 is the current 2D style anchor", "MPFB body is wire reference only", "Manual high-resolution mesh required", "No Unity import"]
    }
    (out / "reports" / f"CH101_A_{anchor_tag.upper()}_ModelingGuide_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print(f"Status: WIP / {anchor_tag} modeling guide / not approved")


if __name__ == "__main__":
    main()
