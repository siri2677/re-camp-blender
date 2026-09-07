# CH101 artifact recovery and texture correction — 2026-09-07

## Verified state

- Branch: `feature/ch101-free-ai3d-autobuild`; baseline `3b3d4da`.
- The September 6 model binaries were **not** committed to Git or Git LFS.
- The fresh Kaggle session has no `re-camp-ai3d/CH101/hybrid` directory or Blender.
- Saved notebook versions `347727598` and `347708972` expose no downloadable model files in Output. Their saved code/logs are not a model backup.
- The historical 0.601063 score belongs to an unavailable, visually rejected artifact. It is not a current passing model.
- Final modeling, Gate B, Production Mesh, Unity and Android remain incomplete.

## Corrected defects

The real-Blender regression suite initially failed 4 of 5 tests. It exposed:

1. Setting a generated image's color space after its pixel buffer discarded the foreground alpha before packing.
2. Front/back texture assignment disagreed with the evaluator's `neg_y` front camera; back-view horizontal handedness was also reversed.
3. Per-object local UV bounds repeated a whole character sheet on each semantic object.

`CH101_REVIEW_WORLDSPACE_MASKED_TEXTURE_V002` fixes those defects, excludes the review floor, preserves the input file, and records input/output/reference hashes. Eight real-bpy regression tests now pass, including packed-image save/reopen. These synthetic fixtures are **not** modeling results or evidence of character quality.

## Resume order

1. Recreate the pinned reference preprocessing in Kaggle. Require the historical conditioned PNG SHA256 `d775f8c4b2e443908f61a4ceff41cc9bb11ed3ed0a88680955cfe708f3003bf2` before provider execution. The historical environment used Pillow 11.3.0; Windows Pillow 12.3.0 did not reproduce the PNG hash. Do not override this mismatch.
2. Use `scripts/ai3d/recover_spar3d_reference_artifact.py` for **one diagnostic-only lost-file reconstruction**, not a quality retry. The script defaults to preparation only; `--execute` also requires the existing SPAR3D preflight and pinned provider checkout. It never registers a candidate or approves a gate.
3. Compare the recreated mesh hash with historical `2807ba362917373e2ee632da6847165eb92472b237a704d5a6ad439e7051a99f`. A different hash must be recorded as a reconstruction, not the original artifact, and old scores must not be reused.
4. Download the resulting archive, verify its hash outside Kaggle, and record the durable location. A ZIP still inside `/kaggle/working` remains `LOCAL_DOWNLOAD_OR_DURABLE_UPLOAD_REQUIRED`.
5. Only after a real source is preserved: Blender refine → geometry inspection → corrected texture mapping → new renders → score → strict visual QA. Restore Blender executable discovery with `shutil.which('blender')` and an optional `xvfb-run` prefix; do not depend on old notebook globals.
6. Retain historical rejection records. Do not fabricate semantic separation, face shapes, equipment or visual approval from texture projection. CH102–CH105 wait for CH101's technical and human approval.

## Tests

```text
python -m unittest discover -s tests -q
blender -b --factory-startup --python-exit-code 1 --python tests/blender/test_review_texture_projection.py
python scripts/validate_ai3d_free_package.py
python scripts/validate_colab_package.py
```

Gate state remains `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`, `productionPromotionAllowed=false` throughout recovery.
