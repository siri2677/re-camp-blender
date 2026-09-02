#!/usr/bin/env python3
"""Run the pinned PartCrafter part-level inference once.

PartCrafter is selected as the low-memory CH101 path because it emits a
compositional scene with separate mesh parts.  This wrapper only orchestrates
the official inference script; it does not install packages, store tokens, or
promote the result to Production/Unity.  Part names are deliberately treated
as unlabeled until human review: the provider returns parts, not reliable
CH101 body/hair/outfit/equipment labels.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "3d773bf02fad51c7ab31a5615573fec93b287b30"
STRATEGY_ID = "PARTCRAFTER_PART_LEVEL_V001"
MODEL_ID = "wgsxm/PartCrafter"
MINIMUM_VRAM_MB = 8192


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--input-image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--num-parts", type=int, default=6)
    parser.add_argument("--num-tokens", type=int, default=1024)
    parser.add_argument("--num-inference-steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=101001)
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
    """Import only; never download weights or start inference."""

    imports = (
        "import torch; import trimesh; import accelerate; "
        "from src.pipelines.pipeline_partcrafter import PartCrafterPipeline"
    )
    result = subprocess.run(
        [sys.executable, "-c", imports],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (
        "READY_IMPORTS" if result.returncode == 0 else "PARTCRAFTER_DEPENDENCIES_IMPORT_FAILED"
    )


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.provider_repo.resolve()
    image = args.input_image.resolve()
    preflight_path = args.preflight.resolve()
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    actual_commit = git_head(repo)
    blockers: list[str] = []
    if actual_commit != EXPECTED_COMMIT:
        blockers.append("PARTCRAFTER_COMMIT_MISMATCH")
    if not image.is_file():
        blockers.append("INPUT_IMAGE_MISSING")
    if preflight.get("provider") != "partcrafter":
        blockers.append("PARTCRAFTER_PREFLIGHT_PROVIDER_MISMATCH")
    if preflight.get("status") != "READY_GPU_VISIBLE":
        blockers.append("PROVIDER_PREFLIGHT_NOT_READY")
    provider_preflight = preflight.get("providerPreflight", {})
    if provider_preflight.get("heavyweightInstallAllowed") is not True:
        blockers.append("HEAVYWEIGHT_INSTALL_NOT_AUTHORIZED")
    if provider_preflight.get("vramSufficient") is not True:
        blockers.append("PARTCRAFTER_VRAM_INSUFFICIENT")
    if provider_preflight.get("licenseTermsAcknowledged") is not True:
        blockers.append("PARTCRAFTER_LICENSE_ACK_REQUIRED")
    if preflight.get("unityInputAllowed") is True or preflight.get("productionPromotionAllowed") is True:
        blockers.append("PROJECT_GATE_ALREADY_OPEN")
    if not 4 <= args.num_parts <= 16:
        blockers.append("NUM_PARTS_OUT_OF_RANGE")
    if not 256 <= args.num_tokens <= 2048:
        blockers.append("NUM_TOKENS_OUT_OF_RANGE")
    if args.num_inference_steps < 1:
        blockers.append("INFERENCE_STEPS_OUT_OF_RANGE")
    return {
        "schemaVersion": "partcrafter-one-shot-run-report-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "partcrafter",
        "strategyId": STRATEGY_ID,
        "providerRepository": str(repo),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": actual_commit,
        "model": MODEL_ID,
        "inputImage": str(image),
        "preflight": preflight,
        "officialEntrypoint": "scripts/inference_partcrafter.py",
        "memoryProfile": "8GB_CLASS_PART_LEVEL",
        "numParts": _safe_int(args.num_parts, 6),
        "numTokens": _safe_int(args.num_tokens, 1024),
        "numInferenceSteps": _safe_int(args.num_inference_steps, 50),
        "guidanceScale": _safe_float(args.guidance_scale, 7.0),
        "seed": _safe_int(args.seed, 101001),
        "rmbgEnabled": True,
        "semanticPartLabels": "UNLABELED_PROVIDER_PARTS_PENDING_HUMAN_MAPPING",
        "status": "READY_TO_RUN_ONCE" if not blockers else "BLOCKED_PROVIDER_PREFLIGHT",
        "blockers": blockers,
        "actualInference": False,
        "meshOutputs": [],
        "partOutputs": [],
        "semanticComponentAudit": {
            "status": "PENDING_HUMAN_MAPPING",
            "providerPartCount": _safe_int(args.num_parts, 6),
            "expectedReviewGroups": ["body_face", "hair", "outfit", "equipment"],
            "labelsAreInferred": False,
        },
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def _find_outputs(output_dir: Path) -> tuple[list[Path], list[Path], Path | None]:
    object_paths = sorted(
        path for path in output_dir.glob("**/object.glb") if path.is_file()
    )
    if not object_paths:
        return [], [], None
    object_path = object_paths[-1]
    part_paths = sorted(
        path for path in object_path.parent.glob("part_*.glb") if path.is_file()
    )
    manifest = object_path.parent / "manifest.json"
    return [object_path], part_paths, manifest if manifest.is_file() else None


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
            report["blockers"].append("PARTCRAFTER_DEPENDENCIES_IMPORT_FAILED")
        else:
            tag = "CH101_PARTCRAFTER_V001"
            command = [
                sys.executable,
                str(args.provider_repo.resolve() / "scripts" / "inference_partcrafter.py"),
                "--image_path",
                str(args.input_image.resolve()),
                "--num_parts",
                str(args.num_parts),
                "--output_dir",
                str(output_dir),
                "--tag",
                tag,
                "--seed",
                str(args.seed),
                "--num_tokens",
                str(args.num_tokens),
                "--num_inference_steps",
                str(args.num_inference_steps),
                "--guidance_scale",
                str(args.guidance_scale),
                "--rmbg",
            ]
            report["command"] = command
            result = subprocess.run(command, cwd=args.provider_repo.resolve(), check=False)
            report["returnCode"] = result.returncode
            mesh_outputs, part_outputs, manifest = _find_outputs(output_dir)
            report["actualInference"] = result.returncode == 0
            report["meshOutputs"] = [str(path.resolve()) for path in mesh_outputs]
            report["partOutputs"] = [str(path.resolve()) for path in part_outputs]
            report["providerManifest"] = str(manifest.resolve()) if manifest else ""
            report["observedPartCount"] = len(part_outputs)
            report["semanticComponentAudit"]["status"] = (
                "PENDING_HUMAN_MAPPING" if len(part_outputs) >= 4 else "FAIL"
            )
            if result.returncode != 0:
                report["status"] = "PARTCRAFTER_EXECUTION_FAILED"
            elif not mesh_outputs:
                report["status"] = "PARTCRAFTER_EXECUTION_NO_MESH"
                report["blockers"] = ["MESH_OUTPUT_MISSING"]
            elif len(part_outputs) < 4:
                report["status"] = "PARTCRAFTER_PART_COUNT_INSUFFICIENT"
                report["blockers"] = ["SEMANTIC_PART_OUTPUT_COUNT_BELOW_FOUR"]
            else:
                report["status"] = "PARTCRAFTER_EXECUTED"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY_TO_RUN_ONCE", "PARTCRAFTER_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
