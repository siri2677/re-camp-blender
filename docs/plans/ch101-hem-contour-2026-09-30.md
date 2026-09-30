# CH101 bounded hem contour — 2026-09-30

## Outcome: preserve as evidence, do not replace the baseline

The close-up shows a small reduction of the sharp highlight/contour corner, but
the full ring and clothed front/side/back change is subtle. Maximum centerline
turn only changes from **29.395966° to 29.215735°**; RMS turn from 6.564850° to
6.145803°. This is not sufficient reason to replace the rounded-hem baseline or
declare the contour complete. `adoptionAllowed=false`; retain this comparison
and proceed to actual garment-layer authoring, not another micro-smoothing pass.

Static tests pass: zero tested intersections/manifold/winding/zero-area errors,
one closed 2,048-vertex / 4,096-triangle component. Minimum sampled body gap is
**0.364835 mm** across 10,240 samples; it is SMALLER than the prior 0.46062 mm
reading, not a clearance improvement. Symmetric sampled distance against the
original rectangular band is 0.121809 / 0.159622 mm, below 0.2 mm in both directions.
Actual stored maximum movement is **0.100036142 mm**, within the unchanged
0.100100 mm storage guard. Body movement is zero. Face area ratios are
0.986366–1.010140 and minimum normal dot is 0.996449.

New Blender tests: **5 passed**, including saved reopen and render hashes;
Python unittest: **132 passed**. AI3D and Colab validators pass (10 notebooks,
42 catalogued Blender scripts, 36 utilities). Explicit new script/test compile
passes. The optional source-tree check is skipped; this run independently checks
the pinned art/reference hashes. These passes concern safety/reproducibility,
NOT whole-character visual acceptance.

Output SHA256: `a4bcaa94aa84b851566b70c9b7f5ef5681234d420a385fce0d40e196468df33b`.

## Resume checkpoint

This checkout initially lagged at `ea9efaf` (September 23). Remote inspection
found `588f448` (September 29) and the verified rounded-hem release. Do not
repeat the obsolete seam-interface plan or publish that old trial as latest.

Five interrupted local files were preserved in the named Git stash
`646eb1dcb819071236d371d054e78bf545d46857` before a fast-forward to `588f448`.
Ignored September 23 Blend/renders remain on disk; nothing was deleted. Review
stash differences before restoring individual files; applying the old README
wholesale would overwrite newer planning. Branch remains
`feature/ch101-free-ai3d-autobuild`.

The latest rounded-hem ZIP and all 12 payload hashes were freshly verified.
Actual continuation starts from `CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend`,
SHA256 `39f5e07de24a433a7d74ff51a607219ace089162c916a0c1040c96c9b7b31a20`.
Local Blender 5.2.0 LTS CPU; no Kaggle job or provider inference.

## Method and scope

- Quantify the turn between consecutive centerline segments of the 128 sections.
  This is a contour diagnostic, NOT a face/skin detail or full-character score.
- Three fixed, arc-length-weighted Jacobi steps on the centerline only. Each
  proposed shift is clamped relative to the ORIGINAL rounded centerline, not
  the previous iteration. No open-ended quality retry loop.
- Translate all 16 points in each section together, preserving its rounded
  cross-section, topology, material, UVs, weights and existing smooth shading.
  Do not enlarge corner radius, add triangles, move the body or repaint masks.
- Nominal maximum movement is 0.1 mm; stored-coordinate tolerance remains
  0.0001 mm (1e-7 m). Actual maximum is reported, not rounded down to the limit.
- Face-normal dot must stay at least 0.95; face area ratios stay in [0.75,1.25].
- Critically, symmetric sampled surface deviation is checked against the FIRST
  rectangular physical binding, not merely the preceding rounded copy. The
  existing 0.2 mm cumulative envelope and 0.2 mm sampled body-gap floor remain.
- Body and all source objects remain unchanged. The pre-existing cumulative
  body displacement budget is not reset. This band remains floating/unattached.

## Storage precision regression

The initial actual-scene regression failed: vertex 1885 moved 0.100123433 mm,
exceeding the 0.100100 mm stored-coordinate guard. The failure reduces to one
vertex. Three hypotheses were checked: large-coordinate arithmetic order,
per-iteration budget accumulation, and transform scale.

The source transform is identity. With the SAME planned centers, `p + new - old`
stores a maximum of 0.100123433 mm; computing `delta = new - old` first and then
`p + delta` stores 0.100036142 mm, matching the planned maximum. The regression
went from failing to passing without raising any limits. Original CLI and
saved-scene tests are rerun after the fix. Temporary debug probes were inline
only and are not committed.

## Verification and decision rules

Static checks cover closed topology, positive volume, winding, zero-area faces,
non-adjacent self-intersections, body/equipment intersections, finite body-gap
sampling and symmetric source-surface sampling. Shared-vertex self pairs are
excluded. These are NOT continuous containment, animation or cloth simulation.

Ten matched views cover front/side/back, isolated full ring and the original
sharpest sector close-up. Inspect them before declaring any local improvement.
Do not equate turn-angle reduction with a completed sleeve, exact reference fit,
attachment, optimized runtime topology or whole-character approval.

Source/art hashes and saved render hashes are verified. The locked art commit
remains `b6c9b3128358e061eee6184230929413eba84101`. Full-character pointers stay
unchanged; publish a separate review prerelease and freshly verify its payloads.

## Next bounded work

Keep the September 29 rounded-hem file as the starting point; this new trial is
not an adopted replacement. Stop repeating micro-smoothing. The
remaining substantive task is the white oversleeve's actual layer structure:

1. Inspect a longitudinal section through the panel and binding against the
   approved Character Sheet / Turnaround; distinguish designed folds from
   residual source geometry.
2. Define the upper panel boundary, lower rim and inner/outer shell surfaces in
   a new authoring copy. Preserve the body and existing floating band as rollback.
3. Decide and record the joining/attachment hypothesis; do not silently call the
   current floating trim a sewn or rigged garment. Validate a bounded local shell
   for thickness, winding, intersections and static clearance before extending it.
4. Only if that geometry is defensible, author UV/material transfer and bake
   with coverage checks. Then evaluate deformation separately. Do not export a
   Unity package or fabricate Face BlendShapes / Gate B approval.

## Reproduction

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_hem_contour.py -- --source PATH/CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_hem_contour.py -- --source PATH/CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_HemContour_NOT_PRODUCTION_v001.blend
```

`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`gateB=PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `rigBound=false`, `fullCharacterScore=null`.
