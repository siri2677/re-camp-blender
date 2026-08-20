#!/usr/bin/env python3
"""Prepare or execute the research-only Wonder3D multiview stage."""

from __future__ import annotations

import argparse
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
        sha256_file,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        require_reference_manifest,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-view", choices=("front",), default="front")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract)
    provider = contract["experimentalProviders"]["wonder3D"]
    if provider.get("fallbackEnabled") is not False:
        raise ValueError("Wonder3D must remain research-only and disabled as a fallback")
    if provider.get("unityInputAllowed") is not False:
        raise ValueError("Wonder3D cannot enable Unity input")

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

    reference_manifest_path = args.reference_manifest.resolve()
    reference_manifest = require_reference_manifest(reference_manifest_path, contract)
    reference = Path(reference_manifest["views"][args.reference_view]["path"]).resolve()
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if sha256_file(reference) != reference_manifest["views"][args.reference_view]["sha256"]:
        raise ValueError("Wonder3D reference image hash mismatch")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
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
        "status": "EXECUTION_NOT_REQUESTED" if not args.execute else "GENERATION_IN_PROGRESS",
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
        report.update({"status": "FAILED_NO_MULTIVIEW_OUTPUT", "completedAt": utc_now()})
        write_json(report_path, report)
        raise RuntimeError(f"Wonder3D produced no files under {output_dir}")
    report.update(
        {
            "status": "MULTIVIEW_GENERATED",
            "completedAt": utc_now(),
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
