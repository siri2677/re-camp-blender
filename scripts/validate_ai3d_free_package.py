#!/usr/bin/env python3
"""Static validation for the zero-cost CH101 AI 3D candidate package."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ai3d.common import (
    DEFAULT_CONTRACT_PATH,
    EXPECTED_ROSTER_CHARACTERS,
    ROSTER_CONTRACT_PATH,
    load_contract,
    load_roster_contract_index,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "05_ch101_ai3d_free_autobuild.ipynb"
PLAN = ROOT / "docs" / "plans" / "ch101-free-ai3d-autobuild-plan.md"
PYTHON_SOURCES = (
    ROOT / "scripts" / "ai3d" / "common.py",
    ROOT / "scripts" / "ai3d" / "prepare_reference_views.py",
    ROOT / "scripts" / "ai3d" / "prepare_roster_reference_views.py",
    ROOT / "scripts" / "ai3d" / "tripo_api.py",
    ROOT / "scripts" / "ai3d" / "run_open_source_provider.py",
    ROOT / "scripts" / "ai3d" / "run_wonder3d_multiview.py",
    ROOT / "scripts" / "ai3d" / "register_wonder3d_candidate.py",
    ROOT / "scripts" / "ai3d" / "colab_runtime_preflight.py",
    ROOT / "scripts" / "run_no_gpu_workstream.py",
    ROOT / "scripts" / "run_adaptive_workstream.py",
    ROOT / "scripts" / "ai3d" / "score_candidate_renders.py",
    ROOT / "scripts" / "ai3d" / "build_assisted_visual_review.py",
    ROOT / "scripts" / "ai3d" / "rank_candidates.py",
    ROOT / "scripts" / "ai3d" / "build_gate_b_review_package.py",
    ROOT / "scripts" / "ai3d" / "build_final_evaluation_archive.py",
    ROOT / "scripts" / "blender" / "evaluate_ai3d_candidate.py",
    ROOT / "scripts" / "blender" / "refine_ai3d_candidate.py",
    ROOT / "scripts" / "blender" / "fit_review_silhouette.py",
    ROOT / "scripts" / "blender" / "repair_review_components.py",
    ROOT / "scripts" / "blender" / "analyze_review_components.py",
    ROOT / "scripts" / "blender" / "stitch_nearest_review_component.py",
    ROOT / "scripts" / "blender" / "bridge_nearest_review_components.py",
    ROOT / "scripts" / "blender" / "apply_reference_projection_review.py",
    ROOT / "scripts" / "blender" / "build_ai3d_review_asset.py",
)
NOTEBOOK_MARKERS = (
    "TRIPO_API_KEY",
    "HF_TOKEN",
    "RE_CAMP_AI3D_PROVIDER",
    "run_adaptive_workstream.py",
    "ADAPTIVE_NO_GPU_COMPLETED",
    "GPU_WORK_ENABLED",
    "'sf3d'",
    "'instantmesh'",
    "prepare_reference_views.py",
    "tripo_api.py",
    "run_open_source_provider.py",
    "evaluate_ai3d_candidate.py",
    "refine_ai3d_candidate.py",
    "fit_review_silhouette.py",
    "RE_CAMP_FIT_REVIEW_SILHOUETTE",
    "repair_review_components.py",
    "RE_CAMP_REPAIR_REVIEW_COMPONENTS",
    "MAX_ATTEMPTS",
    "REFINED_REVIEW_CANDIDATE",
    "AUTO_ESTIMATED_NOT_APPROVED",
    "score_candidate_renders.py",
    "build_assisted_visual_review.py",
    "rank_candidates.py",
    "build_ai3d_review_asset.py",
    "unityInputAllowed",
    "NOT_PRODUCTION",
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_notebook(errors: list[str]) -> None:
    if not NOTEBOOK.is_file():
        fail(errors, f"missing notebook: {NOTEBOOK.relative_to(ROOT)}")
        return
    try:
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid notebook JSON: {exc}")
        return
    if notebook.get("nbformat") != 4:
        fail(errors, "AI 3D notebook must use nbformat 4")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or not cells:
        fail(errors, "AI 3D notebook has no cells")
        return
    text = "\n".join("".join(cell.get("source", [])) for cell in cells)
    for marker in NOTEBOOK_MARKERS:
        if marker not in text:
            fail(errors, f"AI 3D notebook missing marker: {marker}")
    for index, cell in enumerate(cells, start=1):
        if cell.get("cell_type") != "code":
            continue
        try:
            compile("".join(cell.get("source", [])), f"{NOTEBOOK.name}#cell-{index}", "exec")
        except SyntaxError as exc:
            fail(errors, f"AI 3D notebook code cell {index} has syntax error: {exc}")


def validate_sources(errors: list[str]) -> None:
    forbidden = ("TRIPO_API_KEY = 'sk-", 'TRIPO_API_KEY = "sk-', '"unityInputAllowed": true')
    for path in PYTHON_SOURCES:
        if not path.is_file():
            fail(errors, f"missing AI 3D source: {path.relative_to(ROOT)}")
            continue
        source = path.read_text(encoding="utf-8")
        try:
            compile(source, str(path.relative_to(ROOT)), "exec")
        except SyntaxError as exc:
            fail(errors, f"syntax error in {path.relative_to(ROOT)}: {exc}")
        for marker in forbidden:
            if marker in source:
                fail(errors, f"forbidden secret/gate marker in {path.relative_to(ROOT)}: {marker}")


def validate_contract(errors: list[str]) -> None:
    try:
        contract = load_contract(DEFAULT_CONTRACT_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(errors, f"invalid AI 3D contract: {exc}")
        return
    providers = contract["providers"]
    provider_policy = contract.get("providerPolicy", {})
    if provider_policy.get("mode") != "FREE_FIRST":
        fail(errors, "providerPolicy.mode must be FREE_FIRST")
    if provider_policy.get("defaultProvider") != "stableFast3D":
        fail(errors, "stableFast3D must be the default provider")
    if provider_policy.get("freeFallbackOrder") != ["stableFast3D", "instantMesh", "tripoSR"]:
        fail(errors, "freeFallbackOrder must be stableFast3D then instantMesh then tripoSR")
    if provider_policy.get("apiCreditsRequiredByDefault") is not False:
        fail(errors, "API credits must not be required by default")
    for key in ("stableFast3D", "instantMesh", "tripoSR"):
        commit = providers[key].get("commit", "")
        if not isinstance(commit, str) or len(commit) != 40:
            fail(errors, f"{key} must pin a 40-character commit")
    experimental = contract.get("experimentalProviders", {})
    wonder3d = experimental.get("wonder3D", {})
    if len(wonder3d.get("commit", "")) != 40:
        fail(errors, "experimentalProviders.wonder3D must pin a 40-character commit")
    if wonder3d.get("fallbackEnabled") is not False:
        fail(errors, "Wonder3D must remain disabled as an automatic fallback until T4 validation")
    if wonder3d.get("unityInputAllowed") is not False or wonder3d.get("productionPromotionAllowed") is not False:
        fail(errors, "Wonder3D research candidate must keep Unity and production gates locked")
    if "hunyuan3d2" not in contract.get("excludedProviders", {}):
        fail(errors, "Hunyuan3D-2 must remain explicitly excluded for the South Korea workflow")
    thresholds = contract["candidateAcceptance"]
    for key in (
        "minimumOverallScore",
        "minimumSilhouetteScore",
        "minimumAppearanceScore",
        "minimumColorScore",
        "minimumFaceDetailScore",
    ):
        value = thresholds.get(key)
        if not isinstance(value, (int, float)) or not 0 < value < 1:
            fail(errors, f"candidateAcceptance.{key} must be between 0 and 1")
    visual_policy = thresholds.get("visualReviewPolicy", {})
    if not isinstance(visual_policy, dict):
        fail(errors, "candidateAcceptance.visualReviewPolicy must be an object")
        visual_policy = {}
    for key in (
        "minimumAutoReviewOverallScore",
        "minimumAutoReviewSilhouetteScore",
        "minimumAutoReviewAppearanceScore",
        "minimumAutoReviewColorScore",
        "minimumAutoReviewFaceDetailScore",
        "minimumAutoReviewTechnicalScore",
    ):
        value = visual_policy.get(key)
        if not isinstance(value, (int, float)) or not 0 < value < 1:
            fail(errors, f"visualReviewPolicy.{key} must be between 0 and 1")
    if visual_policy.get("decisionMode") != "REJECTION_ONLY_AUTO_QA_DEFER_IF_NO_OBJECTIVE_FAILURE":
        fail(errors, "visualReviewPolicy must remain rejection-only")
    hard_gates = thresholds.get("geometryHardGates", {})
    for key in (
        "minimumLargestComponentVertexRatio",
        "maximumLooseVertexRatio",
        "maximumNonManifoldEdgeRatio",
        "maximumDegenerateTriangleRatio",
        "minimumVisiblePrimaryComponentAreaRatio",
    ):
        value = hard_gates.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            fail(errors, f"candidateAcceptance.geometryHardGates.{key} must be between 0 and 1")
    if hard_gates.get("minimumLargestComponentVertexRatio", 0) < 0.9:
        fail(errors, "geometry hard gate must reject candidates with more than 10% detached vertices")

    try:
        roster = load_roster_contract_index(ROSTER_CONTRACT_PATH)
        roster_contracts = [
            load_contract(ROSTER_CONTRACT_PATH, character)
            for character in EXPECTED_ROSTER_CHARACTERS
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(errors, f"invalid current roster AI 3D contract: {exc}")
        roster = {"characters": []}
        roster_contracts = []
    if [entry.get("character") for entry in roster.get("characters", [])] != list(
        EXPECTED_ROSTER_CHARACTERS
    ):
        fail(errors, "current roster AI 3D contract must contain CH101 through CH105 in order")
    for roster_contract in roster_contracts:
        if roster_contract["statusPolicy"].get("unityInputAllowed") is not False:
            fail(errors, f"{roster_contract['character']}: roster AI 3D contract enables Unity")

    source_root_value = os.environ.get("RE_CAMP_SOURCE_DIR", "")
    source_root = Path(source_root_value).resolve() if source_root_value else ROOT.parent / "re-camp-art"
    if source_root.is_dir():
        source_paths = {
            relative
            for current in roster_contracts or [contract]
            for relative in (
                current["authoritativeSource"],
                current["generationSource"]["path"],
            )
        }
        for relative in sorted(source_paths):
            if not (source_root / relative).is_file():
                fail(errors, f"locked AI 3D art source is missing: {relative}")


def validate_review_records(errors: list[str]) -> None:
    review_path = ROOT / "docs" / "records" / "ch101-ai3d" / "2026-08-20-assisted-visual-review-v001.json"
    package_path = ROOT / "docs" / "records" / "ch101-ai3d" / "2026-08-20-gate-b-review-package-v001.json"
    roster_record_path = ROOT / "docs" / "records" / "current-roster-ai3d" / "2026-08-20-reference-view-preflight-v001.json"
    final_record_path = ROOT / "docs" / "records" / "ch101-ai3d" / "2026-08-20-final-hard-gated-candidate-evaluation-v002.json"
    for path in (review_path, package_path, roster_record_path):
        if not path.is_file():
            fail(errors, f"missing AI 3D review record: {path.relative_to(ROOT)}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(errors, f"invalid review record JSON {path.relative_to(ROOT)}: {exc}")
            continue
        if data.get("unityInputAllowed") is not False:
            fail(errors, f"review record enables Unity: {path.relative_to(ROOT)}")
        if data.get("productionPromotionAllowed") is not False:
            fail(errors, f"review record enables production: {path.relative_to(ROOT)}")
    contact_sheets = (
        ROOT / "docs" / "records" / "ch101-ai3d" / "assets" / "CH101_GateB_ContactSheet_NOT_APPROVED_v001.png",
        ROOT / "docs" / "records" / "current-roster-ai3d" / "assets" / "CurrentRoster_ReferenceViews_NOT_PRODUCTION_v001.png",
    )
    for path in contact_sheets:
        if not path.is_file() or path.stat().st_size == 0:
            fail(errors, f"missing review contact sheet: {path.relative_to(ROOT)}")
    if roster_record_path.is_file() and contact_sheets[1].is_file():
        roster_record = json.loads(roster_record_path.read_text(encoding="utf-8"))
        if roster_record.get("contactSheetSha256") != sha256_file(contact_sheets[1]):
            fail(errors, "current roster reference contact sheet SHA256 mismatch")
    if not final_record_path.is_file():
        fail(errors, f"missing final hard-gated record: {final_record_path.relative_to(ROOT)}")
    else:
        try:
            final_record = json.loads(final_record_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(errors, f"invalid final hard-gated record JSON: {exc}")
        else:
            if final_record.get("status") != "REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW":
                fail(errors, "final hard-gated record status mismatch")
            evaluation = final_record.get("evaluation", {})
            if evaluation.get("candidateCount") != 6:
                fail(errors, "final hard-gated record must contain six candidates")
            if evaluation.get("selectedCandidate") is not None:
                fail(errors, "final hard-gated record must not select a candidate")
            gate = final_record.get("gate", {})
            if gate.get("unityInputAllowed") is not False:
                fail(errors, "final hard-gated record enables Unity")
            if gate.get("productionPromotionAllowed") is not False:
                fail(errors, "final hard-gated record enables production")
            package = final_record.get("package", {})
            if package.get("reviewAssetIncluded") is not False:
                fail(errors, "final hard-gated package cannot include a rejected Review asset")
            if package.get("trackedInGit") is not False:
                fail(errors, "large final hard-gated package cannot be tracked in normal Git history")
            artifact_name = package.get("fileName")
            if isinstance(artifact_name, str):
                local_artifact = ROOT / "artifacts" / artifact_name
                if local_artifact.is_file():
                    if package.get("bytes") != local_artifact.stat().st_size:
                        fail(errors, "local final hard-gated package size mismatch")
                    if package.get("sha256") != sha256_file(local_artifact):
                        fail(errors, "local final hard-gated package SHA256 mismatch")
            if contact_sheets[0].is_file():
                recorded_hash = final_record.get("visualEvidence", {}).get("contactSheetSha256")
                if recorded_hash != sha256_file(contact_sheets[0]):
                    fail(errors, "final hard-gated contact sheet SHA256 mismatch")


def main() -> int:
    errors: list[str] = []
    if not PLAN.is_file():
        fail(errors, f"missing plan: {PLAN.relative_to(ROOT)}")
    validate_notebook(errors)
    validate_sources(errors)
    validate_contract(errors)
    validate_review_records(errors)
    if errors:
        print("AI 3D free package validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1
    print("AI 3D free package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
