#!/usr/bin/env python3
"""Select and run the safe Re:Camp workstream for the visible runtime.

The dispatcher performs no AI inference itself. On a GPU runtime it authorizes
the provider Notebook to continue. Without a GPU it immediately runs the
GPU-independent maintenance workstream instead of installing model packages.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ai3d.colab_runtime_preflight import build_report as build_runtime_report
from run_no_gpu_workstream import build_report as build_no_gpu_report


GPU_PROVIDERS = {"sf3d", "instantmesh", "triposr", "wonder3D", "trellis"}
CONTINUATION_NOTEBOOKS = {
    "sf3d": "notebooks/05_ch101_ai3d_free_autobuild.ipynb",
    "instantmesh": "notebooks/05_ch101_ai3d_free_autobuild.ipynb",
    "triposr": "notebooks/05_ch101_ai3d_free_autobuild.ipynb",
    "tripo": "notebooks/05_ch101_ai3d_free_autobuild.ipynb",
    "wonder3D": "notebooks/06_ch101_wonder3d_multiview_experiment.ipynb",
    "trellis": "notebooks/07_ch101_hybrid_quality_strategies.ipynb",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatically choose the GPU, non-GPU provider, or No-GPU workstream."
    )
    parser.add_argument(
        "--provider",
        choices=("tripo", *sorted(GPU_PROVIDERS)),
        default="sf3d",
    )
    parser.add_argument("--art-root", type=Path, default=ROOT.parent / "re-camp-art")
    parser.add_argument(
        "--character",
        choices=("CH101", "CH102", "CH103", "CH104", "CH105"),
        default="CH101",
    )
    parser.add_argument("--skip-reference", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--force-mode",
        choices=("auto", "gpu", "no-gpu"),
        default="auto",
        help="Testing/recovery override. auto is the normal mode.",
    )
    return parser.parse_args()


def select_workstream(
    provider: str,
    runtime_preflight: dict[str, Any],
    force_mode: str = "auto",
) -> str:
    """Return GPU, NO_GPU, NON_GPU_PROVIDER, or BLOCKED_FORCED_GPU."""

    if force_mode == "no-gpu":
        return "NO_GPU"
    if provider == "tripo":
        return "NON_GPU_PROVIDER"
    if runtime_preflight.get("status") == "READY_GPU_VISIBLE":
        torch_info = runtime_preflight.get("torch")
        if isinstance(torch_info, dict) and torch_info.get("torchKernelSupportsDevice") is False:
            return "BLOCKED_FORCED_GPU" if force_mode == "gpu" else "NO_GPU"
        return "GPU"
    if force_mode == "gpu":
        return "BLOCKED_FORCED_GPU"
    return "NO_GPU"


def build_adaptive_report(
    args: argparse.Namespace,
    *,
    runtime_preflight: dict[str, Any] | None = None,
    no_gpu_builder: Callable[[argparse.Namespace], dict[str, Any]] = build_no_gpu_report,
) -> dict[str, Any]:
    preflight = runtime_preflight or build_runtime_report(args.provider)
    character = getattr(args, "character", "CH101")
    selected = select_workstream(args.provider, preflight, args.force_mode)
    report: dict[str, Any] = {
        "workstream": "ADAPTIVE_GPU_NO_GPU",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "character": character,
        "forceMode": args.force_mode,
        "runtimePreflight": preflight,
        "selectedWorkstream": selected,
        "continuationNotebook": CONTINUATION_NOTEBOOKS[args.provider],
        "actualInference": False,
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }

    if selected == "GPU":
        report.update(
            {
                "status": "READY_GPU_WORKSTREAM",
                "gpuExecutionAllowed": True,
                "nextAction": "CONTINUE_PROVIDER_NOTEBOOK",
                "completedWorkstream": None,
            }
        )
        return report

    if selected == "NON_GPU_PROVIDER":
        report.update(
            {
                "status": "READY_NON_GPU_PROVIDER",
                "gpuExecutionAllowed": False,
                "nextAction": "CONTINUE_TRIPO_API_OR_DRY_RUN",
                "completedWorkstream": None,
            }
        )
        return report

    if selected == "BLOCKED_FORCED_GPU":
        report.update(
            {
                "status": "BLOCKED_FORCED_GPU_UNAVAILABLE",
                "gpuExecutionAllowed": False,
                "nextAction": "REMOVE_FORCE_MODE_OR_RECONNECT_GPU",
                "completedWorkstream": None,
            }
        )
        return report

    no_gpu_args = argparse.Namespace(
        art_root=args.art_root,
        character=character,
        skip_reference=args.skip_reference,
        output=None,
    )
    no_gpu_report = no_gpu_builder(no_gpu_args)
    no_gpu_failed = no_gpu_report.get("status") == "FAIL"
    report.update(
        {
            "status": "FAIL" if no_gpu_failed else "ADAPTIVE_NO_GPU_COMPLETED",
            "gpuExecutionAllowed": False,
            "nextAction": (
                "FIX_NO_GPU_VALIDATION_FAILURES"
                if no_gpu_failed
                else "RETRY_ADAPTIVE_RUNNER_WHEN_GPU_RETURNS"
            ),
            "completedWorkstream": no_gpu_report,
        }
    )
    return report


def main() -> int:
    args = parse_args()
    report = build_adaptive_report(args)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if report["status"] in {"FAIL", "BLOCKED_FORCED_GPU_UNAVAILABLE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
