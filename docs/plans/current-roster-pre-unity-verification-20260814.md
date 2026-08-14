# Current roster pre-Unity verification — 2026-08-14

The five-character batch notebook was executed in Google Colab on 2026-08-14 (KST) from the following revisions:

- Art source branch: `art/current-roster-gate-a-ch102`
- Art checkout: `b6c9b3128358e061eee6184230929413eba84101`
- Tools branch: `agent/current-roster-pre-unity`
- Tools checkout: `33cc1b0ca81085adcde7eb284afd1dfbdfe93ce0`
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

This is a successful technical preflight, not final production skinning, Unity Humanoid import proof, Android performance evidence, or Gate B approval.
