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

When a real high-resolution production model is available, use
notebooks/03_ch101_production_mesh_intake.ipynb. It checks out the tool
repository at pinned commit c2f8247ec4fd9b29877ff38b92af64eca18f56aa,
uploads CH101_A_HighRes_Production_v001.blend, runs
validate_ch101_mesh_intake.py with headless Blender, and downloads the
validation report, SHA256, handoff JSON, and ZIP. A successful technical
intake sets sourceStatus to PRODUCTION_MESH_READY, but leaves gateB as
PENDING_HUMAN_REVIEW; it does not approve visual quality or unlock Unity.

For CH102-CH105, use
notebooks/04_current_roster_production_mesh_intake.ipynb. Set CHARACTER_CODE
to the character being checked; the roster validator applies the character's
equipment/socket contract together with the common mesh budget.

The single socket contract is
contracts/current_roster_socket_contract_v001.json. After all five technical
handoffs are downloaded, merge them into a Unity-gated manifest:

```text
python scripts/merge_current_roster_handoffs.py --handoff-dir /path/to/handoffs --output /path/to/current-roster-manifest.json
```

The merge command never enables Unity input automatically. The generated
manifest remains `unityInputAllowed: false` until a separate human Gate B
decision is recorded.

## Free AI 3D candidate path

`notebooks/05_ch101_ai3d_free_autobuild.ipynb` prepares the locked CH101
front/right/back references, plans or runs a free-tier candidate provider,
renders four cardinal Blender views, scores silhouettes, and builds a
non-production review scene from the best eligible candidate.

The preferred order is the Tripo API new-account trial, Stable Fast 3D in
Colab, and TripoSR as the final fallback. Secrets are read from Colab Secrets
or environment variables and are never stored in Git. Every generated result
remains `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, and
`unityInputAllowed: false`.

The detailed zero-cost plan, expected quality, license constraints, commands,
and stopping rules are documented in
[docs/plans/ch101-free-ai3d-autobuild-plan.md](docs/plans/ch101-free-ai3d-autobuild-plan.md).
The local dry-run and Blender negative-gate evidence is recorded in
[docs/plans/ch101-free-ai3d-local-verification-2026-08-18.md](docs/plans/ch101-free-ai3d-local-verification-2026-08-18.md).

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
The execution checklist for production mesh intake is in [docs/plans/ch101-production-mesh-intake-checklist.md](docs/plans/ch101-production-mesh-intake-checklist.md).
