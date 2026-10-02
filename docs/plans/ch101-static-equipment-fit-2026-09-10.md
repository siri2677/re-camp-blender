# CH101 static equipment fit diagnostic — 2026-09-10

## Outcome

The preserved character and separate authored saber/sheath now have an actual
combined **estimated static placement** scene. This is not a rig-bound attachment,
closed-hand grip, Production candidate or Unity package. The ribbon is retained
but hidden/staged, not placed. Character geometry, weights and materials remain
unchanged, as do both input files.

Source SHA256: `db64df69f1c86dbf1605dbcaccbd5af9c613904cc2de67ff05407d1c93f3b80b`.
Hardware SHA256: `9ac9a4b59c61ebc7a831b02a230c2497552609269b95117e6b2e670d21025845`.
Pinned art: `b6c9b3128358e061eee6184230929413eba84101`.

## What was fixed and measured

1. Loading the equipment succeeded, but changing visibility while iterating
   Blender's live `collection.all_objects` invalidated the iterator. A failing
   loaded-library regression reproduced the None object. A list snapshot fixes
   the iteration without skipping objects or deleting anything.
2. The first lateral waist ray hit the outer arm (x=0.31946 m). The revised
   geometric torso region excludes triangles outside 55% of the half-width and
   outside the normalized 0.56–0.66 height band. Its hit is x=0.21522 m, z=1.02480 m.
   It is still a shell/clothing hit, not verified anatomical belt geometry.
3. A narrower distal hand band yielded 77 vertices and a median position of
   approximately (-0.38340, -0.00628, 0.84525) m. Hand/cuff ambiguity remains.
4. Three explicit static orientations were compared at the same hand anchor.
   This is bounded pose diagnosis, not repeated AI inference or an acceptance
   threshold change. All pose matrices and results are retained in the report.

| Saber orientation | Crossing triangles away from hand | Near hand |
| --- | ---: | ---: |
| Forearm aligned | 19 | 23 |
| Vertical | 0 | 38 |
| Front pitched | 0 | 34 |

The front-pitched trial is the selected **diagnostic** pose. Selection only
minimizes the above surface test, not grasp quality. Counts sum unique crossing
triangles per saber/detail object; they are not contact volume or severity.
Near-hand means within 0.065 m of the estimated anchor, not confirmed fingers.

The revised sheath still has 38 crossing triangles. Nine distinct retained
material-slot names exist across character/equipment, exceeding the six-material
contract. Slots may include unused review materials; this conservative count
does not claim nine active draw calls. Neither obstruction is waived.

## Visual judgement

Actual hand and waist close-ups show an open hand intersecting the handle and
residual sheath/body interference. The full-body view is useful for scale and
layout, **not proof of a valid attachment**. Existing character white texture
patches and fused semantic geometry remain visible; this step does not repair them.

BVH triangle overlap plus nearest-vertex surface distance is a static surface
test only. It does not detect every solid-containment case, guarantee clearances,
or simulate animation/physics. A zero away-hand count is not collision-free status.

## Next implementation boundary

- Create a reliable palm/finger/cuff separation and a closed grip pose before
  binding this weapon. Do not just offset the saber away from the hand to clear
  overlaps and then call it held.
- Identify a real belt/hip attachment surface and check sheath clearance through
  the planned motion. The current ray may still select clothing or artifacts.
- Reconcile equipment and character materials with a persistent shared/baked
  atlas; preserve the old reference projection and do not silently drop detail.
- Then revisit rig weights, clearance and full-character quality. Current skin
  weights are unchanged and no limb deformation or attachment approval is claimed.

## Reproduction and retention

Run `scripts/blender/review_ch101_equipment_fit.py` with `--source`,
`--source-sha256`, `--hardware`, `--hardware-sha256`, `--art-root`, and a new
`--output` directory. Paths are resolved before scene loads. Input hashes and
reference hashes must match; existing output is refused.

Five actual Blender tests cover loaded visibility iteration, exact anchor
transforms, crossing/disjoint surface detection and exclusion of the outer arm
from the waist ray. Tests use generated fixtures, not local untracked assets.
The full Python suite and AI3D/Colab validators also run.

Release: `ch101-static-equipment-fit-review-v001`; separate pointer:
`docs/artifacts/CH101-latest-static-fit.json`. The archive preserves the initial
incorrect placement, revised bounded-pose placement, reports and all eight
renders. The original character/equipment/landmark pointers are unchanged.

All gates remain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`; `attachmentApproved=false` and
`graspPoseVerified=false`. Full-character score is null. Execution used local
Blender CPU; no new provider inference or paid resource was used.
