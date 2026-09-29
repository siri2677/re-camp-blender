# CH101 raised hem binding study — 2026-09-29

## Outcome and scope

Continues the verified September 27 panel-layout Blend. Its interrupted release
metadata handoff was finished at `46445e0` before this study. No new inference,
Kaggle GPU job, provider change or modification of the pinned art checkout.

The color-only hem now has a **separate closed, narrow graphite binding mesh**.
Front/side/back comparisons show a raised edge and shadow. The band follows the
source's uneven contour: facet highlights and small kinks remain visible. This
is a useful physical edge hypothesis, **not finished clothing or visual approval**.
The prior white cap, longitudinal gold, source texture crossfade, body folds,
opposite hand and other coarse character areas are unchanged.

The binding deliberately floats above the existing surface. It is not sewn,
welded, rigged or a full overlapping white oversleeve shell. Reference sheets
support a layered short-white/long-dark sleeve, but do not establish these exact
dimensions. No measured 2D-to-3D pattern registration is claimed.

## Construction and invariants

- Source SHA256: `3d8c83891d89fe6f7bd3d2fbe10655a51ff93efa14ffea1620adaf4974017bcc`.
- Keep the existing signed hem: `height - .245 - .15 * handU` meters.
- 128 angular samples; two edge planes at signed hem ±1.5 mm, four corners per
  section. In-plane rays find the body and must hit the inspected arm bounds
  with radial distance 20–70 mm and non-grazing outward normal.
- Inner offset 1.0 mm; wall thickness 0.8 mm, both **along the ray direction**.
  These are not guaranteed surface-normal or geodesic dimensions.
- 512 vertices, 512 quads / 1,024 triangles, one closed connected component,
  Euler characteristic 0, positive signed volume about `6.94339e-7 m³`.
- Original meshes, UVs, materials, equipment, weights and packed atlas preserved.
  Original body moved vertices: **0**. Existing cumulative body deformation stays
  approximately 2.999919 mm from the September 23 anchor; its 3 mm ceiling is
  **not reset** by this separate new mesh. The new binding has its own disclosed
  offset and is not counted as a body displacement result.
- Default saved viewport: original current body + twelve review parts + binding
  = fourteen visible mesh objects. Older source copies remain hidden and intact.

## Verification

- Non-manifold edges, winding discontinuities, zero-area faces: **0**.
- Non-adjacent self-intersection pairs: **0**; shared-vertex triangle pairs are
  excluded by this diagnostic and this is not a universal solid-validity proof.
- Triangle intersections against the body and each of twelve review parts: **0**.
- 2,560 finite nearest-surface samples (vertices, edge midpoints, triangle
  centroids): minimum gap **0.55765 mm**, maximum **1.82546 mm**. Acceptance floor
  is 0.2 mm. Unsigned sampled distance plus intersection checks is not continuous
  clearance, containment proof, or an animation/deformation test.
- Blender tests: **5 passed**, including invalid frame/source, repeat rejection,
  intentionally intersecting duplicate rejection, open-ring rejection, saved
  reopen, original preservation and render hashes.
- Python suite: **132 run, 131 passed, 1 skipped**. AI3D and Colab package validators
  passed; Colab checks 40 Blender scripts, 36 utility scripts and 10 notebooks.
- Seven review renders: matched front/side/back before and after, plus isolated
  oblique binding. Visual decision remains a local geometry study, not Gate B.

## Reproduce

First restore the prior source using `CH101-latest-garment-panel-layout.json`.
Use Blender 5.2.0 LTS, art commit `b6c9b3128358e061eee6184230929413eba84101`,
and a fresh output directory; the builder refuses overwriting artifacts.

```powershell
& $blender --background --python-exit-code 1 --python scripts/blender/build_ch101_hem_binding.py -- --source <panel-layout.blend> --art-root <re-camp> --output <new-output-directory>
& $blender --background --python-exit-code 1 --python tests/blender/test_hem_binding.py -- --source <panel-layout.blend> --artifact <new-output-directory>/CH101_RaisedHemBinding_NOT_PRODUCTION_v001.blend
```

## Shared artifact and recovery

- [Review prerelease](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-hem-binding-study-v001).
- Tools commit: `aeef4f0e242e71b580ba52b1d03e3a73e6a9657a`.
- Actual Blend: `CH101_RaisedHemBinding_NOT_PRODUCTION_v001.blend`, SHA256
  `c39909027aa7c85459dc081450f2ba7f327f248474f10ff21de585ee202ed42e`.
- ZIP: `CH101-hem-binding-NOT_PRODUCTION-v001.zip`, 23,270,400 bytes, SHA256
  `97c6f37278a077e44b675698c607378481d23ee12ea40ed76d8a8fb060114f64`.
- Fresh download verified all **11 payloads** and the ZIP hash on 2026-09-29.
- Restore via `docs/artifacts/CH101-latest-hem-binding.json`; rollback via
  `CH101-latest-garment-panel-layout.json`. No full-character pointer changed.

```bash
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-hem-binding.json --output-dir artifacts/CH101-hem-binding
```

## Next bounded work

Review the raised binding's thickness and faceted profile against the turnaround.
If retained, smooth/bevel **only this separate mesh** within its recorded envelope,
recheck local body clearance and compare matched renders. Do not hide roughness
with stronger lighting or loosen intersection/clearance checks. The white cap's
real layered shell and attachment require a distinct later design step; do not
infer those are now complete or proceed directly to final bake/rig/Unity.

`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`gateB=PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `rigBound=false`, `fullCharacterScore=null`.
No new 0.6 whole-character pass is claimed. Whole-character pointers are untouched.
