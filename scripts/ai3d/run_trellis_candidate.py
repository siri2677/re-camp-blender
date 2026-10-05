#!/usr/bin/env python3
"""Run a verified, one-shot TRELLIS candidate command.

TRELLIS has changed its example entrypoints across upstream revisions.  This
wrapper therefore refuses to guess a CLI.  The caller must provide the pinned
checkout, a verified runtime preflight, and an explicit command after the
``--`` separator.  It records no tokens and never changes project gates.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "442aa1e1afb9014e80681d3bf604e8d728a86ee7"
STRATEGY_ID = "TRELLIS_SINGLE_VIEW_V001"
MESH_SUFFIXES = {".obj", ".ply", ".glb", ".gltf"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--input-image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.provider_repo.resolve()
    image = args.input_image.resolve()
    preflight = json.loads(args.preflight.resolve().read_text(encoding="utf-8"))
    actual_commit = git_head(repo)
    blockers: list[str] = []
    if actual_commit != EXPECTED_COMMIT:
        blockers.append("TRELLIS_COMMIT_MISMATCH")
    if not image.is_file():
        blockers.append("INPUT_IMAGE_MISSING")
    if preflight.get("status") != "READY_GPU_VISIBLE":
        blockers.append("PROVIDER_PREFLIGHT_NOT_READY")
    if preflight.get("providerPreflight", {}).get("heavyweightInstallAllowed") is not True:
        blockers.append("HEAVYWEIGHT_INSTALL_NOT_AUTHORIZED")
    command = [str(part) for part in args.command if str(part) != "--"]
    if not command:
        blockers.append("TRELLIS_ENTRYPOINT_UNVERIFIED")
    return {
        "schemaVersion": "trellis-one-shot-run-report-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "trellis",
        "strategyId": STRATEGY_ID,
        "providerRepository": str(repo),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": actual_commit,
        "inputImage": str(image),
        "preflight": preflight,
        "command": command,
        "status": "READY_TO_RUN_ONCE" if not blockers else "BLOCKED_PROVIDER_PREFLIGHT",
        "blockers": blockers,
        "actualInference": False,
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.execute and report["status"] == "READY_TO_RUN_ONCE":
        result = subprocess.run(report["command"], cwd=args.provider_repo, check=False)
        report["returnCode"] = result.returncode
        report["actualInference"] = result.returncode == 0
        meshes = sorted(
            str(path.resolve())
            for path in args.output_dir.resolve().rglob("*")
            if path.is_file() and path.suffix.lower() in MESH_SUFFIXES
        )
        report["meshOutputs"] = meshes
        if result.returncode != 0:
            report["status"] = "TRELLIS_EXECUTION_FAILED"
        elif not meshes:
            report["status"] = "TRELLIS_EXECUTION_NO_MESH"
            report["blockers"] = ["MESH_EXTRACTION_OUTPUT_MISSING"]
        else:
            report["status"] = "TRELLIS_EXECUTED"
    args.output_dir.resolve().mkdir(parents=True, exist_ok=True)
    args.output_report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output_report.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY_TO_RUN_ONCE", "TRELLIS_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
