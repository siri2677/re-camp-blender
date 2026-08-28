#!/usr/bin/env python3
"""Register a non-production mesh from any approved review strategy.

The registrar is intentionally provider-neutral so TRELLIS and the semantic
proxy use the same downstream refine/evaluate/score/rank path.  It copies the
source mesh into an output-owned directory, records immutable hashes, and
keeps every production and Unity gate disabled.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        require_reference_manifest,
        sha256_file,
        write_json,
    )
    from .convert_glb_to_obj import convert_glb_to_obj
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        require_reference_manifest,
        sha256_file,
        write_json,
    )
    from convert_glb_to_obj import convert_glb_to_obj  # type: ignore


SUPPORTED_MESH_SUFFIXES = {".obj", ".ply", ".glb", ".gltf"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_token(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Z0-9_-]+", "_", value.strip().upper()).strip("_-")
    return token or fallback


def _provider_metadata(contract: dict[str, Any], provider: str, strategy_id: str) -> dict[str, Any]:
    experimental = contract.get("experimentalProviders", {})
    provider_entry = experimental.get(provider, {})
    strategy = contract.get("qualityStrategies", {}).get(strategy_id, {})
    if not isinstance(provider_entry, dict):
        provider_entry = {}
    if not isinstance(strategy, dict):
        strategy = {}
    return {
        "providerMode": str(
            provider_entry.get("mode")
            or strategy.get("strategyScope")
            or "REVIEW_ONLY_UNCLASSIFIED_PROVIDER"
        ),
        "providerCommit": str(provider_entry.get("commit") or ""),
        "providerRepository": str(provider_entry.get("repository") or ""),
        "requiresGpu": bool(
            provider_entry.get("requiresGpu", strategy.get("requiresGpu", False))
        ),
    }


def build_candidate_manifest(
    contract: dict[str, Any],
    reference_manifest_path: Path,
    mesh_path: Path,
    destination: Path,
    *,
    provider: str,
    strategy_id: str,
    source_stage: str,
    candidate_label: str,
    asset_files: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy = contract.get("qualityStrategies", {}).get(strategy_id)
    if not isinstance(strategy, dict):
        raise ValueError(f"unknown review strategy: {strategy_id}")
    if strategy.get("provider") != provider:
        raise ValueError(
            f"strategy/provider mismatch: {strategy_id} expects {strategy.get('provider')!r}, got {provider!r}"
        )
    provider_token = _safe_token(provider, "PROVIDER")
    label = _safe_token(candidate_label, "001")
    metadata = _provider_metadata(contract, provider, strategy_id)
    candidate = {
        "candidateId": f"{contract['character']}-{provider_token}-{label}",
        "status": "DOWNLOADED",
        "modelPath": str(destination.resolve()),
        "sha256": sha256_file(destination),
        "bytes": destination.stat().st_size,
        "assetFiles": asset_files or [destination.name],
        "provider": provider,
        "providerCommit": metadata["providerCommit"],
        "artCommit": contract["artLock"]["commit"],
        "strategyId": strategy_id,
        **candidate_gate_fields(contract),
    }
    if metadata:
        semantic_counts = metadata.get("semanticPartObjectCountsLOD0")
        if isinstance(semantic_counts, dict):
            candidate["semanticComponentAudit"] = {
                "status": "PASS" if all(int(value) > 0 for value in semantic_counts.values()) else "FAIL",
                "partObjectCountsLOD0": semantic_counts,
                "slabGrayboxAccepted": bool(metadata.get("qualityPolicy", {}).get("slabGrayboxAccepted", True)),
                "faceStatus": metadata.get("face", {}).get("status", ""),
            }
    return {
        "schemaVersion": "review-candidate-manifest-v001",
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "provider": provider,
        "providerMode": metadata["providerMode"],
        "providerCommit": metadata["providerCommit"],
        "providerRepository": metadata["providerRepository"],
        "sourceStage": source_stage,
        "strategyId": strategy_id,
        "status": "CANDIDATES_DOWNLOADED",
        "completedAt": utc_now(),
        "referenceManifest": str(reference_manifest_path.resolve()),
        "referenceManifestSha256": sha256_file(reference_manifest_path),
        "artCommit": contract["artLock"]["commit"],
        "candidates": [candidate],
        **candidate_gate_fields(contract),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--source-stage", required=True)
    parser.add_argument("--candidate-label", default="001")
    parser.add_argument("--metadata-json", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    reference_manifest = args.reference_manifest.resolve()
    require_reference_manifest(reference_manifest, contract)
    mesh = args.mesh.resolve()
    if not mesh.is_file() or mesh.suffix.lower() not in SUPPORTED_MESH_SUFFIXES:
        raise ValueError(f"review mesh must be a supported file: {mesh}")
    metadata = None
    if args.metadata_json:
        metadata = json.loads(args.metadata_json.resolve().read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("metadata JSON must contain an object")
    output_dir = args.output_dir.resolve()
    candidate_dir = output_dir / f"{contract['character']}_{_safe_token(args.provider, 'PROVIDER')}_{_safe_token(args.candidate_label, '001')}"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    original_destination = candidate_dir / mesh.name
    shutil.copy2(mesh, original_destination)
    destination = original_destination
    asset_files = [original_destination.name]
    if mesh.suffix.lower() == ".obj":
        sidecar = mesh.with_suffix(".mtl")
        if sidecar.is_file():
            shutil.copy2(sidecar, candidate_dir / sidecar.name)
            asset_files.append(sidecar.name)
    transport_report = None
    if mesh.suffix.lower() == ".glb":
        destination = candidate_dir / f"{mesh.stem}_blender_compat.obj"
        transport_report = candidate_dir / f"{mesh.stem}_glb_to_obj_report.json"
        report = convert_glb_to_obj(mesh, destination)
        write_json(transport_report, report)
        asset_files.extend([destination.name, transport_report.name])
    manifest = build_candidate_manifest(
        contract,
        reference_manifest,
        mesh,
        destination,
        provider=args.provider,
        strategy_id=args.strategy_id,
        source_stage=args.source_stage,
        candidate_label=args.candidate_label,
        asset_files=asset_files,
        metadata=metadata,
    )
    if transport_report is not None:
        manifest["transportCompatibility"] = {
            "status": "GLB_TO_OBJ_CONVERTED",
            "originalGlb": str(original_destination.resolve()),
            "blenderReviewInput": str(destination.resolve()),
            "report": str(transport_report.resolve()),
            "materialsPreserved": False,
            "texturesPreserved": False,
        }
    manifest_path = output_dir / "candidate-manifest.json"
    write_json(manifest_path, manifest)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
