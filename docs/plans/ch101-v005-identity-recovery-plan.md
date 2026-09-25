# CH101 v005 identity-recovery regeneration plan

## Current reason for regeneration

The v004 package passed archive and technical validators, but all reviewed candidates were rejected for semantic visual mismatch:

- face identity was not recognizable;
- high ponytail structure did not match;
- jacket, shorts, and color blocking were not preserved;
- saber and signal ribbon were missing or unidentifiable;
- hands and fingers were malformed.

The current state remains `REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW` with `unityInputAllowed: false`.

## v005 input policy

CH101 uses the `CH101_V005_IDENTITY_RECOVERY` profile:

- keep the provider input as the locked neutral full-body front view;
- run the three single-view attempts as `front`, `front`, `front` instead of using side/back views for identity generation;
- use foreground ratios `0.80`, `0.90`, and `0.98`;
- record the approved character sheet, expression sheet, and equipment sheet as auxiliary references with SHA256;
- auxiliary references improve traceability and human review, but are not silently merged into the provider input;
- run Geometry Gate, score, and assisted visual review again after generation.

## Gate rules

The v005 result is accepted for Alpha Review only when the score and geometry thresholds pass and assisted visual review does not reject it. Even then:

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

No FBX/GLB Unity package is created from a v005 candidate before human Gate B approval.

## Execution

The profile is prepared in the repository and runs automatically from Notebook 05 when a GPU workstream is selected. When Colab reports `BLOCKED_GPU_UNAVAILABLE`, the notebook stops before dependency installation and inference; the reference manifest and profile remain reusable for the next GPU session.
