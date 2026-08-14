#!/usr/bin/env python3
"""Validate the Colab + Blender automation package without Blender installed."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
        "art/current-roster-gate-a-ch102",
        "apt-get",
        "DRIVE_ROOT",
    ),
    "notebooks/01_ch101_blockout.ipynb": (
        "CH101",
        "418ef96",
        "build_blockout.py",
        "validate_asset.py",
        "TOOLS_DIR",
        "drive_output",
    ),
    "notebooks/00_colab_blender_nodrive_test.ipynb": (
        "No Google Drive access is used.",
        "https://github.com/siri2677/re-camp.git",
        "https://github.com/siri2677/re-camp-blender.git",
        "418ef96",
        "xvfb-run",
        "files.download",
        "CH101_Blockout_REVIEW_v005.blend",
        "v005",
    ),
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


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
