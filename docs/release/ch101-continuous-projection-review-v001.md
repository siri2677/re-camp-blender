# CH101 continuous projection + face curvature — NOT PRODUCTION

This prerelease preserves two actual Blender postprocessing experiments, their
five-view renders, SHA256 evidence and a comparison against the previous model.

| Candidate | Overall | Appearance |
| --- | ---: | ---: |
| Previous profile baseline | 0.834283 | 0.734795 |
| Continuous projection | 0.833999 | 0.733662 |
| Bounded face curvature | 0.833983 | 0.733597 |

The continuous shader reduces abrupt polygon material switching. Bounded
curvature smoothing moves 349 face-region vertices by at most 3.78 mm. Neither
experiment demonstrates a meaningful overall quality improvement. The previous
baseline is preserved; no candidate is selected or approved.

**Strict result: REGENERATE_REQUIRED / SEMANTIC_COMPONENT_STRUCTURE_MISSING.**
Malformed facial volume, cross-view double features and absent independently
modeled hair/outfit/equipment remain. Face-edge score is not semantic face proof.
Human Gate B remains pending. Unity input and Production promotion remain false.

The new material uses Blender nodes and packed references. It is not a baked
GLB/FBX production material. No new paid service or provider inference was used.
Latest archive means latest preserved experiment, not final modeling completion.

![Reference, previous profile, continuous projection, bounded face curvature](https://github.com/siri2677/re-camp-blender/releases/download/ch101-continuous-projection-review-v001/CH101_before_after_NOT_APPROVED.png)
