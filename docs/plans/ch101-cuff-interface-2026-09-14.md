# CH101 hollow cuff interface hypothesis — 2026-09-14

## Outcome and scope

A separate hollow graphite cuff now exists in an actual Blender CPU scene.
It explores whether the broad source section can be interpreted as sleeve/cuff
rather than enlarging the bare hand to match it. This is a **design hypothesis**,
not an approved interpretation of the character sheet and not a joined wrist.
The original character, original equipment and all prior study meshes remain
unchanged. No source hand was removed, welded or hidden to claim integration.
Context renders show the original body in clay; the orange loop is provisional.
The isolated render hides the original body to expose only the separate study.

### Measured results

| Check | Result | Meaning |
| --- | --- | --- |
| Cuff vertices / triangles | 128 / 256 | A small part study, not full-character modeling completion |
| Connected components | 1 | Connected shell |
| Non-manifold edges / zero-area faces | 0 / 0 | Topology checks only |
| Euler characteristic | 0 | Closed hollow-tube topology |
| Non-adjacent cuff self-surface overlap pairs | 0 | Limited static triangle test, not a motion guarantee |
| Cuff triangles crossing new hand | 5 (28 pairs) | **Unresolved clearance; attachment rejected** |
| Cuff triangles crossing preserved source body | 104 (154 pairs) | Old hand remains; includes coincident provisional boundary |
| Source geometry digest | Preserved | No source replacement |

The hand comparison uses the closed section 15 mm distal to the wrist, with
80 triangle-plane intersections. Its area is 0.00123994 m²; do not compare this
as a same-plane boundary to the previous 5 mm diagnostic. Both loops are sampled
on 32 common angular rays. Distal radial clearance is 1.5 mm and radial wall
offset is 2 mm; these are not exact normal thickness or whole-volume clearance.
UV is an automatic study unwrap; there is no final atlas, skinning or animation.
The additional graphite study material has not been consolidated into the final
six-material character budget; this part study is not a production-budget pass.
The generic topology audit does not itself perform self-intersection checking;
the separate `nonAdjacentSelfSurfaceOverlapPairs` report is that limited check.

## Reproduced defect and fix

The first real cuff failed before saving, with four non-adjacent wall intersections.
A two-ellipse fixture reproduced the defect without source body or textures:
arc-length correspondence produced 32 overlap pairs. Shared angular rays reduced
that to 16, but did not fix it alone. Inspection showed the outer and inner walls
were tessellated on different geometric diagonals. On a thin, non-planar loft,
those triangles can cross even though each ring has positive radial thickness.

The fix combines single-hit angular ray correspondence with explicit triangles
using the same proximal-to-distal diagonal on both walls. The minimized fixture
now reports zero pairs, as does the original actual scene. No collision threshold
was relaxed. Ambiguous radial intersections and collapsing offsets are refused.
Three Blender fixture tests cover hollow manifold topology, offset rejection and
the rotated unequal ellipse regression. Temporary probes were not saved as code.
The full Python suite passed 132 tests. AI3D and Colab package validation passed
(10 notebooks, 28 Blender scripts, 36 utilities). The optional Colab source-tree
environment check was skipped; the actual Blender run independently verified the
art commit and reference hashes. No Unity or Android runtime test was performed.

## Still failing, and the next modeling step

The five cuff/new-hand crossing triangles are all on the inner longitudinal wall,
not the distal rim. Their vertices span the 0 to -15 mm interval. Matching the
end sections therefore does not establish clearance along the hand's changing
profile. Next, measure intermediate hand sections and test a piecewise fitted
inner wall against a bulging-hand fixture and the actual hand. Keep a bounded
clearance offset, wall thickness and zero-self-crossing checks; do not inflate
the hand, loosen the checker or hide the original to manufacture a pass.

Only after clearance is resolved should a reversible *working-copy* source-hand
replacement be considered. The sleeve/skin boundary must first be identified:
the geometric loop is not anatomical approval. The source body remains intact
until then. Palm/knuckle fidelity, sheath interference, face/hair/outfit semantic
geometry, full-character strict QA and human Gate B remain unfinished.

## Reproduction and retention

Script: `scripts/blender/build_ch101_cuff_interface_study.py`.
Arguments: `--source`, `--source-sha256`, `--art-root`, `--output` (new directory).

- Source: `CH101_WristPairFit_NOT_PRODUCTION_v001.blend`
- Source SHA256: `f79851bea699ad2dbb94315e36a67d9f6e19b3488190acfec64bef71a5ea2dfd`
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`
- Output: `CH101_HollowCuffInterface_NOT_PRODUCTION_v001.blend`
- Output SHA256: `9af7c1c4dcb52063aa3690924c10ea546fc3a53b638b81cb35bb1776eaec44fc`
- Record: `docs/records/ch101-ai3d/2026-09-14-cuff-interface.json`
- Release: `ch101-cuff-interface-hypothesis-v001` (prerelease; includes known failures)
- Pointer: `docs/artifacts/CH101-latest-cuff-interface-study.json`

Retain the blend, three unmerged renders, measured report and this readme; download
the release bundle and verify all hashes before recording retention as complete.
Do not replace the latest full-character candidate pointer with a part study.
The preceding wrist-pair release was also published and re-downloaded on 2026-09-14.

All results remain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`,
`sourceHandReplaced=false`, `designApproved=false`, `attachmentApproved=false`,
`anatomicalSeamVerified=false`, `wristIntegrationAllowed=false`.
