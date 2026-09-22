# CH101 locked-rim seam contour study — 2026-09-22

This continues the shared body–sleeve seam on a preserved working copy. It is
local topology/shading work, not production modeling completion or rig approval.

## Construction

- Verify the exact source Blend and locked art/reference hashes before changing a copy.
- Keep all 8,123 existing vertices exactly fixed, including the 41-vertex body
  rim, 32-vertex sleeve rim, internal cap and separate 48-vertex thigh strip.
- Split each of the 73 cross-bridge edges once. Replace 73 bridge triangles with
  219 triangles, adding 73 intermediate vertices. Preserve shared topology.
- Derive a bounded midpoint offset from retained boundary normals. Remove its
  axial component. Limit displacement to the smaller of 0.6 mm and 2.5% of the
  minimum altitude of either incident original bridge triangle.
- Preserve original UV loops, groups, field values and material slots. Interpolate
  new UV loops per face; interpolate mask/trim fields for new points. No rig-weight
  transfer is claimed. Smooth the bridge and 105 retained rim-adjacent faces only.
- Keep originals hidden and recoverable. No original file is overwritten.

## Failure diagnosis and regression

The first global-only 0.6 mm cap was unsafe for thin triangles: minimum face
normal dot became -0.784643 and subdivision area ratios reached 1.960803.
The run rejected the copy instead of publishing it. The failure was reproduced
in a minimal direct call before altering the implementation.

Reducing only displacement isolated the cause: near-zero displacement split
correctly; 0.02 mm passed, while 0.05 mm crossed the unchanged normal-dot limit.
The source transform was identity. Thus the defect was disproportionate movement
relative to local triangle width, not subdivision winding or coordinate frames.

A regression test failed before the fix and passed after the local altitude cap.
The original unsafe setting is still explicitly tested to fail and clean up its
temporary copy. Acceptance remains normal dot >= 0.90 and subtriangle area
ratio within [0.05, 0.85]. Stored displacement is checked with 1e-7 m tolerance.
No quality threshold was reduced.

## Measured results

| Check | Result |
| --- | --- |
| Vertices / triangles | 8,196 / 16,384 |
| Connected components | 8,148 + unchanged 48 |
| Shared rim edges / new bridge triangles | 73 / 219 |
| Maximum actual midpoint offset | 0.190963 mm |
| Minimum new-face normal dot | 0.995835 |
| Subtriangle area-ratio range | 0.235239–0.504288 |
| Non-manifold / zero-area / winding errors | 0 / 0 / 0 |
| Copied UV errors / retained normal mismatches | 0 / 0 |
| Non-adjacent self-crossing pairs / hand-equipment crossings | 0 / 0 |
| Default visible meshes after reopen | 13 |

The self-check excludes triangle pairs sharing a vertex. Static triangle tests
do not establish solid containment, skinning, swept-motion clearance or animation.

## Visual decision and next step

Eight 1000x1000 CPU Cycles renders show front/side/back before and after, material
mask context and full front. The seam's faceted shading is softer; the narrow gold
line remains continuous. This is mostly a local shading improvement plus bounded
surface subdivision, not a major silhouette redesign. A side fold/dimple remains,
as do coarse upper-arm anatomy, projected white artifacts and the provisional hand.
The full view still exposes unfinished face/hair, opposite limb and clothing.

Next: identify a bounded upper-transition region from approved references to
address the remaining side fold. Preserve the cuff/hand fit and full originals;
compare front/side/back and reject new crossings or a worse silhouette. Do not
repeat the same shading pass or hide defects with a larger material mask. Then
design forearm/wrist deformation tests with explicit temporary rig/weight provenance.

## Reproduce and validate

Local Blender 5.2.0 LTS `fbe6228777e7`; CPU Cycles 32 samples; not Kaggle/GPU.
Five Blender tests pass, including preserved data, unsafe-offset rejection,
invalid frame/hash/gate rejection and saved-file reopen with static QA.
132 Python tests and both AI3D/Colab package validators pass. The optional source
tree check is skipped in the package validator; this Blender run independently
verifies art commit and reference hashes. New script/test explicitly compile.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_seam_contour.py -- --source PATH/CH101_BodySleeveSeam_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_seam_contour.py -- --source PATH/CH101_BodySleeveSeam_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_SeamContour_NOT_PRODUCTION_v001.blend
```

- Input SHA256: `66933822dbef7553c47d052e9d517fd5c22a424492486ac40a3c36e2f55ea6e3`.
- Output SHA256: `3979e9c6929659ae8d462eceecfa89cd63fd73882f3d0e82581e0991523c4b4d`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Full report: `seam-contour-report.json` inside the versioned artifact bundle.

`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`; `PENDING_HUMAN_REVIEW`;
`unityInputAllowed=false`; `productionPromotionAllowed=false`.
No whole-character score, final texture atlas, material-budget approval, rig,
animation, production promotion or Unity export is produced.
