# CH101 reference correction — NOT PRODUCTION

This prerelease preserves the recovered model after correcting gray-canvas
segmentation, padded texture projection and Blender silhouette fitting.

| Same corrected evaluator | Overall | Silhouette | Appearance |
| --- | ---: | ---: | ---: |
| Previous model reranked | 0.774501 | 0.817458 | 0.572612 |
| Subject-bounds texture correction | 0.812296 | 0.820783 | 0.715149 |
| Two-axis geometry correction | 0.834283 | 0.847052 | 0.734795 |
| Minimum | 0.60 | 0.50 | 0.55 |

Color `0.662127`, face-edge proxy `0.871344`, technical `1.0` and topology
checks also pass their numeric thresholds. The historical `0.53343` used an
incorrect gray-canvas mask and is not a like-for-like quality comparison.

**Strict disposition: REGENERATE_REQUIRED.** Independent body/face, hair,
outfit and equipment geometry is unverified. Direct agent inspection still
finds malformed facial/head volume, side texture seams and missing equipment.
There is no human Gate B approval. Production promotion and Unity input remain
false. Numeric score increases do not constitute final modeling completion.

The ZIP contains actual review Blends, review GLBs, renders, masks, provenance,
per-file SHA256 and same-evaluator comparisons. `comparison/assisted-visual-review.json`
is the current v004 QA and supersedes older missing-semantic-evidence decisions.
The two-axis profile candidate is the latest experiment, not an approved selection.

Validation: 132 Python tests, 12 real-Blender regression tests, AI3D/Colab
package validators, plus the recorded same-strategy rejection check.
Tools commit: `32bd4c91c27bb8952b1e0411071c9727eea17851`.
Branch: `feature/ch101-free-ai3d-autobuild`.

![Reference, previous render, texture correction, profile correction](https://github.com/siri2677/re-camp-blender/releases/download/ch101-reference-correction-review-v001/CH101_before_after_NOT_APPROVED.png)

Next: actual semantic geometry authoring and continuous texture coverage, then
multi-angle inspection and technical validation before human Gate B.
