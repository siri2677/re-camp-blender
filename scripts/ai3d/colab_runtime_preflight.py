#!/usr/bin/env python3
"""Record whether a Colab runtime can execute the selected AI 3D provider.

This check is intentionally lightweight and secret-free. It does not install
packages or start a model. Open-source providers require a visible NVIDIA GPU;
the optional Tripo API path can create a dry-run plan without one.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


GPU_PROVIDERS = {
    "sf3d",
    "instantmesh",
    "triposr",
    "wonder3D",
    "trellis",
    "trellis16",
    "trellis2",
}

# TRELLIS is deliberately conservative: a visible GPU is not enough to
# authorize installation of its heavyweight stack.  The documented pipeline
# needs a high-memory CUDA device and its upstream/checkpoint terms must be
# acknowledged in the runtime without storing a secret.
TRELLIS_MINIMUM_VRAM_MB = 24576
TRELLIS16_MINIMUM_VRAM_MB = 16384
TRELLIS2_MINIMUM_VRAM_MB = 24576


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
        return {
            "available": False,
            "cudaAvailable": None,
            "version": "",
            "deviceCapability": None,
            "torchKernelSupportsDevice": False,
        }
    capability = None
    device_name = ""
    arch_list: list[str] = []
    cuda_available = bool(torch.cuda.is_available())
    if cuda_available:
        try:
            major, minor = torch.cuda.get_device_capability(0)
            capability = {"major": int(major), "minor": int(minor), "label": f"{major}.{minor}"}
            device_name = str(torch.cuda.get_device_name(0))
            arch_list = [str(value) for value in torch.cuda.get_arch_list()]
        except Exception:
            capability = None
    target_arch = f"sm_{capability['major']}{capability['minor']}" if capability else ""
    return {
        "available": True,
        "cudaAvailable": cuda_available,
        "version": str(getattr(torch, "__version__", "")),
        "cudaVersion": str(getattr(getattr(torch, "version", None), "cuda", "") or ""),
        "deviceName": device_name,
        "deviceCapability": capability,
        "torchArchList": arch_list,
        "torchKernelSupportsDevice": bool(target_arch and target_arch in arch_list),
    }


def build_report(provider: str) -> dict[str, Any]:
    gpus = nvidia_gpus()
    torch_info = torch_status()
    requires_gpu = provider in GPU_PROVIDERS
    provider_preflight: dict[str, Any] = {}
    if provider in {"trellis", "trellis16", "trellis2"}:
        minimum_vram_mb = (
            TRELLIS2_MINIMUM_VRAM_MB
            if provider == "trellis2"
            else TRELLIS16_MINIMUM_VRAM_MB
            if provider == "trellis16"
            else TRELLIS_MINIMUM_VRAM_MB
        )
        license_env = (
            "RE_CAMP_TRELLIS2_LICENSE_ACK"
            if provider == "trellis2"
            else "RE_CAMP_TRELLIS16_LICENSE_ACK"
            if provider == "trellis16"
            else "RE_CAMP_TRELLIS_LICENSE_ACK"
        )
        maximum_vram = max(
            (gpu.get("memoryMb") or 0 for gpu in gpus),
            default=0,
        )
        license_acknowledged = os.environ.get(license_env, "0") == "1"
        provider_preflight = {
            "minimumVramMb": minimum_vram_mb,
            "maximumVisibleVramMb": maximum_vram or None,
            "vramSufficient": maximum_vram >= minimum_vram_mb,
            "cudaRuntimeVisible": bool(torch_info.get("cudaAvailable")),
            "torchKernelSupportsDevice": bool(
                torch_info.get("torchKernelSupportsDevice")
            ),
            "licenseTermsAcknowledged": license_acknowledged,
            "licenseAcknowledgementEnv": license_env,
            "heavyweightInstallAllowed": False,
        }
        if provider == "trellis16":
            provider_preflight["linuxRuntime"] = platform.system() == "Linux"
        trellis_ready = (
            bool(gpus)
            and torch_info.get("available")
            and torch_info.get("cudaAvailable")
            and torch_info.get("torchKernelSupportsDevice")
            and provider_preflight["vramSufficient"]
            and license_acknowledged
            and (
                provider != "trellis16"
                or provider_preflight.get("linuxRuntime") is True
            )
        )
        if trellis_ready:
            status = "READY_GPU_VISIBLE"
            provider_preflight["heavyweightInstallAllowed"] = True
        else:
            status = "BLOCKED_PROVIDER_PREFLIGHT"
    elif not requires_gpu:
        status = "READY_NO_GPU_REQUIRED"
    elif not gpus:
        status = "BLOCKED_GPU_UNAVAILABLE"
    elif not (
        torch_info.get("available")
        and torch_info.get("cudaAvailable")
        and torch_info.get("torchKernelSupportsDevice")
    ):
        status = "BLOCKED_GPU_UNSUPPORTED"
    else:
        status = "READY_GPU_VISIBLE"
    return {
        "provider": provider,
        "requiresGpu": requires_gpu,
        "status": status,
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "gpuCount": len(gpus),
        "gpus": gpus,
        "torch": torch_info,
        "providerPreflight": provider_preflight,
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
    return 0 if report["status"] not in {
        "BLOCKED_GPU_UNAVAILABLE",
        "BLOCKED_GPU_UNSUPPORTED",
        "BLOCKED_PROVIDER_PREFLIGHT",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
