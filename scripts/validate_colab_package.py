#!/usr/bin/env python3
"""Validate the Colab + Blender automation package without Blender installed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK_PATH = ROOT / "source_lock.json"
SOURCE_BRANCH = "current/art-roster-gate-a-ch102"
SOURCE_COMMIT = "b6c9b3128358e061eee6184230929413eba84101"
SOURCE_REFERENCE = "art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png"
CONTRACT_PATH = ROOT / "contracts" / "current_roster_socket_contract_v001.json"
CONTRACT_VERSION = "current-roster-socket-contract-v001"
NOTEBOOKS = (
    "notebooks/00_colab_blender_setup.ipynb",
    "notebooks/01_ch101_blockout.ipynb",
    "notebooks/00_colab_blender_nodrive_test.ipynb",
    "notebooks/03_ch101_production_mesh_intake.ipynb",
    "notebooks/04_current_roster_production_mesh_intake.ipynb",
    "notebooks/05_ch101_ai3d_free_autobuild.ipynb",
    "notebooks/06_ch101_wonder3d_multiview_experiment.ipynb",
    "notebooks/07_ch101_hybrid_quality_strategies.ipynb",
)
BLENDER_SCRIPTS = (
    "scripts/blender/build_blockout.py",
    "scripts/blender/validate_asset.py",
    "scripts/blender/validate_current_roster_mesh_intake.py",
    "scripts/blender/validate_ch101_mesh_intake.py",
    "scripts/blender/evaluate_ai3d_candidate.py",
    "scripts/blender/refine_ai3d_candidate.py",
    "scripts/blender/fit_review_silhouette.py",
    "scripts/blender/repair_review_components.py",
    "scripts/blender/analyze_review_components.py",
    "scripts/blender/stitch_nearest_review_component.py",
    "scripts/blender/bridge_nearest_review_components.py",
    "scripts/blender/apply_reference_projection_review.py",
    "scripts/blender/apply_review_multiview_textures.py",
    "scripts/blender/build_ai3d_review_asset.py",
    "scripts/blender/repair_partcrafter_review_candidate.py",
    "scripts/blender/build_ch101_semantic_proxy.py",
)
UTILITY_SCRIPTS = (
    "scripts/merge_current_roster_handoffs.py",
    "scripts/validate_ai3d_free_package.py",
    "scripts/ai3d/common.py",
    "scripts/ai3d/prepare_reference_views.py",
    "scripts/ai3d/prepare_roster_reference_views.py",
    "scripts/ai3d/tripo_api.py",
    "scripts/ai3d/run_open_source_provider.py",
    "scripts/ai3d/run_wonder3d_multiview.py",
    "scripts/ai3d/convert_glb_to_obj.py",
    "scripts/ai3d/quality_progress_gate.py",
    "scripts/ai3d/prepare_semantic_reconstruction_handoff.py",
    "scripts/ai3d/hybrid_quality_orchestrator.py",
    "scripts/ai3d/register_review_candidate.py",
    "scripts/ai3d/run_trellis_candidate.py",
    "scripts/ai3d/run_trellis16_candidate.py",
    "scripts/ai3d/run_trellis2_candidate.py",
    "scripts/ai3d/run_partcrafter_candidate.py",
    "scripts/ai3d/run_spar3d_candidate.py",
    "scripts/ai3d/diagnose_partcrafter_review.py",
    "scripts/ai3d/register_wonder3d_candidate.py",
    "scripts/ai3d/build_wonder3d_voxel_surface.py",
    "scripts/ai3d/colab_runtime_preflight.py",
    "scripts/run_no_gpu_workstream.py",
    "scripts/ai3d/score_candidate_renders.py",
    "scripts/ai3d/rank_candidates.py",
    "scripts/ai3d/build_gate_b_review_package.py",
    "scripts/ai3d/build_final_evaluation_archive.py",
    "scripts/ai3d/run_review_remediation_chain.py",
    "scripts/validate_unity_input_package.py",
    "scripts/run_adaptive_workstream.py",
)
REQUIRED_MARKERS = {
    "notebooks/00_colab_blender_setup.ipynb": (
        "drive.mount('/content/drive')",
        "REPO_URL",
        "TOOLS_REPO_URL",
        SOURCE_BRANCH,
        SOURCE_COMMIT,
        SOURCE_REFERENCE,
        "git",
        "fetch",
        "checkout",
        "--detach",
        "apt-get",
        "DRIVE_ROOT",
    ),
    "notebooks/01_ch101_blockout.ipynb": (
        "CH101",
        SOURCE_COMMIT,
        SOURCE_REFERENCE,
        "REFERENCE.is_file()",
        "FileNotFoundError",
        "build_blockout.py",
        "validate_asset.py",
        "TOOLS_DIR",
        "drive_output",
    ),
    "notebooks/00_colab_blender_nodrive_test.ipynb": (
        "No Google Drive access is used.",
        "https://github.com/siri2677/re-camp.git",
        "https://github.com/siri2677/re-camp-blender.git",
        SOURCE_COMMIT,
        SOURCE_REFERENCE,
        "REFERENCE.is_file()",
        "FileNotFoundError",
        "xvfb-run",
        "files.download",
        "CH101_Blockout_REVIEW_v010.blend",
        "v010",
    ),
    "notebooks/03_ch101_production_mesh_intake.ipynb": (
        "TOOLS_REPO_URL",
        "TOOLS_COMMIT",
        "ART_COMMIT",
        "c2f8247ec4fd9b29877ff38b92af64eca18f56aa",
        CONTRACT_VERSION,
        "CH101_A_HighRes_Production_v001.blend",
        "EXPECTED_BLEND_NAME",
        "PRODUCTION_BLEND",
        "validate_ch101_mesh_intake.py",
        "validate_current_roster_mesh_intake.py",
        "xvfb-run",
        "files.upload",
        "PRODUCTION_MESH_READY",
        "PENDING_HUMAN_REVIEW",
        "files.download",
    ),
    "notebooks/04_current_roster_production_mesh_intake.ipynb": (
        "CHARACTER_CODE",
        "CH101",
        "CH102",
        "CH103",
        "CH104",
        "CH105",
        "TOOLS_COMMIT",
        "ART_COMMIT",
        "c2f8247ec4fd9b29877ff38b92af64eca18f56aa",
        CONTRACT_VERSION,
        "EXPECTED_BLEND_NAME",
        "validate_current_roster_mesh_intake.py",
        "files.upload",
        "PRODUCTION_MESH_READY",
        "PENDING_HUMAN_REVIEW",
        "files.download",
    ),
    "notebooks/05_ch101_ai3d_free_autobuild.ipynb": (
        "CHARACTER_CODE",
        "CH101",
        "RE_CAMP_CHARACTER_CODE",
        "current_roster_ai3d_pipeline_v001.json",
        "TOOLS_REPO_URL",
        "TOOLS_COMMIT",
        "ART_COMMIT",
        "TRIPO_API_KEY",
        "HF_TOKEN",
        "prepare_reference_views.py",
        "tripo_api.py",
        "run_open_source_provider.py",
        "RE_CAMP_INSTANTMESH_NO_REMBG",
        "run_adaptive_workstream.py",
        "ADAPTIVE_NO_GPU_COMPLETED",
        "GPU_WORK_ENABLED",
        "provider_attempts",
        "trimesh>=4.4.0",
        "onnxruntime-gpu",
        "evaluate_ai3d_candidate.py",
        "--integrity-blend",
        "refine_ai3d_candidate.py",
        "fit_review_silhouette.py",
        "REFINED_REVIEW_CANDIDATE",
        "face_driver_status",
        "AUTO_ESTIMATED_NOT_APPROVED",
        "score_candidate_renders.py",
        "rank_candidates.py",
        "build_ai3d_review_asset.py",
        "unityInputAllowed",
        "NOT_PRODUCTION",
        "files.download",
    ),
    "notebooks/06_ch101_wonder3d_multiview_experiment.ipynb": (
        "Wonder3D",
        "WONDER3D_COMMIT",
        "run_wonder3d_multiview.py",
        "register_wonder3d_candidate.py",
        "test_mvdiffusion_seq.py",
        "generatedViewCount",
        "run_adaptive_workstream.py",
        "ADAPTIVE_NO_GPU_COMPLETED",
        "GPU_WORK_ENABLED",
        "NeuS",
        "refine_ai3d_candidate.py",
        "evaluate_ai3d_candidate.py",
        "rank_candidates.py",
        "unityInputAllowed",
        "NOT_PRODUCTION",
        "files.download",
    ),
    "notebooks/07_ch101_hybrid_quality_strategies.ipynb": (
        "PARTCRAFTER_PART_LEVEL_V001",
        "SPAR3D_SINGLE_VIEW_V001",
        "TRELLIS_SINGLE_VIEW_V001",
        "TRELLIS_SINGLE_VIEW_16GB_V002",
        "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
        "TRELLIS_REPO_URL",
        "TRELLIS_COMMIT",
        "TRELLIS16_COMMIT",
        "hybrid_quality_orchestrator.py",
        "build_ch101_semantic_proxy.py",
        "register_review_candidate.py",
        "run_trellis_candidate.py",
        "run_trellis16_candidate.py",
        "run_partcrafter_candidate.py",
        "run_spar3d_candidate.py",
        "diagnose_partcrafter_review.py",
        "repair_partcrafter_review_candidate.py",
        "RE_CAMP_PARTCRAFTER_REPAIR_BLEND",
        "PARTCRAFTER_STORED_ARTIFACT_REPAIR",
        "2026-09-02-kaggle-partcrafter-v002-review.json",
        "RE_CAMP_TRELLIS16_SETUP_COMMAND",
        "RE_CAMP_PARTCRAFTER_SETUP_COMMAND",
        "RE_CAMP_SPAR3D_SETUP_COMMAND",
        "BLOCKED_PROVIDER_PREFLIGHT",
        "BLOCKED_PROVIDER_ENTRYPOINT_UNVERIFIED",
        "REGENERATE_REQUIRED",
        "RE_CAMP_INSTALL_CPU_BLENDER",
        "RE_CAMP_TRELLIS_COMMAND",
        "strict visual QA",
        "sourceStatus",
        "gateB",
        "unityInputAllowed",
        "productionPromotionAllowed",
        "files.download",
    ),
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_socket_contract(errors: list[str]) -> None:
    if not CONTRACT_PATH.is_file():
        fail(errors, "missing socket contract: contracts/current_roster_socket_contract_v001.json")
        return
    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid socket contract JSON: {exc}")
        return
    if contract.get("contractVersion") != CONTRACT_VERSION:
        fail(errors, f"socket contract version must equal {CONTRACT_VERSION!r}")
    common = contract.get("commonRuntimeSockets")
    if not isinstance(common, list) or set(common) != {
        "Socket_Equipment_Primary",
        "Socket_VFXCenter",
        "Socket_CameraFocus",
    }:
        fail(errors, "socket contract commonRuntimeSockets does not match the three common anchors")
    characters = contract.get("characters")
    if not isinstance(characters, list) or len(characters) != 5:
        fail(errors, "socket contract must contain exactly five characters")
        return
    codes = [entry.get("code") for entry in characters if isinstance(entry, dict)]
    expected_codes = ["CH101", "CH102", "CH103", "CH104", "CH105"]
    if codes != expected_codes:
        fail(errors, f"socket contract character order must equal {expected_codes!r}")
    source_references = []
    for entry in characters:
        if not isinstance(entry, dict):
            fail(errors, "socket contract contains a non-object character entry")
            continue
        code = entry.get("code", "<missing>")
        for key in ("subject", "modelNamePrefix", "productionBlend", "sourceReference", "detailSockets", "runtimeSocketMap"):
            if not entry.get(key):
                fail(errors, f"{code}: socket contract missing {key}")
        details = entry.get("detailSockets", [])
        runtime_map = entry.get("runtimeSocketMap", {})
        source_reference = entry.get("sourceReference", "")
        production_blend = entry.get("productionBlend", "")
        source_references.append(source_reference)
        if isinstance(code, str) and production_blend != f"{code}_A_HighRes_Production_v001.blend":
            fail(errors, f"{code}: productionBlend does not match the character code")
        if not isinstance(source_reference, str) or not source_reference.endswith(".png"):
            fail(errors, f"{code}: sourceReference must point to a PNG")
        if isinstance(details, list) and len(details) != len(set(details)):
            fail(errors, f"{code}: duplicate detail socket")
        if isinstance(runtime_map, dict):
            for runtime_name, source_name in runtime_map.items():
                if not isinstance(runtime_name, str) or not isinstance(source_name, str):
                    fail(errors, f"{code}: runtimeSocketMap must contain string pairs")
    if len(source_references) != len(set(source_references)):
        fail(errors, "socket contract contains duplicate sourceReference paths")


def validate_source_lock(errors: list[str]) -> None:
    if not SOURCE_LOCK_PATH.is_file():
        fail(errors, "missing source lock: source_lock.json")
        return
    try:
        lock = json.loads(SOURCE_LOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid source_lock.json: {exc}")
        return
    expected = {
        "repository": "https://github.com/siri2677/re-camp.git",
        "branch": SOURCE_BRANCH,
        "commit": SOURCE_COMMIT,
        "reference": SOURCE_REFERENCE,
    }
    for key, value in expected.items():
        if lock.get(key) != value:
            fail(errors, f"source_lock.json {key!r} must equal {value!r}")

    source_dir_text = os.environ.get("RE_CAMP_SOURCE_DIR", "")
    candidates = [Path(source_dir_text)] if source_dir_text else []
    candidates.append(ROOT.parent / "re-camp")
    source_dir = next((path for path in candidates if (path / ".git").exists()), None)
    if source_dir is None:
        print("Source tree check skipped: set RE_CAMP_SOURCE_DIR for local commit/file verification.")
        return

    git_prefix = ["git", "-c", f"safe.directory={source_dir.resolve()}", "-C", str(source_dir)]
    commit_check = subprocess.run(
        [*git_prefix, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if commit_check.returncode != 0:
        fail(errors, f"source commit is not available in {source_dir}: {SOURCE_COMMIT}")
        return

    tree_check = subprocess.run(
        [
            *git_prefix,
            "ls-tree",
            "-r",
            "--name-only",
            SOURCE_COMMIT,
            "--",
            SOURCE_REFERENCE,
        ],
        capture_output=True,
        text=True,
    )
    if tree_check.returncode != 0 or SOURCE_REFERENCE not in tree_check.stdout.splitlines():
        fail(errors, f"source reference is missing at {SOURCE_COMMIT}: {SOURCE_REFERENCE}")
    else:
        print(f"Source tree check passed: {SOURCE_COMMIT} contains {SOURCE_REFERENCE}")


def validate_notebook(relative: str, errors: list[str]) -> None:
    path = ROOT / relative
    if not path.is_file():
        fail(errors, f"missing notebook: {relative}")
        return
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid notebook JSON in {relative}: {exc}")
        return
    if notebook.get("nbformat") != 4:
        fail(errors, f"{relative} must use nbformat 4")
    cells = notebook.get("cells")
    if not isinstance(cells, list) or not cells:
        fail(errors, f"{relative} has no cells")
        return
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
    if not code_cells:
        fail(errors, f"{relative} has no code cells")
    text = "\n".join("".join(cell.get("source", [])) for cell in cells)
    for marker in REQUIRED_MARKERS.get(relative, ()):
        if marker not in text:
            fail(errors, f"{relative} missing marker: {marker!r}")
    for index, cell in enumerate(code_cells, start=1):
        source = "".join(cell.get("source", []))
        try:
            compile(source, f"{relative}#cell-{index}", "exec")
        except SyntaxError as exc:
            fail(errors, f"{relative} code cell {index} has syntax error: {exc}")


def validate_blender_script(relative: str, errors: list[str]) -> None:
    path = ROOT / relative
    if not path.is_file():
        fail(errors, f"missing Blender script: {relative}")
        return
    source = path.read_text(encoding="utf-8")
    try:
        compile(source, relative, "exec")
    except SyntaxError as exc:
        fail(errors, f"{relative} has syntax error: {exc}")


def main() -> int:
    errors: list[str] = []
    validate_socket_contract(errors)
    validate_source_lock(errors)
    for notebook in NOTEBOOKS:
        validate_notebook(notebook, errors)
    for script in BLENDER_SCRIPTS:
        validate_blender_script(script, errors)
    for script in UTILITY_SCRIPTS:
        validate_blender_script(script, errors)
    if errors:
        print("Colab Blender package validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Colab Blender package validation passed "
        f"({len(NOTEBOOKS)} notebooks, {len(BLENDER_SCRIPTS)} Blender scripts, "
        f"and {len(UTILITY_SCRIPTS)} utility scripts checked)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
