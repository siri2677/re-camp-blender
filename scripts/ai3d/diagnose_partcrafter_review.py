#!/usr/bin/env python3
"""Explain a rejected PartCrafter review without rerunning the provider.

The PartCrafter lane is one-shot by policy.  This module turns its persisted
review record into a deterministic, actionable diagnosis so the next run can
repair only what is objectively repairable and pivot when the provider's
geometry or appearance is the limiting factor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"


def _score_snapshot(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    scores = record.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("PartCrafter review record has no scores object")
    snapshot: dict[str, dict[str, float]] = {}
    for name, entry in scores.items():
        if not isinstance(entry, dict):
            raise ValueError(f"score entry is not an object: {name}")
        try:
            value = float(entry["value"])
            minimum = float(entry["minimum"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"score entry is incomplete: {name}") from exc
        snapshot[name] = {
            "value": round(value, 6),
            "minimum": round(minimum, 6),
            "gap": round(max(0.0, minimum - value), 6),
        }
    return snapshot


def build_diagnosis(record: dict[str, Any]) -> dict[str, Any]:
    """Build a root-cause report from the immutable v002 review record."""

    if record.get("character") != "CH101":
        raise ValueError("PartCrafter diagnosis is currently restricted to CH101")
    if record.get("provider", {}).get("name") != "partcrafter":
        raise ValueError("review record is not a PartCrafter record")
    if record.get("unityInputAllowed") is True or record.get("gates", {}).get("unityInputAllowed") is True:
        raise ValueError("diagnosis refuses a record that has opened Unity input")
    if record.get("productionPromotionAllowed") is True or record.get("gates", {}).get("productionPromotionAllowed") is True:
        raise ValueError("diagnosis refuses a record that has opened production promotion")

    failure_reasons = list(record.get("failureReasons") or [])
    scores = _score_snapshot(record)
    fixes_available_now: list[str] = []
    external_inputs_required: list[str] = []
    findings: list[dict[str, Any]] = []

    if "LARGEST_CONNECTED_COMPONENT_BELOW_MINIMUM" in failure_reasons:
        fixes_available_now.append("CONNECTIVITY_REPAIR_REVIEW_ONLY")
        findings.append(
            {
                "code": "DETACHED_PROVIDER_PARTS",
                "evidence": "PartCrafter emitted separate parts and the largest connected component failed the hard gate.",
                "repair": "Join provider meshes, bridge only measured nearby gaps, and remeasure component ratios.",
                "limit": "A bridge cannot repair incorrect anatomy or semantic part boundaries.",
            }
        )

    if "SOURCE_TRIANGLE_COUNT_ABOVE_MAXIMUM" in failure_reasons:
        fixes_available_now.append("TRIANGLE_BUDGET_REPAIR_REVIEW_ONLY")
        findings.append(
            {
                "code": "SOURCE_TRIANGLE_BUDGET_EXCEEDED",
                "evidence": "The source mesh exceeded the contract's maximum triangle budget before review export.",
                "repair": "Apply deterministic decimation after component repair, then remeasure the exported review mesh.",
                "limit": "Decimation can remove detail; it cannot add missing detail.",
            }
        )

    if "COLOR_SCORE_BELOW_MINIMUM" in failure_reasons or scores.get("color", {}).get("gap", 0.0) > 0.0:
        external_inputs_required.append("SEMANTIC_MATERIAL_MAPPING_REQUIRED")
        findings.append(
            {
                "code": "UNLABELED_PROVIDER_APPEARANCE",
                "evidence": "Provider part indices are not reliable CH101 body/hair/outfit/equipment labels and color score is below the contract.",
                "repair": "Use explicit semantic material mapping or reference-conditioned texture authoring; coarse palette blocking remains review-only.",
                "limit": "Automatic height bands must not be presented as final textures or semantic truth.",
            }
        )

    if (
        "SILHOUETTE_SCORE_BELOW_MINIMUM" in failure_reasons
        or "APPEARANCE_SCORE_BELOW_MINIMUM" in failure_reasons
        or scores.get("silhouette", {}).get("gap", 0.0) > 0.0
        or scores.get("appearance", {}).get("gap", 0.0) > 0.0
    ):
        external_inputs_required.append("REFERENCE_CONDITIONED_GEOMETRY_REQUIRED")
        findings.append(
            {
                "code": "REFERENCE_IDENTITY_MISMATCH",
                "evidence": "The generated surface does not preserve CH101 silhouette/appearance strongly enough for strict review.",
                "repair": "Use a new reference-conditioned provider or semantic Blender authoring; do not repeat PartCrafter inference.",
                "limit": "Topology repair and palette assignment cannot create missing face, hair, outfit, or equipment design.",
            }
        )

    if scores.get("technical", {}).get("gap", 0.0) > 0.0:
        fixes_available_now.append("TECHNICAL_REVIEW_REPAIR_AND_REMEASURE")

    # Preserve deterministic ordering and avoid duplicate action labels.
    fixes_available_now = list(dict.fromkeys(fixes_available_now))
    external_inputs_required = list(dict.fromkeys(external_inputs_required))
    if fixes_available_now:
        next_step = "RUN_STORED_ARTIFACT_REPAIR_THEN_REEVALUATE"
    else:
        next_step = "PIVOT_TO_NEW_REFERENCE_CONDITIONED_STRATEGY"

    return {
        "schemaVersion": "partcrafter-quality-diagnosis-v001",
        "status": "QUALITY_DIAGNOSIS_COMPLETE",
        "recordVersion": record.get("recordVersion", ""),
        "character": "CH101",
        "provider": "partcrafter",
        "strategyId": record.get("strategyId", ""),
        "failureReasons": failure_reasons,
        "scores": scores,
        "findings": findings,
        "fixesAvailableNow": fixes_available_now,
        "externalInputsRequired": external_inputs_required,
        "providerInferenceRerunAllowed": False,
        "nextStep": next_step,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.resolve().read_text(encoding="utf-8"))
    diagnosis = build_diagnosis(record)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
