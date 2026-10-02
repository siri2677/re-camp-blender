# CH101 Part-Level Low-Memory Quality Pivot

## Decision

The next free-first candidate route is the official PartCrafter repository,
pinned to commit `3d773bf02fad51c7ab31a5615573fec93b287b30`. It is selected
before TRELLIS when a compatible GPU is visible because it generates a
compositional set of mesh parts and has an official minimum of 8 GB VRAM.

This is a research/review lane, not a Production Mesh path. The repository
code is MIT, but the pretrained checkpoint, RMBG checkpoint, and dependencies
must be checked separately before any commercial redistribution.

## Why this is a better fit

Earlier candidates repeatedly failed on face, hair, outfit, equipment, and
hand boundaries. A part-level output gives the Blender review path separate
geometry to inspect and map instead of treating a single opaque surface as a
character. Provider part indices are not silently renamed as CH101 semantic
labels: body/face, hair, outfit, and equipment mapping remains a human-review
item.

## Runtime contract

- Provider: `partcrafter`
- Strategy: `PARTCRAFTER_PART_LEVEL_V001`
- Official entrypoint: `scripts/inference_partcrafter.py`
- Pinned commit: `3d773bf02fad51c7ab31a5615573fec93b287b30`
- Default: six parts, 1024 tokens, 50 inference steps, seed 101001
- Minimum VRAM preflight: 8192 MB
- Required acknowledgement: `RE_CAMP_PARTCRAFTER_LICENSE_ACK=1`
- Required setup command: `RE_CAMP_PARTCRAFTER_SETUP_COMMAND`

The setup command is deliberately explicit. The notebook never guesses a
package installation command and never installs the heavyweight provider when
preflight, acknowledgement, or setup is missing.

## Execution order

```text
reference preparation
→ GPU/CUDA/kernel/license preflight
→ pinned PartCrafter checkout
→ official inference script
→ object.glb + individual part_*.glb registration
→ Blender refine
→ evaluate
→ score
→ geometry hard gate
→ strict visual QA
→ rank
```

The object mesh and all generated part files are recorded with provenance.
Part files are preserved beside the review candidate; no provider part is
promoted to a Unity socket or production semantic group automatically.

## Stop rules

- No compatible GPU: record `BLOCKED_PROVIDER_PREFLIGHT` without installing.
- Missing acknowledgement or setup command: record a blocked setup state.
- Wrong provider commit: reject the run.
- Fewer than four generated parts: reject the candidate.
- Any strict visual or geometry failure: record `REGENERATE_REQUIRED` and do
  not repeat this strategy.
- All results remain
  `AI_GENERATED_CANDIDATE_NOT_PRODUCTION` + `PENDING_HUMAN_REVIEW` with
  `unityInputAllowed=false` and `productionPromotionAllowed=false`.

## Follow-up

If PartCrafter fails, compare one new strategy such as SPAR3D only when its
Hugging Face access is available. Do not rerun PartCrafter with the same
strategy after a rejection, and do not lower the strict thresholds.

## Rejection diagnosis and stored-artifact repair

The v002 rejection record is also supplied to `quality_progress_gate`. Its
top-level `strategyId`, `scores`, and `REGENERATE_REQUIRED` state are flattened
into the gate history, so PartCrafter cannot be selected again by a fresh
Kaggle notebook run.

The only automatic repair allowed for the stored v002 artifact is
`scripts/blender/repair_partcrafter_review_candidate.py`. Set
`RE_CAMP_PARTCRAFTER_REPAIR_BLEND` to a supplied review `.blend` to run the
bounded path:

```text
join provider objects
→ bridge measured gaps only within the safe distance
→ decimate to the contract triangle budget
→ generate missing UVs
→ apply the coarse CH101 review palette
→ re-evaluate and re-score
```

An unsafe component gap blocks the repair without saving a partial output.
Semantic material mapping and reference-conditioned face/hair/outfit/equipment
geometry remain external-input requirements. The repair is never a provider
rerun, never a Production Mesh, and never enables Gate B or Unity input.
