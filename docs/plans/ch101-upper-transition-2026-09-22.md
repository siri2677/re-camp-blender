# CH101 upper-transition geometry trial — 2026-09-22

## Decision

**Static checks pass; visible improvement is insufficient. Do not adopt this as
the completed sleeve fix or repeat the same relaxation strategy.** The saved
copy is a recoverable experiment. Keep the preceding seam-contour source as the
baseline for the next topology rewrite. No full-character score or Gate B approval.

Ten renders include the usual front/side/back before/after, mask context, full
front, and a matched neutral-material side comparison. The neutral comparison
retains the same flat/smooth face flags, camera and lights: it exposes the residual
sharp shelf/fold instead of hiding it with material or smoothing changes.
The approved sheet suggests controlled cloth folds; this trial does not establish
reference-faithful tailoring, anatomy or the final silhouette.

## Implemented experiment

- Exact input `CH101_SeamContour_NOT_PRODUCTION_v001.blend` SHA256:
  `3979e9c6929659ae8d462eceecfa89cd63fd73882f3d0e82581e0991523c4b4d`.
- Art commit `b6c9b3128358e061eee6184230929413eba84101`; the Character Sheet
  and Equipment Sheet hashes are checked by the runner before working on a copy.
- Select a connected 100-vertex forearm region, hand-local axial window
  0.1101–0.195 m, with fades at 0.130/0.170 m and radial fade 0.060–0.075 m.
  Guard the full support of its 240 affected polygons against an inspected
  world-space forearm box. The existing material mask is not enlarged.
- Eight fixed Jacobi steps propose radial-only displacement. Total movement is
  capped at 3 mm times region weight and 10% of each incident source triangle's
  minimum altitude. Use actual loop triangles for clipped n-gons.
- The body/sleeve rim vertices and bridge midpoints (146 total), lower sleeve,
  wrist, hand, equipment, other limbs, original sources and 48-vertex strip stay fixed.
- Geometry topology, UV loops, groups, weights, material slots and flat/smooth
  flags are unchanged. Only the plane-distance trim attribute is updated to follow
  moved positions; the mask values remain identical. No UV bake or rig binding.

## Diagnosed implementation failure

The first global-only move proposal was constrained by narrow source triangles,
including triangles away from the seam. An original area-ratio check reached
26.0868. Global backtracking needed scale 0.03125, leaving only 0.0938 mm movement;
the run correctly rejected it as negligible. A direct-function regression test
reproduced this without rendering (under two seconds of test time).

Identity source transforms ruled out coordinate-space mismatch. Per-vertex
incident-triangle altitude bounds allow wide regions to move while protecting
slivers; the fixed normal/area limits then pass at scale 1.0. Reprojecting total
displacement each iteration also prevents accumulation of float axial drift.
The regression was observed failing before these changes and passing afterward.
No acceptance limit or visual-quality threshold was reduced.

## Measurements and limits

| Check | Result |
| --- | --- |
| Selected/moved vertices; affected polygons | 100 / 100; 240 |
| Maximum actual movement | 1.287559 mm |
| Maximum axial drift | 0.000057504 mm |
| Minimum affected face normal dot | 0.985887 (limit 0.90) |
| Affected face area-ratio range | 0.920066–1.143134 (limits 0.5–1.5) |
| Radial Laplacian RMS | 6.874190 → 6.633319 mm |
| Vertices / triangles / component sizes | 8,196 / 16,384 / [8,148, 48] |
| Non-manifold / zero-area / winding / non-adjacent self pairs | 0 / 0 / 0 / 0 |
| Hand/equipment static surface crossings | 0 |

The RMS reduction is approximately 3.5%, a mesh roughness diagnostic, **not**
a visual quality score. The principal notch remains in clay and textured views.
All static checks exclude shared-vertex self pairs and do not prove solid
validity, swept-motion clearance or deformation quality. Original faces are not
removed merely to improve the statistics.

## Next work: replace the limiting local topology, not another smoothing run

1. Start from the preserved seam-contour source, not this unadopted trial.
2. Inspect actual source-edge connectivity above the 0.110 m body ring; identify
   an upper boundary before the unmodified upper-arm region. Validate one closed
   loop and unique edge correspondence before cutting any working copy.
3. Build a regular surface patch between that upper boundary and the existing
   41-vertex body ring, avoiding the source sliver triangles. Preserve shared rim
   vertices and cuff/hand fit; keep all originals hidden and recoverable.
4. If the locked ring itself prevents the silhouette correction, report that
   separately and design a coordinated boundary/bridge update on another copy.
   Do not silently move the cuff or claim smoothing solved the notch.
5. Transfer UVs/material fields from bounded source triangles with recorded
   projection distances; reject extrapolation onto another body part. Compare
   clay plus textured front/side/back views, not roughness statistics alone.
6. Revalidate topology, UVs, field continuity, intersections and saved-file reopen.
   Only a visually defensible shape should continue to provisional deformation
   tests. Gate B/Production/Unity remain independently locked.

## Execution and reproduction

Local Blender 5.2.0 LTS `fbe6228777e7`, CPU Cycles 32 samples, exit 0; not Kaggle.
The render process emitted a 23-byte unfreed-memory shutdown warning; saved-file
reopen, hashes and tests passed. No inference or paid API was used.

```text
blender --background --python-exit-code 1 --python scripts/blender/relax_ch101_upper_transition.py -- --source PATH/CH101_SeamContour_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_upper_transition.py -- --source PATH/CH101_SeamContour_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_UpperTransition_NOT_PRODUCTION_v001.blend
```

Four Blender tests pass: real movement with distortion limits, exact locked
data/original preservation, invalid input plus rejected-copy cleanup, and saved
reopen/static QA/render hashes. Explicit Python compile, 132 Python tests, AI3D
and Colab validators pass. Optional source-tree package validation is skipped;
the actual runner independently verifies art references. Temporary debug probes
ran inline only; no debug instrumentation remains in committed scripts.

Output Blend SHA256: `5a5a545f24cbc8c62b2226d84f47705c09088afa7e0ebb384d637c2b268d7402`.
The artifact includes a separate `visual-review.json` recording non-adoption;
this is an assistant assessment, not human Gate B approval.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
visualDecision: INSUFFICIENT_IMPROVEMENT_NOT_ADOPTED
```

## Release and restore verification

[Upper-transition trial v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-transition-trial-v001)
is a prerelease of the experiment, not visual acceptance. The ZIP and all 14
payload SHA256s were re-downloaded and verified on 2026-09-22.

- Pointer: `docs/artifacts/CH101-latest-upper-transition-trial.json`.
- ZIP bytes: 18,730,344.
- ZIP SHA256: `8cfaefba5a8305b9b55c0fac14d0f156a2046e23a4d66dcd9cad512d1208db38`.
- Tools commit: `95595ca6fb9f7c46861ee917b114a72d6b6ad39c`.

Before (neutral material):

![Clay before](https://github.com/siri2677/re-camp-blender/releases/download/ch101-upper-transition-trial-v001/clay_before_side.png)

After (principal crease remains):

![Clay after](https://github.com/siri2677/re-camp-blender/releases/download/ch101-upper-transition-trial-v001/clay_after_side.png)
