# CH101 equipment hardware detail study — 2026-09-10

## Result and scope

The 2026-09-08 unfinished hardware implementation has now run successfully in
local Blender 5.2 CPU mode. No provider/GPU retry, paid resource or reference
change was used. Strategy: `CH101_REFERENCE_EQUIPMENT_HARDWARE_STUDY_V002`.
The earlier study and full-character assets remain unchanged.

New authored geometry: seven cyan grip diamonds, two guard insets, a pommel
ring, sheath end ring, sheath badge and bezel, one ribbon clasp and clasp pin.
These 15 detail meshes are parented to the three canonical equipment parts.
They are not extra sabers or ribbons, nor falsely joined semantic body parts.

- Total: 1,448 triangles (budget 2,000), six shared equipment materials.
- All 18 mesh objects have UVs, one connected component each and zero
  non-manifold edges. This is not a collision or self-intersection test.
- Closed hardware loops have real apertures, not flat image decals.
- Equipment Primary still aliases Weapon R; no duplicate Transform is created.
- Nine actual renders: front/back/side/3-4, isolated saber/sheath sides,
  grip/guard close-up, sheath badge close-up and ribbon clasp close-up.

Direct agent inspection of the 3-4 and close-up renders confirms readable
hardware silhouettes. Detail is improved over the bare initial study, but
the result is still simplified: grip wrap relief, accurate bevels, blade edge,
surface shading, ribbon faceting and clasp mechanics remain unfinished.
This is not final reference-matched equipment or a full-character QA pass.

## Character attachment evidence

Read-only inspection used the preserved best profile Blend with SHA256
`db64df69f1c86dbf1605dbcaccbd5af9c613904cc2de67ff05407d1c93f3b80b`.
It contains `geometry_0` and no Armature or Socket objects. No verified
hand/waist attachment evidence exists. The source hash was unchanged after
inspection. Status: `BLOCKED_UNVERIFIED_CHARACTER_ATTACHMENT`.

Do not guess a hand position and report attachment complete. Next character
work is to establish an explicit rig/hand/waist landmark review on this actual
mesh, test the grip pose and clearance, then attach against that evidence.
The six-material equipment budget also must be reconciled with the combined
character material budget before integration. Body/face/hair/outfit quality
and deformable topology remain separate incomplete work.

## Resolved execution defect

The initial run on 2026-09-08 reached render but passed a relative path into
Blender. It tried to save `C:/artifacts/.../front.png`, not the workspace
directory. A boundary regression test reproduced the relative path leak.
CLI paths are now resolved before loading/resetting Blender scenes. The same
relative-output invocation then produced all nine files under the intended
workspace. No permission expansion or directory deletion was needed.

Four real Blender hardware tests pass, including the regression, wrong source
hash rejection, source preservation/attachment blocking and hardware topology/
parenting/budget. The initial test assertion was normalized for Windows short
versus long temporary path names. 132 Python tests and both package validators
also pass. The tests do not assert visual acceptance.

## Reproduce

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_equipment_detail_study.py -- --art-root ../re-camp-art --output-dir artifacts/new-hardware-study --character-blend path/to/preserved-character.blend --character-sha256 db64df69f1c86dbf1605dbcaccbd5af9c613904cc2de67ff05407d1c93f3b80b
blender --background --python-exit-code 1 --python tests/blender/test_equipment_hardware.py
```

Both locked reference image hashes and art commit
`b6c9b3128358e061eee6184230929413eba84101` are verified before output. An
existing output directory is refused, and the source is never saved over.

Release: `ch101-equipment-hardware-study-v002`. Latest pointer:
`docs/artifacts/CH101-latest-equipment-study.json`. The archive contains the
actual Blend, nine PNGs, report, preflight record and this note as text.
The full-character pointer is not replaced by the partial kit.

All gates remain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`. Full-character score is deliberately null.
No Production/Unity/Android completion is claimed.
