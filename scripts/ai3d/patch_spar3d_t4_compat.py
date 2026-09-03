#!/usr/bin/env python3
"""Patch the pinned SPAR3D runner for Kaggle's pre-Ampere CUDA devices.

The pinned SPAR3D runner has two compatibility problems on a stock Kaggle T4:
it unconditionally enters CUDA autocast with ``torch.bfloat16`` even though
T4 (compute capability 7.5) has no CUDA BF16 support, and it defines the
``reduction_count_type``/``target_count`` CLI arguments only when optional
remeshing packages are installed even though the values are always consumed.
This small, idempotent patch keeps BF16 on supported devices, selects FP16 on
older CUDA GPUs, and makes those two defaulted arguments unconditional.

The provider checkout remains detached at the pinned commit.  The patch is
applied only to the ephemeral runtime copy used by Kaggle and its exact
source change is recorded in a JSON report; no upstream commit is rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1"
PATCH_ID = "SPAR3D_T4_BF16_CLI_DEFAULTS_V002"

_DEVICE_PRINT = '    print("Device used: ", device)'
_DEVICE_PRINT_PATCHED = '''    print("Device used: ", device)

    # Tesla T4 (sm_75) has no CUDA BF16 support.  Keep BF16 on supported
    # devices, but use FP16 on pre-Ampere GPUs so the official runner can
    # complete inference instead of failing at autocast construction.
    amp_dtype = (
        torch.bfloat16
        if "cuda" not in device or torch.cuda.is_bf16_supported()
        else torch.float16
    )
    print("Autocast dtype: ", amp_dtype)'''
_AUTOCAST = "                torch.autocast(device_type=device, dtype=torch.bfloat16)"
_AUTOCAST_PATCHED = "                torch.autocast(device_type=device, dtype=amp_dtype)"

_OPTIONAL_REDUCTION_BLOCK = '''    if TRIANGLE_REMESH_AVAILABLE or QUAD_REMESH_AVAILABLE:
        parser.add_argument(
            "--reduction_count_type",
            choices=["keep", "vertex", "faces"],
            default="keep",
            help="Vertex count type",
        )
        parser.add_argument(
            "--target_count",
            type=check_positive,
            help="Selected target count.",
            default=2000,
        )'''
_UNCONDITIONAL_REDUCTION_BLOCK = '''    # The runner consumes these values even when optional remeshing
    # packages are unavailable, so define safe defaults unconditionally.
    parser.add_argument(
        "--reduction_count_type",
        choices=["keep", "vertex", "faces"],
        default="keep",
        help="Vertex count type",
    )
    parser.add_argument(
        "--target_count",
        type=check_positive,
        help="Selected target count.",
        default=2000,
    )'''


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def patch_runner(provider_repo: Path) -> dict[str, Any]:
    runner = provider_repo / "run.py"
    if not runner.is_file():
        raise FileNotFoundError(runner)

    original = runner.read_text(encoding="utf-8")
    original_sha256 = sha256_file(runner)
    updated = original
    applied: list[str] = []
    already_present: list[str] = []
    missing: list[str] = []

    if _DEVICE_PRINT_PATCHED in updated:
        already_present.append("runner.dynamic_amp_dtype")
    elif _DEVICE_PRINT in updated:
        updated = updated.replace(_DEVICE_PRINT, _DEVICE_PRINT_PATCHED, 1)
        applied.append("runner.dynamic_amp_dtype:1")
    else:
        missing.append("runner.dynamic_amp_dtype")

    if _AUTOCAST_PATCHED in updated:
        already_present.append("runner.autocast_dtype")
    elif _AUTOCAST in updated:
        updated = updated.replace(_AUTOCAST, _AUTOCAST_PATCHED, 1)
        applied.append("runner.autocast_dtype:1")
    else:
        missing.append("runner.autocast_dtype")

    if _UNCONDITIONAL_REDUCTION_BLOCK in updated:
        already_present.append("runner.cli_defaults")
    elif _OPTIONAL_REDUCTION_BLOCK in updated:
        updated = updated.replace(
            _OPTIONAL_REDUCTION_BLOCK, _UNCONDITIONAL_REDUCTION_BLOCK, 1
        )
        applied.append("runner.cli_defaults:1")
    else:
        missing.append("runner.cli_defaults")

    if updated != original:
        runner.write_text(updated, encoding="utf-8")

    return {
        "patchId": PATCH_ID,
        "path": str(runner),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": git_head(provider_repo),
        "originalSha256": original_sha256,
        "patchedSha256": sha256_file(runner),
        "changed": updated != original,
        "applied": applied,
        "alreadyPresent": already_present,
        "missing": missing,
        "providerCommitUnchanged": True,
        "productionMesh": False,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider_repo = args.provider_repo.resolve()
    report = patch_runner(provider_repo)
    if report["providerCommitActual"] != EXPECTED_COMMIT:
        report["status"] = "BLOCKED_PROVIDER_COMMIT_MISMATCH"
        report["missing"].append("provider.commit")
    elif report["missing"]:
        report["status"] = "PATCH_PARTIAL"
    else:
        report["status"] = "PATCHED" if report["changed"] else "ALREADY_PATCHED"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PATCHED", "ALREADY_PATCHED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
