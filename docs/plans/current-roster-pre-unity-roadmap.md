# Current roster pre-Unity roadmap

This plan expands the verified CH101 v007 blockout pipeline to the five
currently approved characters. Historical character folders are intentionally
out of scope until they receive a new approval gate.

## Locked source set

The Colab batch notebook clones the source branch
`art/current-roster-gate-a-ch102` and checks these approved sheets. The
per-character approval commit is recorded in every generated report.

| ID | Character | Approved sheet | Approval commit |
| --- | --- | --- | --- |
| CH101 | Rin | `art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png` | `ae111815f356f105a170bf1c473ae3cd086fee4c` |
| CH102 | Mao | `art_refs/characters/mao/concept/CH102_Mao_CharacterSheet_APPROVED_v001.png` | `c01a4e2d90919872997dccf46679cf8ab10f1e87` |
| CH103 | Nozomi | `art_refs/characters/nozomi/concept/CH103_Nozomi_CharacterSheet_APPROVED_v001.png` | `f231ed5a4491eaa274237b7a2c8d4911d538b0ab` |
| CH104 | Shion | `art_refs/characters/shion/concept/CH104_Shion_CharacterSheet_APPROVED_v001.png` | `2dcb002f2691006008d0c20fa8157cbdd7d52538` |
| CH105 | Akari | `art_refs/characters/akari/concept/CH105_Akari_CharacterSheet_APPROVED_v001.png` | `d876bbc0c2eef7e9e549de274c15b3ab190ad6ce` |

## Pre-Unity work package

For each character, the batch job produces:

1. Approved-sheet provenance in the scene and JSON report.
2. Art-directed blockout silhouette and equipment cue.
3. Mesh conversion, applied transforms/modifiers, UV maps, material slots,
   triangle count, and generated LOD1/LOD2 proxy meshes.
4. Shared 22-bone humanoid-aligned rig prototype.
5. Eight sockets parented to the expected bones.
6. `Idle`, `Run`, `Attack`, and `A_Pose_Check` review actions.
7. Rigid blockout weights and armature modifiers for deformation review.
8. Seven collider proxy empties parented to rig bones and eight face target
   placeholders for later Unity wiring.
9. Front/side/back and four pose preview renders.
10. `.blend`, `.fbx`, per-character validation JSON, and one combined ZIP.

The generated weights are deliberately marked as `RIGID BLOCKOUT WEIGHTS`.
They prove pipeline wiring and deformation review only; they are not final
production skinning.

## Current implementation

- CH101 keeps the canonical `build_blockout.py` v007 output.
- CH102~CH105 use `build_roster.py` with character-specific visual cues:
  folding bow, orb baton and veil, prism fan and map ring, and paired
  gauntlets with anchor ring.
- `validate_asset.py --character CH10x` validates the same contract for every
  character, including LOD1/LOD2, collider parenting, and face target names.
- `notebooks/02_current_roster_pre_unity.ipynb` runs all five characters in a
  single Colab workflow and downloads
  `re-camp-current-roster-pre-unity-v001.zip`.

## Exit criteria before Unity

The pre-Unity package is complete when all five reports are `PASS`, all four
preview action images exist for each character, and the combined ZIP contains
five `.blend`, five `.fbx`, five validation reports, and the roster manifest.

The following remain intentionally blocked until a Unity Editor/device
environment is available:

- final Unity Humanoid mapping and FBX import settings proof;
- prefab/material/texture hookup inside Unity;
- runtime socket placement proof;
- Android build, frame-time, memory, and thermal measurements;
- Gate B approval.

## Verification command

```powershell
python scripts/validate_colab_package.py
```

The actual Blender verification is performed by running the batch notebook in
Colab because the local workspace is not the Unity/Blender runtime target.
