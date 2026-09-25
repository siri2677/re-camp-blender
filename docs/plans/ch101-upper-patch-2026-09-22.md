# CH101 bounded upper forearm topology patch — 2026-09-22

## Result and visual decision

**Local geometry progress; texture rework required. Not final visual acceptance.**
This is a different operation from the unadopted relaxation: it replaces the
sliver-constrained interior of one inspected annulus, sharing both real boundary
loops with the retained mesh. It starts from the preserved seam-contour source.

Ten renders include textured front/side/back comparisons, full front, mask context
and neutral side comparison. The upper transition looks more regular in neutral
views, but the lower locked-boundary kink remains. Textured views show upper-edge
streaks/pointed white contamination and distorted inherited decoration. Do not
adopt this as a finished garment, enlarge the gray mask to conceal defects, or
proceed to rigging on the basis of static tests alone.

Neutral views use the saved face-shading flags: new patch faces are smooth while
retained flags are unchanged. Their appearance therefore reflects BOTH changed
topology and normal interpolation, not a controlled geometry-only score.

## Construction and preservation

1. Verify source SHA256, locked art commit and reference-image hashes.
2. Select 221 original polygons by bounded hand-local centroid height/radius.
   Verify one connected annulus, Euler characteristic zero, degree-two boundary
   cycles, full forearm support bounds, and exact lower `BodySeam` correspondence.
3. The lower boundary has 41 vertices at approximately 0.110 m; the upper boundary
   follows 24 actual source-edge vertices at heights 0.1803–0.2144 m. Neither loop
   is snapped or moved. No floating overlay substitutes for shared topology.
4. Remove those polygons and 88 now-orphaned vertices ONLY on the output copy.
   Keep all original objects/file recoverable. Add four 32-vertex interior rings
   and 321 zipper triangles, interpolating between boundary curves.
5. Keep the proposed interior within 6 mm of the removed source patch (29 points
   need this cap). The 12 mm projection rejection limit remains unchanged and is
   also checked at new face centers when choosing material slots.
6. Project only onto triangles belonging to the removed forearm patch, never
   another limb or body surface. Record per-vertex source triangle, barycentric
   weights, UVs and distance. Transfer material mask values; update the existing
   plane-distance trim field for new points. This is provisional projection UV,
   not a final atlas or proof of UV-island continuity.
7. Copy every retained polygon's positions, UV loops, material slot and smoothing
   flag exactly. Remap all retained vertex-group weights. New points receive only
   a study group, not invented rig weights. Lower sleeve, hand and equipment stay fixed.

The source's separate 48-vertex strip remains untouched. Internal void cap, coarse
face/hair and other source defects remain. Original full-character pointers are
not replaced by this scoped geometry study.

## Diagnosis and regression evidence

UV transfer initially rejected a point located exactly at a source triangle vertex.
The single-precision barycentric utility returned approximately
`[-0.000010698, -0.000010698, 0.999989331]` for an exact vertex whose weight is
`[0, 0, 1]`. The minimized direct build test failed before the fix. Double-precision
dominant-plane interpolation now handles exact vertices explicitly, rejects real
extrapolation under the unchanged 1e-5 bound, normalizes tiny roundoff only after
that test, and checks reconstructed position within 2 micrometres.

The next rejection was genuine geometric deviation, not numerical noise. A ruled
interior exceeded the 12 mm source projection bound. An 8 mm point cap still left
a face center too far away; the final 6 mm cap keeps the tested vertices AND face
centers within the existing limit. No acceptance threshold was increased.

Five Blender tests pass: real transfer and shared boundaries, exact-vertex and
invalid barycentric cases, retained data/original preservation, invalid inputs
and gates, saved reopen/static QA/render hashes. The initial failing regression
and original full CLI both pass after the fixes. Inline debug probes were not
saved to repository files.

## Measured static results

| Check | Result |
| --- | --- |
| Removed source polygons / retained polygons | 221 / 16,114 |
| New interior vertices / new patch triangles | 128 / 321 |
| Shared lower + upper boundary edges | 41 + 24 |
| Output vertices / triangles | 8,236 / 16,464 |
| Connected component sizes | 8,188 + unchanged 48 |
| Maximum new-patch vertex projection distance | 6.000038 mm |
| Copied retained UV errors / normal mismatches | 0 / 0 |
| Non-manifold / zero-area / winding errors | 0 / 0 / 0 |
| Non-adjacent self pairs / hand-equipment surface crossings | 0 / 0 |

The vertex projection maximum is not a full surface Hausdorff bound. Self-tests
exclude triangle pairs sharing a vertex. None proves solid containment, skinning,
swept-motion clearance, final UV continuity or aesthetic quality.

## Next bounded task

- Diagnose new-patch UV-island/material-boundary correspondence using source
  polygon provenance, checker textures and close-ups. Separate actual UV seams
  from the mask fade; do not assume nearest-triangle interpolation preserves islands.
- Design face/corner-aware transfer or a dedicated patch UV layout with preserved
  boundary correspondence, then rebake only the bounded source material evidence.
- Compare reference, clay and textured views. Keep original images and shaders
  recoverable. A geometry pass must not hide a texture regression.
- Address the lower locked-ring kink separately with a coordinated interface
  design if still necessary; do not silently move the wrist or widen the edit scope.
- Only after silhouette/material continuity is defensible, design provisional
  deformation tests. Human Gate B and all Production/Unity gates remain separate.

## Reproduction and status

Local Blender 5.2.0 LTS `fbe6228777e7`, CPU Cycles 32 samples, exit 0; not Kaggle.
Explicit script/test compile, 132 Python tests, AI3D and Colab package validators
pass. The package validator's optional source-tree check is skipped; this run
independently verifies the locked art/reference hashes.

```text
blender --background --python-exit-code 1 --python scripts/blender/rebuild_ch101_upper_patch.py -- --source PATH/CH101_SeamContour_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_upper_patch.py -- --source PATH/CH101_SeamContour_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_UpperPatch_NOT_PRODUCTION_v001.blend
```

- Input SHA256: `3979e9c6929659ae8d462eceecfa89cd63fd73882f3d0e82581e0991523c4b4d`.
- Output SHA256: `9d55a8f2e470c5a844e09e78eab6cda4d36afdaa28c7f8fd86632e6f0ddc22d1`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Source status: `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`.
- Gate B: `PENDING_HUMAN_REVIEW`.
- `unityInputAllowed=false`; `productionPromotionAllowed=false`.
- No full-character score, final-quality grade, rig, Unity or Android claim.

The user's simplified stylized-game target is recorded in the main continuation
plan. This output is far from an established commercial-character quality level;
neither resemblance to reference art nor this local pass guarantees that target.

## Release and recovery

[Upper patch study v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-patch-study-v001)
contains the Blend, ten renders, full technical report, visual decision and read-me.
All 14 payloads and the ZIP were re-downloaded and SHA256 verified on 2026-09-22.
Prior releases and the rollback baseline remain available.

- Pointer: `docs/artifacts/CH101-latest-upper-patch.json`.
- ZIP bytes: 18,883,136.
- ZIP SHA256: `35f45959ab0c3deb0cb4136959480bb3a5c81ec6952df0e8843a2433584f68e9`.
- Tools commit: `fbd9e7d06a3ac1cfedfecc56124c77632139644d`.

Before:

![Neutral before](https://github.com/siri2677/re-camp-blender/releases/download/ch101-upper-patch-study-v001/clay_before_side.png)

After (includes new smooth-face normals):

![Neutral after](https://github.com/siri2677/re-camp-blender/releases/download/ch101-upper-patch-study-v001/clay_after_side.png)

Remaining texture defects:

![Texture rework required](https://github.com/siri2677/re-camp-blender/releases/download/ch101-upper-patch-study-v001/after_side.png)
