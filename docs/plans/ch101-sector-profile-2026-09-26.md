# CH101 directional sector profile — 2026-09-26

## Outcome and continuation

Remote was checked: `c8681db10ac29b68f4d068ed44cd7908d9c726aa` had no newer
commits. Continue the verified September 25 shared-interface copy, preserving
the original September 23 albedo geometry as the cumulative displacement anchor.
This is local Blender CPU work, not another Kaggle/SPAR3D inference.

**Subtle partial local improvement, not final sleeve acceptance.** Eleven matched
and diagnostic renders were inspected. Lower side/back contour is slightly less
bulged, but the angular side fold remains prominent. Upper inherited texture and
gold trim do not yet form a coherent garment. Whole-character face, hair, body,
outfit and opposite hand remain coarse. No 0.6 or full-character score is claimed.

## Bounded operation

Measure outer radius at 64 hand-frame angles and heights 83, 98 and 110 mm.
Two observed ridges are targeted at 326.25 and 157.5 degrees with angular half
widths 50 and 35 degrees. These are authored geometry hypotheses after reference
review, NOT exact angular measurements recovered from the character sheet.
Compact cosine-squared angular weights combine with an axial smoothstep over
78–98–132 mm. An inward radial move has maximum requested amplitude 1.2 mm.

The resulting TOTAL displacement from the original albedo copy is projected into
a 3 mm ball with a 0.0001 mm storage margin. It is **not** an extra 3 mm allowance
on the September 25 result. Both input file SHA and the hidden original geometry
digest are pinned. Existing over-budget inputs and baseline substitution fail
closed. No repeated whole-band smoothing, remeshing or material-mask expansion.

| Check | Result |
| --- | --- |
| Selected / actually changed vertices | 138 / 137 (one rounds to its original stored coordinate) |
| Outside-support vertices preserved exactly | 8,098 |
| Affected polygons / cumulative-budget-clipped vertices | 337 / 7 |
| Maximum incremental / original-cumulative move | 1.198497 / 2.999919 mm |
| Maximum axial drift | 0.00004773 mm |
| Incremental normal dot minimum / area ratio | 0.994589 / 0.954939–1.026023 |
| Cumulative normal dot minimum / area ratio | 0.979208 / 0.794276–1.138441 |
| Sampled inner/outer rim distances | 1.464511–1.550532 mm |
| Vertices / polygons / triangles | 8,236 / 16,435 / 16,464 |
| Components | 8,188 + 48 |
| Non-manifold / zero-area / winding errors | 0 / 0 / 0 |
| Non-adjacent self / equipment surface crossing pairs | 0 / 0 |

Sampled RMS radial slope-jump: 0.2513454494 → 0.2382133006. Local ridge excess
at 326.25 degrees: 2.969391 → 2.341978 mm; at 157.5 degrees: 2.581702 →
1.691781 mm. These are geometry diagnostics, **not quality scores**. Static BVH
excludes shared-vertex triangle pairs. Rim pairs are samples, not exhaustive
solid clearance, skinning or swept-animation evidence.

## Preservation and visual evidence

New body copy only. Source file and all existing meshes are unchanged. Topology,
polygon order, all UV layers, material slots, shading flags, weights, material
mask and trim attributes are exact. The separate 48-vertex thigh-side strip and
twelve hand/saber parts are untouched. Existing body/sleeve shared topology stays
joined. Packed albedo atlas is unchanged:
`8a3d3efebdd933ab23a9e2a9796b2747a71f5871efab031644c1efc8652342f0`.

Eleven 1000×1000 renders: front/side/back before/after, full assembly, inherited
material-mask context, neutral side before/after, and new `sector_support.png`.
The last image shows requested geometry edit weights on a diagnostic copy only;
it is not a new material mask and does not show exact post-clamp displacement.
No obvious distant silhouette/hand/saber regression is visible in these views.
The side notch, upper projection artifacts and trim mismatch remain. Preserved
UVs still stretch/compress with geometry; this is not a final garment atlas/PBR.

## Verification and reproduction

- Blender 5.2.0 LTS (`fbe6228777e7`), CPU, render exit 0.
- Eight Blender tests pass: compact support, cumulative budget, real asset/static
  QA, baseline/frame/limit rejection, UV/field/locked-vertex guards, failed-copy
  cleanup, CLI/Gate rejection, saved-file reopen/hash/visibility/budget checks.
- Python: 132 tests run, 131 pass, one skip. AI3D and Colab validators pass;
  Colab checks 10 notebooks, 37 Blender scripts and 36 utilities.
- Source SHA256: `78d3cff27162913ac30283c8ac56ea2f8a57566cb98066cdc3ca2c3b71fe08e2`.
- Original budget anchor object: `CH101_SourceBody_DistalReplacement_PatchBake_NOT_PRODUCTION`.
- Anchor geometry digest: `5e4b05c4ed4c58f63460225c283a154bcb3e39ccdbf971741b4095b2fe4adc2a`.
- Output: `CH101_SectorProfile_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `12bb1194b7706cf7cc5518586ab62dbaf6488f0bab59fd6a779d11a02ed38fde`.
- Art commit remains `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_sector_profile.py -- --source PATH/CH101_SharedInterface_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_sector_profile.py -- --source PATH/CH101_SharedInterface_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_SectorProfile_NOT_PRODUCTION_v001.blend
```

NOT_PRODUCTION, PENDING_HUMAN_REVIEW, Unity input and Production promotion remain
disabled. `rigBound=false`, `attachmentApproved=false`, `fullCharacterScore=null`.
Keep this in a separate prerelease; do not replace whole-character, albedo or
shared-interface restoration pointers.

Published and freshly downloaded on 2026-09-26:
[sector profile study v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-sector-profile-study-v001).
All 15 payloads passed SHA256 verification. ZIP: 24,243,862 bytes;
SHA256 `927f3d807216ad67d2275608e71b4ff4391163677570838f505ff181154bafb0`.
Tools commit: `fa195908e6f57efb8facdc44ed5b3b94365d6abd`.
Restore pointer: `docs/artifacts/CH101-latest-sector-profile.json`.

## Next bounded task

The coordinate-only correction is close to its original 3 mm ceiling. Do not
repeat this operation, reset its baseline or raise the budget to force a pass.
Next author the upper trim/material transition explicitly on a new copy, against
the approved garment reference. For residual contour, decide whether garment
fold/topology reauthoring is needed; any changed connectivity needs an explicit
affected-face rebake. Do not cover defects by expanding gray masks. Rigging and
deformation acceptance remain deferred until contour/material continuity is sound.
