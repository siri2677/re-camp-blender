# Re:Camp Blender

Public Colab and Blender automation workspace for the Re:Camp project.

## What this repository contains

- Colab notebooks for Drive and no-Drive execution
- Blender Python scripts for CH101 blockout, AI3D review, and CH101-CH105 intake contracts
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

`notebooks/05_ch101_ai3d_free_autobuild.ipynb` defaults to CH101 and also
supports CH102-CH105 through `RE_CAMP_CHARACTER_CODE`. It prepares locked
front/right/back references, plans or runs a free-tier candidate provider,
renders cardinal and 3/4 Blender views, applies score and geometry Hard Gates,
and only builds a non-production review scene when a candidate remains eligible.

The preferred free-only order is Stable Fast 3D, InstantMesh, then TripoSR.
Wonder3D is pinned as a research-only consistent-multiview experiment and is not
silently inserted into the normal fallback order.
Tripo API remains an optional multiview path when its credits and terms are
acceptable. Secrets are read from Colab Secrets or environment variables and
are never stored in Git. Every generated result
remains `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, and
`unityInputAllowed: false`.

The detailed zero-cost plan, expected quality, license constraints, commands,
and stopping rules are documented in
[docs/plans/ch101-free-ai3d-autobuild-plan.md](docs/plans/ch101-free-ai3d-autobuild-plan.md).
When Colab GPU access is unavailable, run the GPU-independent workstream from
[docs/plans/ch101-no-gpu-workstream.md](docs/plans/ch101-no-gpu-workstream.md)
with `python scripts/run_no_gpu_workstream.py`.
To detect the runtime and switch automatically, use
[docs/plans/adaptive-gpu-workstream.md](docs/plans/adaptive-gpu-workstream.md)
with `python scripts/run_adaptive_workstream.py --provider wonder3D`.
The local dry-run and Blender negative-gate evidence is recorded in
[docs/plans/ch101-free-ai3d-local-verification-2026-08-18.md](docs/plans/ch101-free-ai3d-local-verification-2026-08-18.md).
The durable, secret-free CH101 run metadata is tracked in
[docs/records/ch101-ai3d/2026-08-19-triposr-reference-and-material-preserve.json](docs/records/ch101-ai3d/2026-08-19-triposr-reference-and-material-preserve.json).
The notebook caps free candidate generation at three attempts and runs
`scripts/blender/refine_ai3d_candidate.py` before scoring. Refinement produces a
review-only artifact; it does not create a Production Mesh or unlock Unity.

The completed CH101 local evaluation contains six candidates and 30 renders.
Two TripoSR candidates passed the automated score and geometry gates, but all
technically relevant candidates were rejected by assisted visual QA for face,
hair, outfit, equipment, and hand quality. The final manifest therefore has
`selectedCandidate: null` and status
`REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW`. See the
[final machine record](docs/records/ch101-ai3d/2026-08-20-final-hard-gated-candidate-evaluation-v002.json)
and [Gate B comparison sheet](docs/records/ch101-ai3d/assets/CH101_GateB_ContactSheet_NOT_APPROVED_v001.png).

The current roster GPU/No-GPU execution order and remaining external blockers
are documented in
[docs/plans/current-roster-ai3d-pre-unity-plan.md](docs/plans/current-roster-ai3d-pre-unity-plan.md).

## Local checks

```text
python scripts/validate_colab_package.py
python scripts/validate_ai3d_free_package.py
python -m unittest discover -s tests
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

## Shared branch naming

New shared branches use one prefix convention:

- `feature/<scope>-<short-description>` for implementation work
- `fix/<scope>-<short-description>` for corrections
- `docs/<scope>-<short-description>` for documentation-only work
- `chore/<scope>-<short-description>` for tooling and maintenance

`agent/` and `codex/` are not used for new shared branches. Existing historical
branches are preserved for traceability, but new Colab links, commits, and draft
PRs should use the `feature/` convention when they contain implementation work.
The execution checklist for production mesh intake is in [docs/plans/ch101-production-mesh-intake-checklist.md](docs/plans/ch101-production-mesh-intake-checklist.md).

Before Unity is available, validate the future roster input manifest with
[docs/plans/unity-input-package-preflight.md](docs/plans/unity-input-package-preflight.md).
The preflight checks the five-character socket contract, source/tool commits,
blend hashes, Gate lock, and—after approval—the final Unity package SHA256.
