# CH101 16GB TRELLIS fallback plan

## Decision

TRELLIS.2 is not a required dependency for CH101. Its official 24 GB-class
preflight remains locked. For a 16 GB-class CUDA runtime, use the original
Microsoft TRELLIS API as a separate, one-shot research strategy:

```text
TRELLIS_SINGLE_VIEW_16GB_V002
provider: trellis16
minimum visible VRAM: 16384 MB
provider commit: 442aa1e1afb9014e80681d3bf604e8d728a86ee7
official API: TrellisImageTo3DPipeline
```

The current 16 GB route is a compatibility path, not a quality guarantee.
The model is still single-view image-to-3D, so it may not preserve CH101's
face, hair, outfit, equipment, or proportions well enough for strict visual
QA. It is never promoted to Production Mesh or Unity input automatically.

## Runtime rules

1. `trellis2` is evaluated first and only runs when its own 24 GB preflight is
   ready.
2. `trellis16` is selected next on Linux when a single visible GPU has at
   least 16384 MB, PyTorch CUDA kernel support, and
   `RE_CAMP_TRELLIS16_LICENSE_ACK=1`.
3. The Notebook must receive an explicit
   `RE_CAMP_TRELLIS16_SETUP_COMMAND`; it does not guess or silently install
   the upstream dependency stack.
4. The wrapper uses the pinned upstream `example.py` API, the notebook's
   `sys.executable`, `SPCONV_ALGO=native`, and a 1024 texture target to keep
   the 16 GB profile conservative. `ATTN_BACKEND=xformers` is optional and
   must be explicitly provisioned.
5. Missing GPU, insufficient VRAM, unsupported CUDA, missing terms
   acknowledgement, dependency failure, commit mismatch, or missing mesh
   produces a recorded blocked/failure state without a candidate manifest.
6. A successful GLB follows the existing Blender refine → evaluate → score →
   strict visual QA → rank path. Thresholds are not lowered and a failed
   strategy is not repeated.

## Environment notes

- A T4-class 16 GB device can satisfy the nominal preflight if it exposes at
  least 16384 MB to `nvidia-smi`.
- A device that reports less than 16384 MB is rejected rather than pushed
  into an unsafe memory configuration. Two GPUs are not combined into one
  32 GB address space by the single-GPU `.cuda()` pipeline.
- The upstream project is Linux-oriented; Windows is rejected by preflight
  even if a compatible CUDA device is present.
- The local Windows environment currently has no visible CUDA GPU, so this
  route is prepared but not executed locally.

## Locked result state

All outputs remain:

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

If this one-shot route fails strict QA, stop low-memory single-view retries
and require either semantic Blender authoring, a stronger compatible runtime,
or a new provider with verified 16 GB support.
