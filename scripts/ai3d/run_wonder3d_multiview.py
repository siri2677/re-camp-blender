#!/usr/bin/env python3
"""Prepare or execute the research-only Wonder3D multiview stage."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        require_reference_manifest,
        read_json,
        sha256_file,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        require_reference_manifest,
        read_json,
        sha256_file,
        write_json,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_generation_command(
    provider: dict[str, Any],
    provider_repo: Path,
    reference_dir: Path,
    input_filename: str,
    output_dir: Path,
) -> list[str]:
    """Build the command documented by the pinned Wonder3D repository."""

    return [
        "accelerate",
        "launch",
        "--config_file",
        str(provider_repo / "1gpu.yaml"),
        str(provider_repo / "test_mvdiffusion_seq.py"),
        "--config",
        str(provider_repo / "configs" / "mvdiffusion-joint-ortho-6views.yaml"),
        f"validation_dataset.root_dir={reference_dir}",
        f"validation_dataset.filepaths=['{input_filename}']",
        f"save_dir={output_dir}",
    ]


def repo_head(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def inspect_reusable_generation(
    contract: dict[str, Any],
    reference_manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Validate an existing six-view report without touching provider files."""

    reasons: list[str] = []
    report: dict[str, Any] | None = None
    if not report_path.is_file():
        reasons.append("REPORT_MISSING")
    else:
        try:
            report = read_json(report_path)
        except (OSError, ValueError) as error:
            reasons.append(f"REPORT_INVALID:{error}")

    if report is not None:
        provider = contract["experimentalProviders"]["wonder3D"]
        generation_status = report.get("generationStatus", report.get("status"))
        if generation_status != "MULTIVIEW_GENERATED":
            reasons.append("GENERATION_STATUS_NOT_COMPLETE")
        if report.get("provider") != "wonder3D":
            reasons.append("PROVIDER_MISMATCH")
        if report.get("providerCommit") != provider["commit"]:
            reasons.append("PROVIDER_COMMIT_MISMATCH")
        if report.get("providerRepoHead") != provider["commit"]:
            reasons.append("PROVIDER_REPO_HEAD_MISMATCH")
        if report.get("generatedViewCount") != provider["generatedViewCount"]:
            reasons.append("VIEW_COUNT_MISMATCH")
        if report.get("generatedAzimuths") != provider["generatedAzimuths"]:
            reasons.append("VIEW_AZIMUTH_MISMATCH")
        if report.get("unityInputAllowed") is not False:
            reasons.append("UNITY_GATE_UNLOCKED")
        if report.get("productionPromotionAllowed") is not False:
            reasons.append("PRODUCTION_GATE_UNLOCKED")

        if reference_manifest_path.is_file():
            expected_reference_hash = sha256_file(reference_manifest_path)
            if report.get("referenceManifestSha256") != expected_reference_hash:
                reasons.append("REFERENCE_MANIFEST_SHA256_MISMATCH")
        else:
            reasons.append("REFERENCE_MANIFEST_MISSING")

        generated_files = report.get("generatedFiles")
        output_dir = report_path.parent.resolve()
        if not isinstance(generated_files, list) or len(generated_files) < provider["generatedViewCount"]:
            reasons.append("GENERATED_VIEW_FILES_INCOMPLETE")
        else:
            for relative_name in generated_files:
                if not isinstance(relative_name, str) or not relative_name:
                    reasons.append("GENERATED_FILE_ENTRY_INVALID")
                    continue
                generated_path = (output_dir / relative_name).resolve()
                try:
                    generated_path.relative_to(output_dir)
                except ValueError:
                    reasons.append("GENERATED_FILE_ESCAPES_OUTPUT")
                    continue
                if not generated_path.is_file():
                    reasons.append(f"GENERATED_FILE_MISSING:{relative_name}")

    return {
        "reusable": not reasons,
        "status": "REUSABLE" if not reasons else "NOT_REUSABLE",
        "reasons": reasons,
        "report": report,
    }


def mark_generation_reused(
    contract: dict[str, Any],
    report_path: Path,
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Mark a validated generation as reused while keeping its generation proof."""

    if not validation.get("reusable") or not isinstance(validation.get("report"), dict):
        raise ValueError(f"Wonder3D output is not reusable: {validation.get('reasons', [])}")
    report = dict(validation["report"])
    report.update(
        {
            "status": "REUSED",
            "generationStatus": "MULTIVIEW_GENERATED",
            "reusedAt": utc_now(),
            "actualInference": False,
            **candidate_gate_fields(contract),
        }
    )
    write_json(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-view", choices=("front",), default="front")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        default=os.environ.get("RE_CAMP_REUSE_WONDER3D", "1") != "0",
        help="reuse a validated existing multiview report instead of rerunning inference",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    provider = contract["experimentalProviders"]["wonder3D"]
    if provider.get("fallbackEnabled") is not False:
        raise ValueError("Wonder3D must remain research-only and disabled as a fallback")
    if provider.get("unityInputAllowed") is not False:
        raise ValueError("Wonder3D cannot enable Unity input")

    reference_manifest_path = args.reference_manifest.resolve()
    reference_manifest = require_reference_manifest(reference_manifest_path, contract)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "wonder3d-generation-report.json"
    reuse_validation = inspect_reusable_generation(contract, reference_manifest_path, report_path)
    if args.reuse_existing and reuse_validation["reusable"]:
        report = mark_generation_reused(contract, report_path, reuse_validation)
        print(json.dumps({"report": str(report_path), "status": report["status"], "actualInference": False}, indent=2))
        return 0

    provider_repo = args.provider_repo.resolve()
    required_files = (
        provider_repo / "1gpu.yaml",
        provider_repo / "test_mvdiffusion_seq.py",
        provider_repo / "configs" / "mvdiffusion-joint-ortho-6views.yaml",
    )
    for required in required_files:
        if not required.is_file():
            raise FileNotFoundError(required)
    actual_head = repo_head(provider_repo)
    if actual_head != provider["commit"]:
        raise ValueError(f"Wonder3D repository must be pinned to {provider['commit']}, got {actual_head}")

    reference = Path(reference_manifest["views"][args.reference_view]["path"]).resolve()
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if sha256_file(reference) != reference_manifest["views"][args.reference_view]["sha256"]:
        raise ValueError("Wonder3D reference image hash mismatch")

    command = build_generation_command(
        provider,
        provider_repo,
        reference.parent,
        reference.name,
        output_dir,
    )
    report: dict[str, Any] = {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "provider": "wonder3D",
        "providerRepository": provider["repository"],
        "providerCommit": provider["commit"],
        "providerRepoHead": actual_head,
        "providerMode": provider["mode"],
        "referenceManifest": str(reference_manifest_path),
        "referenceManifestSha256": sha256_file(reference_manifest_path),
        "referenceView": args.reference_view,
        "referenceImage": str(reference),
        "referenceImageSha256": sha256_file(reference),
        "command": command,
        "outputDir": str(output_dir),
        "generatedViewCount": provider["generatedViewCount"],
        "generatedAzimuths": provider["generatedAzimuths"],
        "generationStatus": "GENERATION_IN_PROGRESS" if args.execute else "EXECUTION_NOT_REQUESTED",
        "reuseCheck": {
            "status": reuse_validation["status"],
            "reasons": reuse_validation["reasons"],
        },
        "status": "EXECUTION_NOT_REQUESTED" if not args.execute else "GENERATION_IN_PROGRESS",
        "actualInference": False,
        **candidate_gate_fields(contract),
    }
    report_path = output_dir / "wonder3d-generation-report.json"
    if not args.execute:
        write_json(report_path, report)
        print(report_path)
        return 0

    stdout_path = output_dir / "provider-stdout.log"
    stderr_path = output_dir / "provider-stderr.log"
    try:
        result = subprocess.run(
            command,
            cwd=provider_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        stdout_path.write_text(getattr(error, "stdout", None) or "", encoding="utf-8")
        stderr_path.write_text(getattr(error, "stderr", None) or "", encoding="utf-8")
        report.update(
            {
                "status": "FAILED_PROVIDER_EXECUTION",
                "generationStatus": "FAILED_PROVIDER_EXECUTION",
                "returnCode": getattr(error, "returncode", None),
                "stdoutLog": str(stdout_path),
                "stderrLog": str(stderr_path),
                "completedAt": utc_now(),
            }
        )
        write_json(report_path, report)
        raise

    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")
    generated_files = sorted(
        str(path.relative_to(output_dir))
        for path in output_dir.rglob("*")
        if path.is_file() and path.name not in {report_path.name, stdout_path.name, stderr_path.name}
    )
    if not generated_files:
        report.update(
            {
                "status": "FAILED_NO_MULTIVIEW_OUTPUT",
                "generationStatus": "FAILED_NO_MULTIVIEW_OUTPUT",
                "completedAt": utc_now(),
            }
        )
        write_json(report_path, report)
        raise RuntimeError(f"Wonder3D produced no files under {output_dir}")
    report.update(
        {
            "status": "MULTIVIEW_GENERATED",
            "generationStatus": "MULTIVIEW_GENERATED",
            "completedAt": utc_now(),
            "actualInference": True,
            "stdoutLog": str(stdout_path),
            "stderrLog": str(stderr_path),
            "generatedFiles": generated_files,
            "meshExtractionPending": True,
        }
    )
    write_json(report_path, report)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
