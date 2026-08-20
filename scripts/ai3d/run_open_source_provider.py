#!/usr/bin/env python3
"""Run a pinned open-source image-to-3D provider and register its output."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
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


PROVIDER_KEYS = {
    "instantmesh": "instantMesh",
    "sf3d": "stableFast3D",
    "triposr": "tripoSR",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_head(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_command(
    provider_name: str,
    provider: dict[str, Any],
    repo_dir: Path,
    front_image: Path,
    working_output: Path,
    foreground_ratio: float | None = None,
) -> list[str]:
    if provider_name == "instantmesh":
        command = [
            sys.executable,
            str(repo_dir / "run.py"),
            str(repo_dir / provider["config"]),
            str(front_image),
            "--output_path",
            str(working_output),
            "--view",
            str(provider.get("view", 6)),
        ]
        if provider.get("exportTextureMap", True):
            command.append("--export_texmap")
        return command

    command = [
        sys.executable,
        str(repo_dir / "run.py"),
        str(front_image),
        "--output-dir",
        str(working_output),
    ]
    if provider_name == "sf3d":
        command.extend(
            [
                "--pretrained-model",
                provider["model"],
                "--texture-resolution",
                str(provider["textureResolution"]),
                "--remesh_option",
                "triangle",
                "--target_vertex_count",
                str(provider["targetVertexCount"]),
            ]
        )
    elif provider_name == "triposr":
        command.extend(
            [
                "--pretrained-model-name-or-path",
                provider["model"],
                "--model-save-format",
                "glb",
                "--mc-resolution",
                str(provider["marchingCubesResolution"]),
            ]
        )
        if foreground_ratio is not None:
            command.extend(["--foreground-ratio", str(foreground_ratio)])
    return command


def run_provider_command(
    command: list[str],
    *,
    repo_dir: Path,
    output_dir: Path,
    provider: str,
    reference_view: str,
) -> subprocess.CompletedProcess[str]:
    """Run a provider and persist stdout/stderr for reproducible diagnosis."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "provider-stdout.log"
    stderr_path = output_dir / "provider-stderr.log"
    try:
        result = subprocess.run(
            command,
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        stdout = getattr(error, "stdout", None) or ""
        stderr = getattr(error, "stderr", None) or ""
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        write_json(
            output_dir / "provider-failure.json",
            {
                "provider": provider,
                "referenceView": reference_view,
                "command": command,
                "returnCode": getattr(error, "returncode", None),
                "errorType": type(error).__name__,
                "stdoutLog": str(stdout_path),
                "stderrLog": str(stderr_path),
                "status": "FAILED_PROVIDER_EXECUTION",
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            },
        )
        raise
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")
    write_json(
        output_dir / "provider-execution.json",
        {
            "provider": provider,
            "referenceView": reference_view,
            "command": command,
            "returnCode": result.returncode,
            "stdoutLog": str(stdout_path),
            "stderrLog": str(stderr_path),
            "status": "SUCCEEDED",
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        },
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(PROVIDER_KEYS), required=True)
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-view", choices=("front", "right", "back"), default="front")
    parser.add_argument("--foreground-ratio", type=float)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    references = require_reference_manifest(args.reference_manifest.resolve(), contract)
    provider_key = PROVIDER_KEYS[args.provider]
    provider = contract["providers"][provider_key]
    repo_dir = args.provider_repo.resolve()
    if not (repo_dir / "run.py").is_file():
        raise FileNotFoundError(f"provider repository has no run.py: {repo_dir}")
    actual_head = repo_head(repo_dir)
    if actual_head != provider["commit"]:
        raise ValueError(
            f"provider repository must be pinned to {provider['commit']}, got {actual_head}"
        )
    input_image = Path(references["views"][args.reference_view]["path"]).resolve()
    if not input_image.is_file():
        raise FileNotFoundError(input_image)
    if sha256_file(input_image) != references["views"][args.reference_view]["sha256"]:
        raise ValueError(f"{args.reference_view} reference hash mismatch")

    output_dir = args.output_dir.resolve()
    working_output = output_dir / f".{args.provider}-work"
    command = build_command(
        args.provider,
        provider,
        repo_dir,
        input_image,
        working_output,
        foreground_ratio=args.foreground_ratio,
    )
    plan = {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "provider": provider_key,
        "providerMode": provider["mode"],
        "providerRepository": provider["repository"],
        "providerCommit": provider["commit"],
        "status": "DRY_RUN" if not args.execute else "GENERATION_IN_PROGRESS",
        "command": command,
        "referenceManifest": str(args.reference_manifest.resolve()),
        "referenceManifestSha256": sha256_file(args.reference_manifest.resolve()),
        "providerParameters": {
            "referenceView": args.reference_view,
            "foregroundRatio": args.foreground_ratio,
        },
        **candidate_gate_fields(contract),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.execute:
        plan_path = output_dir / f"{args.provider}-dry-run-plan.json"
        write_json(plan_path, plan)
        print(plan_path)
        return 0

    if working_output.exists():
        if working_output.parent != output_dir or working_output.name != f".{args.provider}-work":
            raise ValueError(f"refusing to remove unexpected work directory: {working_output}")
        shutil.rmtree(working_output)
    run_provider_command(
        command,
        repo_dir=repo_dir,
        output_dir=output_dir,
        provider=args.provider,
        reference_view=args.reference_view,
    )
    if args.provider == "instantmesh":
        generated_candidates = sorted(working_output.rglob("*.obj"))
        if len(generated_candidates) != 1:
            raise RuntimeError(
                f"InstantMesh must produce exactly one OBJ, found {generated_candidates}"
            )
        generated = generated_candidates[0]
        asset_dir = output_dir / f"{contract['character']}_{args.provider}_cand_001"
        if asset_dir.exists():
            if asset_dir.parent != output_dir or asset_dir.name != f"{contract['character']}_{args.provider}_cand_001":
                raise ValueError(f"refusing to remove unexpected asset directory: {asset_dir}")
            shutil.rmtree(asset_dir)
        shutil.copytree(generated.parent, asset_dir)
        destination = asset_dir / generated.name
        asset_files = sorted(str(path.relative_to(asset_dir)) for path in asset_dir.rglob("*"))
    else:
        extension = ".glb"
        generated = working_output / "0" / f"mesh{extension}"
        if not generated.is_file() or generated.stat().st_size == 0:
            raise RuntimeError(f"provider did not produce expected GLB: {generated}")
        destination = output_dir / f"{contract['character']}_{args.provider}_cand_001{extension}"
        shutil.copy2(generated, destination)
        asset_files = [destination.name]
    plan.update(
        {
            "status": "CANDIDATES_DOWNLOADED",
            "completedAt": utc_now(),
            "candidates": [
                {
                    "candidateId": f"{contract['character']}-{args.provider.upper()}-001",
                    "status": "DOWNLOADED",
                    "modelPath": str(destination),
                    "sha256": sha256_file(destination),
                    "bytes": destination.stat().st_size,
                    "assetFiles": asset_files,
                    **candidate_gate_fields(contract),
                }
            ],
        }
    )
    plan.pop("command", None)
    manifest_path = output_dir / "candidate-manifest.json"
    write_json(manifest_path, plan)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
