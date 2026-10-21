# CH101 tapered hand and bounded wrist fit — 2026-09-11

## Actual result

Local Blender CPU produced a new part-study blend and five renders. The cage's
26 proximal vertices are tapered: wrist width scale 0.65 and depth scale 0.85,
smoothly returning to the previous shape at local z=0.025 m. Distal cage vertices,
finger paths and thumb tips are unchanged. Subdivision produces 842 vertices,
1,680 triangles, one connected component, zero non-manifold/zero-area faces.
Non-adjacent self-surface triangle overlap pairs are zero in the limited BVH test.

Visual inspection shows a less rectangular wrist base but still simplified
palm, finger and knuckle shapes. This is not an anatomical-quality pass.

## Measurement and limited pose comparison

Three planes 30/45/60 mm toward the estimated elbow from the original geometric
hand anchor yielded 28/29/28 unique intersection samples within a 60 mm ROI.
The fixed target was the middle plane's sample median, approximately
(-0.359139, 0.006596, 0.882520) m. These are geometric sample medians, not verified
closed cut loops, anatomical wrists or authorized source-body cuts. Coplanar
edges are excluded, and insufficient intersection samples fail closed.

Eight combinations were measured once: roll 0/+90/-90/180 degrees around the
handle axis, with slide 0 or +30 mm along the handle. The hand's explicit grip
center follows that slide; the saber itself is unchanged. Each comparison
checks actual saber/detail surface crossings and anchor agreement.

The minimum-distance pose was -90 degrees / +30 mm. All eight happened to pass
the limited equipment surface-overlap check; that does not validate a mechanical
grasp or body integration. No provider inference or quality threshold was changed.

| Metric to the SAME 45mm-slice target | Original rigid pose | Selected pose |
| --- | ---: | ---: |
| Wrist-center distance | 74.315 mm | 44.136 mm |
| Wrist outward-axis / forearm-axis angle | 63.469 degrees | 58.155 degrees |
| Equipment crossing triangles | 0 | 0 |

The prior 47.60 mm figure was nearest source-surface distance, a DIFFERENT metric.
Do not compare 47.60 to 44.14 as if they measured the same improvement.

## Why the image is not attachment evidence

The gray context image retains the original flipper-like source hand under the
new hand. No source vertices were deleted, connected, weighted or moved. A
supplemental probe on the saved scene measured 260 triangle-pair intersections,
188 distinct NEW HAND triangles crossing the source body. It confirms overlapping
meshes, not a joined wrist. Camera perspective can hide the positional/axis error.

The saved model is therefore an unmerged diagnostic. The new wrist remains a
capped end; the original body and earlier hand study remain preserved. Their
visibility changes for isolated inspection only. The source-file hash and source
mesh/material/group/transform digest are checked unchanged.

The original generated report did not yet include the body-overlap field; the
supplemental JSON records the actual saved-scene probe. The final script now
records that probe automatically on future runs as well.

## Next meaningful step

Do not repeat these eight rigid poses or fill the remaining gap with an arbitrary
tube. Identify and visually check the actual cuff/wrist boundary loop in a
separate authoring copy, including correct side/anatomical orientation. Refine
hand size, palm/knuckle volumes and wrist orientation against that boundary.
Only then consider a tested source-hand replacement and seam bridge, with old
source faces preserved in the original file, UV checks and deformation evidence.
No integration should be called complete while the old hand remains underneath.

At present the exact anatomical loop and orientation remain unverified, so body
cutting/merging, skin weights, Gate B, Unity and Android remain unfinished. This
part study does not improve the rest of the character's face/hair/outfit geometry.

## Tests and reproduction

`scripts/blender/refine_ch101_hand_wrist_study.py`: pass `--source`,
`--source-sha256`, `--art-root`, `--output` using a new output directory.
Input blend: `776a8d86188f5e1f47901d2b990f151dd5be703f540f2bb9e32662fe95c5ac1a`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output blend: `0ac9dac544a025270fcdf2f4446d10a87e212eb6ddb88041f76b1bd752378e82`.

Six real Blender tests cover taper locality/topology, explicit anchor alignment,
intersection sampling, tangent-plane rejection, clean self-surface detection,
and the eight-trial stop when all poses cross. The initial plane test mistakenly
used a tangent plane; it was split into interior success and tangent rejection,
not fixed by lowering the sample requirement. Python suite: 132 tests.
AI3D/Colab validators: 10 notebooks, 26 Blender scripts, 36 utilities.

Release target: `ch101-hand-wrist-fit-study-v001`; separate pointer
`docs/artifacts/CH101-latest-hand-wrist-study.json`. Keep prior source/hand releases.
All statuses remain review-only: `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `sourceHandReplaced=false`,
`wristSeamVerified=false`, `attachmentApproved=false`, `graspPoseVerified=false`.
