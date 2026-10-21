# CH101 material consolidation and sheath clearance — 2026-09-11

## Actual outcome

Executed with local Blender 5.2 CPU, not Kaggle GPU. A preserved copy now has
six retained material kinds across character and all equipment, including the
staged hidden ribbon, down from nine. This resolves the Blender material-count
overage only. Character geometry, weights and materials are unchanged.

Four equipment solid shaders (Graphite, Gold, Steel, Cyan_Hardware_Inset) now
share a Principled shader with per-corner color and per-face metallic/roughness
attributes. The two procedural patterned materials remain separate. Original
face parameters and all equipment geometry are preserved. This is not a baked
atlas or an export-ready Unity shader; attribute translation/baking is still needed.

Four identical-camera, identical-light before/after comparisons have identical
alpha and a maximum RGB difference of 1 on the 0–255 scale. Foreground mean RGB
absolute differences range from 0.0000163983 to 0.0000243382. This supports
appearance preservation for these views, not improved character design fidelity.

## Bounded sheath experiment: no improvement

The sheath mouth anchor is held fixed. All three trials are retained:

| Axis trial | Equipment triangles crossing the character surface |
| --- | ---: |
| Original | 38 |
| Vertical | 40 |
| Rear-tip | 40 |

The original pose wins the limited comparison and is retained; anchor error is
zero. It is **not collision-free or attached correctly**. The saber/detail meshes
still have 34 crossing triangles near the estimated hand. Open-hand gripping was
not changed, simulated or approved. BVH surface intersection is not a solid
containment or animated/swept collision test.

## Visual decision and next work

Actual 3/4, hand and waist renders show the character's substantial white patches,
distorted/fused projected surfaces and open hand intersecting the grip. This is
still below the requested Alpha/Production quality. Full-character score remains
null for this diagnostic; no historic scalar is substituted for a current pass.

The next meaningful dependency is reliable palm/finger/cuff and belt/hip surface
authoring, plus correction of the malformed body/outfit surface. Do not repeat
these three orientation trials, lower acceptance thresholds, or move the weapon
away from the hand and call it held. A grip needs actual finger geometry; a
sheath needs a real attachment site and motion clearance. Material baking comes
after that stable geometry/UV exists. Rig, animation, Gate B and Unity remain pending.

## Reproduction and validation

Run `scripts/blender/refine_ch101_fit_materials.py` with `--source`,
`--source-sha256`, `--report`, `--report-sha256`, `--art-root`, `--output`.
It refuses existing outputs and mismatching source/report/reference hashes.
It preserves the input files and checks the character digest and equipment topology.

Input blend: `a2de98a552c022b8c6a1f2ec03a34955034e66b6a45fbdf717636266e3600445`.
Input report: `0312e81eb31702971465a3bf2286f2e1219e28005d566828b0737372c1cb7b90`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output blend: `d09d94258c1ff7fd78f28b36060631ba8c394b7ba7e9a36cecdeb4adbc9133c6`.

Validation: three actual Blender material tests, 132 Python unittests,
AI3D validator and Colab validator (10 notebooks, 23 Blender scripts, 36 utilities).
Twelve actual renders and the model/report are retained in the diagnostic archive.

Release target: `ch101-material-clearance-review-v001`; dedicated pointer:
`docs/artifacts/CH101-latest-material-clearance.json`. Earlier full-character,
equipment, landmark and static-fit releases/pointers are preserved.

All outputs remain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `attachmentApproved=false`.
