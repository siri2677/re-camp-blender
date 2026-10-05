# CH101 upper sleeve fit and source region review — 2026-09-20

The September 20 connected sleeve/cuff has a new fitted working copy, plus an
explicit source-region diagnostic. Original body, original hand, separate parts
and the prior connected mesh remain intact. This is static part fitting, not
finished cloth, anatomical registration or a replacement operation.

## Implemented change

Only 256 upper-sleeve vertices move; 1,408 vertices, including the cuff, bridge
and sleeve at/below 30 mm above the wrist, stay fixed. The same offset is applied
to each inner/outer pair. Maximum displacement is 22.6063 mm under a 25 mm bound;
paired wall-distance change is below 0.000004 mm. UV values/material slots and
mesh topology are preserved, although deformation changes UV stretch.

Profiles at 47, 65, 83 and 98 mm come from the preserved source surface. An
additional 74 mm profile detects an outward bulge between the middle rings.
The target radial ease is 3.5 mm; measured chord-deficit corrections are at most
3.5488 mm under a 6 mm limit. Added diagonal folds have a 1.2 mm amplitude bound
and vanish at the locked region and upper rim. These are authored dimensions,
not dimensions extracted from orthographic art.

The approved sheet provides the dark sleeve, gold trim and exposed-hand design
context already present in the baseline. Numerical fitting uses an approximate
SPAR3D-derived source, not a registered match to the illustration. Preserving
that source's irregularity can worsen local cloth smoothness; do not treat lower
intersection counts as a visual-quality pass.

The old section helper failed at 83 mm because rounded intersection positions
could merge distinct nearby segments. The new local helper connects segments
by their original mesh edge IDs and rejects ambiguous plane-vertex events,
multiple loops or open graphs. It does not invent missing edges or move a plane
to make a section pass. A submicrometre-edge regression covers this distinction.

## Actual measurements and rejected intermediate fits

| Configuration | Upper-band crossing triangles | Whole-part crossing triangles |
| --- | ---: | ---: |
| Pinned joined baseline | 86 | 578 |
| Single upper section, 2.5 mm ease | 37 | 495 |
| Four sections, 2.5 mm ease | 14 | 479 |
| Four sections, 3.5 mm ease | 6 | 466 |
| Measured midpoint correction, retained result | 0 | 460 |

The upper band consists of 320 triangles wholly at/above approximately 65 mm
(floating-point selection threshold 64.9 mm). These are triangle-surface tests;
zero does not prove solid containment, continuous separation or animation fit.
The script now rejects any remaining upper-band surface crossing.

Retained mesh: 1,664 vertices / 3,328 triangles / one component / Euler 0.
Non-manifold edges, zero-area faces, inconsistent winding, non-adjacent
self-surface pairs and authored-hand/cloned-equipment surface crossings are all
zero. Signed volume: 0.0000360612269 m³. Original mesh/material digests and the
input SHA256 are unchanged. Generic topology audit and separate intersection
checks retain their distinct meanings.

## Source replacement-region evidence

All 13,160 source triangles appear in the diagnostic. A bounded centroid cylinder
(-180 to +98 mm axial, 75 mm radial) and edge connectivity isolate a local patch;
the 98 mm plane-straddling collar is a separate review class. Saved triangle IDs
and frontier edges refer only to this pinned mesh's triangulation.

- Gray: 12,831 triangles outside the displayed review classes.
- Red: 288 local replacement-hypothesis triangles.
- Orange: 41 upper-plane-straddling triangles, taking display precedence.
- The connected selection's frontier has 23 vertices, all degree two; this is
  geometric evidence, not anatomical correctness or authorization to delete it.
- No disconnected ROI component was included. No faces were removed or welded.

The nine 1000×1000 Cycles renders were inspected: three isolated part views,
three gray-body context views, and three source-region views. Upper fit is
visibly fuller and follows the offset forearm, but the side contour is angular
and the trim bends with the surface. Remaining lower-body/hand intersections
are visible. The region views show the fused distal forearm/hand volume without
the authored parts hiding it. The orange section is a **working split hypothesis**,
not the real sleeve/skin seam or human approval.

## Verification and reproduction

Blender 5.2.0 LTS, CPU Cycles, 32 samples, process exit 0. Four new Blender tests
pass: unchanged lower geometry/UV/source and gates, displacement/plane rejection,
edge-ID section connectivity, exhaustive region classification/remote exclusion.
Python suite: 132 run, 131 passed, one skipped. AI3D and Colab package validators
pass, including the new script. Sandbox extension-cache warnings occur in tests;
they do not prevent geometry generation or rendering.

Script: `scripts/blender/fit_ch101_upper_sleeve.py`. Blender background arguments:
`--source`, `--source-sha256`, `--art-root`, `--output` (new directory).
`--no-render` is for preflight only; the release uses the full rendered result.

- Input: `CH101_SleeveCuffTransition_NOT_PRODUCTION_v001.blend`.
- Input SHA256: `c3ac8f88468bd5e80623b4911cca65ac1d5e912eab8109407bd6038ba2e70728`.
- Output: `CH101_UpperSleeveFit_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `32319050d3cb189c0be996d4083d58af9e197096f2cc697f13a0103b7ba2360c`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Full source sections/region IDs/QA/renders: `upper-sleeve-fit-report.json` in bundle.
- Separate release: `ch101-upper-sleeve-fit-v001`.
- Separate pointer: `docs/artifacts/CH101-latest-upper-sleeve-fit.json`.

The [prerelease](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-sleeve-fit-v001)
was published and re-downloaded on 2026-09-20; all 12 payload hashes passed.
ZIP SHA256: `0a41f1b62f5cda12a55e5cd284d291dda1fe534ab4f63fe4b394ea33fb124eb4`.
Previous sleeve/cuff and full-character pointers remain unchanged.

## Next work and gates

Review source-texture and approved-reference context at the proposed upper
replacement interface, explicitly identifying cloth continuity and which source
triangles must remain. Then test a reversible replacement on a duplicate, with
the original retained, and check the new boundary/UV/normals and static overlap.
Do not treat the geometric red class as an automatically approved cut mask.
The current fit needs cloth contour polishing before visual approval, then
skinning/deformation tests and final atlas/material budgeting.

`cutAllowed=false`, `sourceHandReplaced=false`, `sourceBodyJoined=false`,
`anatomicalSeamVerified=false`, `attachmentApproved=false`, `designApproved=false`,
`wristIntegrationAllowed=false`. NOT_PRODUCTION, PENDING_HUMAN_REVIEW;
Unity and Production promotion remain false. Full-character score is null.
