#!/usr/bin/env python3
"""Run the pinned SPAR3D low-VRAM single-view experiment once.

This wrapper intentionally performs no dependency installation and never
persists a Hugging Face token.  The Notebook owns the explicit setup command;
this module only verifies the preflight, invokes the provider's official
``run.py`` entrypoint, and records a review-only mesh result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1"
STRATEGY_ID = "SPAR3D_SINGLE_VIEW_V001"
MODEL_ID = "stabilityai/stable-point-aware-3d"
MINIMUM_VRAM_MB = 8192


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--input-image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--texture-resolution", type=int, default=1024)
    parser.add_argument("--target-count", type=int, default=20000)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dependency_preflight(repo: Path) -> tuple[bool, str]:
    """Import only; never download weights or start inference."""

    imports = (
        "import torch; import trimesh; import PIL; import tqdm; "
        "import transparent_background; import spar3d.system"
    )
    result = subprocess.run(
        [sys.executable, "-c", imports],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (
        "READY_IMPORTS" if result.returncode == 0 else "SPAR3D_DEPENDENCIES_IMPORT_FAILED"
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.provider_repo.resolve()
    image = args.input_image.resolve()
    preflight_path = args.preflight.resolve()
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    actual_commit = git_head(repo)
    provider_preflight = preflight.get("providerPreflight", {})
    blockers: list[str] = []
    if actual_commit != EXPECTED_COMMIT:
        blockers.append("SPAR3D_COMMIT_MISMATCH")
    if not image.is_file():
        blockers.append("INPUT_IMAGE_MISSING")
    if preflight.get("provider") != "spar3d":
        blockers.append("SPAR3D_PREFLIGHT_PROVIDER_MISMATCH")
    if preflight.get("status") != "READY_GPU_VISIBLE":
        blockers.append("PROVIDER_PREFLIGHT_NOT_READY")
    if provider_preflight.get("heavyweightInstallAllowed") is not True:
        blockers.append("HEAVYWEIGHT_INSTALL_NOT_AUTHORIZED")
    if provider_preflight.get("vramSufficient") is not True:
        blockers.append("SPAR3D_VRAM_INSUFFICIENT")
    if provider_preflight.get("hfTokenPresent") is not True:
        blockers.append("SPAR3D_HF_TOKEN_REQUIRED")
    if provider_preflight.get("modelAccessAcknowledged") is not True:
        blockers.append("SPAR3D_MODEL_ACCESS_ACK_REQUIRED")
    if provider_preflight.get("licenseTermsAcknowledged") is not True:
        blockers.append("SPAR3D_LICENSE_ACK_REQUIRED")
    if preflight.get("unityInputAllowed") is True or preflight.get("productionPromotionAllowed") is True:
        blockers.append("PROJECT_GATE_ALREADY_OPEN")
    if not 512 <= args.texture_resolution <= 2048:
        blockers.append("TEXTURE_RESOLUTION_OUT_OF_RANGE")
    if not 1000 <= args.target_count <= 100000:
        blockers.append("TARGET_COUNT_OUT_OF_RANGE")
    return {
        "schemaVersion": "spar3d-one-shot-run-report-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "spar3d",
        "strategyId": STRATEGY_ID,
        "providerRepository": str(repo),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": actual_commit,
        "model": MODEL_ID,
        "inputImage": str(image),
        "preflight": preflight,
        "officialEntrypoint": "run.py",
        "lowVramMode": True,
        "memoryProfile": "LOW_VRAM_APPROXIMATELY_7GB",
        "textureResolution": args.texture_resolution,
        "targetCount": args.target_count,
        "hfTokenPresent": provider_preflight.get("hfTokenPresent") is True,
        "actualInference": False,
        "meshOutputs": [],
        "status": "READY_TO_RUN_ONCE" if not blockers else "BLOCKED_PROVIDER_PREFLIGHT",
        "blockers": blockers,
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def find_mesh_outputs(output_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in output_dir.glob("**/mesh.glb")
        if path.is_file() and path.stat().st_size > 0
    )


def main() -> int:
    args = parse_args()
    report = build_report(args)
    output_dir = args.output_dir.resolve()
    report_path = args.output_report.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if args.execute and report["status"] == "READY_TO_RUN_ONCE":
        imports_ready, dependency_status = dependency_preflight(args.provider_repo.resolve())
        report["dependencyPreflight"] = dependency_status
        if not imports_ready:
            report["status"] = "BLOCKED_PROVIDER_DEPENDENCY_PREFLIGHT"
            report["blockers"].append("SPAR3D_DEPENDENCIES_IMPORT_FAILED")
        else:
            command = [
                sys.executable,
                str(args.provider_repo.resolve() / "run.py"),
                str(args.input_image.resolve()),
                "--pretrained-model",
                MODEL_ID,
                "--device",
                "cuda",
                "--output-dir",
                str(output_dir),
                "--texture-resolution",
                str(args.texture_resolution),
                "--low-vram-mode",
            ]
            report["command"] = command
            provider_env = os.environ.copy()
            provider_root = str(args.provider_repo.resolve())
            existing_pythonpath = provider_env.get("PYTHONPATH", "")
            provider_env["PYTHONPATH"] = (
                provider_root
                if not existing_pythonpath
                else provider_root + os.pathsep + existing_pythonpath
            )
            # Do not capture or persist provider output: it could contain
            # environment-specific paths or accidental secret material.
            result = subprocess.run(
                command,
                cwd=args.provider_repo.resolve(),
                env=provider_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            report["returnCode"] = result.returncode
            mesh_outputs = find_mesh_outputs(output_dir)
            if result.returncode != 0:
                report["status"] = "SPAR3D_EXECUTION_FAILED"
                report["blockers"] = ["SPAR3D_PROVIDER_RETURNED_NONZERO"]
            elif len(mesh_outputs) != 1:
                report["status"] = "SPAR3D_EXECUTION_NO_UNIQUE_MESH"
                report["blockers"] = ["EXPECTED_ONE_NONEMPTY_MESH_GLB"]
            else:
                canonical_mesh = output_dir / "CH101_spar3d_cand_001.glb"
                shutil.copy2(mesh_outputs[0], canonical_mesh)
                report["actualInference"] = True
                report["status"] = "SPAR3D_EXECUTED"
                report["meshOutputs"] = [str(canonical_mesh.resolve())]
                report["meshSha256"] = sha256_file(canonical_mesh)
                candidate_manifest = output_dir / "candidate-manifest.json"
                candidate_manifest.write_text(
                    json.dumps(
                        {
                            "schemaVersion": "spar3d-candidate-manifest-v001",
                            "provider": "spar3d",
                            "strategyId": STRATEGY_ID,
                            "candidateLabel": "001",
                            "mesh": str(canonical_mesh.resolve()),
                            "meshSha256": report["meshSha256"],
                            "sourceStatus": report["sourceStatus"],
                            "gateB": report["gateB"],
                            "unityInputAllowed": False,
                            "productionPromotionAllowed": False,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                report["candidateManifest"] = str(candidate_manifest.resolve())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY_TO_RUN_ONCE", "SPAR3D_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
