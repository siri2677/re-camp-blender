# CH101 fitted upper sleeve interface — 2026-09-30

## Result and decision

The smooth lower panel now extends into a fitted upper interface, with a real
shared edge between the old cage and the new bridge. Maximum **sampled upper
outer-edge gap** to the original body/clothing surface falls from 11.954134 to
2.787101 mm. Nine matched/evidence renders show a smaller visible open lip and
a more continuous silhouette at the upper sleeve boundary.

`authoringContinuationAllowed=true` for this separate garment study. The upper
edge still has a visible color/shape transition, particularly from the rear.
The source texture's dark band and coarse shoulder folds remain. This is NOT
a sewn jacket, a finished shoulder pattern or a completed whole-character mesh.
`adoptionAllowed=false` for replacing the whole-character baseline; Gate B and
Unity remain pending. No whole-character score is assigned.

## Source and scope

- Resume branch: `feature/ch101-free-ai3d-autobuild`, clean remote/local
  `571304fc7dcf0ce8b9e3439103bc54d9e3b41c6c`.
- Source: `CH101_SharedHemPanelCage_NOT_PRODUCTION_v001.blend`, SHA256
  `b310f0671bf9a695d60fa671a772dc3a14a30b1a8c905863f7d5d9f62358d5fc`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`; approved Character
  Sheet, Equipment Sheet and REVIEW Turnaround hashes verified. Turnaround was
  visually inspected. Dimensions remain authoring hypotheses, not calibrated
  image measurements or a recovered sewing pattern.
- Runtime: local Blender 5.2.1 LTS, build `9e2066aef7ef`, CPU. No Kaggle inference.

Read-only source inspection found valid local arm rings at signed hem +28 and
+36 mm. At +44 mm, rays can hit torso/underarm surfaces (up to 98.96 mm radius,
normal dot down to -0.828); +60 mm also has missed rays. A simple circular
extrusion toward the shoulder would select the wrong surfaces. The implementation
therefore limits this interface to **+28 through +36 mm** and rejects broader
height requests. Shoulder work needs a branching panel boundary rather than this
ring method.

## Construction and preservation

All **1,152 original cage vertices** are retained at exactly the same stored
positions in the new object, using a recorded source-to-new index mapping.
The original cage object, body, equipment, textures, UVs and materials remain
unchanged. The 48-vertex source strip remains. Previous body displacement limits
are not reset. The rounded-hem whole-character rollback pointer is unchanged.

The new copy removes its old upper end wall, adds rings at +30/+32/+34/+36 mm,
and closes the upper wall at the fitted end. A smooth axial weight blends the
old cage's extrusion into body-surface ray targets. An outward-only safety
constraint keeps each new point at least 2 mm outside its sampled radial target.
The actual surfaces, edges and centroids are subsequently checked for collision.
Added radial expansion is **2.000000–10.797587 mm**, below the unchanged 15 mm
new-cage bound. The old lower cage's larger stand-off remains.

The old loop stays at 64 columns. New interface loops use 128 columns; three
triangles per old interval connect the two densities without duplicated seam
vertices. The bridge shares all 64 original outer loop edges. Inner/outer walls
remain in one closed component. The nominal radial paired wall is 0.8 mm; measured
opposing-surface distances are reported separately. White/graphite materials and
the lower shared hem remain. There is no new UV, bake, rig, Face BlendShape or
armature binding.

`joinedToSourceBodyTopology=false`: the bridge is geometrically joined to the
new garment shell, NOT welded to the old body/jacket surface. A finite static gap
remains. Do not interpret proximity or the closed upper wall as sewing, skinning
or animation acceptance.

## Measured evidence

| Check | Result |
| --- | --- |
| New shell | 2,176 vertices / 2,368 faces / 4,352 triangles |
| Components / Euler characteristic | 1 / 0 |
| Non-manifold / winding / zero-area errors | 0 / 0 / 0 |
| Tested self/body/equipment/old-binding intersections | 0 |
| Minimum sampled body gap | 0.320771 mm, 11,072 samples |
| Sampled opposing wall | 0.364966–0.808939 mm, 6,144 samples |
| Shared outer cage-to-bridge edges | 64, manifold |
| Old upper outer-edge gap | min 2.126595 / max 11.954134 / mean 8.670440 mm |
| New upper outer-edge gap | min 0.771679 / max 2.787101 / mean 2.507852 mm |
| Original body / retained cage vertex movement | 0 / 0 |

Old/new edge statistics include vertices and edge midpoints, respectively 128
and 256 samples. Both are finite samples, not continuous maxima. The full-shell
minimum gap has DECREASED from the prior cage's 1.295067 mm to 0.320771 mm because
the new interface sits closer. It passes the existing 0.2 mm floor but is NOT
an animation-clearance improvement. The maximum full-shell gap remains roughly
11.98 mm in the unchanged lower region.

Topology/intersection checks exclude shared-vertex self pairs. Finite gap and
thickness sampling do not prove continuous collision, solid containment, cloth
simulation or deformation clearance. Additional geometry increases triangle
count; whole-character optimization is still pending.

## Diagnosis and regression

The first 64-column interface failed with **24 body triangle-overlap pairs**
despite every involved vertex sitting at least about 1.08 mm from the body.
Minimum sampled gap fell to 0.026208 mm. The real-source
`test_upper_interface.py --collision-only` test reproduced `24 != 0` in about
two seconds of test time before the fix.

Ranked hypotheses were insufficient angular sampling, too-long axial spans,
and incorrect thickness/ray direction. Intersection probes reduced the problem
to angular interval 16→17 and included the final end wall. Increasing axial rows
alone produced 38 pairs. Splitting angular intervals alone produced zero without
changing the 2 mm ray target clearance. This identifies the angular chord crossing
the source fold as the cause; no wall/gap/quality thresholds were relaxed.

The production implementation subdivides ONLY the new interface and preserves
all original cage vertices. The actual regression, full original CLI, saved
scene and negative tests pass. Diagnostic scripts were removed.

## Verification

- Five Blender tests pass: actual interface collision/gap/preservation; gate,
  hash, output and duplicate rejection; open shell rejection; out-of-scope
  shoulder height and constructed body-penetration rejection; saved scene,
  original mesh digests, visibility, locked gates and nine render hashes.
- Python unittest: 132 passed.
- AI3D and Colab package validators: PASS (10 notebooks, 45 Blender scripts,
  36 utilities). Optional source-tree check is skipped; actual execution checks
  source/art/reference hashes.
- Python compile and `git diff --check`: PASS.
- Output Blend SHA256:
  `a4a9c424fc74005594321fa1d72135ecaa0fbd379452aa25e5b04b8dd9f27e24`.

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_upper_interface.py -- --source PATH/CH101_SharedHemPanelCage_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-upper-output
blender --background --python-exit-code 1 --python tests/blender/test_upper_interface.py -- --source PATH/CH101_SharedHemPanelCage_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_FittedUpperSleeveInterface_NOT_PRODUCTION_v001.blend
```

## Next work

1. Keep this interface as a local authoring copy and preserve all rollback
   artifacts. Do not repeat ring fitting beyond +36 mm; torso hits are known.
2. Define the shoulder/underarm panel boundary from the garment region's actual
   face graph and the approved front/side/back silhouette. Separate decorative
   strap boundaries from the white shell before changing coverage.
3. Author a branching shoulder panel with controlled folds and explicit seam
   correspondence. Resolve the dark upper transition and remaining cuff-like
   proportion through that connected panel design; do not repaint/expand old
   masks to hide it or weld the garment to skin.
4. Verify local/full silhouette, surface deviation, collision, wall thickness and
   static pose before UV/material transfer. Then perform bake and deformation
   checks as separate stages.
5. Face, hair, remaining outfit and production rig are unfinished. Human Gate B,
   Unity and Android remain separate requirements.

`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`gateB=PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `rigBound=false`, `fullCharacterScore=null`.
