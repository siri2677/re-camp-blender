#!/usr/bin/env python3
"""Record one SPAR3D mesh artifact without opening production gates.

The Kaggle runtime is ephemeral, so the provider report must be converted into
an explicit, hash-addressed handoff before the session ends.  This module does
not score or approve the mesh; it only proves that the pinned run produced one
non-empty file and that all provenance and review gates remain safe.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )
except ImportError:  # Direct execution from a Kaggle checkout.
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )


EXPECTED_PROVIDER = "spar3d"
EXPECTED_STRATEGY = "SPAR3D_SINGLE_VIEW_V001"
EXPECTED_RUN_STATUS = "SPAR3D_EXECUTED"
EXPECTED_SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
EXPECTED_GATE_B = "PENDING_HUMAN_REVIEW"


def _require_locked_gates(payload: dict[str, Any], label: str) -> None:
    if payload.get("sourceStatus") != EXPECTED_SOURCE_STATUS:
        raise ValueError(f"{label} sourceStatus must remain review-only")
    if payload.get("gateB") != EXPECTED_GATE_B:
        raise ValueError(f"{label} gateB must remain pending")
    if payload.get("unityInputAllowed") is not False:
        raise ValueError(f"{label} cannot enable Unity input")
    if payload.get("productionPromotionAllowed") is not False:
        raise ValueError(f"{label} cannot enable production promotion")


def _resolve_single_mesh(report: dict[str, Any]) -> tuple[Path, str]:
    outputs = report.get("meshOutputs")
    if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], str):
        raise ValueError("SPAR3D artifact must contain exactly one meshOutputs entry")
    mesh = Path(outputs[0]).resolve()
    if not mesh.is_file() or mesh.stat().st_size <= 0:
        raise FileNotFoundError(f"SPAR3D mesh artifact is missing or empty: {mesh}")
    recorded_sha256 = report.get("meshSha256")
    if not isinstance(recorded_sha256, str) or len(recorded_sha256) != 64:
        raise ValueError("SPAR3D meshSha256 is required")
    actual_sha256 = sha256_file(mesh)
    if actual_sha256 != recorded_sha256:
        raise ValueError("SPAR3D mesh SHA256 mismatch")
    return mesh, actual_sha256


def _validate_candidate_manifest(
    path: Path,
    *,
    contract: dict[str, Any],
    reference_sha256: str,
) -> dict[str, Any]:
    manifest = read_json(path)
    _require_locked_gates(manifest, "candidate manifest")
    if manifest.get("character") != contract["character"]:
        raise ValueError("candidate manifest character mismatch")
    if manifest.get("provider") != EXPECTED_PROVIDER:
        raise ValueError("candidate manifest provider mismatch")
    if manifest.get("strategyId") != EXPECTED_STRATEGY:
        raise ValueError("candidate manifest strategy mismatch")
    if manifest.get("referenceManifestSha256") != reference_sha256:
        raise ValueError("candidate manifest reference SHA256 mismatch")
    if manifest.get("artCommit") != contract["artLock"]["commit"]:
        raise ValueError("candidate manifest art commit mismatch")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ValueError("candidate manifest must contain exactly one candidate")
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        raise ValueError("candidate manifest candidate entry must be an object")
    _require_locked_gates(candidate, "candidate entry")
    model_path = Path(str(candidate.get("modelPath", ""))).resolve()
    if not model_path.is_file() or model_path.stat().st_size <= 0:
        raise FileNotFoundError(f"registered candidate model is missing or empty: {model_path}")
    recorded_sha256 = candidate.get("sha256")
    if recorded_sha256 != sha256_file(model_path):
        raise ValueError("registered candidate SHA256 mismatch")
    return manifest


def build_artifact_record(
    *,
    run_report_path: Path,
    reference_manifest_path: Path,
    output: Path,
    tools_commit: str,
    art_commit: str,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    character: str = "CH101",
    candidate_manifest_path: Path | None = None,
) -> dict[str, Any]:
    report = read_json(run_report_path.resolve())
    contract = load_contract(contract_path, character)
    _require_locked_gates(report, "SPAR3D run report")
    if report.get("provider") != EXPECTED_PROVIDER:
        raise ValueError("SPAR3D run report provider mismatch")
    if report.get("strategyId") != EXPECTED_STRATEGY:
        raise ValueError("SPAR3D run report strategy mismatch")
    if report.get("status") != EXPECTED_RUN_STATUS:
        raise ValueError(
            f"SPAR3D artifact recording requires {EXPECTED_RUN_STATUS}, got {report.get('status')!r}"
        )
    if report.get("actualInference") is not True:
        raise ValueError("SPAR3D artifact must come from actual inference")

    expected_provider_commit = (
        contract.get("experimentalProviders", {}).get(EXPECTED_PROVIDER, {}).get("commit", "")
    )
    if report.get("providerCommitActual") != expected_provider_commit:
        raise ValueError("SPAR3D provider commit mismatch")
    if not isinstance(tools_commit, str) or len(tools_commit) != 40:
        raise ValueError("tools commit must be a 40-character Git commit")
    if art_commit != contract["artLock"]["commit"]:
        raise ValueError("art commit does not match the locked contract")

    reference_manifest = reference_manifest_path.resolve()
    require_reference_manifest(reference_manifest, contract)
    reference_sha256 = sha256_file(reference_manifest)
    mesh, mesh_sha256 = _resolve_single_mesh(report)

    candidate_record: dict[str, Any] | None = None
    candidate_sha256 = ""
    if candidate_manifest_path is not None:
        candidate_path = candidate_manifest_path.resolve()
        candidate_record = _validate_candidate_manifest(
            candidate_path,
            contract=contract,
            reference_sha256=reference_sha256,
        )
        candidate_sha256 = sha256_file(candidate_path)

    provider_commit = report["providerCommitActual"]
    record = {
        "schemaVersion": "spar3d-artifact-handoff-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "character": character,
        "provider": EXPECTED_PROVIDER,
        "strategyId": EXPECTED_STRATEGY,
        "status": (
            "SPAR3D_CANDIDATE_REGISTERED_REVIEW_ONLY"
            if candidate_record is not None
            else "SPAR3D_ARTIFACT_READY_FOR_REVIEW"
        ),
        "runReport": str(run_report_path.resolve()),
        "sourceArtifact": {
            "path": str(mesh),
            "format": mesh.suffix.lower().lstrip("."),
            "bytes": mesh.stat().st_size,
            "sha256": mesh_sha256,
        },
        "referenceManifest": str(reference_manifest),
        "referenceManifestSha256": reference_sha256,
        "provenance": {
            "toolsCommit": tools_commit,
            "artCommit": art_commit,
            "providerCommit": provider_commit,
        },
        "candidateManifest": str(candidate_manifest_path.resolve()) if candidate_record else "",
        "candidateManifestSha256": candidate_sha256,
        "sourceStatus": EXPECTED_SOURCE_STATUS,
        "gateB": EXPECTED_GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "qualityStatus": "PENDING_BLENDER_REFINE_EVALUATE_STRICT_VISUAL_QA",
        "productionMesh": False,
    }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-report", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tools-commit", required=True)
    parser.add_argument("--art-commit", required=True)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character", default="CH101")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    record = build_artifact_record(
        run_report_path=args.run_report,
        reference_manifest_path=args.reference_manifest,
        output=args.output,
        tools_commit=args.tools_commit,
        art_commit=args.art_commit,
        contract_path=args.contract,
        character=args.character,
        candidate_manifest_path=args.candidate_manifest,
    )
    write_json(args.output.resolve(), record)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
