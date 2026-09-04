#!/usr/bin/env python3
"""Run the official TRELLIS.2 Python example as a one-shot candidate.

The upstream project exposes a Python API rather than a stable CLI.  This
wrapper therefore uses the documented ``Trellis2ImageTo3DPipeline`` API and
refuses to run unless the checkout, preflight, input, and project gates are
valid.  It does not install dependencies, record secrets, or promote output
to Unity/Production.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "75fbf0183001ed9876c8dbb35de6b68552ee08bd"
STRATEGY_ID = "TRELLIS2_SINGLE_VIEW_V001"
MODEL_ID = "microsoft/TRELLIS.2-4B"
MINIMUM_VRAM_MB = 24576


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--input-image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--texture-size", type=int, default=2048)
    parser.add_argument("--decimation-target", type=int, default=100000)
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


def dependency_preflight(repo: Path) -> tuple[bool, str]:
    """Verify imports without loading checkpoints or starting inference."""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import torch; import trellis2; import o_voxel",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (
        "READY_IMPORTS" if result.returncode == 0 else "TRELLIS2_DEPENDENCIES_IMPORT_FAILED"
    )


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.provider_repo.resolve()
    image = args.input_image.resolve()
    output_dir = args.output_dir.resolve()
    preflight_path = args.preflight.resolve()
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    actual_commit = git_head(repo)
    blockers: list[str] = []
    if actual_commit != EXPECTED_COMMIT:
        blockers.append("TRELLIS2_COMMIT_MISMATCH")
    if not image.is_file():
        blockers.append("INPUT_IMAGE_MISSING")
    if preflight.get("provider") != "trellis2":
        blockers.append("TRELLIS2_PREFLIGHT_PROVIDER_MISMATCH")
    if preflight.get("status") != "READY_GPU_VISIBLE":
        blockers.append("PROVIDER_PREFLIGHT_NOT_READY")
    provider_preflight = preflight.get("providerPreflight", {})
    if provider_preflight.get("heavyweightInstallAllowed") is not True:
        blockers.append("HEAVYWEIGHT_INSTALL_NOT_AUTHORIZED")
    if provider_preflight.get("vramSufficient") is not True:
        blockers.append("TRELLIS2_VRAM_INSUFFICIENT")
    if preflight.get("unityInputAllowed") is True or preflight.get("productionPromotionAllowed") is True:
        blockers.append("PROJECT_GATE_ALREADY_OPEN")
    if args.texture_size < 512 or args.texture_size > 4096:
        blockers.append("TEXTURE_SIZE_OUT_OF_RANGE")
    if args.decimation_target < 1000:
        blockers.append("DECIMATION_TARGET_OUT_OF_RANGE")
    return {
        "schemaVersion": "trellis2-one-shot-run-report-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "trellis2",
        "strategyId": STRATEGY_ID,
        "providerRepository": str(repo),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": actual_commit,
        "model": MODEL_ID,
        "inputImage": str(image),
        "preflight": preflight,
        "officialApi": "Trellis2ImageTo3DPipeline",
        "textureSize": args.texture_size,
        "decimationTarget": args.decimation_target,
        "status": "READY_TO_RUN_ONCE" if not blockers else "BLOCKED_PROVIDER_PREFLIGHT",
        "blockers": blockers,
        "actualInference": False,
        "meshOutputs": [],
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def _write_inference_script(args: argparse.Namespace, script_path: Path) -> None:
    output_dir = args.output_dir.resolve()
    image = args.input_image.resolve()
    script_path.write_text(
        "\n".join(
            [
                "import os",
                "os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'",
                "os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'",
                "from pathlib import Path",
                "from PIL import Image",
                "import torch",
                "from trellis2.pipelines import Trellis2ImageTo3DPipeline",
                "import o_voxel",
                f"output_dir = Path({str(output_dir)!r})",
                f"image = Image.open({str(image)!r})",
                f"pipeline = Trellis2ImageTo3DPipeline.from_pretrained({MODEL_ID!r})",
                "pipeline.cuda()",
                "mesh = pipeline.run(image, pipeline_type='512')[0]",
                "mesh.simplify(16777216)",
                "glb = o_voxel.postprocess.to_glb(",
                "    vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,",
                "    coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size,",
                "    aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],",
                f"    decimation_target={_safe_int(args.decimation_target, 100000)},",
                f"    texture_size={_safe_int(args.texture_size, 2048)},",
                "    remesh=True, remesh_band=1, remesh_project=0, verbose=True,",
                ")",
                "output_dir.mkdir(parents=True, exist_ok=True)",
                "glb.export(str(output_dir / 'CH101_trellis2_candidate.glb'), extension_webp=True)",
            ]
        )
        + "\n",
        encoding="utf-8",
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
            report["blockers"].append("TRELLIS2_DEPENDENCIES_IMPORT_FAILED")
        else:
            script_path = output_dir / "trellis2-inference.py"
            _write_inference_script(args, script_path)
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=args.provider_repo.resolve(),
                check=False,
            )
            report["returnCode"] = result.returncode
            report["actualInference"] = result.returncode == 0
            report["meshOutputs"] = sorted(
                str(path.resolve())
                for path in output_dir.glob("*.glb")
                if path.is_file()
            )
            if result.returncode != 0:
                report["status"] = "TRELLIS2_EXECUTION_FAILED"
            elif not report["meshOutputs"]:
                report["status"] = "TRELLIS2_EXECUTION_NO_MESH"
                report["blockers"] = ["MESH_EXTRACTION_OUTPUT_MISSING"]
            else:
                report["status"] = "TRELLIS2_EXECUTED"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY_TO_RUN_ONCE", "TRELLIS2_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
