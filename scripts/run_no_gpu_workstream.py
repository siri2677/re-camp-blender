#!/usr/bin/env python3
"""Run the GPU-independent Re:Camp Blender workstream.

This runner deliberately performs no model inference and never enables Unity
input. It keeps contracts, notebooks, tests, and reference/provider dry-runs
healthy while Colab GPU allocation is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art-root", type=Path, default=ROOT.parent / "re-camp-art")
    parser.add_argument("--skip-reference", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def run_step(name: str, command: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return {
        "name": name,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returnCode": result.returncode,
        "command": [str(part) for part in command],
        "stdoutTail": result.stdout[-1200:],
        "stderrTail": result.stderr[-1200:],
    }


def run_reference_dry_run(art_root: Path) -> list[dict[str, Any]]:
    if not art_root.is_dir():
        return [{"name": "reference-and-provider-dry-run", "status": "BLOCKED", "reason": f"missing art root: {art_root}"}]
    with tempfile.TemporaryDirectory(prefix="re-camp-no-gpu-") as temporary:
        output_dir = Path(temporary) / "reference-views"
        prepare = run_step(
            "prepare-reference-views",
            [
                sys.executable,
                str(ROOT / "scripts/ai3d/prepare_reference_views.py"),
                "--art-root",
                str(art_root),
                "--output-dir",
                str(output_dir),
            ],
        )
        if prepare["status"] != "PASS":
            return [prepare]
        dry_run = run_step(
            "tripo-multiview-dry-run",
            [
                sys.executable,
                str(ROOT / "scripts/ai3d/tripo_api.py"),
                "--reference-manifest",
                str(output_dir / "reference-views-manifest.json"),
                "--output-dir",
                str(Path(temporary) / "tripo-dry-run"),
                "--candidate-count",
                "1",
            ],
        )
        return [prepare, dry_run]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    art_root = args.art_root.resolve()
    source_env = None
    if (art_root / ".git").is_dir():
        source_env = os.environ.copy()
        source_env["RE_CAMP_SOURCE_DIR"] = str(art_root)
    steps = [
        run_step(
            "colab-package-validation",
            [sys.executable, "scripts/validate_colab_package.py"],
            env=source_env,
        ),
        run_step("free-ai3d-package-validation", [sys.executable, "scripts/validate_ai3d_free_package.py"]),
        run_step("python-compile", [sys.executable, "-m", "compileall", "-q", "scripts", "tests"]),
        run_step("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
    ]
    if args.skip_reference:
        steps.append({"name": "reference-and-provider-dry-run", "status": "SKIPPED", "reason": "--skip-reference"})
    else:
        steps.extend(run_reference_dry_run(args.art_root.resolve()))
    failed = [step for step in steps if step.get("status") == "FAIL"]
    return {
        "workstream": "NO_GPU",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "gpuRequired": False,
        "steps": steps,
        "status": "FAIL" if failed else "PASS_WITH_BLOCKED_OR_SKIPPED_EXTERNAL_STEPS",
        "blockedGpuTasks": [
            "Stable Fast 3D inference",
            "InstantMesh inference",
            "TripoSR inference",
            "production mesh generation",
            "Unity import and Play Mode",
        ],
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
