#!/usr/bin/env python3
"""Prepare a secret-free CH101 semantic reconstruction input handoff.

This is an authoring preflight, not a model generator.  It verifies that the
locked art references and roster socket contract are available, records their
hashes, and emits the exact component checklist a Blender contributor must
build.  It never creates a mesh or unlocks a project gate.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path
from typing import Any

try:
    from .common import DEFAULT_CONTRACT_PATH, candidate_gate_fields, load_contract, sha256_file, write_json
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        sha256_file,
        write_json,
    )


DEFAULT_SOCKET_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "current_roster_socket_contract_v001.json"
)

REFERENCE_ROLES = {
    "authoritative": (
        "art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png",
        "IDENTITY_AND_SILHOUETTE_ANCHOR",
    ),
    "turnaround": (
        "art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png",
        "PROPORTION_AND_VIEW_REFERENCE",
    ),
    "equipment": (
        "art_refs/characters/rin/concept/CH101_Rin_EquipmentSheet_REVIEW_v001.png",
        "EQUIPMENT_STRUCTURE_REFERENCE",
    ),
    "expression": (
        "art_refs/characters/rin/concept/CH101_Rin_ExpressionSheet_REVIEW_v001.png",
        "FACE_LANDMARK_REFERENCE",
    ),
}

COLLECTIONS = (
    "MODEL_HIGH_BODY",
    "MODEL_CLOTH_OUTFIT",
    "MODEL_HAIR",
    "MODEL_EQUIPMENT",
)

FACE_PLACEHOLDERS = (
    "Blink_L",
    "Blink_R",
    "Face_Smile",
    "Viseme_A",
    "Viseme_E",
    "Viseme_I",
    "Viseme_O",
    "Viseme_U",
)

COMPONENT_PLAN = (
    {
        "id": "body_face",
        "objects": ["body", "head", "jaw", "eyes", "nose", "mouth", "ears"],
        "acceptance": [
            "recognizable CH101 head and facial planes",
            "clean A-pose deformation-ready topology",
            "face landmarks remain explicit and reviewable",
        ],
    },
    {
        "id": "hair",
        "objects": ["main_hair_mass", "hairline", "ponytail"],
        "acceptance": [
            "hairline and ponytail are visible in front/right/back/3-4 views",
            "hair is not fused into a featureless outer shell",
        ],
    },
    {
        "id": "outfit",
        "objects": ["jacket", "shorts", "straps", "boots", "major_seams"],
        "acceptance": [
            "outfit regions follow the approved sheet proportions",
            "white, graphite, skin, cyan, and gold regions remain semantically separated",
        ],
    },
    {
        "id": "equipment",
        "objects": ["saber", "sheath", "ribbon_left", "ribbon_right", "pouch"],
        "acceptance": [
            "equipment is modeled as distinct objects",
            "grip, blade tip, ribbon, and primary equipment attachment are explicit",
        ],
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--socket-contract", type=Path, default=DEFAULT_SOCKET_CONTRACT)
    parser.add_argument("--character", default="CH101")
    return parser.parse_args()


def _png_dimensions(path: Path) -> list[int] | None:
    try:
        with path.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                return None
            stream.read(4)
            if stream.read(4) != b"IHDR":
                return None
            width, height = struct.unpack(">II", stream.read(8))
            return [width, height]
    except (OSError, struct.error):
        return None


def _git_head(art_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(art_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "UNAVAILABLE"
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def _socket_entry(socket_contract: dict[str, Any], character: str) -> dict[str, Any]:
    for entry in socket_contract.get("characters", []):
        if entry.get("code") == character:
            return entry
    raise ValueError(f"socket contract has no character: {character}")


def prepare_handoff(
    *,
    art_root: Path,
    output: Path,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    socket_contract_path: Path = DEFAULT_SOCKET_CONTRACT,
    character: str = "CH101",
) -> dict[str, Any]:
    if character != "CH101":
        raise ValueError("semantic reconstruction handoff currently supports CH101 only")
    contract = load_contract(contract_path, character)
    socket_contract = json.loads(socket_contract_path.read_text(encoding="utf-8"))
    socket_entry = _socket_entry(socket_contract, character)
    art_root = art_root.resolve()
    expected_commit = contract["artLock"]["commit"]
    actual_commit = _git_head(art_root)
    references: list[dict[str, Any]] = []
    missing: list[str] = []
    invalid_png: list[str] = []
    for role, (relative_path, reference_role) in REFERENCE_ROLES.items():
        path = art_root / relative_path
        if not path.is_file():
            missing.append(relative_path)
            continue
        dimensions = _png_dimensions(path)
        if dimensions is None:
            invalid_png.append(relative_path)
        references.append(
            {
                "id": role,
                "path": relative_path,
                "role": reference_role,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
                "pngDimensions": dimensions,
            }
        )

    blockers: list[str] = []
    if actual_commit != expected_commit:
        blockers.append("ART_COMMIT_MISMATCH")
    if missing:
        blockers.append("LOCKED_REFERENCE_MISSING")
    if invalid_png:
        blockers.append("LOCKED_REFERENCE_NOT_VALID_PNG")
    if not blockers:
        blockers.extend(("BLENDER_AUTHORING_ENVIRONMENT_REQUIRED", "SEMANTIC_3D_MODELING_REQUIRED"))

    status = "READY_INPUTS_BLOCKED_AUTHORING" if not missing and not invalid_png and actual_commit == expected_commit else "BLOCKED_REFERENCE_INPUTS"
    return {
        "schemaVersion": "ch101-semantic-reconstruction-handoff-v001",
        "character": character,
        "subject": contract["subject"],
        "status": status,
        "artCommitExpected": expected_commit,
        "artCommitActual": actual_commit,
        "contractVersion": contract["contractVersion"],
        "references": references,
        "missingReferences": missing,
        "invalidPngReferences": invalid_png,
        "collections": list(COLLECTIONS),
        "componentPlan": list(COMPONENT_PLAN),
        "facePlaceholders": list(FACE_PLACEHOLDERS),
        "commonRuntimeSockets": list(socket_contract["commonRuntimeSockets"]),
        "detailSockets": list(socket_entry["detailSockets"]),
        "runtimeSocketMap": dict(socket_entry["runtimeSocketMap"]),
        "requiredReviewEvidence": [
            "front_right_back_3-4_views",
            "A-pose_deformation_check",
            "face_closeup_and_hairline_check",
            "outfit_region_and_equipment_attachment_check",
            "socket_location_capture",
            "Blender_validator_report_and_blend_sha256",
        ],
        "blockers": blockers,
        "nextAction": (
            "OPEN_HANDOFF_IN_BLENDER_AND_BUILD_REVIEW_ONLY_MESH"
            if status == "READY_INPUTS_BLOCKED_AUTHORING"
            else "FIX_REFERENCE_INPUTS_BEFORE_AUTHORING"
        ),
        **candidate_gate_fields(contract),
    }


def main() -> int:
    args = parse_args()
    report = prepare_handoff(
        art_root=args.art_root,
        output=args.output,
        contract_path=args.contract,
        socket_contract_path=args.socket_contract,
        character=args.character,
    )
    write_json(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "READY_INPUTS_BLOCKED_AUTHORING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
