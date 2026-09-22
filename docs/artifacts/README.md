# Review artifact sharing

Generated 3D files are not committed to ordinary Git history.  Use the
standard-library helper below to package a review candidate, publish one
versioned prerelease asset, and commit only the small latest pointer.

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
