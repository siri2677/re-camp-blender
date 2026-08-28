#!/usr/bin/env python3
"""Plan the one-shot free hybrid quality strategies for CH101.

The orchestrator is intentionally lightweight and secret-free.  It performs
quality-progress gates, TRELLIS runtime preflight, and semantic reference
preflight, then tells the Notebook which strategy may run once.  Heavy model
installation and Blender execution remain explicit downstream actions.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .colab_runtime_preflight import build_report as build_runtime_report
    from .common import DEFAULT_CONTRACT_PATH, load_contract, write_json
    from .prepare_semantic_reconstruction_handoff import (
        DEFAULT_SOCKET_CONTRACT,
        prepare_handoff,
    )
    from .quality_progress_gate import build_progress_gate, collect_history
except ImportError:
    from colab_runtime_preflight import build_report as build_runtime_report  # type: ignore
    from common import DEFAULT_CONTRACT_PATH, load_contract, write_json  # type: ignore
    from prepare_semantic_reconstruction_handoff import (  # type: ignore
        DEFAULT_SOCKET_CONTRACT,
        prepare_handoff,
    )
    from quality_progress_gate import build_progress_gate, collect_history  # type: ignore


TRELLIS_STRATEGY = "TRELLIS_SINGLE_VIEW_V001"
SEMANTIC_STRATEGY = "SEMANTIC_PROXY_REFERENCE_FITTED_V001"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--socket-contract", type=Path, default=DEFAULT_SOCKET_CONTRACT)
    parser.add_argument("--character", default="CH101")
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--history-record", action="append", type=Path, default=[])
    parser.add_argument("--blender", default="blender")
    return parser.parse_args()


def _gate(
    provider: str,
    strategy_id: str,
    score_dir: Path | None,
    history_records: list[Path],
) -> dict[str, Any]:
    return build_progress_gate(
        provider=provider,
        strategy_id=strategy_id,
        history=collect_history(score_dir, history_records),
    )


def build_hybrid_report(
    *,
    art_root: Path,
    output: Path,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    socket_contract_path: Path = DEFAULT_SOCKET_CONTRACT,
    character: str = "CH101",
    score_dir: Path | None = None,
    history_records: list[Path] | None = None,
    blender_executable: str = "blender",
) -> dict[str, Any]:
    if character != "CH101":
        raise ValueError("hybrid quality strategies currently support CH101 only")
    contract = load_contract(contract_path, character)
    history_records = history_records or []
    trellis_preflight = build_runtime_report("trellis")
    trellis_gate = _gate("trellis", TRELLIS_STRATEGY, score_dir, history_records)
    semantic_gate = _gate("semanticProxy", SEMANTIC_STRATEGY, score_dir, history_records)
    handoff_path = output.parent / "semantic-reconstruction-inputs.json"
    semantic_handoff = prepare_handoff(
        art_root=art_root,
        output=handoff_path,
        contract_path=contract_path,
        socket_contract_path=socket_contract_path,
        character=character,
    )
    write_json(handoff_path, semantic_handoff)
    blender_path = shutil.which(blender_executable) if blender_executable else None
    semantic_inputs_ready = semantic_handoff["status"] == "READY_INPUTS_BLOCKED_AUTHORING"
    semantic_ready = (
        semantic_gate["status"] == "READY_NEW_STRATEGY"
        and semantic_inputs_ready
        and bool(blender_path)
    )
    trellis_ready = (
        trellis_gate["status"] == "READY_NEW_STRATEGY"
        and trellis_preflight["status"] == "READY_GPU_VISIBLE"
        and trellis_preflight.get("providerPreflight", {}).get("heavyweightInstallAllowed") is True
    )
    trellis_status = (
        "READY_TO_RUN_ONCE"
        if trellis_ready
        else (
            "QUALITY_PLATEAU_SAME_STRATEGY"
            if trellis_gate["status"] == "QUALITY_PLATEAU_SAME_STRATEGY"
            else "BLOCKED_PROVIDER_PREFLIGHT"
        )
    )
    if semantic_ready:
        semantic_status = "READY_TO_RUN_ONCE"
    elif semantic_gate["status"] == "QUALITY_PLATEAU_SAME_STRATEGY":
        semantic_status = "QUALITY_PLATEAU_SAME_STRATEGY"
    elif not semantic_inputs_ready:
        semantic_status = "BLOCKED_REFERENCE_INPUTS"
    elif not blender_path:
        semantic_status = "BLOCKED_BLENDER_AUTHORING_ENVIRONMENT"
    else:
        semantic_status = "BLOCKED_SEMANTIC_PREFLIGHT"
    selected = []
    if semantic_ready:
        selected.append(SEMANTIC_STRATEGY)
    if trellis_ready:
        selected.append(TRELLIS_STRATEGY)
    if not selected:
        next_action = (
            "INSTALL_OR_SELECT_CPU_BLENDER_FOR_SEMANTIC_PROXY"
            if semantic_status == "BLOCKED_BLENDER_AUTHORING_ENVIRONMENT"
            else "RECONNECT_COMPATIBLE_GPU_OR_FIX_PROVIDER_PREFLIGHT"
        )
    else:
        next_action = "RUN_SELECTED_STRATEGIES_ONCE_THEN_ROUTE_ALL_CANDIDATES_TO_STRICT_VISUAL_QA"
    return {
        "schemaVersion": "ch101-hybrid-quality-orchestration-v001",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "character": character,
        "contractVersion": contract["contractVersion"],
        "strategies": {
            TRELLIS_STRATEGY: {
                "provider": "trellis",
                "status": trellis_status,
                "preflight": trellis_preflight,
                "qualityGate": trellis_gate,
                "runAllowed": trellis_ready,
                "maxRuns": 1,
            },
            SEMANTIC_STRATEGY: {
                "provider": "semanticProxy",
                "status": semantic_status,
                "qualityGate": semantic_gate,
                "semanticHandoff": semantic_handoff,
                "blenderExecutable": blender_path or "",
                "runAllowed": semantic_ready,
                "maxRuns": 1,
            },
        },
        "selectedStrategies": selected,
        "nextAction": next_action,
        "sameStrategyRerunPolicy": "REJECT_AFTER_REGENERATE_REQUIRED",
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def main() -> int:
    args = parse_args()
    report = build_hybrid_report(
        art_root=args.art_root,
        output=args.output,
        contract_path=args.contract,
        socket_contract_path=args.socket_contract,
        character=args.character,
        score_dir=args.score_dir,
        history_records=args.history_record,
        blender_executable=args.blender,
    )
    write_json(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
