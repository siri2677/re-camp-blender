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
NOTEBOOKS = (
    "notebooks/00_colab_blender_setup.ipynb",
    "notebooks/01_ch101_blockout.ipynb",
    "notebooks/00_colab_blender_nodrive_test.ipynb",
)
BLENDER_SCRIPTS = (
    "scripts/blender/build_blockout.py",
    "scripts/blender/validate_asset.py",
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
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


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

    commit_check = subprocess.run(
        ["git", "-C", str(source_dir), "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if commit_check.returncode != 0:
        fail(errors, f"source commit is not available in {source_dir}: {SOURCE_COMMIT}")
        return

    tree_check = subprocess.run(
        [
            "git",
            "-C",
            str(source_dir),
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
    validate_source_lock(errors)
    for notebook in NOTEBOOKS:
        validate_notebook(notebook, errors)
    for script in BLENDER_SCRIPTS:
        validate_blender_script(script, errors)
    if errors:
        print("Colab Blender package validation failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Colab Blender package validation passed (3 notebooks and 2 Blender scripts checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
