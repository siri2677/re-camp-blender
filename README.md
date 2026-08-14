# Re:Camp Blender

Public Colab and Blender automation workspace for the Re:Camp project.

## What this repository contains

- Colab notebooks for Drive and no-Drive execution
- Blender Python scripts for the CH101 documentation blockout
- Asset structure validation and package checks
- Workflow documentation

The notebooks clone the source art repository from the locked branch and commit:

`art/current-roster-gate-a-ch102` at `418ef96`

The current generated asset is an art-directed CH101 technical-prep blockout v005: the v004 visual refinement plus applied transforms, procedural-curve-to-mesh conversion, UV generation, material-slot inspection, triangle reporting, and LOD0 metadata. It is still not a final character model, Unity import proof, Android performance result, or Gate B approval.

## Run in Google Colab

Open the no-Drive notebook when Google Drive authorization is blocked:

`notebooks/00_colab_blender_nodrive_test.ipynb`

The notebook clones `siri2677/re-camp` into `/content`, installs Blender, uses `xvfb-run` when the runtime has no display, builds the v005 technical-prep blockout from the locked CH101 sheet, renders front/side/back views, exports `.blend` and `.fbx`, validates UV/material/triangle/LOD metadata, and creates a ZIP for browser download.

Colab session files are temporary. Download the ZIP before the runtime ends.

## Local checks

```text
python scripts/validate_colab_package.py
```

Large generated binaries should be kept out of normal Git history. Use a GitHub Release or Git LFS when persistent `.blend` or `.fbx` storage is needed.

## Production roadmap

The full CH101 production plan, phase status, acceptance criteria, and Unity/Android blockers are documented in [docs/plans/ch101-production-roadmap.md](docs/plans/ch101-production-roadmap.md).
