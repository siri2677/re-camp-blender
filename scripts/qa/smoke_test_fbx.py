#!/usr/bin/env python3
"""Re-import exported FBX files in Blender and verify the handoff contract."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


BLENDER_DIR = Path(__file__).resolve().parents[1] / "blender"
if str(BLENDER_DIR) not in sys.path:
    sys.path.insert(0, str(BLENDER_DIR))

from validate_asset import (  # noqa: E402
    COLLIDER_BONE_MAP,
    FACE_BLENDSHAPE_NAMES,
    MOTION_CLIP_SUFFIXES,
    REQUIRED_RIG_BONES,
    SOCKET_BONE_MAP,
    mesh_triangle_count,
)


CHARACTERS = ("CH101", "CH102", "CH103", "CH104", "CH105")
CONTRACT_VERSION = "pre-unity-export-v001"


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(script_args)


def close_enough(value: float, expected: float = 1.0, tolerance: float = 1e-4) -> bool:
    return math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance)


def import_one(character: str, fbx_path: Path) -> dict[str, object]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    errors: list[str] = []
    bpy.ops.import_scene.fbx(
        filepath=str(fbx_path.resolve()),
        use_anim=True,
        ignore_leaf_bones=True,
    )

    objects = list(bpy.data.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    expected_armature = f"{character}_Rig_Armature"
    armature = bpy.data.objects.get(expected_armature)
    if armature is None:
        errors.append(f"missing imported armature {expected_armature}")
    if len(armatures) != 1:
        errors.append(f"expected one imported armature, found {len(armatures)}")

    imported_bones = {bone.name for bone in armature.data.bones} if armature else set()
    missing_bones = sorted(REQUIRED_RIG_BONES - imported_bones)
    if missing_bones:
        errors.append(f"missing imported bones: {', '.join(missing_bones)}")

    action_names = {action.name for action in bpy.data.actions}
    expected_actions = {f"{character}_{suffix}" for suffix in MOTION_CLIP_SUFFIXES}
    missing_actions = sorted(expected_actions - action_names)
    if missing_actions:
        errors.append(f"missing imported actions: {', '.join(missing_actions)}")

    triangle_count = sum(mesh_triangle_count(mesh.data) for mesh in meshes)
    if not meshes or triangle_count <= 0:
        errors.append("imported FBX has no non-empty mesh")

    bounds = []
    for mesh in meshes:
        corners = [mesh.matrix_world @ corner for corner in mesh.bound_box]
        bounds.extend(corners)
    dimensions = {
        "x": max((corner.x for corner in bounds), default=0.0) - min((corner.x for corner in bounds), default=0.0),
        "y": max((corner.y for corner in bounds), default=0.0) - min((corner.y for corner in bounds), default=0.0),
        "z": max((corner.z for corner in bounds), default=0.0) - min((corner.z for corner in bounds), default=0.0),
    }
    if dimensions["z"] <= 0.1:
        errors.append("imported mesh height is degenerate")

    scale_deviations = []
    for obj in objects:
        if not all(close_enough(value) for value in obj.scale):
            scale_deviations.append({"object": obj.name, "scale": list(obj.scale)})
    if scale_deviations:
        errors.append(f"non-unit imported object scales: {len(scale_deviations)}")

    return {
        "character": character,
        "fbx": str(fbx_path),
        "status": "PASS" if not errors else "FAIL",
        "contract_version": CONTRACT_VERSION,
        "object_count": len(objects),
        "mesh_object_count": len(meshes),
        "armature_count": len(armatures),
        "armature_name": armature.name if armature else None,
        "bone_count": len(imported_bones),
        "missing_bones": missing_bones,
        "action_names": sorted(action_names),
        "missing_actions": missing_actions,
        "triangle_count": triangle_count,
        "dimensions": dimensions,
        "scale_deviations": scale_deviations,
        "socket_contract_count": len(SOCKET_BONE_MAP),
        "collider_contract_count": len(COLLIDER_BONE_MAP),
        "face_target_contract_count": len(FACE_BLENDSHAPE_NAMES),
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    results = []
    for character in CHARACTERS:
        fbx_path = args.output_root / character / f"{character}_Blockout_REVIEW_v007.fbx"
        if not fbx_path.is_file():
            results.append({"character": character, "status": "FAIL", "errors": [f"missing FBX: {fbx_path}"]})
            continue
        try:
            results.append(import_one(character, fbx_path))
        except Exception as exc:  # Blender operators expose failures as runtime exceptions.
            results.append({"character": character, "status": "FAIL", "errors": [f"import exception: {exc}"]})

    status = "PASS" if all(result.get("status") == "PASS" for result in results) else "FAIL"
    report = {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "characters": results,
        "import_settings": {
            "use_anim": True,
            "ignore_leaf_bones": True,
            "axis_forward": "-Z",
            "axis_up": "Y",
            "unit_scale": 1.0,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "characters": [result["character"] for result in results]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
