#!/usr/bin/env python3
"""Validate the current-roster Unity input manifest without opening Unity.

This validator is deliberately a preflight only. It never changes gate fields,
creates Unity assets, or treats an AI/WIP artifact as a production mesh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "current_roster_socket_contract_v001.json"
SOURCE_LOCK_PATH = ROOT / "source_lock.json"
EXPECTED_CODES = ["CH101", "CH102", "CH103", "CH104", "CH105"]
EXPECTED_SOURCE_STATUS = "PRODUCTION_MESH_READY"
PENDING_GATE = "PENDING_HUMAN_REVIEW"
APPROVED_GATE = "APPROVED"
PENDING_PACKAGE = "PENDING_AFTER_UNITY_EXPORT"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a current-roster Unity input manifest and optional package."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--package",
        type=Path,
        help="Final Unity package file whose name and SHA256 must match the manifest.",
    )
    parser.add_argument(
        "--expected-art-commit",
        help="Override the art commit from source_lock.json.",
    )
    parser.add_argument(
        "--expected-tools-commit",
        help="Require an exact tools commit; otherwise only the 40-character format is checked.",
    )
    parser.add_argument(
        "--require-unity-input",
        action="store_true",
        help="Require Gate B approval, unityInputAllowed=true, a final package, and --package.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def load_contract() -> dict[str, Any]:
    return load_json(CONTRACT_PATH)


def load_source_lock() -> dict[str, Any]:
    return load_json(SOURCE_LOCK_PATH)


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_commit(value: object) -> bool:
    return isinstance(value, str) and COMMIT_PATTERN.fullmatch(value) is not None


def _validate_package(
    manifest: dict[str, Any],
    package_path: Path | None,
    errors: list[str],
    *,
    require_package: bool,
) -> None:
    package_name = manifest.get("packageName")
    package_sha256 = manifest.get("packageSha256")
    package_is_final = (
        isinstance(package_name, str)
        and bool(package_name)
        and package_name != PENDING_PACKAGE
        and Path(package_name).name == package_name
    )

    if require_package and not package_is_final:
        errors.append("Unity input requires a finalized packageName file name")
    if require_package and not _is_sha256(package_sha256):
        errors.append("Unity input requires a lowercase packageSha256")
    if package_name not in (None, PENDING_PACKAGE) and not package_is_final:
        errors.append("manifest packageName must be a file name without path components")
    if package_name not in (None, PENDING_PACKAGE) and not _is_sha256(package_sha256):
        errors.append("finalized packageName requires a lowercase packageSha256")

    if package_path is None:
        if require_package:
            errors.append("--require-unity-input requires --package for on-disk hash verification")
        return
    if not package_path.is_file():
        errors.append(f"package file is missing: {package_path}")
        return
    if not package_is_final:
        errors.append("cannot verify a package while manifest packageName is pending or unsafe")
        return
    if package_path.name != package_name:
        errors.append(
            f"package file name mismatch: manifest={package_name!r}, file={package_path.name!r}"
        )
    actual_sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()
    if actual_sha256 != package_sha256:
        errors.append(f"package SHA256 mismatch: {package_path.name}")


def _validate_character(
    manifest: dict[str, Any],
    contract_entry: dict[str, Any],
    errors: list[str],
    common_sockets: set[str],
) -> None:
    code = contract_entry["code"]
    label = f"{code}"
    manifest_characters = manifest.get("characters")
    if not isinstance(manifest_characters, list):
        return
    entry = next(
        (
            candidate
            for candidate in manifest_characters
            if isinstance(candidate, dict) and candidate.get("code") == code
        ),
        None,
    )
    if entry is None:
        return

    if entry.get("modelNamePrefix") != contract_entry["modelNamePrefix"]:
        errors.append(f"{label}: modelNamePrefix does not match socket contract")
    if entry.get("productionBlend") != contract_entry["productionBlend"]:
        errors.append(f"{label}: productionBlend does not match socket contract")
    if entry.get("sourceReference") != contract_entry["sourceReference"]:
        errors.append(f"{label}: sourceReference does not match socket contract")
    if not _is_sha256(entry.get("blendSha256")):
        errors.append(f"{label}: blendSha256 must be a lowercase SHA256")

    required = entry.get("requiredSockets")
    if not isinstance(required, list):
        errors.append(f"{label}: requiredSockets must be an array")
        required = []
    required_values = [item for item in required if isinstance(item, str)]
    if len(required_values) != len(required):
        errors.append(f"{label}: requiredSockets must contain only strings")
    if len(required_values) != len(set(required_values)):
        errors.append(f"{label}: requiredSockets contains duplicates")
    required_set = set(required_values)
    expected_sockets = (
        common_sockets
        | set(contract_entry["detailSockets"])
        | set(contract_entry["runtimeSocketMap"])
        | set(contract_entry["runtimeSocketMap"].values())
    )
    missing = sorted(expected_sockets - required_set)
    if missing:
        errors.append(f"{label}: requiredSockets missing {', '.join(missing)}")

    aliases = entry.get("runtimeSocketAliases")
    if not isinstance(aliases, list) or not aliases:
        errors.append(f"{label}: runtimeSocketAliases must be a non-empty array")
        return
    runtime_names: list[str] = []
    for alias in aliases:
        if not isinstance(alias, dict):
            errors.append(f"{label}: runtime socket alias must be an object")
            continue
        runtime_name = alias.get("runtimeName")
        source_name = alias.get("sourceName")
        if not isinstance(runtime_name, str) or not isinstance(source_name, str):
            errors.append(f"{label}: runtime socket alias requires runtimeName and sourceName")
            continue
        runtime_names.append(runtime_name)
        if runtime_name not in required_set:
            errors.append(f"{label}: runtime alias {runtime_name} missing from requiredSockets")
        if source_name not in required_set:
            errors.append(f"{label}: runtime source {source_name} missing from requiredSockets")
    if len(runtime_names) != len(set(runtime_names)):
        errors.append(f"{label}: duplicate runtime socket alias")


def validate_manifest(
    manifest: dict[str, Any],
    *,
    contract: dict[str, Any] | None = None,
    source_lock: dict[str, Any] | None = None,
    expected_art_commit: str | None = None,
    expected_tools_commit: str | None = None,
    package_path: Path | None = None,
    require_unity_input: bool = False,
) -> list[str]:
    """Return validation errors; an empty list means the manifest is valid."""

    contract = contract or load_contract()
    source_lock = source_lock or load_source_lock()
    errors: list[str] = []

    if manifest.get("manifestVersion") != 2:
        errors.append("manifestVersion must equal 2")
    if manifest.get("socketContractVersion") != contract["contractVersion"]:
        errors.append("socketContractVersion does not match current roster contract")

    expected_art_commit = expected_art_commit or source_lock.get("commit")
    if manifest.get("artCommit") != expected_art_commit:
        errors.append(f"artCommit must equal {expected_art_commit!r}")
    tools_commit = manifest.get("toolsCommit")
    if not _is_commit(tools_commit):
        errors.append("toolsCommit must be a lowercase 40-character commit")
    if expected_tools_commit and tools_commit != expected_tools_commit:
        errors.append(f"toolsCommit must equal {expected_tools_commit!r}")

    source_status = manifest.get("sourceStatus")
    if source_status != EXPECTED_SOURCE_STATUS:
        errors.append(
            f"sourceStatus must equal {EXPECTED_SOURCE_STATUS!r}; WIP/AI candidates cannot enter Unity"
        )
    gate_b = manifest.get("gateB")
    if gate_b not in (PENDING_GATE, APPROVED_GATE):
        errors.append(f"gateB must equal {PENDING_GATE!r} or {APPROVED_GATE!r}")

    unity_input_allowed = manifest.get("unityInputAllowed")
    if not isinstance(unity_input_allowed, bool):
        errors.append("unityInputAllowed must be a boolean")
        unity_input_allowed = False
    if manifest.get("productionPromotionAllowed", False) is not False:
        errors.append("productionPromotionAllowed must remain false during Unity intake")
    if unity_input_allowed and gate_b != APPROVED_GATE:
        errors.append("unityInputAllowed=true requires gateB=APPROVED")
    if unity_input_allowed and source_status != EXPECTED_SOURCE_STATUS:
        errors.append("unityInputAllowed=true requires sourceStatus=PRODUCTION_MESH_READY")
    if require_unity_input:
        if unity_input_allowed is not True:
            errors.append("--require-unity-input requires unityInputAllowed=true")
        if gate_b != APPROVED_GATE:
            errors.append("--require-unity-input requires gateB=APPROVED")

    characters = manifest.get("characters")
    if not isinstance(characters, list):
        errors.append("characters must be an array")
        characters = []
    codes = [entry.get("code") if isinstance(entry, dict) else None for entry in characters]
    if codes != EXPECTED_CODES:
        errors.append(f"characters must contain {EXPECTED_CODES!r} in order")
    string_codes = [code for code in codes if isinstance(code, str)]
    if len(string_codes) != len(set(string_codes)):
        errors.append("characters contains duplicate codes")

    common_sockets = set(contract["commonRuntimeSockets"])
    for contract_entry in contract["characters"]:
        _validate_character(manifest, contract_entry, errors, common_sockets)

    _validate_package(
        manifest,
        package_path,
        errors,
        require_package=require_unity_input or unity_input_allowed,
    )
    return errors


def print_errors(errors: list[str]) -> None:
    print("Unity input package preflight failed:\n")
    for error in errors:
        print(f"- {error}")


def main() -> int:
    options = parse_args()
    try:
        manifest = load_json(options.manifest)
        contract = load_contract()
        source_lock = load_source_lock()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Unity input package preflight failed: {exc}")
        return 1

    expected_tools_commit = options.expected_tools_commit or os.environ.get(
        "RE_CAMP_EXPECTED_TOOLS_COMMIT"
    )
    errors = validate_manifest(
        manifest,
        contract=contract,
        source_lock=source_lock,
        expected_art_commit=options.expected_art_commit,
        expected_tools_commit=expected_tools_commit,
        package_path=options.package,
        require_unity_input=options.require_unity_input,
    )
    if errors:
        print_errors(errors)
        return 1
    if manifest.get("unityInputAllowed"):
        print("Unity input package preflight passed (Gate B approved package hash checked).")
    else:
        print("Unity input manifest preflight passed with Unity gate locked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
