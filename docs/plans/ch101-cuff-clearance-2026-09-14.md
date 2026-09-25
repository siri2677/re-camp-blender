# CH101 section-fitted cuff clearance v002 — 2026-09-14

## Actual outcome

Local Blender CPU generated and rendered a new hollow cuff fitted to the changing
profile of the separate authored hand. The original body, source hand, new hand
and equipment geometry are preserved. Only the new cuff is authored. This is a
**static clearance part study, not an integrated or approved character**.

| Measurement | Result |
| --- | --- |
| Cuff / new-hand surface crossings | 0 pairs, 0 cuff triangles (previously 28 / 5) |
| Non-adjacent cuff self-surface overlaps | 0 |
| Cuff topology | 2,304 vertices, 4,608 triangles, one connected component |
| Non-manifold edges / zero-area faces | 0 / 0 |
| Euler characteristic | 0, hollow closed shell |
| Maximum outward correction from interpolated inner wall | 2.02705 mm |
| Maximum permitted outward correction | 6 mm; excessive fitting is rejected |
| Minimum sampled cuff-vertex / hand-surface distance | 0.393879 mm |
| Cuff / preserved source-body crossings | 548 pairs, 490 cuff triangles |

The last row includes the old source hand and provisional source boundary. It is
not solved by fixing the separate new-hand fit. Counts are tessellation-dependent:
490 versus the old cuff's 104 does not quantify penetration volume or worsening.
No solid containment, exact minimum triangle-to-triangle clearance or animated
collision proof is claimed. In particular, 1.5 mm **radial** offset is not 1.5 mm
normal clearance: the sampled distance above is smaller. No clearance gate for
motion has been opened. The generic topology audit does not perform the separate
limited self-surface test; its own `selfIntersectionTestPerformed` remains false.

## Diagnosis and bounded correction

The saved v001 scene reproduces five crossing cuff triangles. A three-profile
bulging-hand fixture reproduces the endpoint-only failure without body, textures,
equipment or rig: 128 intersecting cuff triangles. Inserting seven intermediate
sections resolves this fixture, but is insufficient on the real angular wrist.

The actual intermediate-section result with 32 angular samples has 14 crossing
triangles on two angular bands. A thin rectangular fixture independently fails
with 42 crossing triangles: straight chords between sparse radial samples cut
across corners. Increasing angular resolution only gives the bounded comparison:

| Intermediate sections | Angular samples | Actual cuff triangles crossing new hand |
| --- | --- | --- |
| 0 | 32 | 5 |
| 7 | 32 | 14 |
| 7 | 64 | 2 |
| 7 | 128 | 0 |

The number of triangles changes with resolution; these are detection counts, not
a continuous severity score. Both causes are handled: changing longitudinal hand
profile and angular chord approximation. No collision threshold was relaxed.
The old matched inner/outer triangulation is retained to avoid wall self-crossings.

At each intermediate plane, a single closed hand section is required. Radial rays
must have one unambiguous positive intersection. The inner wall expands outward
only to at least the sampled hand radius plus 1.5 mm; the outer wall follows with
a 2 mm radial offset. Proximal and distal construction offsets are unchanged,
although their polygonal sampling is denser. No source-hand vertex is altered.
If any static hand/cuff surface crossing remains, fitted mode stops before saving
a review blend. Source hashes and scene promotion gates are verified as before.

## Tests and preservation

- Three new Blender tests: bulging-profile clearance and source-hand preservation;
  thin rectangular corner clearance and locked gates; excessive-fit rejection.
- Three prior cuff tests remain passing: hollow manifold, collapsing offset,
  different elliptical wall profiles.
- Full Python suite: 132 tests passing.
- AI3D and Colab package validators pass: 10 notebooks, 28 Blender scripts,
  36 utilities. Optional Colab source-tree environment check is skipped; the actual
  Blender run separately checks the pinned art commit and reference file hashes.
- No Unity, Android, skinning or animation tests have been performed.

Input scene: `CH101_WristPairFit_NOT_PRODUCTION_v001.blend`.
Input SHA256: `f79851bea699ad2dbb94315e36a67d9f6e19b3488190acfec64bef71a5ea2dfd`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output: `CH101_HollowCuffInterface_NOT_PRODUCTION_v002.blend`.
Output SHA256: `99de9dfcbd084b8ad35a72ddf35386423240f31b13df841efe3b5fbd3e191199`.

Run `scripts/blender/build_ch101_cuff_interface_study.py` in Blender background
mode with `--fit-hand-profile`, `--source`, `--source-sha256`, `--art-root` and a
new `--output` directory. Without the flag, historical v001 mode remains available.
Record: `docs/records/ch101-ai3d/2026-09-14-cuff-clearance-v002.json`.
Release: `ch101-cuff-clearance-study-v002`, prerelease.
Pointer: `docs/artifacts/CH101-latest-cuff-interface-study.json`.
Retain blend, three diagnostic renders, report and README; verify a downloaded
release bundle before committing its pointer. Earlier releases remain available.

## Next authoring boundary — not a completion claim

1. Use the dense cuff as a clearance reference for corner-aware lower-density
   topology; repeat the same zero-overlap checks after every simplification.
   This 4,608-triangle cuff and its extra graphite material are not a final budget
   or six-material atlas pass.
2. Establish the actual sleeve/skin replacement boundary on a reversible working
   copy. The geometric source loop remains an unapproved cuff interpretation;
   do not remove the old hand from the original or label the context render merged.
3. Once an explicit boundary is justified, validate replacement topology, UV,
   normals, source preservation and deformation. Palm/knuckles, sheath, face,
   hair and outfit quality still require further work and full-character review.

The isolated preview hides the source body to expose the new hand/cuff/weapon
study; context previews show it in clay, with an orange provisional loop.
Neither image demonstrates final anatomy or an integrated wrist.

All gates stay `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`,
`sourceHandReplaced=false`, `designApproved=false`, `attachmentApproved=false`,
`anatomicalSeamVerified=false`, `wristIntegrationAllowed=false`.
