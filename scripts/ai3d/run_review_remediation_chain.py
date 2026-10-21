#!/usr/bin/env python3
"""Run the opt-in CH101 review remediation chain.

The chain is deliberately review-only: palette assignment, conservative
surface bridge, Blender evaluation, and score reporting are chained without
ever enabling Gate B, Production, or Unity input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-report", action="append", type=Path, default=[])
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--character", required=True)
    parser.add_argument("--tools-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--render-size", type=int, default=256)
    parser.add_argument("--component-rank", type=int, default=1)
    parser.add_argument("--bridge-radius", type=float, default=0.002)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: list[str | Path], env: dict[str, str]) -> None:
    completed = subprocess.run(
        [str(value) for value in command],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed with {completed.returncode}: {' '.join(str(value) for value in command)}\n"
            + completed.stdout[-4000:]
        )


def display_prefix() -> list[str]:
    return ["xvfb-run", "-a"] if shutil.which("xvfb-run") else []


def evaluate_and_score(
    *,
    tools_root: Path,
    reference_manifest: Path,
    contract: Path,
    character: str,
    candidate_id: str,
    candidate_glb: Path,
    integrity_blend: Path,
    output_dir: Path,
    render_size: int,
    env: dict[str, str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation_report = output_dir / "evaluation-report.json"
    normalized_blend = output_dir / f"{candidate_id}_normalized_NOT_PRODUCTION.blend"
    score_report = output_dir / "candidate-score.json"
    blender = shutil.which("blender")
    if not blender:
        raise RuntimeError("BLENDER_NOT_FOUND")
    run_command(
        display_prefix()
        + [
            blender,
            "-b",
            "--python",
            tools_root / "scripts" / "blender" / "evaluate_ai3d_candidate.py",
            "--",
            "--candidate",
            candidate_glb,
            "--character",
            character,
            "--candidate-id",
            candidate_id,
            "--output-dir",
            output_dir,
            "--report",
            evaluation_report,
            "--normalized-blend",
            normalized_blend,
            "--integrity-blend",
            integrity_blend,
            "--render-size",
            str(render_size),
        ],
        env,
    )
    run_command(
        [
            sys.executable,
            tools_root / "scripts" / "ai3d" / "score_candidate_renders.py",
            "--reference-manifest",
            reference_manifest,
            "--evaluation-report",
            evaluation_report,
            "--output",
            score_report,
            "--contract",
            contract,
            "--character",
            character,
        ],
        env,
    )
    return score_report


def main() -> int:
    args = parse_args()
    if args.character != "CH101":
        raise ValueError("review remediation chain is currently restricted to CH101")
    if not args.reference_manifest.is_file() or not args.contract.is_file():
        raise FileNotFoundError("reference manifest or contract is missing")
    if args.render_size < 64 or args.component_rank < 1 or args.bridge_radius <= 0:
        raise ValueError("invalid render size, component rank, or bridge radius")
    args.output_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("BLENDER_USER_CONFIG", str(args.output_root / "blender-config"))
    blender = shutil.which("blender")
    if not blender:
        raise RuntimeError("BLENDER_NOT_FOUND")
    results: list[dict[str, Any]] = []
    for score_path in args.score_report:
        score_path = score_path.resolve()
        score = json.loads(score_path.read_text(encoding="utf-8"))
        source_candidate = Path(score.get("candidatePath", "")).resolve()
        if not source_candidate.is_file():
            raise FileNotFoundError(f"candidatePath missing: {source_candidate}")
        base_id = str(score.get("candidateId", source_candidate.stem))
        palette_id = f"{base_id}-PALETTE"
        palette_dir = args.output_root / palette_id
        palette_blend = palette_dir / f"{palette_id}_NOT_PRODUCTION.blend"
        palette_glb = palette_dir / f"{palette_id}_NOT_PRODUCTION.glb"
        palette_report = palette_dir / "refinement-report.json"
        parent_sha = str(score.get("candidateSha256", "")) or sha256_file(source_candidate)
        run_command(
            display_prefix()
            + [
                blender,
                "-b",
                "--python",
                args.tools_root / "scripts" / "blender" / "refine_ai3d_candidate.py",
                "--",
                "--candidate",
                source_candidate,
                "--character",
                args.character,
                "--output-glb",
                palette_glb,
                "--output-blend",
                palette_blend,
                "--report",
                palette_report,
                "--provider",
                str(score.get("provider", "review")),
                "--attempt",
                str(score.get("attempt", 999)),
                "--parent-sha256",
                parent_sha,
                "--material-mode",
                "palette",
            ],
            env,
        )
        palette_score = evaluate_and_score(
            tools_root=args.tools_root,
            reference_manifest=args.reference_manifest,
            contract=args.contract,
            character=args.character,
            candidate_id=palette_id,
            candidate_glb=palette_glb,
            integrity_blend=palette_blend,
            output_dir=palette_dir,
            render_size=args.render_size,
            env=env,
        )
        bridge_id = f"{palette_id}-BRIDGE"
        bridge_dir = args.output_root / bridge_id
        bridge_blend = bridge_dir / f"{bridge_id}_NOT_PRODUCTION.blend"
        bridge_glb = bridge_dir / f"{bridge_id}_NOT_PRODUCTION.glb"
        bridge_report = bridge_dir / "surface-bridge-report.json"
        run_command(
            display_prefix()
            + [
                blender,
                "-b",
                "--python",
                args.tools_root / "scripts" / "blender" / "bridge_nearest_review_components.py",
                "--",
                "--blend",
                palette_blend,
                "--output-blend",
                bridge_blend,
                "--output-glb",
                bridge_glb,
                "--report",
                bridge_report,
                "--component-rank",
                str(args.component_rank),
                "--sides",
                "6",
                "--radius",
                str(args.bridge_radius),
            ],
            env,
        )
        bridge_score = evaluate_and_score(
            tools_root=args.tools_root,
            reference_manifest=args.reference_manifest,
            contract=args.contract,
            character=args.character,
            candidate_id=bridge_id,
            candidate_glb=bridge_glb,
            integrity_blend=bridge_blend,
            output_dir=bridge_dir,
            render_size=args.render_size,
            env=env,
        )
        results.append(
            {
                "sourceScoreReport": str(score_path),
                "sourceCandidateSha256": parent_sha,
                "paletteScoreReport": str(palette_score),
                "bridgeScoreReport": str(bridge_score),
                "bridgeBlendSha256": sha256_file(bridge_blend),
                "bridgeGlbSha256": sha256_file(bridge_glb),
            }
        )
    report = {
        "status": "REVIEW_REMEDIATION_CHAIN_COMPLETED" if results else "NO_INPUT_SCORE_REPORTS",
        "character": args.character,
        "results": results,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "This chain is opt-in and review-only; it does not approve Gate B or Unity input.",
            "Palette materials are coarse review aids, not final textures.",
            "The surface bridge is heuristic and requires strict visual QA and human review.",
        ],
    }
    report_path = args.output_root / "remediation-chain-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
