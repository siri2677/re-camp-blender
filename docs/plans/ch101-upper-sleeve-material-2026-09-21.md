# CH101 upper sleeve bounded material study — 2026-09-21

This implements step 1 of the [continuation plan](ch101-reference-sleeve-continuation-2026-09-21.md).
It is a reversible **material-region hypothesis**, not a completed sleeve,
semantic mesh reconstruction, visual-quality acceptance or new AI inference.

## Implementation

On a new copy of the latest repaired body, a connected float point-attribute
mask selects the forearm above the authored sleeve. The hand-local axial
window is 0.084–0.225 m, with full axial weight at 0.098–0.185 m; radial
fade runs from 0.060 to 0.075 m. Source triangles interpolate point weights.
The whole support of affected polygons, including zero-weight border vertices,
is bounded and checked, not just the positive-weight vertices.

- 152 positive-weight vertices; 94 at full weight; 337 affected polygons.
- Support world bounds: X [-0.353210, -0.191899], Y [-0.051614, 0.049702],
  Z [0.929663, 1.102858] m. The region does not reach the torso, other arm,
  hands, head or thigh. This is not an anatomical segmentation claim.
- Separate material copies blend the complete original shader with matte
  graphite `#151518` (sRGB converted to linear) at mask weight 1.
- Mask-zero vertices preserve the original shader; wholly zero-weight faces
  are unaffected. Existing image datablocks, UVs and material graph remain in
  the original; the internal cap retains its original material and zero mask.
- Coordinates, edges, polygons, original UVs, weights, vertex groups and
  transforms are identical. No trim reconstruction, contour edit or smoothing
  is performed on the source body. Fourteen working meshes remain visible.

## Visual result, not a final pass

Eight 1000×1000 CPU Cycles renders were generated: matching front/side/back
before and after, orange mask context, and full front. The mask context was
inspected alongside the textured views. White projection contamination is
reduced in the bounded region, but the original painted gold decoration is
also suppressed. The upper fade has a visible gray transition, residual white
patches remain near the distal opening, and the original faceted/inflated arm
shape is more visible. The source gold line and new lower sleeve line still
do not connect. This is a controlled material experiment, **not design approval**.

Retain it as an optional working copy with the prior baseline fully recoverable.
Do not use more gray masking as a substitute for garment authoring or infer
an overall score improvement. Next work is a reference-defined garment boundary
and actual trim continuity, followed by bounded contour changes. Other source
anatomy, face/hair and projection defects remain unchanged.

## Verification

- Blender 5.2.0 LTS `fbe6228777e7`, local CPU Cycles, 32 samples, exit 0.
- No non-adjacent BVH self-pairs; no body versus sleeve/hand/equipment surface
  crossings. Shared-vertex pairs are excluded; no containment/deformation proof.
- Eight Blender tests passed: bounded connected mask/exclusions, fade behavior,
  wrong frame rejection, original geometry/UV/shader preservation, invalid
  weights, input hash mismatch, true Unity gate, saved reopen/reapplication guard.
- One initial test expected a float32 midpoint to equal 0.5 within 7 decimal
  places; observed 0.500000067. The test now uses a documented 1e-6 numeric
  tolerance. No production threshold or quality criterion changed.
- New Python files compile; 132 Python unittests pass; AI3D/Colab validators pass.
  Optional source-tree validation was skipped by those package tools; the
  Blender run separately checks the art commit and reference hashes.

Source SHA256:
`f627a89f822bc7d48269bb34b99415aec6e16be62279e0ad92108df2ce444f66`.
Output `CH101_UpperSleeveMaterial_NOT_PRODUCTION_v001.blend` SHA256:
`e4f8e156052ec2c6dec32bba19ef2a118144f2f1f0e47852a504f38a1c7d9c98`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_upper_sleeve_material.py -- --source PATH/CH101_SleeveSurface_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_upper_sleeve_material.py -- --source PATH/CH101_SleeveSurface_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_UpperSleeveMaterial_NOT_PRODUCTION_v001.blend
```

All results remain AI_GENERATED_CANDIDATE_NOT_PRODUCTION, PENDING_HUMAN_REVIEW,
Unity input false, Production promotion false. No rig, final atlas, welded body,
FBX/Unity package or whole-character score is created.
