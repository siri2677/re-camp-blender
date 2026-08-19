#!/usr/bin/env python3
"""Run a pinned single-view open-source fallback and register its GLB output."""

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


PROVIDER_KEYS = {"sf3d": "stableFast3D", "triposr": "tripoSR"}


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
    else:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(PROVIDER_KEYS), required=True)
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--foreground-ratio", type=float)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract)
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
    front_image = Path(references["views"]["front"]["path"]).resolve()
    if not front_image.is_file():
        raise FileNotFoundError(front_image)
    if sha256_file(front_image) != references["views"]["front"]["sha256"]:
        raise ValueError("front reference hash mismatch")

    output_dir = args.output_dir.resolve()
    working_output = output_dir / f".{args.provider}-work"
    command = build_command(
        args.provider,
        provider,
        repo_dir,
        front_image,
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
    subprocess.run(command, cwd=repo_dir, check=True)
    generated = working_output / "0" / "mesh.glb"
    if not generated.is_file() or generated.stat().st_size == 0:
        raise RuntimeError(f"provider did not produce expected GLB: {generated}")
    destination = output_dir / f"{contract['character']}_{args.provider}_cand_001.glb"
    shutil.copy2(generated, destination)
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
