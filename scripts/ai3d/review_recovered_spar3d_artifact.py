"""Hash-checked, standalone Blender review; no notebook-global dependencies."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .common import load_contract, require_reference_manifest, sha256_file, write_json, candidate_gate_fields
except ImportError:
    from common import load_contract, require_reference_manifest, sha256_file, write_json, candidate_gate_fields

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = "CH101_REVIEW_SUBJECT_BOUNDS_TEXTURE_V003"
PROFILE_STRATEGY = "CH101_REFERENCE_TWO_AXIS_PROFILE_CORRECTION_V002"


def execute(args) -> dict:
    strategy = PROFILE_STRATEGY if getattr(args, 'fit_reference_profile', False) else STRATEGY
    contract = load_contract(args.contract, "CH101")
    gates = candidate_gate_fields(contract)
    if not args.mesh.is_file() or sha256_file(args.mesh) != args.mesh_sha256:
        raise ValueError("SOURCE_MESH_MISSING_OR_SHA256_MISMATCH")
    if sha256_file(args.reference_manifest) != args.reference_sha256:
        raise ValueError("REFERENCE_MANIFEST_SHA256_MISMATCH")
    references = require_reference_manifest(args.reference_manifest, contract)
    if args.output_dir.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS: preserve previous evidence")
    blender = args.blender or shutil.which("blender")
    if not blender:
        raise ValueError("BLOCKED_BLENDER_RUNTIME_UNAVAILABLE")
    args.output_dir.mkdir(parents=True)
    out = args.output_dir.resolve()
    report = dict(status="REVIEW_STARTED", strategyId=strategy,
                  sourceMeshSha256=args.mesh_sha256, referenceManifestSha256=args.reference_sha256,
                  artCommit=contract["artLock"]["commit"], **gates)
    write_json(out / "review-run.json", report)
    env = os.environ.copy()
    env["RE_CAMP_REVIEW_RENDER_ENGINE"] = "EEVEE"
    prefix = ["xvfb-run", "-a"] if shutil.which("xvfb-run") else []

    def run(command):
        result = subprocess.run([str(x) for x in command], env=env, capture_output=True, text=True, errors="replace")
        if result.returncode:
            # Never persist raw subprocess output or environment values.
            raise RuntimeError("REVIEW_STAGE_FAILED:" + str(command[0]) + ":" + str(result.returncode))

    def blender_script(name, *options):
        run(prefix + [blender, "-b", "--python-exit-code", "1", "--python",
                      ROOT / "scripts/blender" / name, "--", *options])

    try:
        gate_command = [sys.executable, ROOT / "scripts/ai3d/quality_progress_gate.py",
                        "--provider", "spar3d", "--strategy-id", strategy,
                        "--score-dir", out.parent, "--output", out / "quality-progress.json"]
        for record in sorted((ROOT / "docs/records/ch101-ai3d").glob("*.json")):
            gate_command += ["--history-record", record]
        run(gate_command)
        refined = out / "refined_NOT_PRODUCTION.blend"
        transport = out / "refined.glb"
        refine_report = out / "refinement-report.json"
        blender_script("refine_ai3d_candidate.py", "--candidate", args.mesh,
                       "--output-glb", transport, "--output-blend", refined,
                       "--report", refine_report, "--provider", "spar3d", "--attempt", "1",
                       "--parent-sha256", args.mesh_sha256, "--material-mode", "preserve")
        payload = json.loads(refine_report.read_text(encoding="utf-8"))
        transport = Path(payload.get("refinedTransportPath") or transport)
        normalized = out / "source_normalized_NOT_PRODUCTION.blend"
        blender_script("evaluate_ai3d_candidate.py", "--candidate", transport,
                       "--candidate-id", "CH101-RECOVERED-SOURCE", "--output-dir", out / "baseline",
                       "--report", out / "baseline-evaluation.json", "--normalized-blend", normalized,
                       "--integrity-blend", refined)
        if getattr(args, 'fit_reference_profile', False):
            # Both axes use the same fixed conservative strength; no score-driven tuning.
            for axis, view in (('neg_y', 'front'), ('pos_x', 'right')):
                fitted = out / f'{view}_fitted_NOT_PRODUCTION.blend'
                transport = out / f'{view}_fitted.glb'
                blender_script('fit_review_silhouette.py', '--blend', refined,
                               '--reference-image', references['views'][view]['path'],
                               '--front-axis', axis, '--strength', '.35',
                               '--output-blend', fitted, '--output-glb', transport,
                               '--report', out / f'{view}-fit-report.json')
                refined = fitted
            normalized = refined
        masked = out / "CH101_WorldspaceMasked_NOT_PRODUCTION.blend"
        blender_script("apply_review_multiview_textures.py", "--input-blend", normalized,
                       "--front-image", references["views"]["front"]["path"],
                       "--right-image", references["views"]["right"]["path"],
                       "--back-image", references["views"]["back"]["path"],
                       "--output-blend", masked, "--report", out / "texture-report.json")
        evaluation = out / "evaluation-report.json"
        blender_script("evaluate_ai3d_candidate.py", "--candidate", transport,
                       "--candidate-id", strategy, "--strategy-id", strategy,
                       "--output-dir", out, "--report", evaluation, "--integrity-blend", refined,
                       "--reuse-normalized-blend", masked,
                       "--normalized-blend", out / "CH101_Review_NOT_PRODUCTION.blend")
        score = out / "candidate-score.json"
        run([sys.executable, ROOT / "scripts/ai3d/score_candidate_renders.py",
             "--reference-manifest", args.reference_manifest, "--evaluation-report", evaluation,
             "--output", score, "--contract", args.contract, "--character", "CH101"])
        assisted = out / "assisted-visual-review.json"
        run([sys.executable, ROOT / "scripts/ai3d/build_assisted_visual_review.py",
             "--score-report", score, "--output", assisted, "--contract", args.contract])
        run([sys.executable, ROOT / "scripts/ai3d/rank_candidates.py", "--score-report", score,
             "--assisted-visual-review", assisted, "--output", out / "ranking.json",
             "--contract", args.contract])
        report.update(status="REVIEW_EVIDENCE_GENERATED_NOT_APPROVED",
                      semanticValidation="PENDING_REAL_MESH_AND_VISUAL_INSPECTION")
    except (ValueError, RuntimeError) as exc:
        report.update(status="REVIEW_FAILED", failureReason=str(exc))
    write_json(out / "review-run.json", report)
    manifest = dict(files=[dict(path=str(p.relative_to(out)), sha256=sha256_file(p), bytes=p.stat().st_size)
                           for p in sorted(out.rglob("*")) if p.is_file()], **gates)
    write_json(out / "files-sha256.json", manifest)
    archive = Path(shutil.make_archive(str(out), "zip", root_dir=out))
    report.update(archive=str(archive), archiveSha256=sha256_file(archive),
                  persistenceStatus="DOWNLOAD_AND_VERIFY_OUTSIDE_KAGGLE_REQUIRED")
    write_json(out.with_suffix(".archive.json"), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--mesh-sha256", required=True)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=ROOT / "contracts/ch101_ai3d_free_pipeline_v001.json")
    parser.add_argument("--blender")
    parser.add_argument('--fit-reference-profile', action='store_true',
                        help='One-shot two-axis geometry correction using the verified bottom-up profile fit.')
    args = parser.parse_args()
    report = execute(args)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "REVIEW_EVIDENCE_GENERATED_NOT_APPROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
