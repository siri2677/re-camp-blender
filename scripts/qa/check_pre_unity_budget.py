#!/usr/bin/env python3
"""Check current-roster metrics against the pre-Unity performance budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CHARACTERS = ("CH101", "CH102", "CH103", "CH104", "CH105")
DEFAULT_BUDGET = {
    "lod0_triangles": 25000,
    "lod1_triangles": 15000,
    "lod2_triangles": 8000,
    "mesh_objects": 64,
    "lod_mesh_objects": 128,
    "bones": 32,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    characters = []
    errors = []
    for character in CHARACTERS:
        report_path = args.output_root / character / "reports" / f"{character}_validation.json"
        if not report_path.is_file():
            errors.append(f"{character}: missing validation report")
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        lod_counts = report.get("lod_triangle_counts", {})
        metrics = {
            "lod0_triangles": report.get("triangle_count", 0),
            "lod1_triangles": lod_counts.get("LOD1", 0),
            "lod2_triangles": lod_counts.get("LOD2", 0),
            "mesh_objects": report.get("mesh_object_count", 0),
            "lod_mesh_objects": report.get("lod_mesh_object_count", 0),
            "bones": report.get("bone_count", 0),
        }
        violations = [
            f"{key}={value} > {DEFAULT_BUDGET[key]}"
            for key, value in metrics.items()
            if value > DEFAULT_BUDGET[key]
        ]
        if violations:
            errors.append(f"{character}: " + ", ".join(violations))
        characters.append({"character": character, "metrics": metrics, "violations": violations})

    status = "PASS" if len(characters) == len(CHARACTERS) and not errors else "FAIL"
    output = {
        "status": status,
        "budget": DEFAULT_BUDGET,
        "characters": characters,
        "errors": errors,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
