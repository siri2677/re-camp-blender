# Re:Camp Blender

Public Colab and Blender automation workspace for the Re:Camp project.

## What this repository contains

- Colab notebooks for Drive and no-Drive execution
- Blender Python scripts for the CH101 documentation blockout
- Asset structure validation and package checks
- Workflow documentation

The notebooks clone the source art repository from the locked branch and commit:

`current/art-roster-gate-a-ch102` at `b6c9b3128358e061eee6184230929413eba84101`

The lock points to the CH101 Gate A production-sheet handoff. The notebooks
fetch and detach to this exact commit before resolving
`art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png`.

The current generated asset is a procedural CH101 technical scaffold v010: the v009 LOD-review blockout plus deterministic two-bone review weights, six-material budget compliance, armature deformation modifiers, and pose preview renders. It is intentionally not a visual production model. It does not meet the requested premium Japanese-subculture character quality, and must not be shown as a final character or Gate B candidate.

## Run in Google Colab

Open the no-Drive notebook when Google Drive authorization is blocked:

`notebooks/00_colab_blender_nodrive_test.ipynb`

The notebook clones `siri2677/re-camp` into `/content`, installs Blender, uses `xvfb-run` when the runtime has no display, builds the v010 production-skinning-review blockout from the locked CH101 sheet, renders front/side/back plus pose-review views, exports `.blend` and `.fbx`, validates UV/material/triangle/LOD plus rig/weight/motion metadata, and creates a ZIP for browser download.

Colab session files are temporary. Download the ZIP before the runtime ends.

## Local checks

```text
python scripts/validate_colab_package.py
```

When a sibling `re-camp` checkout exists (or `RE_CAMP_SOURCE_DIR` is set),
the validator also confirms that the locked commit contains the exact
approved-sheet path. The notebook repeats this check inside Colab before
starting Blender.

Large generated binaries should be kept out of normal Git history. Use a GitHub Release or Git LFS when persistent `.blend` or `.fbx` storage is needed.

For the budget-review variant, pass `--optimize-budget` to
`scripts/blender/build_blockout.py`. This produces v008 while preserving the
original v007 review output.

Add `--generate-lods` to produce the v009 LOD review variant. Add
`--production-skinning-review` with the budget and LOD flags to produce v010
with normalized two-bone review weights and the six-material budget audit.
Unity still needs
to assign the exported LOD0/LOD1/LOD2 objects to a `LODGroup`.

## Production roadmap

The full CH101 production plan, phase status, acceptance criteria, and Unity/Android blockers are documented in [docs/plans/ch101-production-roadmap.md](docs/plans/ch101-production-roadmap.md).
