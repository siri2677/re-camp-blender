# CH101 shared body–sleeve seam — 2026-09-22

Step 2b now has a **real shared-boundary topology study** on a new working copy.
Unlike the previous material-only work, the body and authored sleeve no longer
remain two disconnected overlapping surfaces at this interface. This does not
approve the silhouette, garment design, skinning or final character quality.

## Construction and preservation

1. Verify the exact upper-trim input Blend, locked art commit and reference hashes.
2. On an intermediate body copy, move the artificial clothing cut from its old
   internal termination to 0.110 m along the authored hand-local proximal axis.
   The sleeve upper opening remains at 0.098 m: the bridge spans 12 mm axially.
3. The copy removes 113 source triangles and clips 41 in the bounded distal ROI;
   12,810 source triangles are untouched. All original objects/files remain intact.
4. Remove the intermediate body cap and sleeve upper annular cap in the output.
   Join the 41-vertex body rim to the 32-vertex sleeve outer rim with 73 arc-length
   zipper triangles. Each of the 73 rim edges has exactly one retained face and
   one bridge face. No floating overlay or position-only coincidence is used.
5. Close the sleeve inner rim with a new internal void cap. This remains an
   artificial internal termination, not anatomical skin or final cloth thickness.
6. Preserve all sleeve positions and vertex-group weights by exact remapping.
   Copy retained UV loops into UVMap, StudyUV and SleeveTrimStudy; preserve the
   default UV path for each original material, including the narrow gold shader.
7. Preserve body material-mask/trim attributes at 6,418 retained vertices;
   interpolate only the 41 cut vertices barycentrically on source triangles.
   Maximum cut projection error: 0.000000032168 m. Existing original data is not edited.

The prior 48-vertex thigh strip remains a separate, unchanged component. It is
not deleted or merged to improve component counts. All prior working sources
and the intermediate cut copy are hidden but recoverable in the saved scene.

## Static verification

| Check | Result |
| --- | --- |
| Output vertices / triangles | 8,123 / 16,238 |
| Connected-component sizes | 8,075 + preserved 48 |
| Shared boundary edges / new bridge triangles | 73 / 73 |
| Non-manifold edges / zero-area faces / winding errors | 0 / 0 / 0 |
| Retained normal mismatches / copied UV errors | 0 / 0 |
| Non-adjacent BVH self-crossing pairs | 0 |
| Hand/equipment triangle surface crossings | 0 |
| Visible working mesh objects after reopen | 13 (formerly 14) |

Self-check excludes shared-vertex triangle pairs. No exhaustive solid validity,
cloth collision, swept-motion or pose-dependent clearance proof is claimed.
Normals of retained faces are checked without globally recalculating the merged
mesh, avoiding an unrecorded whole-body change.

## Visual decision

Eight 1000×1000 CPU Cycles renders include front/side/back before and after,
material-mask context, and full front. The baseline renderer shows the original
body and separate sleeve together; the after view shows only the connected copy.

The side view's former open-looking interruption is now covered by a connected
transition, with the gold line carried across it. The bridge is visibly faceted
and its contour forms an angular band. The coarse upper-arm folds, white source
projection defects, upper painted decoration and provisional hand remain.
**Topology pass is not aesthetic acceptance.** No full-character score is assigned.

Next: refine this connected transition's contour and shading on a bounded copy,
preserving the shared rings and established UV/field correspondence. Then define
forearm/wrist deformation tests with explicit rig/weight provenance. Face/hair,
the other limb and full clothing structure still require real authoring.

## Reproduction and tests

- Local Blender 5.2.0 LTS `fbe6228777e7`, CPU Cycles 32 samples, exit 0.
- Six Blender tests pass: shared topology and preserved originals/sleeve/strip,
  exact attribute transfer plus off-surface rejection, degenerate ring rejection,
  wrong hash, true gate, saved reopen with UV/attributes/visibility.
- New/changed Python files compile; 132 Python tests pass; AI3D/Colab validators pass.
  Package validator's optional source-tree check is skipped. The run independently
  verifies the art commit and reference hashes.
- Input SHA256: `ac0ecd79c2f2f65ab9db3efa639f350e8ee5a0a6bae55f5a3ef0451919d25309`.
- Output `CH101_BodySleeveSeam_NOT_PRODUCTION_v001.blend` SHA256:
  `66933822dbef7553c47d052e9d517fd5c22a424492486ac40a3c36e2f55ea6e3`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/join_ch101_body_sleeve.py -- --source PATH/CH101_UpperTrimContinuity_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_body_sleeve_seam.py -- --source PATH/CH101_UpperTrimContinuity_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_BodySleeveSeam_NOT_PRODUCTION_v001.blend
```

NOT_PRODUCTION; Gate B pending human review; Unity input and Production promotion
remain false. No final material-budget consolidation, texture bake, rig, animation
or Unity package is produced. This study is not permission to modify original sources.

Release: [body–sleeve seam v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-body-sleeve-seam-study-v001).
Restore pointer: `docs/artifacts/CH101-latest-body-sleeve-seam.json`.
Re-download verification passed for all 11 payloads on 2026-09-22.
ZIP: 14,804,735 bytes; SHA256
`c51cba515438618c50b7edd56e2de92e77819ed855bf25202e9034711dfc63cc`.
Tools commit: `471c81ce8fe66aa887e8eb53f1b51e572720c24f`.
