"""Reconstruct a lost SPAR3D artifact once, without retrying quality selection.

Installation and secret loading belong to the Kaggle setup cell. This runner
checks the recorded input hash and invokes diagnostic-only inference. It never
registers/ranks a new candidate or treats a recreated file as the original.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .common import sha256_file, read_json, write_json
except ImportError:
    from common import sha256_file, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_INPUT_SHA = "d775f8c4b2e443908f61a4ceff41cc9bb11ed3ed0a88680955cfe708f3003bf2"
ORIGINAL_MESH_SHA = "2807ba362917373e2ee632da6847165eb92472b237a704d5a6ad439e7051a99f"
GATES = dict(sourceStatus="AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
             gateB="PENDING_HUMAN_REVIEW", unityInputAllowed=False,
             productionPromotionAllowed=False)


def prepare_input(source_path: Path, output_path: Path) -> None:
    # Exact preprocessing recovered from the 2026-09-06 Notebook execution.
    from PIL import Image, ImageChops
    with Image.open(source_path) as opened:
        source = opened.convert("RGBA")
    diff = ImageChops.difference(source.convert("RGB"), Image.new("RGB", source.size, "white"))
    bbox = diff.convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bbox:
        raise ValueError("REFERENCE_FOREGROUND_MISSING")
    left, top, right, bottom = bbox
    padx, pady = max(24, int((right-left)*.08)), max(24, int((bottom-top)*.06))
    crop = source.crop((max(0,left-padx), max(0,top-pady),
                        min(source.width,right+padx), min(source.height,bottom+pady)))
    scale = min(992/crop.width, 992/crop.height)
    resized = crop.resize((max(1,round(crop.width*scale)), max(1,round(crop.height*scale))),
                          Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (1024,1024), (255,255,255,255))
    canvas.alpha_composite(resized, ((1024-resized.width)//2, (1024-resized.height)//2))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front-image", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider-repo", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "recovery-attempt.json"
    if marker.exists():
        raise RuntimeError("RECOVERY_ALREADY_ATTEMPTED: preserve the existing outputs")
    image = out / "CH101_front_reference_conditioned.png"
    prepare_input(args.front_image, image)
    input_hash = sha256_file(image)
    report = dict(schemaVersion="spar3d-lost-artifact-recovery-v001",
                  reason="PREVIOUS_KAGGLE_ARTIFACT_NOT_PERSISTED",
                  inputSha256=input_hash, expectedInputSha256=ORIGINAL_INPUT_SHA,
                  expectedOriginalMeshSha256=ORIGINAL_MESH_SHA,
                  qualityRetry=False, candidateRegistrationAllowed=False,
                  actualInference=False, **GATES)
    if input_hash != ORIGINAL_INPUT_SHA:
        report["status"] = "BLOCKED_RECOVERY_INPUT_HASH_MISMATCH"
        write_json(out / "recovery-report.json", report)
        print(json.dumps(report))
        return 2
    if not args.execute:
        report["status"] = "RECOVERY_INPUT_VERIFIED_NOT_EXECUTED"
        write_json(out / "recovery-report.json", report)
        print(json.dumps(report))
        return 0
    if not args.provider_repo or not args.preflight:
        raise ValueError("provider-repo and preflight are required for execution")
    preflight = read_json(args.preflight)
    if (preflight.get("status") != "READY_GPU_VISIBLE" or
            preflight.get("providerPreflight", {}).get("heavyweightInstallAllowed") is not True):
        report["status"] = "BLOCKED_PROVIDER_PREFLIGHT"
        write_json(out / "recovery-report.json", report)
        print(json.dumps(report))
        return 2
    write_json(marker, dict(status="ONE_DIAGNOSTIC_RECOVERY_RESERVED", **GATES))
    env = os.environ.copy()
    env.setdefault("SPAR3D_DECODER_CHUNK_SIZE", "8192")
    env.setdefault("SPAR3D_ATTENTION_QUERY_CHUNK_SIZE", "256")
    provider_report = out / "provider-report.json"
    command = [sys.executable, str(ROOT / "scripts/ai3d/run_spar3d_candidate.py"),
               "--provider-repo", str(args.provider_repo), "--input-image", str(image),
               "--output-dir", str(out / "provider-output"), "--preflight", str(args.preflight),
               "--output-report", str(provider_report), "--texture-resolution", "512",
               "--target-count", "20000", "--strategy-id", "SPAR3D_REFERENCE_CONDITIONED_V001",
               "--diagnostic-only", "--execute"]
    result = subprocess.run(command, env=env, check=False)
    payload = read_json(provider_report) if provider_report.is_file() else {}
    report.update(actualInference=payload.get("actualInference", False), returnCode=result.returncode,
                  providerStatus=payload.get("status", "NO_PROVIDER_REPORT"),
                  providerCommit=payload.get("providerCommitActual"))
    meshes = [Path(p) for p in payload.get("meshOutputs", [])]
    if (result.returncode == 0 and payload.get("status") == "SPAR3D_DIAGNOSTIC_EXECUTED"
            and len(meshes) == 1 and meshes[0].is_file() and meshes[0].stat().st_size > 0):
        mesh_hash = sha256_file(meshes[0])
        report.update(status="RECOVERY_ARTIFACT_CREATED_NOT_QUALITY_APPROVED",
                      meshSha256=mesh_hash, meshPath=str(meshes[0]),
                      byteIdenticalToPrevious=mesh_hash == ORIGINAL_MESH_SHA)
    else:
        report["status"] = "RECOVERY_FAILED_NO_MESH"
    write_json(out / "recovery-report.json", report)
    archive = Path(shutil.make_archive(str(out), "zip", root_dir=out))
    # An archive on a temporary disk is NOT durable publication.
    archive_record = dict(archive=str(archive), archiveSha256=sha256_file(archive),
                          persistenceStatus="LOCAL_DOWNLOAD_OR_DURABLE_UPLOAD_REQUIRED", **GATES)
    write_json(out.with_suffix(".archive.json"), archive_record)
    print(json.dumps(dict(report=report, archive=archive_record), indent=2))
    return 0 if report["status"] == "RECOVERY_ARTIFACT_CREATED_NOT_QUALITY_APPROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
