# CH101 unbound landmark guide — 2026-09-10

## What actually changed

Eight geometric candidate anchors (hand, elbow, shoulder, waist on NegX/PosX)
were estimated from real vertices of the preserved character. A seven-bone
non-deforming guide was created in a separate review collection. This is not
a final humanoid rig, an anatomy prediction model or a production candidate.

Source SHA256:
`db64df69f1c86dbf1605dbcaccbd5af9c613904cc2de67ff05407d1c93f3b80b`.
The original file, vertices, topology, material slots/assignments, modifiers
and weight memberships are unchanged. No skin weights, Armature modifier,
official Socket objects, or equipment attachment were added to the character.

The existing generic auto-rig was not reused: its fixed bounding-box ratios
are not evidence that joint positions or anatomical left/right match this mesh.
This guide uses **geometric** NegX/PosX labels, deliberately not LeftHand/RightHand.

## Read the renders

- Orange = NegX; cyan = PosX (world coordinate sign, not verified anatomy).
- `xray_landmark_map.png` uses temporary ghost-body material so internal markers
  are visible without shifting their actual positions. Source materials are
  restored before saving. Lines are diagnostic guides, not deforming mesh.
- Front/right/3-4 renders show the same guide against the existing textured model.
- Debug spheres and lines are in a separate collection and must be excluded
  from character topology, material counts and quality evaluation.

Direct inspection finds the hand/arm candidates in the general limb regions,
but it does not prove joint centers or a usable weapon grip. Samples can contain
clothing or floating geometry. The PosX waist band spans about 0.33 m in depth,
so its median must not be treated as a confirmed belt attachment.

The early diagnostic render had occluded markers. A second presentation added
guide lines and a ghost-body view without changing the landmark strategy,
source mesh or acceptance criteria. Both output directories are preserved locally.
The latest diagnostic is released separately from equipment and character assets.

## Verification and next step

Three real Blender tests cover seven non-deforming bones, source preservation,
insufficient-sample rejection and explicit geometric side labels. AI3D/Colab
package checks and the existing Python test suite also run. Actual render-time
digests verify restoration after the ghost-body view.

Next useful work: examine hand surface/cuff separation in close-up, establish
palm/forearm orientation and grip clearance, then test a **clearly estimated**
equipment pose in a separate scene. A waist attachment needs a narrower surface
selection. Do not claim completed binding, deformation, humanoid mapping or
reference-matched face/hair/outfit from this guide.

Run using `scripts/blender/prepare_ch101_landmark_rig_review.py` with `--source`,
`--source-sha256`, `--art-root` and a new `--output` directory. The source hash and
both locked reference image hashes are checked before output; sparse bands
fail rather than silently inventing anchors. Execution used local Blender CPU,
not Kaggle GPU or new provider inference.

Release: `ch101-landmark-guide-review-v001`. Separate pointer:
`docs/artifacts/CH101-latest-landmark-guide.json`. This cannot replace the
full-character or equipment pointers. All outputs retain
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`.
