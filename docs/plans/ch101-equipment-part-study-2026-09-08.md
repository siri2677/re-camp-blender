# CH101 equipment part study — 2026-09-08

## Scope and decision

This is a genuine part-authoring step, not another full-character smoothing or
projection attempt. The recovered character remains unchanged. Its best prior
numeric score of 0.834283 and strict rejection are not replaced by a part score.

The approved Character Sheet and review Equipment Sheet at art commit
`b6c9b3128358e061eee6184230929413eba84101` explicitly show **one saber and one
signal ribbon**. Earlier prose saying "ribbon pair" conflicts with that source.
The L/R Socket contract labels are preserved as endpoints of the same ribbon;
they do not authorize a duplicate ribbon. The sheath is a storage component.

Equipment is the first isolated part study because its forms are clearly
visible in the locked sheet. This parallel authoring step does not imply that
body/face, hair or outfit work is complete or unnecessary.

## Actual output

`scripts/blender/build_ch101_equipment_study.py` builds separate connected,
closed meshes using beveled cross-section lofts and a thick curved sweep:

| Part | Vertices | Triangles | Components | Non-manifold edges |
| --- | ---: | ---: | ---: | ---: |
| Saber | 96 | 188 | 1 | 0 |
| Hollow-mouth sheath | 72 | 140 | 1 | 0 |
| Single signal ribbon | 324 | 644 | 1 | 0 |

Total: 972 triangles, five shared materials, UV on each part. The materials
are procedural Blender shaders, not baked game textures. Reference images
are hash-checked and packed in the Blend. No new AI inference or GPU quota
was consumed: this ran in local Blender 5.2 CPU mode.

`Socket_Equipment_Primary` aliases the actual `Socket_Weapon_R` object through
the map; there is no second Transform. Blade-tip and ribbon endpoints exist
in part-local coordinates. They have **not** been fitted to the character or
validated through animation. VFXCenter/CameraFocus, rig and LOD are deliberately
not fabricated in this equipment-only scene.

## Render diagnosis and correction

The first rendered implementation stretched most of the blade into 1/11 of
UV V. The physical blade instead occupies approximately 67% of total length.
A real Blender regression test failed with `0.090909 < 0.65`. A second test
found the ribbon broad face used only 0.25 of the pattern width instead of 1.

The implementation now uses accumulated centerline distance for V and full
broad-face width for ribbon U. Those two regression tests pass, as do the
other four equipment tests. No score threshold, reference or scene lighting
was changed. The fixed rerender shows repeated blade stripes and a continuous
ribbon pattern. Revision V002 is a UV bug fix, not a repeated rejected quality
strategy. Both pre-fix and fixed outputs are retained.

## Visual judgement and remaining work

Agent inspection of front, side and 3/4 renders confirms deliberate equipment
volumes and a hollow sheath mouth. The result is still a simplified authoring
study, **not acceptable as final reference-matched equipment**:

- Saber guard, pommel loop, grip wraps and cyan insets lack the sheet's detail.
- Sheath ornaments and the ribbon clasp are not authored yet.
- Ribbon lattice scale and surface shading differ from the reference; visible
  faceting remains. Its 3D path and all absolute dimensions are estimates.
- Side view overlaps the layout items; isolated part views are needed before
  judging fitted silhouette. No collision/self-intersection or physics pass
  is claimed by the manifold check.
- Body/face/hair/outfit are not part of this asset. No full-character evaluator
  was run and no Alpha Review or Gate B evidence is fabricated.

Next: author guard/inset/clasp detail within the 2,000 triangle budget, improve
isolated side/close-up presentation, then fit these parts to a verified hand
and waist on the character. Full-character face/hair/outfit authoring remains
a separate substantial task. Preserve all prior character binaries and scores.

## Reproduce and retain

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_equipment_study.py -- --art-root ../re-camp-art --output-dir artifacts/new-equipment-study --render
blender --background --python-exit-code 1 --python tests/blender/test_equipment_study.py
```

Output directories are never overwritten. Art commit and both pinned image
hashes must match before output creation. The initial strategy preflight was
`READY_NEW_STRATEGY`; no quality retry override was used.

Release: `ch101-equipment-part-study-v001`. Use the separate
`docs/artifacts/CH101-latest-equipment-study.json` pointer. The existing latest
full-character pointer stays unchanged, avoiding accidental replacement by a
partial kit. The archive contains both implementations, their reports, four
views each, this note and preflight evidence. Full SHA256 records accompany
every file in the release manifest.

All outputs remain `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`. Technical part checks do not imply visual
acceptance, Production intake, Unity export or Android readiness.
