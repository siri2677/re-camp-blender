# Review artifact sharing

## September 26 directional sector profile comparison

`CH101-latest-sector-profile.json` restores `ch101-sector-profile-study-v001`:
the actual Blend, eleven renders, technical report, read-me and visual review.
All 15 payloads were freshly downloaded and SHA256-verified on 2026-09-26.
The two local profile lobes preserve a TOTAL 3 mm displacement ceiling against
the original albedo baseline, not a new budget per stage. Only subtle partial
improvement; side fold and upper material/trim remain unfinished. No full-character
pass, 0.6 score, rigging, Unity or Production acceptance. Previous pointers stay intact.

```bash
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-sector-profile.json --output-dir artifacts/CH101-sector-profile
```

## September 25 shared-interface comparison

`CH101-latest-shared-interface.json` restores `ch101-shared-interface-study-v001`:
a duplicate of the September 23 albedo model with coordinated motion across
both shared sleeve rims. The 320-vertex adjustment stays below 3 mm and preserves
topology, all UVs, the packed atlas and material masks/weights. Ten renders show
partial lower-notch improvement, not elimination or final visual acceptance.
All 14 payloads were re-downloaded and hash-verified on 2026-09-25. Prior albedo,
seam-contour and full-character pointers remain unchanged.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-shared-interface.json --output-dir artifacts/CH101-shared-interface
```

## General publishing and restoration

Generated 3D files are not committed to ordinary Git history.  Use the
standard-library helper below to package a review candidate, publish one
versioned prerelease asset, and commit only the small latest pointer.

## Bounded patch albedo bake — 2026-09-23

[Patch albedo bake v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-patch-albedo-bake-v001)
contains a preserved-copy 321-face patch bake, eight renders, two texture/coverage
PNGs, full report, visual decision and read-me. All 14 payloads and the ZIP were
re-downloaded and SHA256 verified. Pointed white streaks decrease; the lower
notch and coarse source character remain. **Not a whole-character quality pass.**
Original geometry/UVs/masks and prior releases remain recoverable; the patch
shader alone uses the new atlas. No rig, Gate B or Unity promotion.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-patch-albedo-bake.json --output-dir artifacts/restored-patch-albedo
```

Full-character pointers are unchanged. Rollback: upper-patch and seam-contour
pointers below. Next: bounded coordinated lower seam-interface study.

## Bounded upper topology patch — 2026-09-22

[Upper patch v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-patch-study-v001)
replaces 221 polygons on a copy, preserving the 41/24-vertex boundary loops and
all original sources. **Local geometry progress, texture rework required**: upper
streaks and the lower boundary kink remain. This is not a production-quality
character or an approved garment. Rollback baseline: `CH101-latest-seam-contour.json`.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-upper-patch.json --output-dir artifacts/restored-upper-patch
```

All 14 payloads (Blend, ten renders, technical report, visual decision, read-me)
were re-downloaded and SHA256 verified on 2026-09-22. Next: seam-aware UV/material
correspondence. Gate B, Production and Unity stay locked; full-character pointers
remain untouched.

## Upper-transition trial, not adopted — 2026-09-22

[Upper-transition trial v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-transition-trial-v001)
contains a bounded 100-vertex geometry experiment and ten renders, including
matched clay views. **Static PASS, visual improvement insufficient:** the main
notch remains. Preserve this as evidence, not a quality-approved replacement.
Continue topology authoring from `CH101-latest-seam-contour.json`; do not rerun
the same relaxation or overwrite the full-character pointer.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-upper-transition-trial.json --output-dir artifacts/restored-upper-transition-trial
```

All 14 payloads (Blend, ten renders, technical report, visual decision and read-me)
were re-downloaded and SHA256 verified on 2026-09-22. Gate B remains pending.

## Locked-rim seam contour continuation — 2026-09-22

[Seam contour v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-seam-contour-study-v001)
refines the shared seam on a copy, keeping all original vertices and rim edges
fixed. The 73 added midpoints use a thin-triangle altitude limit. Eight renders
show softer shading but a remaining side crease; no rig or full-character pass.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-seam-contour.json --output-dir artifacts/restored-seam-contour
```

All 11 payloads were re-downloaded and SHA256 verified on 2026-09-22. Previous
seam and full-character pointers remain intact; Unity and Production stay locked.

## Shared body–sleeve seam continuation — 2026-09-22

[Body–sleeve seam v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-body-sleeve-seam-study-v001)
is the next actual geometry study: 73 bridge triangles share the body/sleeve
rims on a new working copy. The previous sources and the separate thigh strip
are preserved. It is not rigged or design-approved; the internal void cap and
faceted transition remain. Prior pointers describe prior geometry states.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-body-sleeve-seam.json --output-dir artifacts/restored-body-sleeve-seam
```

Re-downloaded and verified all 11 payloads on 2026-09-22. Do not replace the
full-character candidate pointer with this scoped study.

## Upper sleeve local material alternative — 2026-09-21

The [bounded upper sleeve material study](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-upper-sleeve-material-study-v001)
is an optional unapproved copy, not a new full-character quality pass. It reduces
local projection contamination but suppresses painted trim and retains boundary
defects. Original geometry, UVs and shaders remain recoverable. The continuation
plan is `docs/plans/ch101-reference-sleeve-continuation-2026-09-21.md`.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-upper-sleeve-material.json --output-dir artifacts/restored-upper-sleeve-material
```

Eleven payloads (Blend, eight renders, report, read-me) were re-downloaded and
verified on 2026-09-21. This pointer does not replace the prior sleeve-surface
or full-character pointers. Do not continue by merely expanding the gray mask.

## Latest sleeve surface continuation — 2026-09-21

The September 20 repaired distal assembly now has a separate material/shading
study: [sleeve surface v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-sleeve-surface-study-v001).
It contains the full preserved working scene, seven comparison renders and report,
but its **change scope is sleeve-only**, not an approved full-character candidate.
Geometry and original UVs remain fixed. The shader is not Unity-ready; upper-arm
projection artifacts, contour and trim continuity remain unfinished.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-sleeve-surface.json --output-dir artifacts/restored-sleeve-surface
```

Re-download verified all ten payloads on 2026-09-21. Previous full-character and
local-topology pointers stay available; do not replace their distinct scopes.

## Publish from a machine that has the candidate

Install and authenticate the GitHub CLI once:

```text
gh auth login
```

Then run:

```text
python scripts/ai3d/review_artifact_release.py publish --artifact-root path/to/remediation-multiview-textures-v012-mask-s074 --output-bundle artifacts/CH101-SPAR3D-REF001-MASK-s074.zip --repo siri2677/re-camp-blender --release-tag ch101-ai3d-review-s074 --candidate-id CH101-SPAR3D-REF001-MULTIVIEW-TEXTURE-MASK-s074 --tools-commit 0000000000000000000000000000000000000000 --art-commit b6c9b3128358e061eee6184230929413eba84101
```

The command verifies every payload before upload and writes
`docs/artifacts/CH101-latest-review.json`.  Commit and push that pointer:

```text
git add docs/artifacts/CH101-latest-review.json
git commit -m "docs: point to latest CH101 review artifact"
git push
```

Replace the placeholder tools commit with the exact commit used to produce
the candidate.  Never put tokens, credentials, or `.env` files in the
artifact directory.

## Fetch from Kaggle, Blender, or another workstation

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-review.json --output-dir artifacts/CH101-latest-review
```

The fetch command downloads the public Release asset, checks its byte count
and SHA256, safely extracts it, and verifies every file against the embedded
manifest.  The manifest always enforces
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, disabled
Unity input, and disabled Production promotion.

The committed pointer in `docs/artifacts/CH101-latest-review.json` now points
to the latest recovered CH101 SPAR3D review bundle:

- Release: `ch101-continuous-projection-review-v001`
- Bundle: `CH101-continuous-projection-NOT_PRODUCTION-v001.zip`
- Bundle SHA256: `7f093002263ddae2b65b39e78f6c1f314f62621ce90f415c1193f30938cbff9f`
- Decision: `REJECT_GATE_B_AND_REGENERATE`

This contains continuous projection and bounded face-curvature experiments,
plus the source profile Blend, same-evaluator comparison and comparison image.
The 40-payload ZIP preserves the latest experiments, not an approved or improved
selection. Their scores are effectively unchanged and semantic/visual QA still
rejects them. The previous profile baseline remains in
`ch101-reference-correction-review-v001`.

The bundle remains review-only; it is not a Production Mesh or Unity input.

## Duplicate-only distal replacement assembly

Its follow-up `CH101-latest-local-topology-repair.json` restores the bounded
one-vertex repair from `ch101-local-topology-repair-v001`. The three inherited
non-adjacent crossings become zero with approximately 0.05 mm of movement on
a new working copy. Other vertices, UVs, topology and the separate 48-vertex
thigh-side strip are preserved. This is not exhaustive solid/deformation
validation or semantic approval of that strip. All 10 payloads (Blend, seven
renders, report and read-me) were re-downloaded and verified on 2026-09-20.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-local-topology-repair.json --output-dir artifacts/CH101-local-topology-repair
```

`CH101-latest-distal-replacement.json` restores the next static working assembly
from `ch101-distal-replacement-study-v001`. The original source is preserved;
only a new body copy omits the fused distal arm/hand and receives a temporary
internal cap. Body-surface crossings with authored sleeve/hand/saber change
from 460/119/5 to 0/0/0. Three inherited body self-crossing pairs and a separate
48-vertex component remain; this is not a topology-clean, rigged or approved
full-character candidate. The interface is layered, not welded, and its
materials and animated cap coverage still need work.

The Blend, nine renders, full report and read-me (12 payloads) were published,
re-downloaded and SHA256-verified on 2026-09-20. Previous pointers are unchanged.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-distal-replacement.json --output-dir artifacts/CH101-distal-replacement
```

## Joined sleeve/cuff part study

The follow-up `CH101-latest-upper-sleeve-fit.json` points to
`ch101-upper-sleeve-fit-v001`: fitted working copy, nine renders and geometric
replacement-region review. Upper-band surface crossings are zero; 460 joined
triangles still cross the preserved body below that band. This is not a body
replacement or anatomical cut approval. All 12 payloads were re-downloaded and
hash-verified on 2026-09-20.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-upper-sleeve-fit.json --output-dir artifacts/CH101-upper-sleeve-fit
```

`CH101-latest-sleeve-cuff-transition.json` restores the September 20 connected
authored sleeve/cuff mesh, six context/isolated renders and static QA report from
`ch101-sleeve-cuff-transition-v001`. All nine release payloads were re-downloaded
and hash-verified. This does not replace the full-character, separate sleeve or
cuff pointers. The original body/hand remains present and intersecting; the
upper opening, final cloth, skinning and animation remain unfinished.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-sleeve-cuff-transition.json --output-dir artifacts/CH101-sleeve-cuff-transition
```

## Independent equipment study

`CH101-latest-equipment-study.json` identifies the latest equipment-only Blend
and nine hardware-detail renders in `ch101-equipment-hardware-study-v002`.
The initial four-view study remains in `ch101-equipment-part-study-v001`. It does not replace
the full-character pointer above. Use the same fetch command with this separate
pointer to restore the part study. It contains one saber, one sheath and one
signal ribbon, not a full character or approved Unity package.

## Unbound landmark diagnostic

`CH101-latest-landmark-guide.json` points to `ch101-landmark-guide-review-v001`.
It preserves a source-mesh copy with eight estimated geometric anchors, a
non-deforming seven-bone guide and four diagnostic views. No equipment is
attached. This pointer is intentionally separate from character/equipment
deliverables, and its debug geometry is not a quality-scored model.

## Static equipment-fit diagnostic

`CH101-latest-static-fit.json` points to `ch101-static-equipment-fit-review-v001`.
It preserves initial and revised combined placement scenes and surface-overlap
reports. These show remaining hand/sheath interference; they are not approved
attachments. Character, equipment and landmark pointers remain separate.
