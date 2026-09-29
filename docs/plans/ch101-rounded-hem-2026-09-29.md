# CH101 rounded hem binding — 2026-09-29

## Outcome

Continues shared branch `b71db5b` and the verified physical hem release, with no
new remote commits at start. Local Blender CPU study; no new SPAR3D inference,
Kaggle job or art checkout update. The original body and first binding remain
unchanged; a separate rounded binding is the visible comparison candidate.

The front/side/back and isolated matched renders show less segmented highlight
on the graphite rim. Actual cross-section rounding **and smooth shading** both
contribute; the comparison does not isolate their individual effects. The result
is subtle local edge improvement, not overall clothing/reference acceptance.
The original 128-section circumferential path is not smoothed: contour kinks,
side crease, upper texture crossfade and floating attachment remain.

## Method and scope

- Source Blend SHA256:
  `c39909027aa7c85459dc081450f2ba7f327f248474f10ff21de585ee202ed42e`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Retain 128 angular sections. Replace each four-corner section with 16 points:
  four corner arcs, three segments each, authored radius parameter **0.15 mm**.
  Bilinear weights remain within [0,1], so new section points stay within the
  convex hull of the original section. Distorted sections are not exact circular
  fillets, and no continuous triangle-envelope guarantee is claimed.
- New band: 2,048 vertices, 2,048 quads / 4,096 triangles, one closed component,
  Euler 0, positive signed volume `6.87819e-7 m³`. This increases triangle count
  fourfold; it is a review mesh, not runtime-optimized topology.
- Original body moved vertices: **0**. Original binding, old hidden copies,
  materials, UVs, atlas, weights and equipment are preserved. New band reuses the
  original graphite material; no new bake. Original cumulative body deformation
  remains about 2.999919 mm against the September 23 anchor, not a reset budget.
- Saved view contains fourteen meshes: current body, twelve review parts,
  rounded band. First binding remains hidden as rollback evidence.

## Verification and limitations

- Non-manifold/winding-discontinuity/zero-area counts: **0**.
- Non-adjacent self-intersections and body/twelve-part triangle overlaps: **0**.
  Shared-vertex pairs are excluded; this diagnostic is not universal solid proof.
- **10,240** finite body-distance samples: minimum **0.46062 mm**, maximum
  **1.82319 mm**. Original acceptance floor stays **0.2 mm**. The minimum is
  lower than the previous 0.55765 mm reading; sample positions and triangulation
  changed, so this is not evidence of improved clearance or a direct continuous
  clearance comparison. No animation, continuous gap or containment proof.
- Symmetric finite source-surface comparison (vertices and triangle centroids):
  new-to-old maximum **0.04557 mm**, old-to-new **0.07641 mm**, both below the
  predeclared **0.2 mm** envelope limit. No loosened QA thresholds.
- Rounded Blender tests **6 passed**; prior binding regression tests **5 passed**.
  Includes invalid dimensions/source/gates, preservation, oversized displacement,
  intersecting duplicate, open mesh, saved reopen and render hashes.
- Python suite **132 run / 131 passed / 1 skipped**; AI3D and Colab validators
  passed (41 Blender scripts, 36 utility scripts, 10 notebooks).
- Eight renders inspected: front, side, back and isolated, each before/after.

## Shared artifact

- [Review prerelease](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-rounded-hem-study-v001).
- Tools commit `2096eec0fdcf1c5ac47684193dc3297ca664d785`.
- Blend SHA256 `39f5e07de24a433a7d74ff51a607219ace089162c916a0c1040c96c9b7b31a20`.
- ZIP `CH101-rounded-hem-NOT_PRODUCTION-v001.zip`, 23,664,893 bytes, SHA256
  `a032a07d0ead434c785d60a96838903ec85ed30681806fb745a211f4841bbd31`.
- Fresh download verified ZIP and **12 payloads** on 2026-09-29.
- Restore pointer: `CH101-latest-rounded-hem.json`. Rollback: original physical
  binding and panel-layout pointers, both preserved.

```bash
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-rounded-hem.json --output-dir artifacts/CH101-rounded-hem
```

## Reproduce and next step

Restore the prior `CH101-latest-hem-binding.json` artifact first. Use Blender
5.2.0 LTS and a fresh output directory; no artifact overwrite is permitted.

```powershell
& $blender --background --python-exit-code 1 --python scripts/blender/round_ch101_hem_binding.py -- --source <raised-hem.blend> --art-root <re-camp> --output <new-output-directory>
& $blender --background --python-exit-code 1 --python tests/blender/test_rounded_hem.py -- --source <raised-hem.blend> --artifact <new-output-directory>/CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend
```

Next: inspect the **remaining circumferential contour**, quantify its sharp
sectors, and propose a bounded contour correction without changing the body.
Do not repeat larger corner rounding as a substitute for fixing path kinks or
claim the real white oversleeve shell/attachment is complete. A complete garment
layer and attachment design remain separate work before any final bake or rig.

`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`gateB=PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `rigBound=false`, `fullCharacterScore=null`.
No 0.6 whole-character pass; no full-character pointer replacement.
