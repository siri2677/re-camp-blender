#!/usr/bin/env python3
"""Apply a small, idempotent runtime compatibility patch to Wonder3D NeuS.

The pinned NeuS code assumes that scalar masks and RGB tensors will always
broadcast cleanly.  On the current Python 3.12/Torch runtime that assumption
can surface as a ``size of tensor a (3) ... b (2)`` error during PSNR
calculation.  This script patches only the ephemeral provider checkout used by
the notebook; it never modifies the pinned Wonder3D commit in Git.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _patch_file(path: Path, replacements: list[tuple[str, str, str]]) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    updated = source
    applied: list[str] = []
    already_present: list[str] = []
    missing: list[str] = []
    for label, old, new in replacements:
        if new in updated:
            already_present.append(label)
            continue
        if old in updated:
            occurrence_count = updated.count(old)
            updated = updated.replace(old, new)
            applied.append(f"{label}:{occurrence_count}")
            continue
        if old not in updated:
            missing.append(label)
            continue
    if updated != source:
        path.write_text(updated, encoding="utf-8")
    return {
        "path": str(path),
        "changed": updated != source,
        "applied": applied,
        "alreadyPresent": already_present,
        "missing": missing,
    }


def patch_neus(neus_dir: Path) -> dict[str, Any]:
    dataset_path = neus_dir / "models" / "dataset_mvdiff.py"
    runner_path = neus_dir / "exp_runner.py"
    for required in (dataset_path, runner_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    dataset = _patch_file(
        dataset_path,
        [
            (
                "dataset.mask_column",
                "mask = self.masks[img_idx][(pixels_y, pixels_x)]",
                "mask = self.masks[img_idx][(pixels_y, pixels_x)].reshape(-1, 1)",
            ),
            (
                "dataset.cosine_column",
                "cosines = self.cos(rays_v, normal)",
                "cosines = self.cos(rays_v, normal).reshape(-1, 1)",
            ),
        ],
    )
    runner = _patch_file(
        runner_path,
        [
            (
                "runner.training_channel_slices",
                "                    data[:, 13:],\n                )",
                "                    data[:, 13:],\n                )\n                # Keep legacy NeuS tensors explicit on the current Torch runtime.\n                true_rgb = true_rgb[:, :3]\n                mask = mask[:, :1]\n                true_normal = true_normal[:, :3]\n                cosines = cosines[:, :1]",
            ),
            (
                "runner.psnr_mask_broadcast",
                "                psnr = 20.0 * torch.log10(1.0 / (((color_fine - true_rgb) ** 2 * mask).sum() / (mask_sum * 3.0)).sqrt())",
                "                rgb_error = color_fine - true_rgb\n                mask_rgb = mask.expand_as(rgb_error)\n                psnr = 20.0 * torch.log10(1.0 / ((rgb_error ** 2 * mask_rgb).sum() / (mask_sum * 3.0)).sqrt())",
            ),
        ],
    )
    missing = dataset["missing"] + runner["missing"]
    return {
        "status": "PATCHED" if not missing else "PATCH_PARTIAL",
        "provider": "Wonder3D",
        "neusDir": str(neus_dir),
        "dataset": dataset,
        "runner": runner,
        "missing": missing,
        "providerCommitUnchanged": True,
        "productionMesh": False,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neus-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = patch_neus(args.neus_dir.resolve())
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["missing"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
