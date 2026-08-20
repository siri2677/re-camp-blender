#!/usr/bin/env python3
"""Static validation for the zero-cost CH101 AI 3D candidate package."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ai3d.common import DEFAULT_CONTRACT_PATH, load_contract


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "05_ch101_ai3d_free_autobuild.ipynb"
PLAN = ROOT / "docs" / "plans" / "ch101-free-ai3d-autobuild-plan.md"
PYTHON_SOURCES = (
    ROOT / "scripts" / "ai3d" / "common.py",
    ROOT / "scripts" / "ai3d" / "prepare_reference_views.py",
    ROOT / "scripts" / "ai3d" / "tripo_api.py",
    ROOT / "scripts" / "ai3d" / "run_open_source_provider.py",
    ROOT / "scripts" / "ai3d" / "colab_runtime_preflight.py",
    ROOT / "scripts" / "run_no_gpu_workstream.py",
    ROOT / "scripts" / "ai3d" / "score_candidate_renders.py",
    ROOT / "scripts" / "ai3d" / "rank_candidates.py",
    ROOT / "scripts" / "blender" / "evaluate_ai3d_candidate.py",
    ROOT / "scripts" / "blender" / "refine_ai3d_candidate.py",
    ROOT / "scripts" / "blender" / "build_ai3d_review_asset.py",
)
NOTEBOOK_MARKERS = (
    "TRIPO_API_KEY",
    "HF_TOKEN",
    "RE_CAMP_AI3D_PROVIDER",
    "'sf3d'",
    "'instantmesh'",
    "prepare_reference_views.py",
    "tripo_api.py",
    "run_open_source_provider.py",
    "evaluate_ai3d_candidate.py",
    "refine_ai3d_candidate.py",
    "MAX_ATTEMPTS",
    "REFINED_REVIEW_CANDIDATE",
    "AUTO_ESTIMATED_NOT_APPROVED",
    "score_candidate_renders.py",
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

    source_root_value = os.environ.get("RE_CAMP_SOURCE_DIR", "")
    source_root = Path(source_root_value).resolve() if source_root_value else ROOT.parent / "re-camp-art"
    if source_root.is_dir():
        for relative in (contract["authoritativeSource"], contract["generationSource"]["path"]):
            if not (source_root / relative).is_file():
                fail(errors, f"locked AI 3D art source is missing: {relative}")


def main() -> int:
    errors: list[str] = []
    if not PLAN.is_file():
        fail(errors, f"missing plan: {PLAN.relative_to(ROOT)}")
    validate_notebook(errors)
    validate_sources(errors)
    validate_contract(errors)
    if errors:
        print("AI 3D free package validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1
    print("AI 3D free package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
