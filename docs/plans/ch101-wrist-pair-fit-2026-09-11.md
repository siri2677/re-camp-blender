# CH101 closed wrist loop and rigid pair fit — 2026-09-11

## Completed geometry work

Local Blender CPU found one closed, degree-two intersection graph with 29 points
on the predefined plane 45 mm toward the estimated elbow. Triangle-plane
intersections are welded at 1 micrometre rounding; gaps/branches, degenerate
segments and local vertex-on-plane ambiguities are refused. The signed area
centroid replaces the earlier sample median. No body geometry was cut.

The area is 0.00219458 m² and centroid approximately
(-0.35788590, 0.00495563, 0.88205302) m. A closed geometric section is not evidence
of a semantically correct skin/cuff seam. Its loop has not been approved as the
anatomical wrist, and no self-crossing polygon proof is claimed by degree-two alone.

The new operation applies one rotation/translation to CLONED hand and saber
together, including cloned hardware and sockets. This is different from the
previous eight poses with a stationary saber. It preserves the established grip
instead of trying to stretch the hand across a positional gap.

- Geometric wrist-center error: 9.31e-10 m.
- Geometric wrist outward-axis error: 0 degrees at measured precision.
- Maximum hand-relative-saber matrix element difference: 1.79e-7.
- New hand versus saber/detail surface crossings: zero.

These are transform-consistency results, not quality, grasp or integration gates.
The original body, equipment and earlier hand studies are retained unchanged;
the isolated study hides them, and the context images temporarily show the body
in clay with an orange PROVISIONAL section marker.

## Still unmerged; do not mistake the context images for completion

The old source hand remains under the new hand. Measured source-body crossings:

| Study object | Unique study triangles crossing source body | Against wholly proximal source triangles | Against wholly distal source triangles | Against plane-straddling source triangles |
| --- | ---: | ---: | ---: | ---: |
| New hand | 119 | 0 | 95 | 30 |
| New saber | 5 | 0 | 5 | 0 |

Column categories overlap: a study triangle can cross multiple source triangles
of different categories, so 95+30 is not a disjoint count. These are geometric
plane-side categories, NOT a declaration that distal faces may safely be deleted.
Surface tests do not establish containment, clearance under motion or force closure.

A supplemental saved-scene section 5 mm distal to the new wrist has 82 intersection
points and area 0.00071039 m², approximately 32.4% of the source candidate section.
The section planes differ by 5 mm, so this is a nearby-size diagnostic, not a
matched-boundary comparison or a measured seam gap. It nonetheless shows why
matching centers/axes alone does not produce matching boundaries. The source
candidate may include cuff bulk rather than skin; enlarging the hand arbitrarily
to equal that area would not establish anatomical correctness.

## Next authoring boundary

Identify whether the orange loop represents sleeve/cuff or skin using the source
reference and local geometry. Establish the intended hand/cuff interface before
any source-hand replacement: distinct cuff opening versus a welded skin seam
need different topology. Reconcile perimeter shape and thickness, not only vertex
count; do not weld the 29/82 diagnostic intersection samples directly.

Then validate a reversible working-copy replacement, removing only the identified
old hand region from that copy, preserving the original, and checking connected
geometry, normals, UV and deformation. Until that explicit boundary is established,
do not cut the original or claim a merged wrist. Palm/knuckle fidelity, skinning,
face/hair/outfit improvements, full-character QA and Gate B remain unfinished.

## Reproduction and retention

Script: `scripts/blender/fit_ch101_hand_saber_pair.py`, arguments `--source`,
`--source-sha256`, `--art-root`, `--output` (new directory).
Input: `0ac9dac544a025270fcdf2f4446d10a87e212eb6ddb88041f76b1bd752378e82`.
Art commit: `b6c9b3128358e061eee6184230929413eba84101`.
Output: `f79851bea699ad2dbb94315e36a67d9f6e19b3488190acfec64bef71a5ea2dfd`.

Four Blender fixture tests cover closed-section centroid, open-section rejection,
pair transform preservation and descendant hierarchy preservation. Python suite:
132 tests. AI3D/Colab validation covers 10 notebooks, 27 Blender scripts, 36 utilities.

Release target: `ch101-wrist-pair-fit-study-v001`, separate pointer
`docs/artifacts/CH101-latest-wrist-pair-study.json`. Retain the actual blend,
three renders, main report, supplemental section measurement and this readme.
The supplemental section probe is recorded separately from the original run report.

All results stay `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`,
`sourceHandReplaced=false`, `anatomicalSeamVerified=false`,
`wristIntegrationAllowed=false`, `attachmentApproved=false`.
