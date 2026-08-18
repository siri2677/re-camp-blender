#!/usr/bin/env python3
"""Rank AI 3D candidates without granting Gate B or Unity approval."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-report", action="append", type=Path, default=[])
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def rank_reports(
    contract: dict[str, Any], reports: list[tuple[Path, dict[str, Any]]]
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
        if report.get("unityInputAllowed") is not False:
            raise ValueError(f"score report illegally enables Unity: {path}")
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
                "selectedOrientation": report.get("selectedOrientation", {}),
            }
        )
    entries.sort(key=lambda item: (item["overallScore"], item["silhouetteScore"]), reverse=True)
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    selected = next((entry for entry in entries if entry["eligibleForHumanReview"]), None)
    status = "AUTO_SELECTED_FOR_HUMAN_REVIEW" if selected else "REGENERATE_REQUIRED"
    return {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "artCommit": contract["artLock"]["commit"],
        "status": status,
        "selectedCandidate": selected,
        "ranking": entries,
        "selectionDoesNotApproveVisualQuality": True,
        **candidate_gate_fields(contract),
    }


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract)
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
    manifest = rank_reports(contract, reports)
    write_json(args.output.resolve(), manifest)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
