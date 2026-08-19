#!/usr/bin/env python3
"""Record whether a Colab runtime can execute the selected AI 3D provider.

This check is intentionally lightweight and secret-free. It does not install
packages or start a model. Open-source providers require a visible NVIDIA GPU;
the optional Tripo API path can create a dry-run plan without one.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


GPU_PROVIDERS = {"sf3d", "instantmesh", "triposr"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("tripo", *sorted(GPU_PROVIDERS)), required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def nvidia_gpus() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    result = subprocess.run(
        [executable, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if not parts or not parts[0]:
            continue
        gpus.append(
            {
                "name": parts[0],
                "memoryMb": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
                "driverVersion": parts[2] if len(parts) > 2 else "",
            }
        )
    return gpus


def torch_status() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except ImportError:
        return {"available": False, "cudaAvailable": None, "version": ""}
    return {
        "available": True,
        "cudaAvailable": bool(torch.cuda.is_available()),
        "version": str(getattr(torch, "__version__", "")),
        "cudaVersion": str(getattr(getattr(torch, "version", None), "cuda", "") or ""),
    }


def build_report(provider: str) -> dict[str, Any]:
    gpus = nvidia_gpus()
    torch_info = torch_status()
    requires_gpu = provider in GPU_PROVIDERS
    if not requires_gpu:
        status = "READY_NO_GPU_REQUIRED"
    elif gpus:
        status = "READY_GPU_VISIBLE"
    else:
        status = "BLOCKED_GPU_UNAVAILABLE"
    return {
        "provider": provider,
        "requiresGpu": requires_gpu,
        "status": status,
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "gpuCount": len(gpus),
        "gpus": gpus,
        "torch": torch_info,
        "secretFree": True,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args.provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] != "BLOCKED_GPU_UNAVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
