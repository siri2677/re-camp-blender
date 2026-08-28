#!/usr/bin/env python3
"""Build rejection-only automatic visual QA for AI 3D candidates.

The score reporter is intentionally permissive enough to route technically
interesting candidates to review.  This second pass applies stricter identity
and presentation thresholds so a gray, generic, or poorly matching candidate
is rejected before it is presented as a viable Alpha Review selection.

This tool can reject or defer.  It can never approve Gate B, Production Mesh,
Unity input, or production promotion.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        read_json,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        candidate_gate_fields,
        load_contract,
        read_json,
        write_json,
    )


REVIEWER_CLASS = "ASSISTED_VISUAL_QA_NOT_HUMAN_GATE_B"
REVIEW_VERSION = "ch101-assisted-visual-review-v003"
ALLOWED_DISPOSITIONS = {"REJECT", "DEFER_TO_HUMAN_REVIEW"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-report", action="append", type=Path, default=[])
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    return parser.parse_args()


def _policy(contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract.get("candidateAcceptance", {}).get("visualReviewPolicy")
    if not isinstance(policy, dict):
        raise ValueError("candidateAcceptance.visualReviewPolicy is missing")
    required = (
        "minimumAutoReviewOverallScore",
        "minimumAutoReviewSilhouetteScore",
        "minimumAutoReviewAppearanceScore",
        "minimumAutoReviewColorScore",
        "minimumAutoReviewFaceDetailScore",
        "minimumAutoReviewTechnicalScore",
    )
    for key in required:
        value = policy.get(key)
        if not isinstance(value, (int, float)) or not 0 < float(value) < 1:
            raise ValueError(f"visualReviewPolicy.{key} must be between 0 and 1")
    if policy.get("decisionMode") != "REJECTION_ONLY_AUTO_QA_DEFER_IF_NO_OBJECTIVE_FAILURE":
        raise ValueError("visual review policy must remain rejection-only")
    return policy


def _validate_score_report(contract: dict[str, Any], report: dict[str, Any]) -> None:
    if report.get("contractVersion") != contract["contractVersion"]:
        raise ValueError("score report contract mismatch")
    if report.get("character") != contract["character"]:
        raise ValueError("score report character mismatch")
    if report.get("artCommit") != contract["artLock"]["commit"]:
        raise ValueError("score report art commit mismatch")
    if report.get("sourceStatus") != contract["statusPolicy"]["sourceStatus"]:
        raise ValueError("score report source status mismatch")
    if report.get("gateB") != contract["statusPolicy"]["gateB"]:
        raise ValueError("score report Gate B mismatch")
    for key in ("unityInputAllowed", "productionPromotionAllowed"):
        if report.get(key) is not False:
            raise ValueError(f"score report cannot enable {key}")
    candidate_id = report.get("candidateId")
    candidate_sha = report.get("candidateSha256")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("score report candidateId is missing")
    if not isinstance(candidate_sha, str) or len(candidate_sha) != 64:
        raise ValueError(f"score report candidateSha256 is invalid: {candidate_id}")


def assess_score_report(
    contract: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    """Return a rejection/defer decision without granting any project gate."""

    _validate_score_report(contract, report)
    policy = _policy(contract)
    checks = (
        (
            "overallScore",
            "minimumAutoReviewOverallScore",
            "OVERALL_IDENTITY_SCORE_WEAK",
        ),
        (
            "silhouetteScore",
            "minimumAutoReviewSilhouetteScore",
            "SILHOUETTE_PROPORTION_MISMATCH",
        ),
        (
            "appearanceScore",
            "minimumAutoReviewAppearanceScore",
            "OUTFIT_HAIR_EQUIPMENT_EDGES_WEAK",
        ),
        (
            "colorScore",
            "minimumAutoReviewColorScore",
            "OUTFIT_COLOR_BLOCKING_WEAK",
        ),
        (
            "faceDetailScore",
            "minimumAutoReviewFaceDetailScore",
            "FACE_DETAIL_EVIDENCE_WEAK",
        ),
        (
            "technicalScore",
            "minimumAutoReviewTechnicalScore",
            "TECHNICAL_REVIEW_READINESS_WEAK",
        ),
    )
    failures: list[dict[str, Any]] = []
    for metric, threshold_key, reason in checks:
        actual = float(report.get(metric, 0.0))
        threshold = float(policy[threshold_key])
        if actual < threshold:
            failures.append(
                {
                    "reasonCode": reason,
                    "metric": metric,
                    "actual": round(actual, 6),
                    "minimum": round(threshold, 6),
                }
            )

    hard_gate = report.get("qualityHardGateAudit", {})
    if not isinstance(hard_gate, dict) or hard_gate.get("status") != "PASS":
        failures.append(
            {
                "reasonCode": "GEOMETRY_OR_RENDER_HARD_GATE_FAILED",
                "metric": "qualityHardGateAudit",
                "actual": hard_gate.get("status", "MISSING")
                if isinstance(hard_gate, dict)
                else "MISSING",
                "minimum": "PASS",
            }
        )

    if report.get("eligibleForHumanReview") is not True:
        failures.append(
            {
                "reasonCode": "AUTOMATED_SCORE_GATE_FAILED",
                "metric": "eligibleForHumanReview",
                "actual": False,
                "minimum": True,
            }
        )

    semantic_audit = report.get("semanticComponentAudit")
    if isinstance(semantic_audit, dict):
        counts = semantic_audit.get("partObjectCountsLOD0")
        required_parts = {"body_face", "hair", "outfit", "equipment"}
        if semantic_audit.get("status") != "PASS" or not isinstance(counts, dict) or any(
            part not in counts or int(counts.get(part, 0)) <= 0 for part in required_parts
        ):
            failures.append(
                {
                    "reasonCode": "SEMANTIC_COMPONENT_STRUCTURE_MISSING",
                    "metric": "semanticComponentAudit",
                    "actual": semantic_audit.get("status", "MISSING"),
                    "minimum": "body_face/hair/outfit/equipment present",
                }
            )
        if semantic_audit.get("slabGrayboxAccepted") is True:
            failures.append(
                {
                    "reasonCode": "SLAB_OR_GRAYBOX_NOT_ACCEPTED",
                    "metric": "semanticComponentAudit.slabGrayboxAccepted",
                    "actual": True,
                    "minimum": False,
                }
            )

    limitation = report.get("metricLimitations", {}).get("faceDetailScore", "")
    review_notes = []
    if policy.get("faceMetricRequiresHumanConfirmation"):
        review_notes.append(
            "FACE_METRIC_IS_NOT_SEMANTIC_IDENTITY_PROOF_AND_REQUIRES_HUMAN_CONFIRMATION"
        )
    if limitation:
        review_notes.append(str(limitation))

    disposition = "REJECT" if failures else "DEFER_TO_HUMAN_REVIEW"
    return {
        "candidateId": report["candidateId"],
        "candidateSha256": report["candidateSha256"],
        "strategyId": report.get("strategyId", ""),
        "disposition": disposition,
        "reasonCodes": [item["reasonCode"] for item in failures],
        "thresholdFailures": failures,
        "reviewNotes": review_notes,
        "decisionBasis": "STRICT_VISUAL_IDENTITY_POLICY",
    }


def build_review(
    contract: dict[str, Any], reports: list[tuple[Path, dict[str, Any]]]
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one score report is required")
    decisions = []
    seen: set[str] = set()
    for path, report in reports:
        decision = assess_score_report(contract, report)
        if decision["candidateId"] in seen:
            raise ValueError(f"duplicate candidateId: {decision['candidateId']}")
        seen.add(decision["candidateId"])
        decision["scoreReport"] = str(path.resolve())
        decisions.append(decision)
    rejected = sum(item["disposition"] == "REJECT" for item in decisions)
    recommendation = (
        "REJECT_GATE_B_AND_REGENERATE"
        if rejected
        else "DEFER_TO_HUMAN_GATE_B_REVIEW"
    )
    return {
        "reviewVersion": REVIEW_VERSION,
        "character": contract["character"],
        "artCommit": contract["artLock"]["commit"],
        "reviewerClass": REVIEWER_CLASS,
        "scope": "ALL_SCORE_REPORTS_STRICT_AUTOMATIC_VISUAL_QA",
        "recommendation": recommendation,
        "policy": _policy(contract),
        "candidateReviews": decisions,
        "summary": {
            "reviewedCandidateCount": len(decisions),
            "rejectedCandidateCount": rejected,
            "deferredCandidateCount": len(decisions) - rejected,
        },
        "humanGateBDecision": "PENDING_HUMAN_REVIEW",
        **candidate_gate_fields(contract),
    }


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    paths = list(args.score_report)
    if args.score_dir:
        paths.extend(sorted(args.score_dir.resolve().glob("**/candidate-score.json")))
    unique_paths = []
    seen_paths: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            unique_paths.append(resolved)
    reports = [(path, read_json(path)) for path in unique_paths]
    review = build_review(contract, reports)
    write_json(args.output.resolve(), review)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
