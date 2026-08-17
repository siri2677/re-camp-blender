#!/usr/bin/env python3
"""Validate a future CH101-A production mesh before Gate B.

The validator intentionally fails the current WIP/reference scenes.  It is an
intake contract for the first real high-resolution mesh, not a replacement for
human visual review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


BODY_TRIANGLE_LIMIT = 18_000
EQUIPMENT_TRIANGLE_LIMIT = 2_000
MATERIAL_LIMIT = 8
REQUIRED_COLLECTIONS = {"MODEL_HIGH_BODY", "MODEL_CLOTH_OUTFIT", "MODEL_HAIR", "MODEL_EQUIPMENT"}
REQUIRED_SOCKETS = {"Socket_Weapon_R", "Socket_Ribbon_L", "Socket_Ribbon_R", "Socket_Pouch_L", "Socket_Pouch_R", "Socket_Hair_Ponytail"}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def mesh_objects(collection_name: str) -> list[bpy.types.Object]:
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        return []
    return [obj for obj in collection.objects if obj.type == "MESH"]


def main() -> int:
    options = parse_args()
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
    armature = next((obj for obj in bpy.data.objects if obj.type == "ARMATURE" and "CH101" in obj.name), None)
    sockets = {obj.name for obj in bpy.data.objects if obj.name.startswith("Socket_")}
    missing_sockets = sorted(REQUIRED_SOCKETS - sockets)
    unweighted = []
    for obj in meshes:
        if armature and not any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
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
        errors.append("missing CH101 armature")
    if missing_sockets:
        errors.append(f"missing sockets: {', '.join(missing_sockets)}")
    if uv_missing:
        errors.append(f"missing UVs: {', '.join(sorted(uv_missing))}")
    if body_triangles > BODY_TRIANGLE_LIMIT:
        errors.append(f"body triangle budget exceeded: {body_triangles} > {BODY_TRIANGLE_LIMIT}")
    if equipment_triangles > EQUIPMENT_TRIANGLE_LIMIT:
        errors.append(f"equipment triangle budget exceeded: {equipment_triangles} > {EQUIPMENT_TRIANGLE_LIMIT}")
    if len(material_names) > MATERIAL_LIMIT:
        errors.append(f"material budget exceeded: {len(material_names)} > {MATERIAL_LIMIT}")
    if unweighted:
        errors.append(f"unweighted meshes: {', '.join(sorted(unweighted))}")
    status = scene.get("re_camp_status", "")
    if "WIP" in status or "NOT APPROVED" in status:
        errors.append("scene is still WIP / NOT APPROVED")
    report = {
        "blend": str(blend),
        "status": "PASS" if not errors else "FAIL",
        "scene_status": status,
        "collection_status": {name: len(mesh_objects(name)) for name in sorted(REQUIRED_COLLECTIONS)},
        "mesh_count": len(meshes),
        "body_triangle_count": body_triangles,
        "equipment_triangle_count": equipment_triangles,
        "material_count": len(material_names),
        "material_names": sorted(material_names),
        "uv_missing": sorted(uv_missing),
        "armature": armature.name if armature else "",
        "missing_sockets": missing_sockets,
        "unweighted": sorted(unweighted),
        "gate_b": "PASS" if not errors else "BLOCKED",
        "gate_c": "PENDING AFTER GATE B",
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
