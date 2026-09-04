# CH101 TRELLIS.2 quality pivot

## Why this pivot exists

The pinned Wonder3D, single-view provider, semantic proxy, and semantic detail
strategies have already reached their one-shot limits. Their rejection history
is preserved and the same `strategyId` must not be run again. The next free
candidate lane is the official Microsoft TRELLIS.2 repository.

## What is prepared

- Repository: `https://github.com/microsoft/TRELLIS.2.git`
- Pinned commit: `75fbf0183001ed9876c8dbb35de6b68552ee08bd`
- Model: `microsoft/TRELLIS.2-4B`
- Official API: `Trellis2ImageTo3DPipeline`
- Strategy: `TRELLIS2_SINGLE_VIEW_V001`
- Required runtime: Linux, CUDA, supported PyTorch kernel, NVIDIA GPU with at
  least 24 GB VRAM
- Required acknowledgement: `RE_CAMP_TRELLIS2_LICENSE_ACK=1`

The wrapper follows the upstream `example.py` API and exports a GLB. It does
not guess a CLI, install dependencies automatically, write secrets, or open
any Unity/Production gate. The optional setup command is explicit:
`RE_CAMP_TRELLIS2_SETUP_COMMAND`.

## Execution order

1. Notebook 07 checks the TRELLIS.2 preflight before installing or importing
   its heavyweight stack.
2. If preflight is not ready, it writes
   `BLOCKED_PROVIDER_PREFLIGHT` and continues without installation or
   inference.
3. If preflight is ready but no explicit setup command is supplied, it writes
   `BLOCKED_PROVIDER_SETUP_UNVERIFIED` and stops safely.
4. After setup, the wrapper imports `torch`, `trellis2`, and `o_voxel` without
   loading checkpoints. An import failure is recorded as
   `BLOCKED_PROVIDER_DEPENDENCY_PREFLIGHT` and inference does not start.
5. With preflight, setup, and import smoke check approved, the pinned checkout
   runs once through `run_trellis2_candidate.py`.
6. Any GLB follows the existing candidate registration → Blender refine →
   evaluate → score → geometry hard gate → strict visual QA → ranking path.

## Gates

Even a successful candidate remains:

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

TRELLIS.2 output is not a production mesh, does not create a Unity package,
and does not replace the need for human Gate B review. A candidate that fails
strict QA is recorded as `REGENERATE_REQUIRED`; thresholds are not lowered.

## Current block

No TRELLIS.2 inference is claimed in this commit. The local host has no
supported NVIDIA runtime, and the Kaggle notebook must first obtain a 24 GB or
larger GPU session. The next valid execution is a fresh Kaggle run using the
latest feature branch, followed by the explicit setup command and the normal
candidate QA path.
