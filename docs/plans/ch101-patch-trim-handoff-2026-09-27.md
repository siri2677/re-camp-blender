# CH101 patch trim handoff — 2026-09-27

## Outcome

Continued remote `87b03f8688e726b2e65b7a7da0307d3be5c8ea45`; no newer remote
work was present. Local Blender CPU shader study only, not Kaggle or inference.
The prior sector-profile release was the verified input.

**Technical gold-line handoff with only subtle visible change.** The eight
retained renders do not support a major aesthetic improvement or final sleeve
acceptance. Side fold, upper white/graphite boundary, duplicated inherited trim,
coarse face/hair/body/outfit and temporary hand material remain. No 0.6 or other
whole-character score is inferred from shader or static geometry checks.

## Diagnosis and bounded change

The joined seam uses a signed-distance gold strip. The adjacent 321-face upper
patch instead reads the September 23 baked image. Projection/bake sampling and
the later geometry changes do not guarantee that these two representations draw
the exact same line. This study replaces only the patch's material datablock on
a new body copy, keeping its old packed atlas as the base-color fallback.

- Read the existing seam half-width: 0.959636469 mm (planar width 1.919272938 mm,
  not exact geodesic width). Reuse `UpperTrimSignedPlaneDistance`, graphite
  `151518` and gold `D2A445`, with sRGB-to-linear conversion.
- Blend factor is `smoothstep(.98,.995,existingMask) *
  (1-smoothstep(.170,.185,handFrameHeight))`. Shader evaluation is per shading
  point over interpolated attributes, not interpolated vertex-computed weights.
- Zero new influence where the original mask is <=.98 or height >=185 mm.
  Do not widen or rewrite that mask. At 170–185 mm fade back into the old atlas.
- Exactly 321 patch faces retain material slot 10. Other ten material slots and
  all polygon material assignments stay unchanged. 142 patch vertices have
  positive formula weights; this is not a changed-face or painted-pixel count.
- There are 41 seam/patch boundary edges. The four edges intersecting the two
  gold lanes have full blend weight; their shader line criterion is identical
  on both sides. Elsewhere the mask is weaker and may give zero new influence.
  Therefore `formulaTrimBoundaryContinuity=true`, but
  `wholeBoundaryContinuity=false` and `visualContinuityApproved=false`.

During development, the initial whole-boundary full-weight guard correctly
rejected the assumption that the existing mask covered the entire ring.
Inspection showed lower weights away from the gold lanes. The mask was NOT
expanded; the promised continuity was restricted to the four measured gold
crossing edges. A Blender collection lookup was corrected before output existed.
The inherited barycentric mask ranges from 0 to 1.000009179. The diagnostic
formula tolerates only 1e-5 endpoint roundoff and mirrors the shader clamp; the
original values are preserved, not normalized or repainted.

## Preserved data and remaining limitations

Zero moved vertices; 8,236 vertices, 16,435 polygons and 16,464 triangles remain.
Source objects, geometry connectivity, all old UVs and active UV settings,
weights, old material-mask/trim fields, shading flags, equipment and original
material datablocks remain unchanged. Only the new copy gains a height attribute
and an independent patch material. Packed atlas SHA256 stays
`8a3d3efebdd933ab23a9e2a9796b2747a71f5871efab031644c1efc8652342f0`.
The prior cumulative displacement budget is unchanged because no geometry moves.

Static QA passes: non-manifold/zero-area/winding errors zero, non-adjacent
self-surface and equipment surface crossing pairs zero. This BVH check excludes
shared-vertex triangle pairs; it is not a solid containment or animation test.
Original hidden objects remain recoverable; thirteen review meshes are visible.

Inspected front/side/back before/after, full assembly and material-mask context
(eight 1000×1000 CPU Cycles renders). No obvious distant appearance regression
was observed, but visible benefit is small. `mask_context.png` is the inherited
mask, not this narrower shader influence. Geometry and its visible crease are
unchanged. Upper projected trim fragments, broad texture transition and source
white artifacts remain. The new shader is Blender-only procedural authoring;
the packed atlas was NOT rebaked and is NOT an export of the new appearance.

## Verification and reproduction

- Blender 5.2.0 LTS (`fbe6228777e7`); final render exits 0.
- Six Blender regressions cover support restrictions, shader graph and boundary
  contracts, original/UV/field preservation, mutation rejection, temporary-copy
  cleanup, reapply/input/frame/Gate rejection, saved reopen and render hashes.
- Python: 132 run, 131 passed, one skipped; AI3D and Colab validators pass
  (10 notebooks, 38 Blender scripts, 36 utilities).
- Source SHA256: `12bb1194b7706cf7cc5518586ab62dbaf6488f0bab59fd6a779d11a02ed38fde`.
- Output: `CH101_PatchTrimHandoff_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `510e183538be551e4c5c08aaddab137a789a9748f5a5e48cfa9f4c998ba9fbb0`.
- Art commit remains `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_patch_trim_handoff.py -- --source PATH/CH101_SectorProfile_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_patch_trim_handoff.py -- --source PATH/CH101_SectorProfile_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_PatchTrimHandoff_NOT_PRODUCTION_v001.blend
```

NOT_PRODUCTION and PENDING_HUMAN_REVIEW stay locked, Unity input and Production
promotion disabled. No rig, human approval or full-character score.

Published and freshly downloaded on 2026-09-27:
[patch trim handoff study v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-patch-trim-handoff-study-v001).
All 12 payloads passed SHA256 verification. ZIP: 22,935,017 bytes;
SHA256 `52b7cbc8547ca152db8fb05405734a66e95480c956419f9aba465b649d3bf194`.
Tools commit: `0c6ce0fa9125c58758f8ecc9b973ac1984abcbde`.
Restore pointer: `docs/artifacts/CH101-latest-patch-trim-handoff.json`.

## Next substantive step

Preserve this as a separate shader study, not a replacement for the full-character
or sector-profile baseline. Do not repeat near-identical shader/mask tweaks as
quality progress. Next define the white/graphite garment panel boundary explicitly
against the approved reference and author its transition on a separate copy.
Retain before/after evidence and source provenance; bake an explicitly approved
material design for portability only after appearance is defensible. Any topology
redesign requires rebaking the affected faces. Do not increase the original 3 mm
coordinate budget or promote the remaining folded geometry to rig acceptance.
