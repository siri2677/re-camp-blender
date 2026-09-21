# CH101 anchored upper trim study — 2026-09-21

This is step 2a of the reference sleeve continuation plan, not completion of
step 2's geometric seam or exact reconstruction of the approved garment pattern.

## Change

A new body copy adds thin gold trim inside the existing 152-vertex local clothing
mask. The mask is not enlarged or reweighted. Two anchors are obtained from the
midpoints of the lower sleeve's existing gold lanes at its top ring. Those two
anchors and the hand-local arm axis define a plane. An interpolated signed plane
distance drives a narrow gold strip in the local graphite shader, preserving
the original image/UV/shader path outside the mask.

- Planar strip width: **1.919273 mm**, matched to the average of the lower rim
  lane-width samples. This is not a constant geodesic width on the body surface.
- Coordinates, topology, original UVs, weights and existing mask: unchanged.
- Old objects and material datablocks: preserved, hidden in the saved working scene.
- Non-adjacent BVH self-pairs and body/hand/sleeve/equipment surface crossings: 0.
  Shared-vertex pairs are excluded; no exhaustive solid or animation proof.
- Two anchor-to-body nearest-surface distances: **4.444847 and 4.253501 mm**.
  These are two point samples, not a global minimum gap. They confirm that
  projected line alignment does **not** mean the sleeve is geometrically joined.

## Visual decision

Eight 1000×1000 CPU Cycles images are retained: front/side/back before and after,
unchanged mask context, and full front. Front/back views show a more coherent
line direction across the layered pieces. The side view still exposes a break
at the opening; the top fade and original painted double-line decoration do
not reproduce a coherent tailored pattern. The line bends with coarse source
triangles. This is an unapproved placement study, not restored final trim.

Do not iterate by widening the gray mask or announce a new overall quality
score. The next real change is upper opening contour and seam construction,
with reference-guided trim routing. Body/sleeve are still unwelded with an
internal temporary cap; no rig, weights, Unity texture bake or approval exists.

## Evidence and execution

- Local Blender 5.2.0 LTS `fbe6228777e7`, CPU Cycles, 32 samples, exit 0.
- Six Blender tests passed: anchor plane/axis, geometry/mask/material retention,
  invalid frame/width, missing mask, true gate rejection, saved reopen/reapply.
- New files compile; 132 Python tests, AI3D validator and Colab validator pass.
  Optional source-tree package check skipped; execution independently checks
  locked art commit and reference hashes.
- Input SHA256: `e4f8e156052ec2c6dec32bba19ef2a118144f2f1f0e47852a504f38a1c7d9c98`.
- Output `CH101_UpperTrimContinuity_NOT_PRODUCTION_v001.blend` SHA256:
  `ac0ecd79c2f2f65ab9db3efa639f350e8ee5a0a6bae55f5a3ef0451919d25309`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/restore_ch101_upper_sleeve_trim.py -- --source PATH/CH101_UpperSleeveMaterial_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_upper_sleeve_trim.py -- --source PATH/CH101_UpperSleeveMaterial_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_UpperTrimContinuity_NOT_PRODUCTION_v001.blend
```

Review-only gates remain locked: AI_GENERATED_CANDIDATE_NOT_PRODUCTION,
PENDING_HUMAN_REVIEW, Unity input false and Production promotion false.
