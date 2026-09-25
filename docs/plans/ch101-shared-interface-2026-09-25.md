# CH101 coordinated shared-interface study — 2026-09-25

## Progress recovered and decision

The local checkout was 16 commits behind the shared branch. A clean fast-forward
to `ea9efaf` recovered the September 21–23 sleeve shading/material/trim, actual
body–sleeve join, seam contour, rejected relaxation, upper patch and isolated
albedo bake. The latest albedo prerelease was downloaded and all 14 payload
hashes verified. The pinned art checkout was NOT updated.

This follow-up is **partial local contour improvement, not final visual
acceptance**. Matched neutral and textured views show a modestly softer lower
notch. The side crease, upper inherited texture transition, stylized fold design
and coarse full character remain unfinished. Keep previous baselines; do not
interpret static eligibility or a geometric metric as a whole-character pass.

## Different operation from the rejected locked-rim relaxation

The previous relaxation held the offending shared boundaries fixed. This study
moves BOTH shared rims, their bridge, the lower sleeve and nearby upper patch
with one coordinated radial field on a new mesh copy.

- Two outer cross-sections at hand-local heights 65 and 160 mm define a ruled
  envelope at matching radial angles. Wrist, distant body and exterior vertices
  stay locked. All affected face support is inside the inspected forearm box.
- A smooth axial envelope fades to zero at the fixed boundaries. The field uses
  25% of the radial envelope difference, with a hard maximum movement of 3 mm.
  This is an authored shape hypothesis, not recovered anatomical truth.
- The SAME additive radial field applies to inner and outer surfaces, avoiding
  their collapse onto one target radius. Only radial motion is permitted.
- Shared indices, connectivity and polygon order do not change. Existing UVs,
  including the face-index baked atlas, remain exact. No rebake, painted mask
  expansion, shader change, new rig weights or topology replacement is performed.
- Preserved trim/mask attributes travel with the vertices. This avoids silently
  realigning the procedural line independently of the already-baked patch.

Exploratory full-envelope displacement required 11.295 mm and produced strong
distortion. It was NOT retained. The committed 0.25-strength operation remains
below the 3 mm ceiling. Do not rerun it cumulatively or increase limits to force
a visual pass. The input SHA is pinned to the prior albedo copy.

## Measured results

| Check | Result |
| --- | --- |
| Moved / exactly preserved vertices | 320 / 7,916 |
| Affected polygons | 713 |
| Maximum actual move / hard maximum | 2.823655 / 3 mm |
| Maximum axial drift | 0.00005074 mm (<0.0001 mm tolerance) |
| Moved SleeveSeam / BodySeam / bridge vertices | 32 / 41 / 73 |
| Moved inner upper-rim vertices | 32 |
| Minimum affected face-normal dot | 0.980186 (minimum allowed 0.90) |
| Affected area ratio | 0.774131–1.132731 (allowed 0.5–1.5) |
| Sampled inner/outer rim distances | 1.477660–1.550532 mm; prior ~1.5 mm |
| Vertices / triangles / components | 8,236 / 16,464 / 8,188 + 48 |
| Non-manifold / zero-area / winding errors | 0 / 0 / 0 |
| Non-adjacent self / hand-equipment surface pairs | 0 / 0 |

At 32 radial angles and four fixed section heights, RMS radial slope-jump changes
from 0.325427 to 0.251345. This is a sampled geometry diagnostic, NOT a visual
quality score, an anatomical fit measure or proof that the notch is gone.
The 32 rim-thickness pairs are samples, not whole-shell clearance proof.
Self-BVH checks exclude shared-vertex triangle pairs. No swept motion, solid
containment, skinning, Unity or Android test is claimed.

## Preservation and visual evidence

All original objects/file remain unchanged and recoverable. The separate
48-vertex thigh-side strip is unchanged. Material slots, face shading flags,
all existing UV layers, groups/weights, masks and trim fields are unchanged.
The active shader still reads the same packed isolated atlas. Packed atlas
SHA256: `8a3d3efebdd933ab23a9e2a9796b2747a71f5871efab031644c1efc8652342f0`.

All ten retained 1000×1000 CPU Cycles renders (32 samples) were inspected:
front/side/back before/after, full assembly, inherited material-mask context,
and neutral side before/after. `mask_context.png` shows the PREVIOUS material
mask, not the geometry edit support. Exact moved IDs and displacements are in
the report. A prior input-validator guard was strengthened after rendering;
the saved output passed the final implementation's preservation/reopen tests.

Texture comparison shows no return of the earlier pointed white patch streaks,
but upper projection artifacts and trim inconsistency remain. UV preservation
does not imply constant texel density: the recorded face-area changes still
stretch/compress the existing texture. The final garment atlas/PBR budget is
not accepted. Full-character face/hair/outfit authoring remains substantial.

## Verification, reproducibility and locked gates

- Local Blender 5.2.0 LTS (`fbe6228777e7`), CPU; render process exit 0.
- Six Blender tests pass: coordinated motion/static QA, exact preservation and
  mutation rejection, bounds/frame rejection, failed-copy cleanup, wrong input/
  path/Gate rejection, saved reopen/visible-object/render-hash verification.
- Python: 132 run, 131 passed, one skipped. AI3D and Colab validators pass,
  including the pinned art source-tree check; `git diff --check` passes.
- Source SHA256: `84d73be3ada9f946a930c5dd96b7a228fde36fabad7e5320f2597b49e15490e9`.
- Output: `CH101_SharedInterface_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `78d3cff27162913ac30283c8ac56ea2f8a57566cb98066cdc3ca2c3b71fe08e2`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_shared_interface.py -- --source PATH/CH101_PatchAlbedoBake_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_shared_interface.py -- --source PATH/CH101_PatchAlbedoBake_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_SharedInterface_NOT_PRODUCTION_v001.blend
```

Review-only separate release: `ch101-shared-interface-study-v001`.
Restore pointer: `docs/artifacts/CH101-latest-shared-interface.json`.
Never replace the full-character, original albedo or seam-contour pointers.

Published and freshly re-downloaded on 2026-09-25:
[shared interface study v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-shared-interface-study-v001).
All 14 payloads (Blend, ten renders, technical report, read-me and visual decision)
passed SHA256 verification. ZIP: 21,612,435 bytes;
SHA256 `2d1ff0ef19caece8b8e9a2e79b177b319b277b93898cd6cf941942fde5742cfd`.
Tools commit: `7257913291c0267da5df742a46ea0ba7bd1816e7`.

All results retain NOT_PRODUCTION, PENDING_HUMAN_REVIEW, Unity input disabled,
Production promotion disabled, `rigBound=false`, and `fullCharacterScore=null`.

## Next bounded work

1. Compare residual side/back crease against the approved garment silhouette;
   define angle-specific profile/fold support rather than reapplying this field
   or another whole-band smoothing pass. Preserve the original displacement budget.
2. Treat upper trim/material mismatch as a separate bounded authoring task. If
   connectivity changes, explicitly rebake affected faces instead of blindly
   reusing this face-index atlas. Do not expand gray masks to hide defects.
3. Deformation remains deferred until contour/material continuity is defensible;
   do not promote this partial result into final rig or Gate B acceptance.
