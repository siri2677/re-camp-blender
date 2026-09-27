# CH101 explicit garment panel layout — 2026-09-27

## Decision and reference basis

Continue verified trim-handoff output from remote `81cfc60`; no newer remote
commits were present. Local Blender CPU work; no Kaggle run or new inference.

The approved character sheet and its turnaround support show a short white
oversleeve over a longer graphite sleeve, with gold undersleeve trim. This study
authors that color separation explicitly. It is **not** a registered 2D-to-3D
measurement, approved sewing pattern, or actual layered cloth geometry.
Hand-frame hem height 245 mm and slope 0.15 are authored layout choices.

Compared front/side/back renders show a clearer white/graphite boundary and less
projected color/trim clutter in the authored region. This is a local readability
improvement, NOT complete reference fidelity or whole-character acceptance.
The white region is simplified, some original decorative detail is deliberately
replaced, and the fade into the upper source image remains visible. Faceted folds,
the side crease, temporary hand material and coarse character elsewhere remain.

## Explicit pattern and scope

- A slanted signed hem is `handHeight - .245 - .15 * handU` (meters).
- Above +1.5 mm: white `F5F4EF`. Between -1.5 and +1.5 mm: graphite binding
  `151518`. Below: graphite undersleeve with existing signed-distance gold line
  `D2A445`. Longitudinal gold stops at the binding instead of continuing through
  the white panel. The 3 mm band is a shader-space width, not sewn thickness.
- The new material domain fades in at hand heights 140–160 mm and out at
  270–290 mm; radial influence is full to 60 mm and zero at 70 mm. These are
  separate new attributes, evaluated per shading point after interpolation.
- Select all faces whose interpolated height/radius can enter this support.
  The region must be connected and wholly within the inspected arm box. Actual
  selection: 433 faces, 244 support vertices; slots 0/1/2/10 map to new slots
  11/12/13/14. Other faces retain their exact prior material assignment.
- Actual full-face world support bounds, meters: X [-0.333801,-0.160387],
  Y [-0.051933,0.056903], Z [0.967195,1.170430]. Torso, other arm, thigh strip,
  cuff, shared lower seam and twelve equipment/hand objects are not edited.

This is an explicit new authored panel domain, **not a claim that the changed
appearance remains inside the old mask**. The original mask itself is unchanged.
Source texture details inside the new domain are intentionally replaced; the
old shaders remain available as fallbacks and on preserved originals.

## Preservation and limits

Zero moved vertices. All 8,236 vertices, 16,435 polygons, 16,464 triangles, UVs,
active UV settings, weights, shading flags, old mask/trim fields and original
eleven material datablocks are preserved. Four independent material copies and
three layout attributes are added only to the new body copy. No source images
are repainted; the old atlas remains packed and the prior cumulative 3 mm
geometry budget does not change.

Static QA still reports zero non-manifold/zero-area/winding errors and zero
non-adjacent self/equipment surface crossing pairs. BVH excludes shared-vertex
triangle pairs; this is not solid containment, skinning or animation proof.
Thirteen body/hand/equipment review meshes are visible when opening the Blend;
all originals remain hidden and recoverable.

Nine renders are retained: matched front/side/back before/after, whole assembly,
inherited `mask_context.png`, and `panel_support.png`. The latter evaluates the
ACTUAL new shader influence on a diagnostic copy; the inherited mask image does
not describe the new domain. No actual overhanging cloth edge, new UV layout,
new texture bake, final PBR, human Gate B or Unity acceptance is claimed.

## Reproduction and verification

Pinned source SHA256:
`510e183538be551e4c5c08aaddab137a789a9748f5a5e48cfa9f4c998ba9fbb0`.
Additional turnaround reference SHA256:
`87d7583cd28081b5bd109ea24e9b00a81e43f2decd621e48225ca3f151ad4b35`.
Art checkout remains `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/design_ch101_garment_panel.py -- --source PATH/CH101_PatchTrimHandoff_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_garment_panel.py -- --source PATH/CH101_PatchTrimHandoff_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_GarmentPanelLayout_NOT_PRODUCTION_v001.blend
```

The initial local eight-render draft was rerun into a fresh directory to add the
actual-domain diagnostic. Only the final nine-render bundle is intended for
publication. Python: 132 tests run, 131 passed, one skipped. AI3D and Colab
validators pass (10 notebooks, 39 Blender scripts, 36 utilities).

Final output: `CH101_GarmentPanelLayout_NOT_PRODUCTION_v001.blend`.
SHA256: `3d8c83891d89fe6f7bd3d2fbe10655a51ff93efa14ffea1620adaf4974017bcc`.
Six Blender regressions cover panel classes/support, connected region and shader
contracts, original geometry/UV/field preservation, mutation rejection, copy
cleanup, input/frame/Gate rejection, saved reopen and all render hashes.

## Next bounded work

Review the hem proportion and whether the reference's short white oversleeve
requires an actual separate edge/layer, instead of treating a color cut as a
finished garment. Plan edge thickness/overlap against the fixed body and existing
equipment with explicit collision checks. The coarse silhouette and upper source
transition need substantive authoring, not another renamed mask tweak. Retain
this layout as a reversible hypothesis; bake only a defensible approved material
design, and explicitly rebake affected faces after topology changes. Rigging,
full-character scoring and Production remain deferred.
