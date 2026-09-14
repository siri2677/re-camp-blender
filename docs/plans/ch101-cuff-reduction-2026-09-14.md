# CH101 bounded cuff reduction — 2026-09-14

## Outcome

The actual local Blender CPU study reduces the fitted cuff from 4,608 triangles
and 2,304 vertices to **2,304 triangles and 1,152 vertices**. Source body, old hand,
authored hand, equipment and dense cuff are preserved. The selected mesh is a
copy, not a source replacement, Unity asset, approved design or final topology.

Four fixed collapse ratios were evaluated independently from the dense cuff:

| Ratio | Triangles | Reference → trial max sampled error, mm | Trial → reference, mm | Verdict |
| --- | ---: | ---: | ---: | --- |
| 0.5 | 2,304 | 0.066058 | 0.087768 | Selected |
| 0.25 | 1,152 | 0.164458 | 0.178119 | Reject: sampled error |
| 0.125 | 576 | 0.431651 | 0.429257 | Reject: sampled error |
| 0.0625 | 288 | 0.664707 | 0.716190 | Reject: sampled error |

The 0.15 mm sampled-error limit was fixed before execution, not relaxed to select
a smaller mesh. This is an engineering bound for this part experiment, not a
replacement for full-character visual QA or a guaranteed perceptual threshold.
Samples are every vertex, triangle centroid and triangle-edge midpoint, in both
directions. These finite samples are **not a continuous Hausdorff error bound**.
Normals are compared at trial triangle centroids against the nearest reference
surface; zero reversed samples is not a global proof of correct shading/anatomy.

## Selected result checks

- One connected component; Euler characteristic 0, preserving hollow topology.
- Zero non-manifold edges and zero zero-area faces.
- Zero non-adjacent self-surface overlaps.
- Zero static surface crossings with the separate authored hand and cloned saber
  mesh/details; zero sampled normal reversals.
- UV exists and coordinates are finite. UV distortion, overlaps, texture baking
  and final six-material consolidation are **not** validated by this check.
- Maximum sampled surface deviation is 0.087768 mm (both directions considered).
- Source geometry digest and source file SHA256 remain unchanged.
- The original body still crosses the study: 392 pairs / 336 cuff triangles.
  This includes the retained original hand and provisional source boundary;
  counts change with tessellation and do not measure penetration volume.

The saved scene retains the dense cuff and rejected trial objects hidden from
render. Only the selected trial is visible with the study hand/equipment in the
isolated preview. Context previews show the original body in clay and an orange
provisional section marker. These are diagnostic unmerged views. Hidden sources
still exist in the file: the saved scene is not a measured runtime polygon budget.
Structured ring metadata on decimated copies is renamed `source_*` so it cannot
be mistaken for the current topology.

## Implementation and validation

`scripts/blender/simplify_ch101_cuff_study.py` accepts `--source`,
`--source-sha256`, `--art-root`, `--output` (new directory only).
It independently clones each trial and chooses the lowest triangle count passing
all checks. If none is eligible, it records `NO_ELIGIBLE_SIMPLIFICATION` without
saving a selected review blend. Production/Unity gates cannot be opened by this
selection. Negative fixtures cover displaced geometry, invalid ratio, missing UV
and forced Unity gate. The copy test checks source preservation and reduction.

Four new Blender tests plus six prior cuff tests pass. Python suite: 132 tests.
AI3D/Colab package checks include 10 notebooks, 29 Blender scripts and 36 utilities.
The optional Colab source-tree environment check is skipped; this actual Blender
run independently verifies the art commit and reference hashes. No GPU inference,
Unity, Android, skinning or animation was executed in this step.

Input: `CH101_HollowCuffInterface_NOT_PRODUCTION_v002.blend`.
Input SHA256: `99de9dfcbd084b8ad35a72ddf35386423240f31b13df841efe3b5fbd3e191199`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output: `CH101_ReducedCuff_NOT_PRODUCTION_v001.blend`.
Output SHA256: `a354ea0f03347be50c5518ad69fcc5dc2a5044790c879f228f3305fd4f7d6c8f`.
Record: `docs/records/ch101-ai3d/2026-09-14-cuff-reduction.json`.
Release: `ch101-cuff-reduction-study-v001` (prerelease).
Pointer: `docs/artifacts/CH101-latest-cuff-interface-study.json`.
Preserve prior Releases; retain the blend, three previews, trial report and README
in a checksummed bundle and verify a re-download before committing its pointer.

## Next boundary

The next step is a reference-backed, reversible sleeve/skin boundary study for
replacing the old source hand on a working copy. Do not automatically cut based
only on the provisional geometric plane. Keep the reduced cuff as a reference,
not a final seam: sampled surface closeness does not prove compatible boundary
vertices or a weld. If reducing further, use corner-aware topology instead of
repeating the already-rejected stronger global collapse ratios.

Actual integration, final material/UV work, deformations and full-character
face/hair/outfit quality are still incomplete. All results remain
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`,
`sourceHandReplaced=false`, `attachmentApproved=false`, `designApproved=false`,
`anatomicalSeamVerified=false`, `wristIntegrationAllowed=false`.
