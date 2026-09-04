#!/usr/bin/env python3
"""Stop repeated AI3D retries after a strategy has already plateaued.

This gate is intentionally conservative.  It does not lower score thresholds,
select a production asset, or infer that a new strategy is visually good.  It
only permits a strategy to run when there is no previous rejected score report
with the same stable strategy ID.  A rejected retry must change strategy or
move to semantic/manual reconstruction instead of consuming another GPU run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--history-record", action="append", type=Path, default=[])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-same-strategy-retry",
        action="store_true",
        help="Explicit emergency override; the output still records that it was used.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _score_entries(
    payload: Any, parent: dict[str, Any] | None = None
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    if isinstance(payload, dict):
        # Durable provider review records may store the strategy, rejection,
        # and score map at the top level without a candidateId.  Flatten that
        # shape into the same synthetic entry used by the explicit plateau
        # record so a fresh Kaggle session cannot rerun a rejected provider.
        top_level_scores = payload.get("scores")
        top_level_status = str(payload.get("status") or "")
        if (
            isinstance(payload.get("strategyId"), str)
            and isinstance(top_level_scores, dict)
            and top_level_status.startswith(("REGENERATE", "REJECT"))
            and not isinstance(payload.get("candidateId"), str)
        ):
            flattened = {
                "candidateId": (
                    f"STRATEGY_RECORD:{payload['strategyId']}:"
                    f"{payload.get('recordVersion', 'UNKNOWN')}"
                ),
                "strategyId": payload["strategyId"],
                "provider": payload.get("provider", ""),
                "status": top_level_status,
                "eligibleForHumanReview": False,
            }
            for output_key, score_key in (
                ("overallScore", "overall"),
                ("appearanceScore", "appearance"),
                ("silhouetteScore", "silhouette"),
                ("colorScore", "color"),
                ("technicalScore", "technical"),
            ):
                score_entry = top_level_scores.get(score_key)
                if isinstance(score_entry, dict) and "value" in score_entry:
                    flattened[output_key] = score_entry["value"]
            yield flattened, payload
        # Durable quality-progress records are intentionally smaller than a
        # candidate score report and may not carry a candidateId.  Treat a
        # recorded same-strategy plateau as one synthetic score entry so a
        # fresh Kaggle session cannot silently select that strategy again.
        if (
            isinstance(payload.get("strategyId"), str)
            and payload.get("status") == "QUALITY_PLATEAU_SAME_STRATEGY"
            and not isinstance(payload.get("candidateId"), str)
        ):
            yield {
                **payload,
                "candidateId": f"STRATEGY_GATE:{payload['strategyId']}",
                "eligibleForHumanReview": False,
            }, parent or {}
        if isinstance(payload.get("candidateId"), str) and (
            "overallScore" in payload
            or isinstance(payload.get("scores"), dict)
            or "disposition" in payload
            or (
                isinstance(payload.get("status"), str)
                and payload["status"].startswith(("REGENERATE", "REJECT"))
            )
        ):
            yield payload, parent or {}
        for value in payload.values():
            yield from _score_entries(value, payload)
    elif isinstance(payload, list):
        for value in payload:
            yield from _score_entries(value, parent)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_entry(
    entry: dict[str, Any], parent: dict[str, Any], path: Path
) -> dict[str, Any]:
    scores = entry.get("scores") if isinstance(entry.get("scores"), dict) else {}
    strategy_id = str(entry.get("strategyId") or parent.get("strategyId") or "")
    status = str(entry.get("status") or parent.get("status") or "")
    strict = entry.get("strictVisualQA") or entry.get("strictVisualQa")
    if not isinstance(strict, dict):
        strict = parent.get("strictVisualQA") or parent.get("strictVisualQa") or {}
    recommendation = str(
        strict.get("recommendation")
        or strict.get("strictDisposition")
        or entry.get("recommendation")
        or entry.get("strictDisposition")
        or ""
    )
    disposition = str(entry.get("disposition") or parent.get("disposition") or "")
    overall = _number(
        entry.get("overallScore", scores.get("overallScore", scores.get("overall")))
    )
    appearance = _number(
        entry.get(
            "appearanceScore", scores.get("appearanceScore", scores.get("appearance"))
        )
    )
    rejected = (
        status.startswith("REGENERATE")
        or recommendation.startswith("REJECT")
        or disposition == "REJECT"
        or entry.get("eligibleForHumanReview") is False
    )
    return {
        "path": str(path.resolve()),
        "candidateId": entry["candidateId"],
        "strategyId": strategy_id,
        "provider": str(entry.get("provider") or parent.get("provider") or ""),
        "overallScore": overall,
        "appearanceScore": appearance,
        "status": status,
        "recommendation": recommendation,
        "disposition": disposition,
        "rejected": rejected,
    }


def collect_history(
    score_dir: Path | None, history_records: Iterable[Path]
) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if score_dir and score_dir.is_dir():
        paths.extend(sorted(score_dir.glob("**/candidate-score.json")))
        paths.extend(sorted(score_dir.glob("**/assisted-visual-review.json")))
    paths.extend(path for path in history_records if path.is_file())
    entries: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        payload = _read_json(resolved)
        # Durable review records keep the strategy under ``authoring`` and
        # the score/candidate under ``evaluation``.  Flatten that sibling
        # relationship before the generic recursive scan so a future session
        # cannot rerun a rejected strategy merely because the record shape
        # differs from candidate-score.json.
        authoring = payload.get("authoring") if isinstance(payload, dict) else None
        evaluation = payload.get("evaluation") if isinstance(payload, dict) else None
        structured_entry = None
        if (
            isinstance(authoring, dict)
            and isinstance(evaluation, dict)
            and isinstance(authoring.get("strategyId"), str)
            and isinstance(authoring.get("candidateId") or evaluation.get("candidateId"), str)
            and (
                isinstance(evaluation.get("scores"), dict)
                or isinstance(evaluation.get("status"), str)
            )
        ):
            structured_entry = {
                **evaluation,
                "candidateId": authoring.get("candidateId") or evaluation.get("candidateId"),
                "strategyId": authoring["strategyId"],
                "provider": authoring.get("provider") or payload.get("provider", ""),
            }
            entries.append(_normalise_entry(structured_entry, {}, resolved))

        generic_entries = [
            _normalise_entry(entry, parent, resolved)
            for entry, parent in _score_entries(payload)
            if entry.get("candidateId")
        ]
        # The evaluation child of the structured shape is already represented
        # above; discard its strategy-less recursive duplicate.
        if structured_entry is not None:
            generic_entries = [item for item in generic_entries if item["strategyId"]]
        entries.extend(generic_entries)
        # Some durable Kaggle execution records store the candidate under a
        # strategy-keyed map and omit the repeated strategyId field.  Preserve
        # that map key when importing the rejection into the one-shot gate.
        strategies = payload.get("strategies") if isinstance(payload, dict) else None
        if isinstance(strategies, dict):
            for strategy_id, strategy_entry in strategies.items():
                if not isinstance(strategy_entry, dict):
                    continue
                if not isinstance(strategy_entry.get("candidateId"), str):
                    continue
                status = str(strategy_entry.get("status") or "")
                if not status.startswith(("REGENERATE", "REJECT")):
                    continue
                enriched = {
                    **strategy_entry,
                    "strategyId": strategy_entry.get("strategyId") or strategy_id,
                }
                entries.append(_normalise_entry(enriched, payload, resolved))
    return entries


def build_progress_gate(
    *,
    provider: str,
    strategy_id: str,
    history: list[dict[str, Any]],
    allow_same_strategy_retry: bool = False,
) -> dict[str, Any]:
    if not provider.strip() or not strategy_id.strip():
        raise ValueError("provider and strategy_id are required")
    same_strategy = [item for item in history if item.get("strategyId") == strategy_id]
    rejected = [item for item in same_strategy if item.get("rejected")]
    best_overall = max(
        (item["overallScore"] for item in same_strategy if item.get("overallScore") is not None),
        default=None,
    )
    best_appearance = max(
        (
            item["appearanceScore"]
            for item in same_strategy
            if item.get("appearanceScore") is not None
        ),
        default=None,
    )
    plateau = bool(rejected) and not allow_same_strategy_retry
    return {
        "status": "QUALITY_PLATEAU_SAME_STRATEGY" if plateau else "READY_NEW_STRATEGY",
        "provider": provider,
        "strategyId": strategy_id,
        "sameStrategyReportCount": len(same_strategy),
        "sameStrategyRejectedCount": len(rejected),
        "bestOverallScore": best_overall,
        "bestAppearanceScore": best_appearance,
        "allowSameStrategyRetry": allow_same_strategy_retry,
        "nextAction": (
            "PIVOT_TO_SEMANTIC_RECONSTRUCTION_OR_NEW_PROVIDER"
            if plateau
            else "RUN_ONCE_THEN_RECORD_RESULT_AND_REASSESS"
        ),
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = build_progress_gate(
        provider=args.provider,
        strategy_id=args.strategy_id,
        history=collect_history(args.score_dir, args.history_record),
        allow_same_strategy_retry=args.allow_same_strategy_retry,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "QUALITY_PLATEAU_SAME_STRATEGY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
