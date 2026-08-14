# Current roster pre-Unity verification — 2026-08-14

The five-character batch notebook was executed in Google Colab on 2026-08-14 (KST) from the following revisions:

- Art source branch: `art/current-roster-gate-a-ch102`
- Art checkout: `b6c9b3128358e061eee6184230929413eba84101`
- Tools branch: `agent/current-roster-pre-unity`
- Tools checkout: `2496969` (`feat: add pre-unity visual QA package checks`)
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

The combined archive was created at:

`/content/re-camp-current-roster-pre-unity-v001.zip`

The archive SHA256 sidecar recorded by the notebook is:

`62156baa8b25c61acf5365ba2b068891981795c3fa075551c285f96082695335`

The final package QA cell also passed and produced:

- visual comparison sheet: `/content/re-camp-output/current-roster-pre-unity-v001/qa/current_roster_visual_qa_contact_sheet.png`;
- package manifest with per-file byte counts and SHA256 values: `/content/re-camp-output/current-roster-pre-unity-v001/pre_unity_package_manifest.json`;
- 62 checked package files across the five-character roster.

The GitHub repository now validates the notebooks, Blender scripts, QA script, Python compilation, and export-contract document in `.github/workflows/pre-unity-package.yml`.

This is a successful technical preflight, not final production skinning, Unity Humanoid import proof, Android performance evidence, or Gate B approval.
