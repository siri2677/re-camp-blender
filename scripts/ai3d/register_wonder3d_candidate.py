#!/usr/bin/env python3
"""Register a Wonder3D/NeuS mesh as a locked, non-production candidate."""

from __future__ import annotations

import argparse
import json
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


def build_candidate_manifest(
    contract: dict[str, Any],
    reference_manifest_path: Path,
    mesh_path: Path,
    destination: Path,
    asset_files: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "provider": "wonder3D",
        "providerMode": contract["experimentalProviders"]["wonder3D"]["mode"],
        "sourceStage": "WONDER3D_MULTIVIEW_NEUS_MESH",
        "status": "CANDIDATES_DOWNLOADED",
        "completedAt": utc_now(),
        "referenceManifest": str(reference_manifest_path.resolve()),
        "referenceManifestSha256": sha256_file(reference_manifest_path),
        "candidates": [
            {
                "candidateId": f"{contract['character']}-WONDER3D-001",
                "status": "DOWNLOADED",
                "modelPath": str(destination.resolve()),
                "sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
                "assetFiles": asset_files or [destination.name],
                **candidate_gate_fields(contract),
            }
        ],
        **candidate_gate_fields(contract),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    require_reference_manifest(args.reference_manifest.resolve(), contract)
    mesh = args.mesh.resolve()
    if not mesh.is_file() or mesh.suffix.lower() not in SUPPORTED_MESH_SUFFIXES:
        raise ValueError(f"Wonder3D mesh must be a supported file: {mesh}")
    output_dir = args.output_dir.resolve()
    asset_dir = output_dir / "CH101_wonder3D_cand_001"
    asset_dir.mkdir(parents=True, exist_ok=True)
    original_destination = asset_dir / mesh.name
    shutil.copy2(mesh, original_destination)
    destination = original_destination
    asset_files = [original_destination.name]
    transport_report = None
    if mesh.suffix.lower() == ".glb":
        # Blender 3.0's bundled glTF importer may reject a valid NeuS GLB. Keep
        # the original transport file and register a deterministic OBJ copy as
        # the downstream review input; this does not improve visual quality or
        # unlock any production gate.
        destination = asset_dir / f"{mesh.stem}_blender_compat.obj"
        transport_report = asset_dir / f"{mesh.stem}_glb_to_obj_report.json"
        report = convert_glb_to_obj(mesh, destination)
        transport_report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        asset_files.extend([destination.name, transport_report.name])
    if mesh.suffix.lower() == ".obj":
        sidecar = mesh.with_suffix(".mtl")
        if sidecar.is_file():
            shutil.copy2(sidecar, asset_dir / sidecar.name)
            asset_files.append(sidecar.name)
    manifest = build_candidate_manifest(
        contract,
        args.reference_manifest.resolve(),
        mesh,
        destination,
        asset_files,
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
