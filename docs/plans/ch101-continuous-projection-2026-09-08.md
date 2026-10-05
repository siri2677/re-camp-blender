# CH101 continuous projection and face curvature experiment — 2026-09-08

## Result

Two genuinely different postprocessing experiments ran once on the preserved
profile-corrected mesh. Both remain rejected by strict semantic QA. The earlier
profile candidate remains the highest numerical score of these three; the latest
artifact pointer indicates the latest experiment, not a selected or approved model.

| Variant | Overall | Silhouette | Appearance | Color | Face-edge proxy | Technical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous profile baseline | 0.834283 | 0.847052 | 0.734795 | 0.662127 | 0.871344 | 1.0 |
| Continuous projection | 0.833999 | 0.847052 | 0.733662 | 0.653626 | 0.889147 | 1.0 |
| Bounded face curvature | 0.833983 | 0.847052 | 0.733597 | 0.653503 | 0.889147 | 1.0 |

The same corrected scorer, references, lighting, cameras and thresholds were used.
Both new variants pass numeric/topology requirements but lack independently
verified body/face, hair, outfit and equipment. Direct agent inspection still
rejects malformed facial volume, projected double features, residual white
patches and absent equipment. No human Gate B approval is claimed.

## Implementation and evidence

`apply_continuous_review_projection.py` replaces per-polygon material selection
with a shared world-position projection and smoothly varying normal/foreground
weights. A single material references three packed images. The exact world
vertex/polygon digest is checked before and after projection. Images are sampled
inside the previously verified foreground bounds. The left side borrows the
right reference and is explicitly marked inferred. The shader is retained in
Blender; no export-ready baked texture atlas or Unity package is claimed.

The side view has fewer abrupt triangle material boundaries, but overlapping
front/side identity features remain. This is not a demonstrated overall quality
gain. The continuous strategy uses ID `CH101_CONTINUOUS_WORLD_PROJECTION_V001`.

`smooth_review_face_region.py` performs four fixed Taubin-style smoothing passes
with lambda 0.25 and mu -0.26 in an explicitly estimated front region between
80% and 90% of character height. The maximum movement is capped at 0.5% of height.
In the actual mesh, 349 of 6,584 vertices moved, with a maximum displacement of
0.003777902 m. All vertices outside the region and polygon connectivity remain
unchanged. The face region is not a semantic landmark transfer. Its visual
benefit is small; it does not create eyes, lips, hair or expression topology.
Strategy ID: `CH101_ESTIMATED_FACE_CURVATURE_CORRECTION_V001`.

## Inputs and reproducibility

- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Input profile Blend SHA256: `b758520e394f22542fe993a4b72fa49c38771508c25f7cef1580ba2d7dee188b`.
- Reference manifest SHA256: `e51d1e7b3fdad92868ff5b8a6169b7ecebd2b6b0e67d0d0032f700ccd436a8d4`.
- Continuous Blend SHA256: `506d771187eefba51a7f4d6c4e09364c84103adaf95c793811aa420b4c6cd696`.
- Face-curvature Blend SHA256: `aad0bb1852c85fe42a55a9b06ee67399bc5d7dd23afa54263e9296263d35ed07`.

`run_continuous_projection_review.py` checks input/reference hashes and pinned
art, runs the recorded strategy gate, creates the shader, renders actual Blender
views, scores, runs strict QA and ranks. It rejects output-directory reuse.
The face-curvature script takes a hash-checked Blend and creates a separate
output. Evaluation then uses that same Blend as both the actual render source
and topology source. The comparison utility recomputes all three candidates.

Validation: 132 Python unit tests, three new real-Blender regression tests
(packed shader/save/reopen, wrong source hash, bounded smoothing and protected
body), and AI3D/Colab validators. The actual experiments used local Blender
5.2; no Kaggle GPU or new provider inference was consumed.

## Next work and stopping condition

Further repetition of these two strategy IDs is rejected. The scores do not
justify replacing the previous best with a new approved selection.

The next useful work needs **real semantic geometry**: a face with deliberate
facial planes and feature topology, distinct hair masses, garment boundaries,
and separate saber/sheath/ribbons/pouch. First audit a new part-level source or
author those structures against the pinned sheets. Spatial renaming or a smooth
shader cannot supply this evidence. Only then repair cross-view texture
registration and build a persistent atlas. These authoring steps remain
unfinished; the current postprocessing experiments do not meet them.

Keep `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`. Preserve every
experiment and its failure reason in GitHub Releases before another runtime.
