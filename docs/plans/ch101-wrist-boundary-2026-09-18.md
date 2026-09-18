# CH101 wrist boundary review — 2026-09-18

## Finding: do not use the provisional plane as the sleeve/skin seam

The approved character sheet depicts a dark sleeve end and exposed hand. A new
Blender CPU diagnostic shows the *preserved original body* alone, without the
new hand/cuff/saber hiding it. In the source-texture front close-up the orange
provisional section does not follow the painted dark-cuff edge; it lies further
toward the hand. The side close-up shows stretched/discontinuous projection over
the fused forearm/hand mass. This is an assistant visual assessment, not a human
Gate B approval or a measured pixel-to-surface anatomical registration.

Therefore the previous section is useful for geometry/clearance diagnostics,
but is **not accepted as an anatomical sleeve/skin cut boundary**. Do not infer
that all distal triangles are hand skin or that all proximal triangles are cloth.
Moving the plane by a few millimetres without reference registration does not
resolve that ambiguity. No original faces were cut, replaced or welded.

## Actual diagnostics

Four 1000×1000 renders are retained: original source texture front/side, and
geometric-side coloring front/side. The colored copy is explicitly diagnostic:

| Color | Triangle class | Count |
| --- | --- | ---: |
| Gray | Outside local geometric review cylinder | 12,872 |
| Cyan | Wholly proximal to plane within ROI | 121 |
| Red | Wholly distal to plane within ROI | 138 |
| Orange | Plane-straddling within ROI | 29 |

The ROI requires all triangle vertices within 60 mm radial distance and 100 mm
axial half-extent. These are exhaustive/disjoint **geometric** classes for 13,160
source triangles, not semantic labels or a deletion mask. Triangle indices only
refer to the pinned source's loop-triangle ordering. The source and diagnostic
copies retain every triangle. The original mesh geometry/material digest and
input file hash are unchanged; render visibility changes only prepare the view.

Closed source sections were also measured at -5, 0 and +5 mm about the provisional
plane. Areas: 0.00217899, 0.00219458 and 0.00217922 m². All three are geometric
loops only: closed graph topology is not anatomical correctness.

| Study object | Unique triangles crossing source body | Against wholly proximal source | Against wholly distal source | Against straddling source |
| --- | ---: | ---: | ---: | ---: |
| Authored hand | 119 | 0 | 95 | 30 |
| Reduced cuff | 336 | 0 | 37 | 309 |
| Cloned saber | 5 | 0 | 5 | 0 |

The last three columns overlap because one study triangle may cross several
source triangles. These counts do not quantify penetration volume. No wholly
proximal crossing is not authorization to delete everything on the other side.
The separate hand/cuff clearance result remains valid in its prior static scope;
it never established integration with the original source hand.

## Concrete next modeling step

1. Preserve this scene and the reduced cuff as references. Work on a separate
   sleeve-end mesh using the approved sheet's dark fabric silhouette and exposed
   wrist/hand relationship, not the source texture's projected edge as truth.
2. Show front/side/back boundary context and the new sleeve end with the authored
   hand. Treat the placement as a design hypothesis until checked against art;
   do not declare the current orange plane approved or shift it solely to remove
   surface intersections.
3. Validate the new sleeve-end/hand clearance and identify an explicit local
   source replacement region on a working copy. Only then consider replacement,
   leaving the original intact and checking topology, UV, normals and deformation.

This step produces evidence rather than falsely completing a join. Face, hair,
outfit, final skinning, animation and full-character quality are still unfinished.

## Validation and retention

Script: `scripts/blender/review_ch101_wrist_boundary.py`; Blender background args
`--source`, `--source-sha256`, `--art-root`, `--output` (new directory).
Three fixtures validate disjoint sides/remote body exclusion, axis reversal and
invalid-axis rejection. Python suite and AI3D/Colab compile checks run separately.

Input: `CH101_ReducedCuff_NOT_PRODUCTION_v001.blend`.
Input SHA256: `a354ea0f03347be50c5518ad69fcc5dc2a5044790c879f228f3305fd4f7d6c8f`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output: `CH101_WristBoundaryReview_NOT_PRODUCTION_v001.blend`.
Output SHA256: `b6fe4f998ebcbd61f391189d22759d15c35ecbc5821714846c34180218c2a552`.
Record: `docs/records/ch101-ai3d/2026-09-18-wrist-boundary.json`.
Release: `ch101-wrist-boundary-review-v001`; separate diagnostic pointer
`docs/artifacts/CH101-latest-wrist-boundary-review.json`. Do not replace the latest
cuff or full-character pointer with this diagnostic. Retain the report, actual
blend, four renders and this explanation; re-download and verify hashes.

Blender returned exit 0 and saved all files; its shutdown printed one unfreed
memory block (0.000023 MB). This is recorded, not treated as visual validation.
All gates stay `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`, `cutAllowed=false`,
`sourceHandReplaced=false`, `anatomicalSeamVerified=false`,
`wristIntegrationAllowed=false`, `attachmentApproved=false`.
