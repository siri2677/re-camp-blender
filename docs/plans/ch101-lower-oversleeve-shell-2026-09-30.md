# CH101 lower oversleeve shell — 2026-09-30

## Decision

**Static geometry study passes; visual replacement is NOT adopted.** Keep the
September 29 rounded-hem baseline. This is a real closed shell with inner/outer
faces, not another recolor or contour-smoothing pass. However, wrapping the
existing source surface inherits its angular folds and creates an obvious raised
upper boundary. Front/back renders show stepped facet shading; the side view
reads as a raised cuff, not a completed reference-faithful short jacket sleeve.

`adoptionAllowed=false`, `fullCharacterScore=null`. Eight matched/evidence renders
and the Blender working scene are preserved as a separate review prerelease.
Do not repeat this same ray-offset strategy with more rows or smoother shading
and call that a completed garment.

## Source and design hypothesis

- Resume commit: `8a77f33aa167cb4393aa17557306ba4e1cd411f1`; local/remote matched.
- Source: `CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend`.
- SHA256: `39f5e07de24a433a7d74ff51a607219ace089162c916a0c1040c96c9b7b31a20`.
- Art: `b6c9b3128358e061eee6184230929413eba84101`.
- Approved Character Sheet and REVIEW Turnaround were visually inspected. They
  support a short white layer over a longer graphite sleeve, but NOT measured
  millimeter dimensions or the exact current source folds. Equipment and
  Turnaround hashes are also checked on execution.
- Runtime: local Blender 5.2.0 LTS CPU; no new Kaggle/provider inference.

The shell covers signed hem coordinates **+3 to +21 mm**: only an 18 mm lower
course of the white panel, deliberately stopping before the old upper shader
crossfade. 128 angular columns and 19 longitudinal rows define paired inner and
outer surfaces. End walls close both ends; the arm bore remains open. 2 mm ray
clearance and 0.8 mm ray wall offsets are authoring hypotheses, NOT constant
normal thickness. Stored vertex pairing and opposing-surface samples are checked.

Both upper and lower edges remain unattached. The 1.5 mm nominal signed-plane
separation from the existing rounded binding is an explicit study gap, NOT an
invisible weld, sewing allowance or completed overlap. No reference sewing
pattern can be inferred from this construction. The longitudinal image is an
isolated side view, NOT a physical cutaway or continuous thickness proof.

Original body, every old mesh, UV, weights, material assignment and the rounded
binding remain unchanged. The old 48-vertex strip remains. Prior body displacement
budget is NOT reset. Original and new geometry coexist in the review scene;
this is not optimized production topology. White material uses `F5F4EF` with
roughness 0.72; true face normals expose rather than disguise source faceting.
No UV/bake, Face BlendShape, rig or animation is fabricated.

## Measured evidence

| Check | Result |
| --- | --- |
| New shell | 4,864 vertices / 4,864 quads / 9,728 triangles |
| Connected components / Euler characteristic | 1 / 0 |
| Non-manifold / winding / zero-area errors | 0 / 0 / 0 |
| Tested non-adjacent self/body/equipment/binding intersections | 0 |
| Minimum sampled body gap | 0.427955 mm, 24,320 samples |
| Paired ray wall dimensions | 0.799939–0.800044 mm |
| Sampled opposing-surface distance | 0.450163–0.800023 mm, 14,080 samples |
| Minimum shell-vertex distance to binding | 1.483252 mm |
| Original body movement | 0 |

Gap sampling uses vertices, edge midpoints and triangle centroids; thickness
sampling uses each side's vertices and triangle centroids. Shared-vertex self
pairs are excluded. No continuous collision, solid containment, cloth simulation
or animation clearance is proven. Geometry passing does not imply visual QA.

Output Blend SHA256:
`24f8fadfae541ffe3ed9dbf6da005025c4eedef4270ea440c0b891eb0ea9f02f`.
`shell-ray-provenance.json` records all 2,432 body hit triangles, positions and
directions; its hash is recorded in the technical report. Render hashes are
recorded there too. The compact `visual-review.json` is the explicit NOT-ADOPTED
decision; the technical report's pending-review label is not an approval.

## Verification

- Five real Blender tests pass: provenance/source preservation, thickness and
  static QA, invalid frame/source/output and gate rejection, open shell rejection,
  body collision rejection, saved reopen/render hashes/locked gates.
- Python unittest: 132 passed.
- AI3D and Colab validators: PASS (10 notebooks, 43 Blender scripts, 36 utilities).
  Optional source-tree check is skipped; the actual Blender run separately
  verifies pinned art and all three reference hashes.
- Eight renders: before/after front/side/back, isolated oblique/longitudinal.
- No whole-character Alpha Review score was recomputed or implied.

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_oversleeve_shell.py -- --source PATH/CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-shell-output
blender --background --python-exit-code 1 --python tests/blender/test_oversleeve_shell.py -- --source PATH/CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_LowerOversleeveShell_NOT_PRODUCTION_v001.blend
```

## Next task — panel topology and interface design, not another offset retry

1. Retain the rounded-hem baseline and this shell only as collision/thickness
   evidence. Create a separate reference-guided panel cage with named front,
   outer-arm and rear rails. The source surface becomes a collision constraint,
   NOT the shape to copy at every ray sample.
2. Define upper and lower interface loops explicitly. Compare the intended short
   white sleeve length and silhouette in front/side/back; do not silently keep
   the provisional 18 mm test-course height as the finished design.
3. Author connected quad flow with controlled folds and an actual shared or
   explicitly separated hem interface. Preserve all source meshes as rollback;
   do not weld skin to clothing or delete the unrelated 48-vertex strip.
4. Validate shape change, intersections, normal thickness and budget BEFORE UV
   transfer/baking. Only a visually defensible panel can proceed to deformation.
5. No new provider rerun, threshold relaxation, material-mask enlargement or
   body-displacement-budget reset. Human Gate B, Unity and Android stay blocked.

All artifacts retain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `rigBound=false`.

## Published recovery checkpoint

[Lower oversleeve shell study v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-lower-oversleeve-shell-study-v001)
contains the model, eight renders, ray provenance and reports. Fresh fetch
verified all 13 payloads. ZIP: 24,233,727 bytes; SHA256
`eb14b1104616818cff9db38200ff71de48ea639d04f9738642884f6859955919`.
Tools commit: `bf5de21b96eee3ee1ed512c80be8375df54e3b97`.
Pointer: `docs/artifacts/CH101-latest-lower-oversleeve-shell.json`.
