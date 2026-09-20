# CH101 duplicate-only distal replacement — 2026-09-20

The authored sleeve/hand/saber now has a static replacement assembly with the
fused original distal arm/hand omitted from a **new body working copy**. The
original source and all prior studies remain intact in the saved scene. Fourteen
working-assembly meshes are shown by default; hidden originals are recoverable.

## Interface decision and actual operation

Front/side/back source-texture inspection showed the proposed 74–98 mm band
crossing projected sleeve decoration, with substantial white/stretch artifacts
on the side. It cannot identify a reliable skin seam. This operation instead
uses an explicitly **artificial internal cloth interface** at 74 mm, 24 mm below
the authored sleeve's upper rim. It is a reversible construction experiment,
not an anatomical approval or application of the earlier red display class as
an automatic deletion mask.

The local connected geometric ROI is re-evaluated at 74 mm. Only the selected
distal region and its plane-crossing collar are clipped. Shared edge identities
give exact new boundary correspondence; per-loop UVs interpolate on clipped
edges while respecting existing seams. A single 32-vertex planar boundary is
required, then closed by an internal cap facing distally. Unexpected holes,
plane-vertex ambiguity, UV/material loss or new self-crossings reject the result.

Of 13,160 original triangles, 243 are omitted from the copy, 32 are clipped and
12,885 retain their original positions, materials and UVs. The cap is an internal
temporary closure with one additional study material and planar UVs; it is not
a finished garment atlas. The sleeve, cuff, authored hand and saber geometry
are unchanged. Source and new sleeve **do not share topology or skin weights**.
The nominal 24 mm overlap is an axial construction dimension, not a proven
normal clearance or guarantee that every animated view hides the cap.

## Static validation

| Pair against body | Before: crossing part triangles | After: crossing part triangles |
| --- | ---: | ---: |
| Authored joined sleeve/cuff | 460 | 0 |
| Authored hand | 119 | 0 |
| Saber | 5 | 0 |
| All ten saber-detail meshes | 0 | 0 |

The new body has 6,486 vertices / 12,964 triangles. Non-manifold edges, zero-area
faces and inconsistent winding edges are zero. Its signed volume is
0.0716840325 m³. Component count remains two: 6,438 vertices in the main shell
and the inherited 48-vertex component. The unmodified source had 6,536 + 48.

The source already has three non-adjacent self-surface overlap pairs. All three
remain with matching world-coordinate triangle-pair signatures (recorded in the
full report); newly introduced pairs are zero. This is **not** a claim of a
self-intersection-free character. Those defects and the small component need
identification before general topology/rig acceptance. Static triangle-surface
tests do not prove solid containment or pose-dependent clearance.

Source file SHA256 and all original mesh/material digests are unchanged.
Retained/interpolated UV/material verification reports zero mismatches. Four
Blender fixtures pass: UV interpolation, closed copy/source preservation,
remote-component preservation and invalid plane/frame rejection. Python suite:
132 run, 131 passed, one skipped. AI3D and Colab validators pass. Blender 5.2.0
LTS, CPU Cycles 32 samples, nine 1000×1000 renders, execution exit 0. Sandbox
extension-cache warnings occurred in tests, without blocking execution.

## Visual result and remaining quality work

All nine retained renders were inspected: three original source-texture views,
three replacement textured views, three replacement clay-context views. The old
fused hand no longer protrudes through the authored hand or sleeve. The upper
interface is concealed in these views, but the projected upper-arm texture and
the new graphite/gold material meet with an obvious style mismatch. The sleeve
is still faceted and the hand's skin/material finish is provisional.

This closes the specific static source-overlap issue. It does not establish
premium full-character quality, an anatomical cut seam, a shared welded mesh,
humanoid binding, deformation, final material budget, FBX or Unity import.
No full-character score is assigned and no human Gate B decision is made.

## Reproduce and retain

Script: `scripts/blender/replace_ch101_distal_source_study.py` with Blender 5.2
background arguments `--source`, `--source-sha256`, `--art-root`, and new `--output`.
`--no-render` is diagnostic only. The script sets the review viewport so the
working assembly appears by default and originals remain hidden, not deleted.
The retained artifact received that same viewport-only configuration after its
render run; all mesh/material digests stayed unchanged and render evidence is
unaffected.

- Input: `CH101_UpperSleeveFit_NOT_PRODUCTION_v001.blend`.
- Input SHA256: `32319050d3cb189c0be996d4083d58af9e197096f2cc697f13a0103b7ba2360c`.
- Output: `CH101_DistalReplacementAssembly_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `0fbf9820bd66cc3b2eb8c41d36358aa490f3451a84a673b2913c7db793060c2b`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Full report and original triangle IDs: `distal-replacement-report.json` in ZIP.
- Separate release: `ch101-distal-replacement-study-v001`.
- Separate pointer: `docs/artifacts/CH101-latest-distal-replacement.json`.

The original full-character, cuff and upper-fit pointers remain unchanged.

## Next implementation

1. Locate the three inherited self-crossing pairs and identify the 48-vertex
   component on the preserved source. Repair only confirmed defects on another
   working copy; do not delete a small component solely because it is small.
2. Refine the visible upper sleeve contour and material/trim transition to the
   retained upper arm, then consolidate the provisional cap/cloth materials.
3. Bind and test the layered body/sleeve/hand assembly with explicit forearm and
   wrist poses; prove cap coverage and grip/clearance under deformation. A static
   cap concealed by a sleeve is not a substitute for that verification.

Status: `sourceReplacementOnWorkingCopy=true`, `originalSourcePreserved=true`,
`sourceHandReplacedInWorkingAssembly=true`, `weldedToSleeve=false`,
`capIsTemporary=true`, `rigBound=false`, `anatomicalSeamVerified=false`.
All results stay NOT_PRODUCTION, PENDING_HUMAN_REVIEW; Unity and Production
promotion remain disabled. Design/attachment approval remains false.
