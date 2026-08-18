#!/usr/bin/env python3
"""Merge five technical Blender handoffs into a Unity-gated roster manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "current_roster_socket_contract_v001.json"
EXPECTED_ART_COMMIT = "b6c9b3128358e061eee6184230929413eba84101"
EXPECTED_TOOLS_COMMIT = "c2f8247ec4fd9b29877ff38b92af64eca18f56aa"
EXPECTED_STATUS = "PRODUCTION_MESH_READY"
EXPECTED_GATE = "PENDING_HUMAN_REVIEW"
EXPECTED_VALIDATOR = "validate_current_roster_mesh_intake.py"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--art-commit", default=EXPECTED_ART_COMMIT)
    parser.add_argument("--tools-commit", default=EXPECTED_TOOLS_COMMIT)
    return parser.parse_args()


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_handoffs(handoff_dir: Path) -> list[tuple[Path, dict[str, object]]]:
    paths = sorted(handoff_dir.rglob("production-mesh-handoff.json"))
    loaded = []
    for path in paths:
        loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return loaded


def validate_handoffs(
    contract: dict[str, object],
    handoffs: list[tuple[Path, dict[str, object]]],
    art_commit: str,
    tools_commit: str,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    errors: list[str] = []
    entries = {
        entry["code"]: entry
        for entry in contract["characters"]
    }
    by_code: dict[str, dict[str, object]] = {}
    if len(handoffs) != len(entries):
        errors.append(f"expected exactly {len(entries)} handoff files, found {len(handoffs)}")

    for path, handoff in handoffs:
        code = handoff.get("character")
        label = f"{path}: {code or '<missing character>'}"
        if code not in entries:
            errors.append(f"{label}: unknown character")
            continue
        if code in by_code:
            errors.append(f"{label}: duplicate character handoff")
            continue
        by_code[code] = handoff
        contract_entry = entries[code]
        required_pairs = {
            "sourceStatus": EXPECTED_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "contractVersion": contract["contractVersion"],
            "artCommit": art_commit,
            "toolsCommit": tools_commit,
            "sourceReference": contract_entry["sourceReference"],
            "blend": contract_entry["productionBlend"],
            "validator": EXPECTED_VALIDATOR,
        }
        for key, expected in required_pairs.items():
            if handoff.get(key) != expected:
                errors.append(f"{label}: {key} must equal {expected!r}")
        digest = handoff.get("blendSha256")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            errors.append(f"{label}: blendSha256 must be a lowercase SHA256")
        if not handoff.get("validatorReport"):
            errors.append(f"{label}: validatorReport is required")

    missing = sorted(set(entries) - set(by_code))
    if missing:
        errors.append(f"missing character handoffs: {', '.join(missing)}")
    return errors, by_code


def build_manifest(
    contract: dict[str, object],
    handoffs: dict[str, dict[str, object]],
    art_commit: str,
    tools_commit: str,
) -> dict[str, object]:
    characters = []
    for entry in contract["characters"]:
        code = entry["code"]
        handoff = handoffs[code]
        required_sockets = sorted(
            set(contract["commonRuntimeSockets"])
            | set(entry["detailSockets"])
            | set(entry["runtimeSocketMap"])
        )
        characters.append(
            {
                "code": code,
                "modelNamePrefix": entry["modelNamePrefix"],
                "productionBlend": entry["productionBlend"],
                "sourceReference": entry["sourceReference"],
                "blendSha256": handoff["blendSha256"],
                "requiredSockets": required_sockets,
                "runtimeSocketAliases": [
                    {"runtimeName": runtime_name, "sourceName": source_name}
                    for runtime_name, source_name in entry["runtimeSocketMap"].items()
                ],
                "validatorReport": handoff["validatorReport"],
            }
        )
    return {
        "manifestVersion": 2,
        "socketContractVersion": contract["contractVersion"],
        "sourceRepository": "https://github.com/siri2677/re-camp.git",
        "toolsRepository": "https://github.com/siri2677/re-camp-blender.git",
        "artCommit": art_commit,
        "toolsCommit": tools_commit,
        "sourceStatus": EXPECTED_STATUS,
        "gateB": EXPECTED_GATE,
        "unityInputAllowed": False,
        "packageName": "PENDING_AFTER_UNITY_EXPORT",
        "packageSha256": "PENDING_AFTER_UNITY_EXPORT",
        "characters": characters,
    }


def main() -> int:
    options = parse_args()
    try:
        contract = load_contract()
        handoffs = load_handoffs(options.handoff_dir)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"handoff merge failed: {exc}")
        return 1

    errors, by_code = validate_handoffs(
        contract,
        handoffs,
        options.art_commit,
        options.tools_commit,
    )
    if errors:
        print("Current roster handoff merge failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    manifest = build_manifest(contract, by_code, options.art_commit, options.tools_commit)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
