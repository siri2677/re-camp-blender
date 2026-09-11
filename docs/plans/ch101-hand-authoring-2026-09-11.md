# CH101 connected hand authoring study — 2026-09-11

## Outcome

A genuine connected hand part was authored in local Blender CPU: palm, thumb,
index, middle, ring and little finger are joined by shared topology at root holes.
This is not a collection of disconnected cylinders or painted-on fingers.
No voxel remeshing or replacement of the source character was performed.

The control cage has 212 vertices / 420 triangles. One applied subdivision level
produces 842 vertices / 1,680 triangles, one connected component, zero
non-manifold edges and zero zero-area faces. Six vertex groups identify authored
regions; they are not skin weights or an approved rig. Smart-project UV is a
study UV, not the final atlas. A single neutral material shows geometry clearly.

The approved sheet was inspected and its pinned hash verified. Hand detail is
small in that sheet; dimensions, palm shape and curved finger paths are authored
estimates, not recovered anatomical measurements. Visual quality is still a
simple stylized part study, not a finished Rin hand. Fingers and palm need
proportion, knuckle, webbing, fingertip and wrist refinement.

## Local correction and regression

The first actual render showed four fingers and thumb, but static surface checks
found 7 saber triangles and 9 diamond-detail triangles crossing the hand.
Weighted region inspection localized every crossing hand triangle to the thumb.

Ranked hypotheses were thumb-path intrusion, subdivision thickness, and global
alignment. A fixture using the real equipment builder, actual hand builder,
applied subdivision and the same alignment reproduced `16 != 0` before the fix.
Only the thumb path's z coordinates were changed from
`[0.040, 0.052, 0.055, 0.046, 0.040]` to
`[0.032, 0.032, 0.032, 0.035, 0.040]` metres. x/y coordinates, palm/fingers,
subdivision and saber/hand anchors remained fixed. This takes the thumb below
the handle cross-section instead of through it.

The test then passed, and a new actual scene reproduced zero crossings for the
saber and every detail object. The original first attempt and its report/renders
are retained. This is a local geometry correction, not a repeat provider strategy
or an acceptance-threshold change. Original source-hand intersections are NOT
fixed by this result, since this hand has not been integrated into that source.

A supplemental BVH self-overlap probe on the saved corrected hand found zero
non-adjacent triangle pairs (pairs sharing any vertex were excluded). This is a
limited static surface check, not complete solid containment, near-contact,
grip force, self-collision through animation, or mechanical grasp validation.
The initial generated report predates this supplemental probe and correctly
records that its own pipeline does not run a self-intersection test.

## Source preservation and the integration boundary

The retained saber anchor is matched within 1e-9 m. The hand wrist center is
approximately 0.04760 m from the nearest original character surface. This is
not an anatomical wrist-to-wrist measure; no defensible body seam has been
established. The approved sheet alone does not define an exact 3D cut loop.

Original character/equipment vertices, material slots, weights and transforms
remain unchanged. The source body is hidden only for viewing the isolated study.
It is retained in the saved file and has not been cut or replaced. The study
adds a neutral material; its separate material count is not a new pass for the
combined six-material production contract.

Next: refine the palm and individual knuckle proportions, identify the source
wrist/cuff seam using additional close-up geometry evidence, and fit the study
wrist to it while retaining a defensible grip. Check normals/UV/connection after
an explicit copy-only join. Do not simply extend a tube across the 4.76 cm gap
and call it anatomical integration. Then address rig weights and motion tests.
Body, face, hair and outfit quality are unchanged and remain below final quality.

## Reproduction, tests and retention

Script: `scripts/blender/build_ch101_hand_authoring_study.py`.
Arguments: `--source`, `--source-sha256`, `--art-root`, `--output` (new directory).
Input hash: `d09d94258c1ff7fd78f28b36060631ba8c394b7ba7e9a36cecdeb4adbc9133c6`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
First blend: `8f6a755db7997ba66e788c0a1d6200bf3aa1e630e659a0845161496bc1bc45f2`.
Corrected blend: `776a8d86188f5e1f47901d2b990f151dd5be703f540f2bb9e32662fe95c5ac1a`.

Four actual Blender tests cover connectivity/groups, pose input rejection,
anchor alignment and subdivided equipment clearance. 132 Python unittests,
AI3D validator and Colab validator pass (10 notebooks, 25 Blender scripts,
36 utilities). No paid API or GPU was used.

Release target: `ch101-connected-hand-study-v001`; separate pointer
`docs/artifacts/CH101-latest-hand-study.json`. Archive directories `initial/`
and `corrected/` retain both real blends, eight renders and the reports. Use
`corrected/CH101_ConnectedHandStudy_NOT_PRODUCTION_v001.blend` for the new study.
Neither file is a production source or an approved full-character candidate.

All gates stay `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `attachmentApproved=false`,
`graspPoseVerified=false`, `sourceHandReplaced=false`.
