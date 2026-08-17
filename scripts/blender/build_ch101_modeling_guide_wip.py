#!/usr/bin/env python3
"""Build a CH101-A manual modeling guide scene.

This file deliberately creates references and named construction guides, not a
fake finished character.  It is the handoff scene for the high-resolution base
mesh stage after the primitive run was rejected.
"""

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
    parser.add_argument("--reference", required=True)
    parser.add_argument("--expression")
    parser.add_argument("--equipment")
    parser.add_argument("--poses")
    parser.add_argument("--neutral-body")
    return parser.parse_args(raw)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection" and collection.users == 0:
            bpy.data.collections.remove(collection)


def collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.get(name)
    if result is None:
        result = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(result)
    return result


def move_to(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    target.objects.link(obj)


def empty(name: str, location: tuple[float, float, float], target: bpy.types.Collection, size: float = 0.08) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = size
    obj.location = location
    target.objects.link(obj)
    return obj


def image_reference(path: Path, target: bpy.types.Collection, name: str, size: float) -> bpy.types.Object:
    image = bpy.data.images.load(str(path), check_existing=True)
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    obj.empty_display_size = size
    obj.color[3] = 0.9
    obj.hide_render = True
    obj["status"] = "WIP / REFERENCE ONLY / NOT APPROVED"
    obj["source"] = path.name
    target.objects.link(obj)
    return obj


def create_guides(target: bpy.types.Collection) -> list[str]:
    # Guide points use the same local scale as the future model scene.  They
    # are intentionally empties so an artist can replace them with sculpt,
    # retopo and clothing meshes without deleting a placeholder blockout.
    points = {
        "Guide_Head_Center": (0.0, 0.0, 3.25),
        "Guide_Neck": (0.0, 0.0, 2.55),
        "Guide_Shoulder_L": (-0.32, 0.0, 2.35),
        "Guide_Shoulder_R": (0.32, 0.0, 2.35),
        "Guide_Bust_Center": (0.0, -0.16, 2.12),
        "Guide_Waist": (0.0, 0.0, 1.90),
        "Guide_Hip": (0.0, 0.0, 1.48),
        "Guide_Knee_L": (-0.18, 0.0, 0.92),
        "Guide_Knee_R": (0.18, 0.0, 0.92),
        "Guide_Ankle_L": (-0.18, 0.0, 0.20),
        "Guide_Ankle_R": (0.18, 0.0, 0.20),
    }
    for name, location in points.items():
        obj = empty(name, location, target, 0.07)
        obj["status"] = "construction guide"
    return list(points)


def create_sockets(target: bpy.types.Collection) -> list[str]:
    sockets = {
        "Socket_Weapon_R": (0.68, -0.24, 1.82),
        "Socket_Ribbon_L": (-0.42, 0.0, 2.65),
        "Socket_Ribbon_R": (0.42, 0.0, 2.65),
        "Socket_Pouch_L": (-0.32, -0.22, 1.92),
        "Socket_Pouch_R": (0.32, -0.22, 1.92),
        "Socket_Hair_Ponytail": (0.26, 0.10, 3.20),
    }
    for name, location in sockets.items():
        obj = empty(name, location, target, 0.10)
        obj["status"] = "export socket guide"
    return list(sockets)


def main() -> None:
    options = parse_args()
    out = Path(options.output_dir).resolve()
    reference = Path(options.reference).resolve()
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear_scene()

    refs = collection("REF_CH101_A")
    body = collection("MODEL_HIGH_BODY")
    cloth = collection("MODEL_CLOTH_OUTFIT")
    hair = collection("MODEL_HAIR")
    equipment = collection("MODEL_EQUIPMENT")
    tech = collection("TECH_RIG_SOCKETS")
    export = collection("EXPORT_READY_AFTER_GATE_B")

    image_reference(reference, refs, "REF_CH101_A_Canonical_Turnaround_v005", 6.0)
    optional_refs = (
        (options.expression, "REF_CH101_A_ExpressionSheet_v006", 3.6),
        (options.equipment, "REF_CH101_A_EquipmentSheet_v007", 3.6),
        (options.poses, "REF_CH101_A_PoseBoard_v008", 3.6),
        (options.neutral_body, "REF_CH101_A_NeutralBodySculpt_v009", 3.6),
    )
    for raw_path, name, size in optional_refs:
        if raw_path:
            candidate = Path(raw_path).resolve()
            if candidate.exists():
                image_reference(candidate, refs, name, size)
    guide_names = create_guides(body)
    socket_names = create_sockets(tech)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene["re_camp_character"] = "CH101"
    scene["re_camp_variant"] = "A / Route Sprint / canonical"
    scene["re_camp_status"] = "WIP / MODELING GUIDE / NOT APPROVED"
    scene["re_camp_reference"] = reference.name
    scene["re_camp_target_heads"] = "5.3-5.4"
    scene["re_camp_gate"] = "Gate A pending; Gate B blocked"

    # Keep production collections empty by design.  An artist replaces these
    # with connected high-resolution meshes, not rounded primitive parts.
    for target, purpose in (
        (cloth, "separate jacket, crop top, shorts, straps, boots meshes"),
        (hair, "connected scalp, bangs, side locks and ponytail masses"),
        (equipment, "saber, ribbons, pouches and signal module"),
        (export, "only populated after visual Gate B evidence"),
    ):
        target["purpose"] = purpose
        target["status"] = "EMPTY / WAITING FOR HIGH-RES MESH"

    blend = out / "CH101_A_ModelingGuide_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "character": "CH101",
        "variant": "A Route Sprint / canonical",
        "status": "WIP / MODELING GUIDE / NOT APPROVED",
        "reference": str(reference),
        "optional_references": [str(path) for path in (options.expression, options.equipment, options.poses, options.neutral_body) if path],
        "blend": str(blend),
        "target_heads": "5.3-5.4",
        "guide_points": guide_names,
        "sockets": socket_names,
        "empty_production_collections": ["MODEL_CLOTH_OUTFIT", "MODEL_HAIR", "MODEL_EQUIPMENT", "EXPORT_READY_AFTER_GATE_B"],
        "review_notes": [
            "Reference-only scene; no final mesh",
            "Primitive blockout intentionally excluded",
            "Gate A human approval required before production mesh lock",
            "Gate B and Unity import remain blocked",
        ],
    }
    (out / "reports" / "CH101_A_ModelingGuide_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / modeling guide / not approved")


if __name__ == "__main__":
    main()
