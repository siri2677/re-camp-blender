# Re:Camp Blender

Public Colab and Blender automation workspace for the Re:Camp project.

## What this repository contains

- Colab notebooks for Drive and no-Drive execution
- Blender Python scripts for the CH101~CH105 current approved roster
- Asset structure validation and package checks
- Visual QA contact sheets, package hashes, and pre-Unity export contract
- Workflow documentation

The notebooks clone the source art repository from the locked branch and commit:

`art/current-roster-gate-a-ch102` at the locked per-character approval commits

The current generated package covers CH101~CH105 with art-directed v007 blockouts,
rigid blockout weights, armature deformation modifiers, LOD1/LOD2 proxies,
collider proxies, face target placeholders, and idle/run/attack/A-pose preview
renders. These are deformation-review prototypes, not final production skinning,
Unity import proof, Android performance results, or Gate B approval.

## Run in Google Colab

Open the no-Drive notebook when Google Drive authorization is blocked:

`notebooks/00_colab_blender_nodrive_test.ipynb`

The current roster notebook clones `siri2677/re-camp` into `/content`, installs
Blender, uses `xvfb-run` when the runtime has no display, builds all five v007
blockouts from the locked sheets, renders front/side/back plus pose-review views,
exports `.blend` and `.fbx`, validates UV/material/triangle/LOD plus
rig/weight/motion metadata, creates a source-vs-render visual QA contact sheet,
records per-file SHA256 hashes, and creates a ZIP for browser download.

Colab session files are temporary. Download the ZIP before the runtime ends.

## Local checks

```text
python scripts/validate_colab_package.py
```

Large generated binaries should be kept out of normal Git history. Use a GitHub Release or Git LFS when persistent `.blend` or `.fbx` storage is needed.

## Production roadmap

The current roster plan, verification record, export contract, and Unity/Android
blockers are documented in [docs/plans/current-roster-pre-unity-roadmap.md](docs/plans/current-roster-pre-unity-roadmap.md),
[docs/plans/current-roster-pre-unity-verification-20260814.md](docs/plans/current-roster-pre-unity-verification-20260814.md),
and [docs/contracts/current-roster-pre-unity-export-contract.md](docs/contracts/current-roster-pre-unity-export-contract.md).
