# CH101 sleeve surface study — 2026-09-21

## Recovered baseline and scope

Remote branch `feature/ch101-free-ai3d-autobuild` had eight newer commits,
ending at `bf69d4f` on 2026-09-20. They already contain the sleeve–cuff join,
upper sleeve fit, working-copy distal replacement and one-vertex crossing repair.
This work continues that baseline, not the older 2026-09-18 separate sleeve.
The local-topology Release was re-downloaded with all ten payload hashes verified.

This is a **material/shading-only study on a duplicate sleeve**. It does not
move vertices, repaint the source body, fix its anatomy, weld the upper rim,
add skin weights or establish whole-character quality. Original scene meshes,
UVs and material datablocks are retained unchanged, hidden for comparison.

## Changes and measured checks

- Approved sheet tokens: graphite `#151518`, gold `#D2A445`, converted from sRGB
  into scene-linear shader values. Rendered pixels are affected by lighting and
  color management; token assignment is not a pixel-color similarity score.
- The two existing gold lanes receive a centered narrow shader mask, occupying
  24% of their former width. Sixteen cross-ring samples yield **1.414–2.094 mm**.
  Width and placement remain authored hypotheses, not measured tailoring data.
- A dedicated `SleeveTrimStudy` UV layer is used only by the copied trim shader.
  All existing UV coordinates and the original active/render UV map stay intact.
- Smooth shading is enabled on 896 sleeve-side triangles. Caps, cuff and bridge
  keep their prior shading. Silhouette and folds are not geometrically changed.
- The mesh remains 1,664 vertices / 3,328 triangles / one connected component.
  Non-manifold edges, zero-area faces and winding errors remain zero.
- Non-adjacent BVH self-pairs and body/hand/equipment surface crossings remain
  zero. These checks exclude shared-vertex pairs and are not exhaustive solid
  containment, deformation or animation-clearance proofs.
- Fourteen working meshes are visible when reopening the saved Blend. Preserved
  older meshes stay hidden. The 48-vertex thigh-side component is untouched.

## Visual inspection and acceptance boundary

Seven 900×900 CPU Cycles renders were generated: matching front, side and back
close-ups before/after, plus full assembly front. The back and side close-ups
show a narrower, less dominant gold line and removal of the triangulated
flat-shading pattern on the new sleeve. This is a useful local appearance change.

The sleeve still reads as an authored tube with an angular opening. The upper
source has white projection artifacts and a double painted gold seam that does
not align with the new single line. The cuff shading, provisional pale hand,
head/hair silhouette, fused clothing/anatomy and other source defects remain.
Do not infer a strict-QA pass or a new overall score from this change.

The new procedural material is Blender review-only, **not a Unity-compatible
texture atlas**. Baking, material consolidation and design approval remain open.
Body assembly remains layered/unwelded with a temporary internal cap and no rig.

## Reproduce and verify

- Script: `scripts/blender/refine_ch101_sleeve_surface.py`.
- Source: `CH101_LocalTopologyRepair_NOT_PRODUCTION_v001.blend`.
- Source SHA256: `e89357579ef64eda53bf8c37eda9942d898e23171f0f0bcb39f2fd833b7456b0`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Output: `CH101_SleeveSurface_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `f627a89f822bc7d48269bb34b99415aec6e16be62279e0ad92108df2ce444f66`.
- Blender 5.2.0 LTS `fbe6228777e7`, CPU Cycles, 32 samples, exit 0.
- Seven Blender tests passed: source/data/material preservation, unsafe width
  rejection, topology mismatch, UV mutation detection, missing/true gate rejection,
  color conversion and saved-artifact reopen/reapplication rejection.
- Python unittest: 132 passed; AI3D and Colab package validators passed.
  The optional validator source-tree check was skipped; the Blender execution
  independently verified the locked art commit and reference-image hashes.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_sleeve_surface.py -- --source PATH/CH101_LocalTopologyRepair_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_sleeve_surface.py -- --source PATH/CH101_LocalTopologyRepair_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_SleeveSurface_NOT_PRODUCTION_v001.blend
```

The exact input hash is required because correspondence relies on that mesh's
retained topology. The original source file is never overwritten.

Published separately as [sleeve surface v001](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-sleeve-surface-study-v001),
with restore pointer `docs/artifacts/CH101-latest-sleeve-surface.json`.
The ZIP was downloaded again and all ten payloads verified on 2026-09-21.
Bundle: 10,233,715 bytes, SHA256
`93f4312e14de4aea3274e8255ffaebec6759b87585b6afb1840a36914f0b0eba`.
Tools commit: `7cead563874212e0882fcb205a6c8ee3e1353eb5`.
The separate before/after back and full-front PNGs are also Release assets.

## Next concrete work

1. Author the upper-arm/sleeve transition against the approved sheet: remove
   projection artifacts on a new semantic clothing copy and establish coherent
   trim continuity, while retaining the current collision-tested baseline.
2. Refine the angular upper opening and cuff contour with bounded geometry
   changes and comparison renders; do not mistake smooth normals for reshaping.
3. Resolve the retained thigh-strip identity before attachment/deletion. Rigging
   and pose-dependent cap/hand/equipment tests follow interface construction.

No changes to thresholds, scores or approval policy. All results remain
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`.
