#!/usr/bin/env python3
"""Run the official original TRELLIS API as a one-shot 16 GB-class candidate.

This is deliberately a separate strategy from the older 24 GB TRELLIS lane
and from TRELLIS.2.  It uses the pinned upstream ``example.py`` API, keeps the
memory profile explicit, and refuses to alter the project's review-only gates.
The wrapper does not install dependencies or record credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "442aa1e1afb9014e80681d3bf604e8d728a86ee7"
STRATEGY_ID = "TRELLIS_SINGLE_VIEW_16GB_V002"
MODEL_ID = "microsoft/TRELLIS-image-large"
MINIMUM_VRAM_MB = 16384
MESH_SUFFIXES = {".obj", ".ply", ".glb", ".gltf"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--input-image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--simplify", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--attention-backend",
        default=os.environ.get("RE_CAMP_TRELLIS16_ATTN_BACKEND", ""),
        help="Optional upstream ATTN_BACKEND value, for example xformers.",
    )
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


def dependency_preflight(repo: Path, attention_backend: str = "") -> tuple[bool, str]:
    """Import only; never load a checkpoint or start inference."""

    imports = "import torch; import trellis; from trellis.utils import postprocessing_utils"
    if attention_backend == "xformers":
        imports += "; import xformers"
    result = subprocess.run(
        [sys.executable, "-c", imports],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (
        "READY_IMPORTS" if result.returncode == 0 else "TRELLIS16_DEPENDENCIES_IMPORT_FAILED"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.provider_repo.resolve()
    image = args.input_image.resolve()
    preflight = json.loads(args.preflight.resolve().read_text(encoding="utf-8"))
    actual_commit = git_head(repo)
    blockers: list[str] = []
    if actual_commit != EXPECTED_COMMIT:
        blockers.append("TRELLIS16_COMMIT_MISMATCH")
    if not image.is_file():
        blockers.append("INPUT_IMAGE_MISSING")
    if preflight.get("provider") != "trellis16":
        blockers.append("TRELLIS16_PREFLIGHT_PROVIDER_MISMATCH")
    if preflight.get("status") != "READY_GPU_VISIBLE":
        blockers.append("PROVIDER_PREFLIGHT_NOT_READY")
    provider_preflight = preflight.get("providerPreflight", {})
    if provider_preflight.get("heavyweightInstallAllowed") is not True:
        blockers.append("HEAVYWEIGHT_INSTALL_NOT_AUTHORIZED")
    if provider_preflight.get("vramSufficient") is not True:
        blockers.append("TRELLIS16_VRAM_INSUFFICIENT")
    if provider_preflight.get("linuxRuntime") is not True:
        blockers.append("TRELLIS16_LINUX_RUNTIME_REQUIRED")
    if preflight.get("unityInputAllowed") is True or preflight.get("productionPromotionAllowed") is True:
        blockers.append("PROJECT_GATE_ALREADY_OPEN")
    if args.texture_size < 512 or args.texture_size > 2048:
        blockers.append("TEXTURE_SIZE_OUT_OF_RANGE")
    if not 0.0 <= args.simplify <= 1.0:
        blockers.append("SIMPLIFY_OUT_OF_RANGE")
    return {
        "schemaVersion": "trellis16-one-shot-run-report-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "trellis16",
        "strategyId": STRATEGY_ID,
        "providerRepository": str(repo),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": actual_commit,
        "model": MODEL_ID,
        "inputImage": str(image),
        "preflight": preflight,
        "officialApi": "TrellisImageTo3DPipeline",
        "officialExample": "example.py",
        "memoryProfile": "16GB_CLASS_TIGHT",
        "textureSize": _safe_int(args.texture_size, 1024),
        "simplify": _safe_float(args.simplify, 0.95),
        "seed": _safe_int(args.seed, 1),
        "attentionBackend": args.attention_backend or "UPSTREAM_DEFAULT",
        "status": "READY_TO_RUN_ONCE" if not blockers else "BLOCKED_PROVIDER_PREFLIGHT",
        "blockers": blockers,
        "actualInference": False,
        "meshOutputs": [],
        "meshSha256": {},
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def _write_inference_script(args: argparse.Namespace, script_path: Path) -> None:
    output_dir = args.output_dir.resolve()
    image = args.input_image.resolve()
    attention_backend = args.attention_backend.strip()
    attention_line = (
        f"os.environ['ATTN_BACKEND'] = {attention_backend!r}"
        if attention_backend
        else "# Use the upstream default attention backend."
    )
    script_path.write_text(
        "\n".join(
            [
                "import os",
                "os.environ['SPCONV_ALGO'] = 'native'",
                attention_line,
                "from pathlib import Path",
                "from PIL import Image",
                "from trellis.pipelines import TrellisImageTo3DPipeline",
                "from trellis.utils import postprocessing_utils",
                f"output_dir = Path({str(output_dir)!r})",
                f"image = Image.open({str(image)!r})",
                f"pipeline = TrellisImageTo3DPipeline.from_pretrained({MODEL_ID!r})",
                "pipeline.cuda()",
                f"outputs = pipeline.run(image, seed={_safe_int(args.seed, 1)})",
                "glb = postprocessing_utils.to_glb(",
                "    outputs['gaussian'][0],",
                "    outputs['mesh'][0],",
                f"    simplify={_safe_float(args.simplify, 0.95)!r},",
                f"    texture_size={_safe_int(args.texture_size, 1024)},",
                ")",
                "output_dir.mkdir(parents=True, exist_ok=True)",
                "glb.export(str(output_dir / 'CH101_trellis16_candidate.glb'))",
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
        imports_ready, dependency_status = dependency_preflight(
            args.provider_repo.resolve(), args.attention_backend.strip()
        )
        report["dependencyPreflight"] = dependency_status
        if not imports_ready:
            report["status"] = "BLOCKED_PROVIDER_DEPENDENCY_PREFLIGHT"
            report["blockers"].append("TRELLIS16_DEPENDENCIES_IMPORT_FAILED")
        else:
            script_path = output_dir / "trellis16-inference.py"
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
                for path in output_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in MESH_SUFFIXES
            )
            report["meshSha256"] = {
                path: _sha256(Path(path)) for path in report["meshOutputs"]
            }
            if result.returncode != 0:
                report["status"] = "TRELLIS16_EXECUTION_FAILED"
            elif not report["meshOutputs"]:
                report["status"] = "TRELLIS16_EXECUTION_NO_MESH"
                report["blockers"] = ["MESH_EXTRACTION_OUTPUT_MISSING"]
            else:
                report["status"] = "TRELLIS16_EXECUTED"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY_TO_RUN_ONCE", "TRELLIS16_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
