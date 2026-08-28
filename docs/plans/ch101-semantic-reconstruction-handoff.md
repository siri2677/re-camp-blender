# CH101 semantic reconstruction handoff

## Purpose

The Wonder3D NeuS/voxel comparison has reached a quality plateau. The recorded
surface is useful as technical evidence, but it does not contain reliable
semantic separation for CH101's face, hair, outfit, equipment, or ribbon. The
next quality step is therefore a review-only semantic reconstruction plan,
not another identical Wonder3D retry.

This document is a handoff checklist for Blender Desktop or a 3D contributor.
It does not promote an asset, approve Gate B, or enable Unity input.

Before opening Blender, prepare and inspect the secret-free input report:

```text
python scripts/ai3d/prepare_semantic_reconstruction_handoff.py \
  --art-root ../re-camp-art \
  --output docs/records/ch101-ai3d/2026-08-28-semantic-reconstruction-inputs-v001.json
```

The command verifies the pinned art commit, hashes the four locked reference
images, and materializes the CH101 collections, sockets, face placeholders,
and review evidence checklist. It does not generate a mesh.

## Locked references

- `re-camp` art commit: `b6c9b3128358e061eee6184230929413eba84101`
- `art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png`
- `art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png`
- `art_refs/characters/rin/concept/CH101_Rin_EquipmentSheet_REVIEW_v001.png`
- `art_refs/characters/rin/concept/CH101_Rin_ExpressionSheet_REVIEW_v001.png`
- Socket contract: `contracts/current_roster_socket_contract_v001.json`

The files above are visual and technical references only. A WIP, primitive,
voxel, or AI slab may not be renamed into a Production Mesh.

## Reconstruction order

1. **Body and face**
   - Establish a clean A-pose body with a recognizable head, jaw, eyes, nose,
     mouth, and ear planes.
   - Keep the face topology separate enough to support the planned blendshape
     driver handoff.
2. **Hair**
   - Build the main hair mass and ponytail as intentional forms with a visible
     hairline, silhouette breakup, and stable attachment to the head.
3. **Outfit**
   - Model the jacket, shorts, straps, boots, and major seams as separate
     semantic regions matching the approved sheet's proportions and palette.
4. **Equipment**
   - Model the saber, sheath, ribbon pair, and pouch as distinct objects.
   - Preserve clear blade tip, grip, ribbon, and equipment-root attachment
     points rather than relying on guessed surface locations.
5. **Presentation pass**
   - Check front, right, back, and 3/4 views against the locked references.
   - Reject any result that still reads as a single slab, box, or unsegmented
     shell even if a numeric silhouette score is high.

## Technical handoff contract

The review Blend should contain these collections:

- `MODEL_HIGH_BODY`
- `MODEL_CLOTH_OUTFIT`
- `MODEL_HAIR`
- `MODEL_EQUIPMENT`

It should also contain the CH101 Armature, UVs, six-or-fewer review materials,
LOD0/LOD1/LOD2 evidence, and these sockets:

- Common: `Socket_Equipment_Primary`, `Socket_VFXCenter`,
  `Socket_CameraFocus`
- CH101 detail: `Socket_Weapon_R`, `Socket_BladeTip`, `Socket_Ribbon_L`,
  `Socket_Ribbon_R`

Face placeholders are required for the handoff plan:
`Blink_L`, `Blink_R`, `Face_Smile`, `Viseme_A`, `Viseme_E`, `Viseme_I`,
`Viseme_O`, `Viseme_U`. If reliable landmarks are unavailable, record the
placeholder as blocked; do not fabricate a face driver from the AI surface.

## Review evidence required

- Front, right, back, and 3/4 rendered views
- A-pose plus a basic deformation/idle check
- Face close-up and hairline check
- Outfit seam, material-region, and equipment attachment check
- Socket location sheet or annotated viewport capture
- Blender validator report and `.blend` SHA256

The expected interim status remains:

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

Only after semantic reconstruction, technical intake, and a human Gate B
decision may the project move to Unity. Until Blender or a compatible 3D
authoring environment is available, this handoff is prepared but blocked.
