# Current roster pre-Unity export contract

This contract is the handoff boundary between the Blender pre-Unity package and
the later Unity import proof. It is deliberately explicit so the Unity step can
be executed without changing Blender-side naming or scale assumptions.

## FBX

- Unit scale: `1.0`
- Forward axis: `-Z`
- Up axis: `Y`
- Leaf bones: disabled
- Animation baking: enabled
- File name: `<CHARACTER>_Blockout_REVIEW_v007.fbx`
- Armature: `<CHARACTER>_Rig_Armature`
- Humanoid-aligned bones: 22, with Unity role mapping still pending

## Runtime preparation

- LOD0 is the source mesh.
- LOD1 and LOD2 are generated reduction proxies. Unity `LODGroup` wiring is
  pending the Unity environment.
- Seven box collider proxies are parented to Hips, Chest, Head, both hands, and
  both feet. Unity physics review is pending.
- Face target placeholders are named `Blink_L`, `Blink_R`, `Viseme_A`,
  `Viseme_I`, `Viseme_U`, `Viseme_E`, `Viseme_O`, and `Face_Smile`.
- Review actions are `<CHARACTER>_A_Pose_Check`, `<CHARACTER>_Idle`,
  `<CHARACTER>_Run`, and `<CHARACTER>_Attack`.

The package is a documentation-grade blockout and technical preflight. Final
production skinning, Unity import settings, prefab hookup, runtime socket proof,
and Android measurements remain outside this contract.
