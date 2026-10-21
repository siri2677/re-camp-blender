#!/usr/bin/env python3
"""Rank AI 3D candidates without granting Gate B or Unity approval."""

from __future__ import annotations

import argparse
import copy
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-report", action="append", type=Path, default=[])
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument(
        "--assisted-visual-review",
        type=Path,
        help="Optional rejection-only visual QA record; it can never approve Gate B.",
    )
    return parser.parse_args()


def apply_assisted_visual_review(
    contract: dict[str, Any],
    entries: list[dict[str, Any]],
    review: dict[str, Any],
) -> dict[str, Any]:
    if review.get("character") != contract["character"]:
        raise ValueError("assisted visual review character mismatch")
    if review.get("artCommit") != contract["artLock"]["commit"]:
        raise ValueError("assisted visual review art commit mismatch")
    if review.get("reviewerClass") != "ASSISTED_VISUAL_QA_NOT_HUMAN_GATE_B":
        raise ValueError("assisted visual review cannot claim human Gate B authority")
    if review.get("humanGateBDecision") != "PENDING_HUMAN_REVIEW":
        raise ValueError("assisted visual review must keep human Gate B pending")
    if review.get("unityInputAllowed") is not False:
        raise ValueError("assisted visual review cannot enable Unity input")
    if review.get("productionPromotionAllowed") is not False:
        raise ValueError("assisted visual review cannot enable production promotion")

    known = {entry["candidateId"]: entry for entry in entries}
    decisions: dict[str, dict[str, Any]] = {}
    candidate_reviews = review.get("candidateReviews")
    if not isinstance(candidate_reviews, list) or not candidate_reviews:
        raise ValueError("assisted visual review must contain candidateReviews")
    for item in candidate_reviews:
        if not isinstance(item, dict):
            raise ValueError("assisted visual review candidate entry must be an object")
        candidate_id = item.get("candidateId")
        if candidate_id not in known:
            raise ValueError(f"assisted visual review has unknown candidate: {candidate_id}")
        if candidate_id in decisions:
            raise ValueError(f"duplicate assisted visual review candidate: {candidate_id}")
        if item.get("candidateSha256") != known[candidate_id]["candidateSha256"]:
            raise ValueError(f"assisted visual review SHA256 mismatch: {candidate_id}")
        disposition = item.get("disposition")
        if disposition not in {"REJECT", "DEFER_TO_HUMAN_REVIEW"}:
            raise ValueError(
                "assisted visual review is rejection/defer only and cannot approve a candidate"
            )
        reason_codes = item.get("reasonCodes")
        if disposition == "REJECT" and (
            not isinstance(reason_codes, list)
            or not reason_codes
            or not all(isinstance(value, str) and value for value in reason_codes)
        ):
            raise ValueError(f"rejected candidate requires reasonCodes: {candidate_id}")
        decisions[candidate_id] = item

    for entry in entries:
        decision = decisions.get(entry["candidateId"])
        entry["assistedVisualReviewDisposition"] = (
            decision["disposition"] if decision else "NOT_REVIEWED"
        )
        entry["assistedVisualReviewReasonCodes"] = (
            list(decision.get("reasonCodes", [])) if decision else []
        )
        entry["eligibleAfterAssistedVisualReview"] = (
            entry["eligibleForHumanReview"]
            and entry["assistedVisualReviewDisposition"] != "REJECT"
        )
    return {
        "reviewVersion": review.get("reviewVersion", ""),
        "reviewerClass": review["reviewerClass"],
        "recommendation": review.get("recommendation", ""),
        "reviewedCandidateCount": len(decisions),
        "rejectedCandidateCount": sum(
            1 for item in decisions.values() if item["disposition"] == "REJECT"
        ),
        "humanGateBDecision": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def rank_reports(
    contract: dict[str, Any],
    reports: list[tuple[Path, dict[str, Any]]],
    assisted_visual_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one score report is required")
    candidate_ids = set()
    entries = []
    for path, report in reports:
        if report.get("contractVersion") != contract["contractVersion"]:
            raise ValueError(f"score contract mismatch: {path}")
        if report.get("character") != contract["character"]:
            raise ValueError(f"score character mismatch: {path}")
        if report.get("artCommit") != contract["artLock"]["commit"]:
            raise ValueError(f"score art commit mismatch: {path}")
        if report.get("sourceStatus") != contract["statusPolicy"]["sourceStatus"]:
            raise ValueError(f"score source status mismatch: {path}")
        if report.get("gateB") != contract["statusPolicy"]["gateB"]:
            raise ValueError(f"score Gate B mismatch: {path}")
        if report.get("unityInputAllowed") is not False:
            raise ValueError(f"score report illegally enables Unity: {path}")
        if report.get("productionPromotionAllowed") is not False:
            raise ValueError(f"score report illegally enables production promotion: {path}")
        candidate_id = report.get("candidateId")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError(f"score report has no candidateId: {path}")
        if candidate_id in candidate_ids:
            raise ValueError(f"duplicate candidateId: {candidate_id}")
        candidate_ids.add(candidate_id)
        entries.append(
            {
                "candidateId": candidate_id,
                "candidatePath": report.get("candidatePath", ""),
                "candidateSha256": report.get("candidateSha256", ""),
                "scoreReport": str(path.resolve()),
                "overallScore": float(report.get("overallScore", 0.0)),
                "silhouetteScore": float(report.get("silhouetteScore", 0.0)),
                "appearanceScore": float(report.get("appearanceScore", 0.0)),
                "colorScore": float(report.get("colorScore", 0.0)),
                "faceDetailScore": float(report.get("faceDetailScore", 0.0)),
                "technicalScore": float(report.get("technicalScore", 0.0)),
                "eligibleForHumanReview": report.get("eligibleForHumanReview") is True,
                "failureReasons": report.get("failureReasons", []),
                "selectedOrientation": report.get("selectedOrientation", {}),
                "orientationValidation": report.get("orientationValidation", {}),
                "qualityHardGateAudit": report.get("qualityHardGateAudit", {}),
                "metricLimitations": report.get("metricLimitations", {}),
                "renders": report.get("evaluationReport", {}).get("renders", {}),
            }
        )
    entries.sort(key=lambda item: (item["overallScore"], item["silhouetteScore"]), reverse=True)
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    automated_selected = next(
        (entry for entry in entries if entry["eligibleForHumanReview"]), None
    )
    assisted_summary = None
    if assisted_visual_review is not None:
        assisted_summary = apply_assisted_visual_review(
            contract, entries, assisted_visual_review
        )
        selected = next(
            (entry for entry in entries if entry["eligibleAfterAssistedVisualReview"]),
            None,
        )
        if selected:
            status = "AUTO_SELECTED_PENDING_HUMAN_REVIEW"
        elif automated_selected:
            status = "REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW"
        else:
            status = "REGENERATE_REQUIRED"
    else:
        selected = automated_selected
        status = "AUTO_SELECTED_FOR_HUMAN_REVIEW" if selected else "REGENERATE_REQUIRED"
    return {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "artCommit": contract["artLock"]["commit"],
        "status": status,
        "selectedCandidate": selected,
        "automatedSelectedCandidate": copy.deepcopy(automated_selected),
        "ranking": entries,
        "selectionDoesNotApproveVisualQuality": True,
        "assistedVisualReview": assisted_summary,
        **candidate_gate_fields(contract),
    }


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    paths = list(args.score_report)
    if args.score_dir:
        paths.extend(sorted(args.score_dir.resolve().glob("**/candidate-score.json")))
    unique_paths = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique_paths.append(resolved)
            seen.add(resolved)
    reports = [(path, read_json(path)) for path in unique_paths]
    assisted_visual_review = (
        read_json(args.assisted_visual_review.resolve())
        if args.assisted_visual_review
        else None
    )
    manifest = rank_reports(contract, reports, assisted_visual_review)
    write_json(args.output.resolve(), manifest)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
