# CH101 bounded patch albedo bake — 2026-09-23

## Decision

**Local texture improvement; not final garment or full-character approval.**
Matched front/side/back renders reduce pointed white streaks at the new upper
patch. Dark cloth and the narrow gold line are more coherent. The locked lower
boundary notch, uneven source transition, inherited surface artifacts, coarse
face/hair and provisional hand remain. Geometry is unchanged in this step.

Working branch: `feature/ch101-free-ai3d-autobuild`. Local Blender 5.2.0 LTS
`fbe6228777e7`, CPU Cycles; no Kaggle GPU or new AI-provider execution.

## Diagnosis and rejected alternatives

The pinned upper-patch input has seven source UV/material charts. Its old
per-vertex mapping mixes charts in 52 of 321 new triangles. Three originally
continuous boundary edges acquire UV breaks (23 continuous / 42 original seams).
These are baseline provenance counts, not a new full-character quality score.

A face/corner-aware single-chart transfer was attempted without relaxing the
12 mm projection limit. It correctly rejects face 16144, vertex 8122, chart 6:
12.910153 mm from that chart. A small chart cannot cover the whole new triangle.
The rejected diagnostic remains tested; it is not automatically retried.

Instead, a fresh 1024-square atlas gives each of the 321 patch triangles a separate
tile. The new patch shader explicitly uses `UpperPatchBakeUV`. The original UVMap
is preserved, including its flawed patch coordinates, but is NOT used by the new
patch shader. This avoids cross-chart interpolation; it does not claim to repair
the old UV layer or create a final optimized garment atlas.

## Bounded bake and preservation

1. Verify input SHA256, locked art commit and approved reference hashes.
2. Bake from the preserved pre-patch source, never from the flawed patch texture.
3. Initial source-only coverage missed 5 of 1,926 interior samples. Stop rather
   than fill pixels or widen the target material mask.
4. Include one edge-ring of original source faces: 221 removed-source faces plus
   60 collar faces = 281. All source vertices must remain inside the inspected
   forearm box (-0.40 < world X < -0.17, 0.91 < world Z < 1.14 metres).
5. Selected-to-active CPU bake uses 20 mm cage extrusion, 60 mm ray limit and
   three-pixel padding. These are ray settings, NOT relaxed geometry acceptance.
6. Independent white-emission coverage now has zero misses in 1,926 samples.
   This checks sampled padded pixels, not every texel, exact source triangle
   identity, or preservation of every decorative detail.
7. Bake diffuse color only, excluding direct/indirect illumination. Save PNG
   and pack it in the Blend. Assign one additional material ONLY to 321 faces.
8. Preserve all geometry, transforms, weights/groups, old UV layers, mask fields,
   retained material assignments, and source objects. Preserve the 48-vertex strip.

Output geometry remains 8,236 vertices / 16,464 triangles, components 8,188 + 48.
Static manifold, winding, area and non-adjacent self/hand/equipment surface checks
pass. They do not prove animated clearance, solid containment or skinning.

This is an albedo-only review bake: roughness is provisional, full PBR is not
transferred, material/atlas count is not the final game budget, and inherited
source artifacts can remain. Do not expand the gray mask to conceal them.

## Regression and validation

- Baseline input fails the isolated-runtime-atlas regression as expected.
- Saved output passes all six Blender tests: diagnosis, rejected chart transfer,
  exact preserved geometry/old UV/masks/weights, shader path and atlas isolation,
  static QA/reopen/hash checks, wrong hash/output/gate rejection.
- Mutation tests reject changes to geometry, old UV and mask data.
- Explicit Python compile of the two new scripts and Blender test passes.
- Existing Python unittest: 132 passed.
- AI3D and Colab package validators passed (10 notebooks, 35 catalogued Blender
  scripts, 36 utilities). Optional source-tree validation was skipped; this bake
  independently verifies pinned art/reference hashes.
- No temporary debug probes are committed. The preservation guard added after
  rendering was also run directly against the saved output by the tests.

```text
blender --background --python-exit-code 1 --python scripts/blender/bake_ch101_patch_albedo.py -- --source PATH/CH101_UpperPatch_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_patch_uv.py -- --source PATH/CH101_UpperPatch_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_PatchAlbedoBake_NOT_PRODUCTION_v001.blend
```

## Next bounded task

1. Use this baked copy as a material comparison study, retaining seam-contour
   and upper-patch originals for rollback.
2. Measure the lower shared-ring notch from matched side/back and neutral views.
   Design a coordinated upper-patch/lower-sleeve interface adjustment. Lock wrist,
   hand, equipment and distant body; record exact changed support and displacement.
3. Reject inverted faces, crossings or texture regression. If connectivity must
   change, explicitly rebake affected faces; do not reuse this face-index atlas
   blindly. No repeated whole-band smoothing with the same failure.
4. Only after silhouette and material continuity are defensible, attempt a bounded
   provisional deformation study. Then address full-character face/hair/outfit
   authoring. A local sleeve pass does not satisfy Alpha Review or human Gate B.

## Evidence and locked gates

- Input SHA256: `9d55a8f2e470c5a844e09e78eab6cda4d36afdaa28c7f8fd86632e6f0ddc22d1`.
- Output SHA256: `84d73be3ada9f946a930c5dd96b7a228fde36fabad7e5320f2597b49e15490e9`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- `sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION`.
- `gateB: PENDING_HUMAN_REVIEW`.
- `unityInputAllowed: false`; `productionPromotionAllowed: false`.
- Full-character score: unmeasured; rig/Unity/Android: not executed.

Bundle contents: Blend, eight before/after/context renders, albedo and coverage
PNGs, full report, this read-me and compact visual decision (14 payload files).
Publish as a new prerelease and verify ZIP/payload hashes after re-download.
Never overwrite the previous release or full-character pointer.

## Published and re-downloaded

[Patch albedo bake v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-patch-albedo-bake-v001)
is a review-only prerelease. ZIP and all 14 payload SHA256 hashes were verified
after a fresh GitHub download on 2026-09-23. Previous releases remain available.

- Tools commit: `000f5db01d757803b5e34ed779be2aff520b110d`.
- ZIP: 18,692,747 bytes.
- ZIP SHA256: `c995294857ddf4d16efe65a1dc280e7976bf6f687d78169e2c14ef7bcff92e6d`.
- Restore pointer: `docs/artifacts/CH101-latest-patch-albedo-bake.json`.

Before:

![Before side](https://github.com/siri2677/re-camp-blender/releases/download/ch101-patch-albedo-bake-v001/before_side.png)

After (same geometry; albedo-only change):

![After side](https://github.com/siri2677/re-camp-blender/releases/download/ch101-patch-albedo-bake-v001/after_side.png)

Full character remains unfinished:

![Unfinished assembly](https://github.com/siri2677/re-camp-blender/releases/download/ch101-patch-albedo-bake-v001/assembly_front.png)
