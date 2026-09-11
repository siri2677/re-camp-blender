#!/usr/bin/env python3
"""Validate a current-roster production mesh before human Gate B review.

This is a technical intake contract for CH101-CH105. It does not create a
model, replace visual review, or authorize Unity/runtime use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "current_roster_socket_contract_v001.json"
BODY_TRIANGLE_LIMIT = 18_000
EQUIPMENT_TRIANGLE_LIMIT = 2_000
MATERIAL_LIMIT = 6
REQUIRED_COLLECTIONS = {
    "MODEL_HIGH_BODY",
    "MODEL_CLOTH_OUTFIT",
    "MODEL_HAIR",
    "MODEL_EQUIPMENT",
}


def load_contract() -> dict[str, object]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    characters = contract.get("characters")
    if not isinstance(characters, list) or len(characters) != 5:
        raise ValueError("socket contract must contain exactly five characters")
    return contract


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def mesh_objects(collection_name: str) -> list[bpy.types.Object]:
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        return []
    return [obj for obj in collection.objects if obj.type == "MESH"]


def max_matrix_delta(left: bpy.types.Object, right: bpy.types.Object) -> float:
    return max(
        abs(left.matrix_world[row][column] - right.matrix_world[row][column])
        for row in range(4)
        for column in range(4)
    )


def main() -> int:
    options = parse_args()
    contract = load_contract()
    characters = {entry["code"]: entry for entry in contract["characters"]}
    if options.character not in characters:
        raise ValueError(f"unsupported character: {options.character}")
    character = characters[options.character]
    common_sockets = set(contract["commonRuntimeSockets"])
    detail_sockets = set(character["detailSockets"])
    runtime_socket_map = dict(character["runtimeSocketMap"])
    required_sockets = common_sockets | detail_sockets | set(runtime_socket_map)

    blend = Path(options.blend).resolve()
    report_path = Path(options.report).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene

    collections = {collection.name for collection in bpy.data.collections}
    missing_collections = sorted(REQUIRED_COLLECTIONS - collections)
    body = mesh_objects("MODEL_HIGH_BODY")
    outfit = mesh_objects("MODEL_CLOTH_OUTFIT")
    hair = mesh_objects("MODEL_HAIR")
    equipment = mesh_objects("MODEL_EQUIPMENT")
    meshes = body + outfit + hair + equipment
    triangles = {}
    uv_missing = []
    material_names = set()
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangles[obj.name] = len(obj.data.loop_triangles)
        if not obj.data.uv_layers:
            uv_missing.append(obj.name)
        for material in obj.data.materials:
            if material:
                material_names.add(material.name)

    body_triangles = sum(triangles[obj.name] for obj in body)
    equipment_triangles = sum(triangles[obj.name] for obj in equipment)
    armature = next(
        (
            obj
            for obj in bpy.data.objects
            if obj.type == "ARMATURE" and options.character in obj.name
        ),
        None,
    )
    socket_objects = {
        obj.name: obj
        for obj in bpy.data.objects
        if obj.name.startswith("Socket_")
    }
    missing_sockets = sorted(required_sockets - set(socket_objects))
    alias_transform_mismatches = []
    for runtime_name, source_name in runtime_socket_map.items():
        runtime_object = socket_objects.get(runtime_name)
        source_object = socket_objects.get(source_name)
        if runtime_object is not None and source_object is not None:
            if max_matrix_delta(runtime_object, source_object) > 0.0001:
                alias_transform_mismatches.append(f"{runtime_name} != {source_name}")

    unweighted = []
    for obj in meshes:
        if armature and not any(
            modifier.type == "ARMATURE" and modifier.object == armature
            for modifier in obj.modifiers
        ):
            unweighted.append(obj.name)

    errors = []
    if missing_collections:
        errors.append(f"missing production collections: {', '.join(missing_collections)}")
    if not body:
        errors.append("no body mesh in MODEL_HIGH_BODY")
    if not outfit:
        errors.append("no outfit mesh in MODEL_CLOTH_OUTFIT")
    if not hair:
        errors.append("no hair mesh in MODEL_HAIR")
    if not equipment:
        errors.append("no equipment mesh in MODEL_EQUIPMENT")
    if not armature:
        errors.append(f"missing {options.character} armature")
    if missing_sockets:
        errors.append(f"missing sockets: {', '.join(missing_sockets)}")
    if alias_transform_mismatches:
        errors.append(f"socket alias transform mismatch: {', '.join(alias_transform_mismatches)}")
    if uv_missing:
        errors.append(f"missing UVs: {', '.join(sorted(uv_missing))}")
    if body_triangles > BODY_TRIANGLE_LIMIT:
        errors.append(f"body triangle budget exceeded: {body_triangles} > {BODY_TRIANGLE_LIMIT}")
    if equipment_triangles > EQUIPMENT_TRIANGLE_LIMIT:
        errors.append(
            f"equipment triangle budget exceeded: {equipment_triangles} > {EQUIPMENT_TRIANGLE_LIMIT}"
        )
    if len(material_names) > MATERIAL_LIMIT:
        errors.append(f"material budget exceeded: {len(material_names)} > {MATERIAL_LIMIT}")
    if unweighted:
        errors.append(f"unweighted meshes: {', '.join(sorted(unweighted))}")

    status = scene.get("re_camp_status", "")
    if not status:
        errors.append("scene status is missing")
    elif any(
        marker in status.upper()
        for marker in (
            "WIP",
            "NOT APPROVED",
            "NOT_PRODUCTION",
            "AI_GENERATED",
            "TEMPLATE",
            "SCAFFOLD",
        )
    ):
        errors.append(f"scene status is not production-eligible: {status}")

    report = {
        "character": options.character,
        "subject": character["subject"],
        "source_reference": character["sourceReference"],
        "production_blend": character["productionBlend"],
        "blend": str(blend),
        "status": "PASS" if not errors else "FAIL",
        "scene_status": status,
        "collection_status": {
            name: len(mesh_objects(name)) for name in sorted(REQUIRED_COLLECTIONS)
        },
        "mesh_count": len(meshes),
        "body_triangle_count": body_triangles,
        "equipment_triangle_count": equipment_triangles,
        "material_count": len(material_names),
        "material_names": sorted(material_names),
        "uv_missing": sorted(uv_missing),
        "armature": armature.name if armature else "",
        "required_sockets": sorted(required_sockets),
        "detail_sockets": sorted(detail_sockets),
        "runtime_socket_map": runtime_socket_map,
        "missing_sockets": missing_sockets,
        "alias_transform_mismatches": alias_transform_mismatches,
        "unweighted": sorted(unweighted),
        "gate_b": "PASS" if not errors else "BLOCKED",
        "gate_c": "PENDING AFTER GATE B",
        "unity_input_allowed": False,
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
