#!/usr/bin/env python3
"""Shared contracts and safe file helpers for AI-generated 3D candidates."""

from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = ROOT / "contracts" / "ch101_ai3d_free_pipeline_v001.json"
ROSTER_CONTRACT_PATH = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"
EXPECTED_CONTRACT_VERSION = "ch101-ai3d-free-pipeline-v001"
EXPECTED_ROSTER_CONTRACT_VERSION = "current-roster-ai3d-pipeline-v001"
EXPECTED_CHARACTER = "CH101"
EXPECTED_ROSTER_CHARACTERS = ("CH101", "CH102", "CH103", "CH104", "CH105")
EXPECTED_SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
EXPECTED_GATE = "PENDING_HUMAN_REVIEW"
VIEW_ORDER = ("front", "right", "back")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"contract field {key!r} must be a non-empty string")
    return value


def _validate_character_contract(
    contract: dict[str, Any], expected_version: str
) -> dict[str, Any]:
    if contract.get("contractVersion") != expected_version:
        raise ValueError(f"contractVersion must be {expected_version!r}")
    if contract.get("character") not in EXPECTED_ROSTER_CHARACTERS:
        raise ValueError(
            f"character must be one of {EXPECTED_ROSTER_CHARACTERS!r}"
        )
    _require_string(contract, "subject")
    _require_string(contract, "authoritativeSource")

    art_lock = contract.get("artLock")
    if not isinstance(art_lock, dict):
        raise ValueError("artLock must be an object")
    for key in ("repository", "branch", "commit"):
        _require_string(art_lock, key)
    if len(art_lock["commit"]) != 40:
        raise ValueError("artLock.commit must be a 40-character Git commit")

    generation_source = contract.get("generationSource")
    if not isinstance(generation_source, dict):
        raise ValueError("generationSource must be an object")
    _require_string(generation_source, "path")
    expected_size = generation_source.get("expectedSize")
    if (
        not isinstance(expected_size, list)
        or len(expected_size) != 2
        or not all(isinstance(value, int) and value > 0 for value in expected_size)
    ):
        raise ValueError("generationSource.expectedSize must contain positive width and height")

    reference_views = contract.get("referenceViews")
    if not isinstance(reference_views, dict) or tuple(reference_views) != VIEW_ORDER:
        raise ValueError(f"referenceViews must be ordered as {VIEW_ORDER!r}")
    for view_name in VIEW_ORDER:
        view = reference_views[view_name]
        crop = view.get("crop") if isinstance(view, dict) else None
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or not all(isinstance(value, int) for value in crop)
            or crop[0] < 0
            or crop[1] < 0
            or crop[2] <= crop[0]
            or crop[3] <= crop[1]
        ):
            raise ValueError(f"{view_name} crop must be [left, top, right, bottom]")
        if crop[2] > expected_size[0] or crop[3] > expected_size[1]:
            raise ValueError(f"{view_name} crop exceeds generationSource.expectedSize")
        if view.get("providerKey") != view_name:
            raise ValueError(f"{view_name} providerKey must equal the view name")

    auxiliary_references = contract.get("auxiliaryReferences", [])
    if not isinstance(auxiliary_references, list):
        raise ValueError("auxiliaryReferences must be a list")
    for reference in auxiliary_references:
        if not isinstance(reference, dict):
            raise ValueError("auxiliaryReferences entries must be objects")
        _require_string(reference, "path")
        _require_string(reference, "role")

    generation_strategy = contract.get("generationStrategy")
    if generation_strategy is not None:
        if not isinstance(generation_strategy, dict):
            raise ValueError("generationStrategy must be an object")
        _require_string(generation_strategy, "profile")
        sequence = generation_strategy.get("singleViewReferenceSequence")
        if (
            not isinstance(sequence, list)
            or not sequence
            or not all(view in VIEW_ORDER for view in sequence)
        ):
            raise ValueError(
                "generationStrategy.singleViewReferenceSequence must contain reference views"
            )

    status_policy = contract.get("statusPolicy")
    if not isinstance(status_policy, dict):
        raise ValueError("statusPolicy must be an object")
    if status_policy.get("sourceStatus") != EXPECTED_SOURCE_STATUS:
        raise ValueError("AI candidate source status cannot claim production readiness")
    if status_policy.get("gateB") != EXPECTED_GATE:
        raise ValueError("AI candidate Gate B state must remain pending")
    if status_policy.get("unityInputAllowed") is not False:
        raise ValueError("AI candidate contract must keep Unity input disabled")
    if status_policy.get("productionPromotionAllowed") is not False:
        raise ValueError("AI candidate contract must prohibit automatic production promotion")

    serialized = json.dumps(contract, sort_keys=True).upper()
    if "SK-" in serialized or "BEARER " in serialized:
        raise ValueError("contract appears to contain an API secret")
    return contract


def load_roster_contract_index(path: Path | None = None) -> dict[str, Any]:
    contract_path = (path or ROSTER_CONTRACT_PATH).resolve()
    roster = read_json(contract_path)
    if roster.get("contractVersion") != EXPECTED_ROSTER_CONTRACT_VERSION:
        raise ValueError(
            f"roster contractVersion must be {EXPECTED_ROSTER_CONTRACT_VERSION!r}"
        )
    base_contract = roster.get("baseContract")
    if not isinstance(base_contract, str) or not base_contract:
        raise ValueError("roster baseContract must be a non-empty string")
    base_path = (contract_path.parent / base_contract).resolve()
    if base_path.parent != contract_path.parent or not base_path.is_file():
        raise ValueError("roster baseContract must resolve inside contracts/")
    characters = roster.get("characters")
    if not isinstance(characters, list):
        raise ValueError("roster characters must be a list")
    codes = [entry.get("character") for entry in characters if isinstance(entry, dict)]
    if tuple(codes) != EXPECTED_ROSTER_CHARACTERS:
        raise ValueError(
            f"roster character order must be {EXPECTED_ROSTER_CHARACTERS!r}"
        )
    if len(codes) != len(set(codes)):
        raise ValueError("roster character codes must be unique")
    return roster


def load_contract(
    path: Path | None = None, character: str | None = None
) -> dict[str, Any]:
    contract_path = (path or DEFAULT_CONTRACT_PATH).resolve()
    raw = read_json(contract_path)
    version = raw.get("contractVersion")
    if version == EXPECTED_CONTRACT_VERSION:
        if character is not None and character != EXPECTED_CHARACTER:
            raise ValueError("the legacy CH101 contract cannot select another character")
        return _validate_character_contract(raw, EXPECTED_CONTRACT_VERSION)
    if version != EXPECTED_ROSTER_CONTRACT_VERSION:
        raise ValueError(
            "contractVersion must be either "
            f"{EXPECTED_CONTRACT_VERSION!r} or {EXPECTED_ROSTER_CONTRACT_VERSION!r}"
        )
    if character not in EXPECTED_ROSTER_CHARACTERS:
        raise ValueError(
            "a roster contract requires --character with one of "
            f"{EXPECTED_ROSTER_CHARACTERS!r}"
        )
    roster = load_roster_contract_index(contract_path)
    base_path = (contract_path.parent / roster["baseContract"]).resolve()
    base = _validate_character_contract(read_json(base_path), EXPECTED_CONTRACT_VERSION)
    character_entry = next(
        entry for entry in roster["characters"] if entry["character"] == character
    )
    materialized = copy.deepcopy(base)
    for key in (
        "character",
        "subject",
        "authoritativeSource",
        "generationSource",
        "referenceViews",
        "auxiliaryReferences",
        "generationStrategy",
    ):
        if key in character_entry:
            materialized[key] = copy.deepcopy(character_entry[key])
    materialized["contractVersion"] = EXPECTED_ROSTER_CONTRACT_VERSION
    materialized["baseContractVersion"] = EXPECTED_CONTRACT_VERSION
    materialized["rosterContractVersion"] = EXPECTED_ROSTER_CONTRACT_VERSION
    return _validate_character_contract(
        materialized, EXPECTED_ROSTER_CONTRACT_VERSION
    )


def candidate_gate_fields(contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract["statusPolicy"]
    return {
        "sourceStatus": policy["sourceStatus"],
        "gateB": policy["gateB"],
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def require_reference_manifest(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(path)
    if manifest.get("contractVersion") != contract["contractVersion"]:
        raise ValueError("reference manifest contract version mismatch")
    if manifest.get("character") != contract["character"]:
        raise ValueError("reference manifest character mismatch")
    if manifest.get("artCommit") != contract["artLock"]["commit"]:
        raise ValueError("reference manifest art commit mismatch")
    views = manifest.get("views")
    if not isinstance(views, dict) or set(views) != set(VIEW_ORDER):
        raise ValueError(f"reference manifest must contain {VIEW_ORDER!r}")
    for view_name in VIEW_ORDER:
        entry = views[view_name]
        if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
            raise ValueError(f"reference manifest has invalid {view_name} entry")
        recorded_path = Path(entry["path"])
        candidates = (recorded_path, path.parent / recorded_path.name)
        resolved_path = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
        if resolved_path is None:
            raise FileNotFoundError(f"reference view is missing: {view_name}: {recorded_path}")
        if sha256_file(resolved_path) != entry["sha256"]:
            raise ValueError(f"reference view SHA256 mismatch: {view_name}: {resolved_path}")
        entry["path"] = str(resolved_path)

    expected_auxiliary = contract.get("auxiliaryReferences", [])
    if expected_auxiliary:
        recorded_auxiliary = manifest.get("auxiliaryReferences")
        if not isinstance(recorded_auxiliary, list) or len(recorded_auxiliary) != len(expected_auxiliary):
            raise ValueError("reference manifest auxiliary reference count mismatch")
        for expected in expected_auxiliary:
            matching = next(
                (
                    item
                    for item in recorded_auxiliary
                    if isinstance(item, dict)
                    and str(item.get("path", "")).replace("\\", "/").endswith(expected["path"])
                ),
                None,
            )
            if matching is None or matching.get("role") != expected["role"]:
                raise ValueError(
                    f"reference manifest missing auxiliary reference: {expected['path']}"
                )
            auxiliary_path = Path(matching["path"])
            if not auxiliary_path.is_file():
                raise FileNotFoundError(f"auxiliary reference is missing: {auxiliary_path}")
            if sha256_file(auxiliary_path) != matching.get("sha256"):
                raise ValueError(
                    f"auxiliary reference SHA256 mismatch: {expected['path']}"
                )
            matching["path"] = str(auxiliary_path.resolve())
        if manifest.get("generationStrategy", {}) != contract.get("generationStrategy", {}):
            raise ValueError("reference manifest generation strategy mismatch")
    if manifest.get("unityInputAllowed") is not False:
        raise ValueError("reference manifest cannot enable Unity input")
    return manifest
