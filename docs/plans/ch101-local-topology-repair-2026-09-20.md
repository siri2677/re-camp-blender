# CH101 bounded local crossing repair — 2026-09-20

The three inherited non-adjacent triangle crossings in the previous distal
replacement are resolved on a **new working copy**. All previous objects and
the downloaded source file remain unchanged. This is a targeted geometric
correction, not a new SPAR3D inference or whole-character quality-score result.

## Diagnosis and selected correction

The original crossing pairs are (3729, 10093), (10093, 10104) and (10093, 10105).
They form one cluster on the negative-X source sleeve, close to the authored
sleeve interface. Independent finite edge/triangle intersections confirm two
distinct intersection points for each pair; they are not merely overlapping
bounding boxes. Coordinates and exact indices are in the full artifact report.

Initial local Laplacian trials removed crossings but rotated a thin incident
triangle too far. They were rejected, not accepted by loosening the limits.
The retained correction moves vertex 3432 along incident triangle 10105's
normal by a requested 0.05 mm, an actual 0.0499909 mm after float storage.
Only this vertex changes. The other 6,485 vertices remain bit-for-bit unchanged.
The input file is hash-pinned because these IDs must not be applied to a
different source mesh. The script is a specific inspected repair, not a general
automatic mesh-cleanup algorithm.

| Check | Retained result |
| --- | --- |
| Non-adjacent triangle BVH pairs | 3 → 0 |
| Changed vertices | 1 / 6,486 |
| Actual movement / hard maximum | 0.0499909 / 0.5 mm |
| Incident triangle count | 6 |
| Minimum incident normal dot | 0.954167 (required ≥ 0.95) |
| Incident area ratio range | 0.999870–1.003458 (required 0.5–2) |
| Non-manifold / zero-area / winding errors | 0 / 0 / 0 |
| Triangles / component sizes | 12,964 / 6,438 + 48 |
| Authored sleeve, hand, saber surface crossings | 0 / 0 / 0 |
| Topology, UV, material, weight changes | None |

BVH self-checks exclude pairs sharing a vertex. Their zero count is **not an
exhaustive self-intersection, solid containment or deformation proof**. The
movement is tiny and clearance is not an animation safety margin. A 0.04 mm
negative-control move leaves crossings and is rejected with its temporary copy
removed; the preserved source does not change.

## The retained 48-vertex component

The detached component is on the positive-X side near the upper thigh:
X 0.1193–0.1783 m, Y 0.0261–0.0885 m, Z 0.7090–0.8646 m. It renders as an
angular, hanging strip alongside the shorts/thigh, not part of the crossing
cluster. The approved character sheet has hanging straps, so a strap-related
origin is plausible, but this does **not** establish semantic identity or
justify automatic attachment/deletion. All 48 vertices and their original
UVs/materials/topology remain unchanged.

The closest sampled component vertex is 1.6873 mm from the main surface.
This is a vertex-sampled distance, not an exact minimum surface-to-surface gap.
No cross-component triangle crossing is detected. Do not delete or merge this
component solely to reduce the component count. Reference-guided authoring and
attachment/deformation decisions remain necessary.

## Render review and limitations

Seven 1000×1000 CPU Cycles renders (24 samples) are retained and inspected:
before/after diagnostic patch, before/after textured sleeve context, two colored
component-context views, and front full assembly. Red identifies the same patch
before/after, orange identifies the retained component. The extremely thin patch
changes local shading in diagnostic close-up; the textured-context silhouette
is essentially unchanged. This does not fix its coarse triangulation.

The full view still shows projected/white texture artifacts, unfinished source
anatomy and faceted clothing. The authored sleeve/upper-arm material transition
and provisional hand material remain obvious. No visual-quality improvement
or score ≥0.6 is inferred from this topology-only change.

The body and sleeve remain layered and unwelded with a temporary internal cap.
There is no verified rig, skin weights, pose-dependent cap coverage, FBX/Unity
import, final atlas/material budget or Gate B approval.

## Verification and reproduction

- Script: `scripts/blender/repair_ch101_local_crossing.py`.
- Blender: 5.2.0 LTS (`fbe6228777e7`), execution exit 0.
- Input: `CH101_DistalReplacementAssembly_NOT_PRODUCTION_v001.blend`.
- Input SHA256: `0fbf9820bd66cc3b2eb8c41d36358aa490f3451a84a673b2913c7db793060c2b`.
- Output: `CH101_LocalTopologyRepair_NOT_PRODUCTION_v001.blend`.
- Output SHA256: `e89357579ef64eda53bf8c37eda9942d898e23171f0f0bcb39f2fd833b7456b0`.
- Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
- Saved Blend reopened: original has 3 pairs, repair 0; UV/topology invariants
  and component preservation pass; 14 working meshes visible, originals hidden.
- Blender tests: all 8 pass in `tests/blender/test_local_crossing_repair.py`, including finite segment
  checks, UV mutation detection, unsafe-limit/no-crossing rejection, actual
  source repair, wrong-region rejection, failed-copy cleanup, saved-file reopen.
- Python suite: 132 run, 131 pass, one skip; AI3D and Colab validators pass.
- Non-blocking Blender messages: extension-cache permission warnings in tests;
  render shutdown reported one unfreed 0.000023 MB block with exit 0. Saved-file
  reopen and validation subsequently passed.

```text
blender --background --python-exit-code 1 --python scripts/blender/repair_ch101_local_crossing.py -- --source PATH/CH101_DistalReplacementAssembly_NOT_PRODUCTION_v001.blend --art-root ../re-camp --output PATH/new-output
```

Use a fresh output path. `--no-render` is for diagnosis only. The final report
explicitly records the non-adjacent BVH scope in its topology metadata; that
metadata clarification does not change the saved mesh or render evidence.

Separate intended release: `ch101-local-topology-repair-v001`.
Separate restore pointer: `docs/artifacts/CH101-latest-local-topology-repair.json`.
Prior full-character and part-study pointers are not replaced.

## Next work

1. Refine the upper-sleeve contour and material/trim transition against the
   approved sheet; preserve a comparison baseline and test authored-part overlap.
2. Identify/author the thigh-side hanging strip against reference before any
   semantic merge/deletion decision. Keep its original recoverable.
3. Bind and test forearm/wrist poses only after interface construction is ready;
   verify skinning, cap coverage and equipment clearance under deformation.

Status remains NOT_PRODUCTION, PENDING_HUMAN_REVIEW, Unity input disabled and
Production promotion disabled. No full-character score is assigned.
