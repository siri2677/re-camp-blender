# Current roster pre-Unity verification — 2026-08-14

The five-character batch notebook was executed in Google Colab on 2026-08-14 (KST) from the following revisions:

- Art source branch: `art/current-roster-gate-a-ch102`
- Art checkout: `b6c9b3128358e061eee6184230929413eba84101`
- Tools branch: `agent/current-roster-pre-unity`
- Tools checkout: `45180eb` (`fix: accept Blender FBX round-trip conventions`)
- Blender: `3.0.1`

## Result

The batch cell completed with:

```json
{
  "status": "PASS",
  "characters": ["CH101", "CH102", "CH103", "CH104", "CH105"]
}
```

For each character, the batch completed the build and the character-aware validator. This proves the shared pre-Unity contract for:

- 2D approved-sheet path and per-character approval commit metadata;
- blockout mesh with UV and material slots;
- generated LOD1/LOD2 proxy meshes;
- 8 sockets and the shared 22-bone rig prototype;
- 7 collider proxies with bone-parenting checks;
- 8 face blendshape target placeholders;
- 4 review actions: A-pose, idle, run, and attack;
- rigid blockout weights and armature deformation modifiers;
- front/side/back and four pose-review render passes;
- `.blend`, `.fbx`, and validation JSON output.

The final validation also reported non-zero LOD triangle totals:

| Character | LOD1 triangles | LOD2 triangles |
| --- | ---: | ---: |
| CH101 | 12,323 | 6,316 |
| CH102 | 7,464 | 3,977 |
| CH103 | 8,042 | 4,261 |
| CH104 | 7,672 | 4,076 |
| CH105 | 7,803 | 4,142 |

The FBX re-import smoke test and the soft performance budget check also passed
for all five characters. Blender 3.0.1 exposes the baked actions with FBX pipe
qualification and reports a uniform `100.0` object scale for the centimeter
conversion; the smoke test records and accepts those forms while checking the
effective mesh bounds. The budget thresholds and observed metrics were:

| Character | LOD0 tris | LOD1 tris | LOD2 tris | Mesh objects | LOD mesh objects | Bones |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CH101 | 26,584 | 12,323 | 6,316 | 89 | 178 | 22 |
| CH102 | 15,744 | 7,464 | 3,977 | 51 | 102 | 22 |
| CH103 | 17,028 | 8,042 | 4,261 | 52 | 104 | 22 |
| CH104 | 16,212 | 7,672 | 4,076 | 54 | 108 | 22 |
| CH105 | 16,504 | 7,803 | 4,142 | 54 | 108 | 22 |

The budget limits are 30,000 / 15,000 / 8,000 triangles for LOD0/LOD1/LOD2,
96 LOD0 mesh objects, 192 total LOD mesh objects, and 32 bones.

The combined archive was created at:

`/content/re-camp-current-roster-pre-unity-v001.zip`

The archive SHA256 sidecar recorded by the notebook is:

`b2d834c0f882ce074e006f85fc3ccc56fab4b6c2b6a8f4c482fd0fbdc47b953e`

The final package QA cell also passed and produced:

- visual comparison sheet: `/content/re-camp-output/current-roster-pre-unity-v001/qa/current_roster_visual_qa_contact_sheet.png`;
- package manifest with per-file byte counts and SHA256 values: `/content/re-camp-output/current-roster-pre-unity-v001/pre_unity_package_manifest.json`;
- 64 checked package files across the five-character roster, including the FBX
  smoke and budget reports.

The GitHub repository now validates the notebooks, Blender scripts, QA script, Python compilation, and export-contract document in `.github/workflows/pre-unity-package.yml`.

This is a successful technical preflight, not final production skinning, Unity Humanoid import proof, Android performance evidence, or Gate B approval.
