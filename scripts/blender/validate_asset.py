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


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(script_args)


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    objects = list(bpy.data.objects)
    names = {obj.name for obj in objects}
    missing = sorted(REQUIRED_SOCKETS - names)
    root = next((obj for obj in objects if obj.name.endswith("_Blockout_Root")), None)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    errors: list[str] = []
    if missing:
        errors.append(f"missing sockets: {', '.join(missing)}")
    if root is None:
        errors.append("missing blockout root empty")
    if not meshes:
        errors.append("no mesh objects found")

    report = {
        "blend": str(Path(args.blend).resolve()),
        "status": "PASS" if not errors else "FAIL",
        "technical_proof": "NOT TESTED",
        "mesh_object_count": len(meshes),
        "socket_count": len(REQUIRED_SOCKETS - set(missing)),
        "missing": missing,
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
