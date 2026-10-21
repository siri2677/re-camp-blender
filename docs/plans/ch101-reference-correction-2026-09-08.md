# CH101 reference correction and remaining modeling work — 2026-09-08

## Evidence and diagnosis

Source: reconstructed SPAR3D GLB SHA256
`3812e28a8c64b08c549abe44a0cf5714de7b7238db51537300468b83e4560371`.
Art commit remains `b6c9b3128358e061eee6184230929413eba84101`.
Source reference manifest SHA256:
`e51d1e7b3fdad92868ff5b8a6169b7ecebd2b6b0e67d0d0032f700ccd436a8d4`.

Real failures were reproduced before fixes:

- The evaluator counted a light-gray inset canvas as character silhouette. A
  synthetic identical-person comparison yielded IoU `0.427454` instead of >0.97.
- Projection mapped the whole padded PNG into mesh bounds, shrinking the face
  and clothing. A real Blender UV extent regression failed before the fix.
- The silhouette fitter inverted Blender's bottom-up image rows, moved vertices
  even at zero strength, and included the review floor. Three bpy tests failed.
- Strict visual QA skipped semantic checks when the report was missing. A
  high-score/no-semantic-evidence fixture was incorrectly deferred for approval.

Shared border-connected light-neutral canvas segmentation now removes the gray
inset while retaining enclosed white clothing. Pixel thresholds define reference
preprocessing, not acceptance thresholds. Mask audit images are retained. This is
not a semantic segmenter; dark/colored background references require a different
verified mask. The subject bounds now define projection extent. The fitter uses
correct bottom-up rows, interpolated centers and a true zero-strength identity.
The strict semantic check now fails closed when evidence is absent.

## Actual experiments on the preserved mesh

All rows below use the **same corrected scorer** and unchanged thresholds.

| Version | Overall | Silhouette | Appearance | Color | Face-edge proxy | Technical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous render, rescored | 0.774501 | 0.817458 | 0.572612 | 0.549267 | 0.672202 | 1.0 |
| Subject-bounds texture correction | 0.812296 | 0.820783 | 0.715149 | 0.669197 | 0.849627 | 1.0 |
| Fixed two-axis profile correction | 0.834283 | 0.847052 | 0.734795 | 0.662127 | 0.871344 | 1.0 |
| Required | 0.60 | 0.50 | 0.55 | 0.38 | 0.25 | 0.90 |

The earlier `0.53343` was measured with the defective canvas mask. Its rise to
`0.774501` is a measurement correction, **not** a mesh improvement. The later
changes are measured on the same corrected scorer. The fixed profile strategy
used front and right references once each at a preselected strength of 0.35,
with no score-driven parameter search. No provider inference or paid service
was used; Blender postprocessing ran on the available local workstation.

Both new candidates remain `REGENERATE_REQUIRED` because body/face, hair,
outfit and equipment are not independently verified semantic geometry.
The initial subject-bounds experiment's legacy v003 QA JSON predates the
missing-evidence fix; the comparison's v004 QA supersedes that decision.
No name-only semantic labels were added to make the candidate pass.

Direct agent inspection of front, side, back and three-quarter renders:

- Texture scale and clothing alignment are visibly improved.
- Head volume remains irregular; facial planes protrude and have no reliable landmarks.
- Side-view surface assignment produces visible texture seams and white patches.
- Saber, sheath, ribbons and pouch cannot be verified as independent modeled parts.
- High face-edge overlap is not evidence of semantic face quality or rig readiness.

## Next work, with the failure causes fixed

1. Preserve and fetch the latest Release before another Kaggle session.
2. Use the corrected masks and subject bounds for all subsequent evaluations.
3. Build or obtain real part-level geometry for face/hair/outfit/equipment;
   retain the recovered candidate as a comparison source. Fix the head and
   face volume and semantic boundaries before refining surface appearance.
4. Address side-view texture seams with a verified atlas or continuous projection.
   Merely raising edge/color metrics or changing light exposure is insufficient.
5. Re-evaluate actual semantic objects and inspect close-ups, four views and
   deformation evidence. A new strategy needs a concrete geometry/material change.
6. Only a visually and technically suitable candidate proceeds to human Gate B.

These two strategy IDs have been executed and rejected; do not blindly repeat:
`CH101_REVIEW_SUBJECT_BOUNDS_TEXTURE_V003` and
`CH101_REFERENCE_TWO_AXIS_PROFILE_CORRECTION_V002`.
The committed comparison record includes their rejected dispositions for the
quality progress gate. No additional GPU dependency setup is needed for these
CPU-capable corrections. Reliable semantic authoring remains unfinished.

## Reproduction and verification

The standalone `scripts/ai3d/review_recovered_spar3d_artifact.py` keeps hash-checked
source/reference arguments and requires a new output directory. Its optional
`--fit-reference-profile` flag selects the new fixed two-axis strategy.
It can also run from Kaggle with a Blender executable and restored inputs.

`scripts/ai3d/build_reference_correction_comparison.py` accepts a reference
manifest and repeated `--evaluation` reports, recomputes scores on one basis,
and writes the comparison, masks, hashes and current strict QA to a new directory.

Verified: 132 Python unit tests; 9 texture projection and 3 silhouette fit tests
in actual Blender; AI3D and Colab package validators. Reference acceptance
thresholds remain unchanged. Generated `.blend`, GLB, renders and reports are
published as a review-only GitHub prerelease. Git stores code and compact records.

All results retain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`. CH102–CH105, Unity and Android remain gated.
