# CH101 authored sleeve–cuff transition — 2026-09-20

The separate sleeve and reduced cuff now have one connected hollow working-copy
mesh. The previous nominal 2 mm axial gap is closed by actual shared-vertex
transition triangles, not overlapping objects or proximity-based welding.
Original objects, source hand/body, materials and the input file are preserved.
This completes steps 1–2 of the September 18 sleeve-end plan in their static
authored-part scope, not integration with the character.

## Boundary construction

The hand-local frame defines the cuff proximal plane at 0 m and sleeve distal
plane at +0.002 m. These are authored-part boundaries, not anatomical cut seams.
The decimated cuff has 63 outer and 60 inner boundary vertices; the sleeve has
32 on each ring. Each selected cap must be one connected annulus with exactly
two simple cycles. The actual mesh edges determine cycle order, a common +u
direction anchors correspondence, and normalized arc length drives the unequal
ring bridge. Named vertex groups preserve all four boundaries for later editing.

The cap-selection tolerance is 10 micrometres; measured maximum plane residual
is 1.3744 micrometres for the cuff and 0.0752 for the sleeve. A 1-micrometre initial
selection missed seven cuff faces and produced invalid topology; it was rejected.
The connected-annulus guard now rejects incomplete cap selection. No source
vertex is moved or snapped, and no collision tolerance was loosened.

123 cuff cap triangles and 64 sleeve cap triangles are omitted only from the
new mesh, replaced by 187 transition triangles. All 3,141 retained faces keep
their positions, material indices and per-loop UV values. Bridge faces have
cylindrical study UVs; this is not a production atlas.

## Actual validation

Blender 5.2.0 LTS, CPU Cycles, 32 samples, six 1000×1000 images; process exit 0.
The input was written by Blender 5.2, so final work used that version rather
than the older installed 4.5. Tests emitted extension-cache permission warnings
under the sandbox; geometry tests and final rendering completed successfully.

| Check | Result |
| --- | --- |
| Vertices / triangles / connected components | 1,664 / 3,328 / 1 |
| Euler characteristic | 0, hollow shell |
| Non-manifold edges / zero-area faces | 0 / 0 |
| Non-adjacent self-surface overlap pairs | 0 |
| Inconsistent winding edges / reversed transition faces | 0 / 0 |
| Retained face normal mismatches | 0 |
| Signed volume | 0.0000346569482 m³ |
| Hand and all 11 cloned equipment objects: surface crossings | 0 |
| Minimum sampled joined vertex to authored hand surface | 0.393879 mm |
| Joined mesh versus preserved original body | 799 pairs / 578 joined triangles |
| Source mesh/material digests and source file hash | unchanged |

The minimum distance is a vertex sample, not a continuous clearance guarantee.
Static surface tests do not establish solid containment or animation clearance.
The generic topology report does not itself test intersections; the separate
`selfSurfacePairs` result does. Four Blender regression tests cover unequal
rings, source/UV retention, transformed frames, malformed caps and invalid inputs.
The Python suite ran 132 tests: 131 passed, one skipped. AI3D and Colab package
validators pass; the latter uses process-local Git safe-directory configuration
for the differently owned, pinned art checkout.

## Visual assessment and limitations

All six images were inspected. The former dark slit is closed in isolated views.
The sleeve remains a faceted tube with simplified gold trim; the transition has
a noticeable shoulder/profile change, not finished cloth tailoring. Gray source
body context visibly exposes remaining intersections. The `UNMERGED` filenames
and `merged:false` render metadata refer to the **source body**; explicit
`authoredSleeveCuffJoined:true` and `sourceBodyJoined:false` distinguish the parts.

No hand replacement, original-body cut, upper-sleeve attachment, rigging, skinning,
animation, FBX or Unity import was performed. No new full-character score or
human Gate B decision is claimed. Gates remain NOT_PRODUCTION, PENDING_HUMAN_REVIEW,
`unityInputAllowed=false`, `productionPromotionAllowed=false`.

## Reproduce and retain

Use `scripts/blender/join_ch101_sleeve_cuff_study.py` with Blender 5.2 background
arguments `--source`, `--source-sha256`, `--art-root`, and a new `--output` directory.
`--no-render` is diagnostic only; the retained release contains actual renders.

- Input: `CH101_SleeveEndStudy_NOT_PRODUCTION_v001.blend` from `ch101-sleeve-end-study-v001`.
- Input SHA256: `3023f8d54bc64218f627455e2602048f243b973e0c1aa078380d8f8c91c6328b`.
- Output: `CH101_SleeveCuffTransition_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `c3ac8f88468bd5e80623b4911cca65ac1d5e912eab8109407bd6038ba2e70728`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Full report: `sleeve-cuff-transition-report.json` in the binary bundle.
- Summary: `docs/records/ch101-ai3d/2026-09-20-sleeve-cuff-transition.json`.
- Dedicated release/pointer: `ch101-sleeve-cuff-transition-v001` /
  `docs/artifacts/CH101-latest-sleeve-cuff-transition.json`.

Keep the separate sleeve, cuff and full-character pointers unchanged. Re-download
and hash-check the new release before recording verified retention.

## Next work

1. Fit the upper sleeve opening and improve the sleeve silhouette/folds against
   the approved reference on a new working copy. Keep this connected part as the
   geometric baseline; do not rerun SPAR3D just to repeat the same result.
2. Establish a reference-backed replacement region on the fused source with
   front/side/back evidence. Existing geometric planes are not approved anatomy.
3. Only then test reversible source replacement, topology/UV/material budgeting
   and deformation. Face/hair/full-outfit quality and human Gate B remain separate.
