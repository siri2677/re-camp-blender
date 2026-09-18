# CH101 texture-free attachment surface diagnosis — 2026-09-11

## Result, not a repair

Local Blender CPU produced five actual clay renders without editing the source.
Front/back hand views show a fused tapered volume without identifiable articulated
fingers. Earlier notes called it an "open hand" based on its texture; the clay
evidence makes that description too generous. The current geometry does not
provide a reliable ready-to-pose palm/thumb/finger structure. This is a visual
assessment, not automatic anatomical segmentation.

The full-body clay image also shows coarse/fused face, hair and outfit forms.
Removing the white texture patches alone will not create the missing detail.
No high-quality model, grasp or attachment is approved by this step.

## Reproduction and ranked hypotheses

A read-only Blender expression opened the exact hashed source, called
`review_ch101_equipment_fit.overlap_report` on `geometry_0` and `CH101_Saber`, and
asserted `nearHandCrossingTriangles == 0`. It failed with
`OPEN_HAND_HANDLE_SURFACE_INTERSECTION`: 85 triangle pairs, 16 distinct saber
triangles near the hand, zero away from it. The independent diagnostic script
reproduced the same numbers. Hardware detail meshes are not needed to reproduce.

1. Missing grasp geometry: supported by front/back clay views with equipment hidden.
   This is the principal authoring dependency. Texture has been removed only via
   a render material override; vertex positions are unchanged.
2. Bad estimated anchor: its nearest body-surface distance is 0.01654 m. This
   establishes that it is not a surface attachment, but does not prove the anchor
   is anatomically wrong (a grip center can lie away from skin). Even a relocated
   anchor would not supply fingers. Do not treat offset-only clearance as holding.
3. Duplicate/non-manifold topology: not supported in the sampled regions. This
   does not rule out self-intersection, near-duplicate vertices, winding errors,
   or other defects elsewhere in the mesh.

| Sphere ROI | Vertices | Induced components | Exact duplicate vertices | Original boundary/non-manifold edges |
| --- | ---: | --- | ---: | --- |
| Hand, radius 0.10 m | 118 | 118 | 0 | 0 / 0 |
| Waist, radius 0.12 m | 260 | 204, 40, 16 | 0 | 0 / 0 |

Sphere ROIs may include cuff, arm or clothing. Induced components can be cut by
the sphere boundary and are not independent anatomical parts or mesh defects.
The waist ray remains a shell hit, not a verified belt attachment site.

## Next modeling sequence

1. Preserve this source and create a separately labeled hand-authoring study.
2. Inspect approved art and identify a defensible wrist/cuff seam; do not cut an
   arbitrary sphere and claim the seam is anatomically verified.
3. Author palm, thumb and four finger volumes with actual connected surfaces;
   establish hand scale and a grip around the retained handle. Reject mere
   texture-painted fingers or disconnected primitive decoration as completed hands.
4. Show bare-clay front/back/side and grip close-ups, then test mesh connections,
   UV, body seam and surface interference. Pose success is not rig/animation success.
5. Only after the hand study passes, merge a tested copy into the character and
   revisit wrist weights, belt attachment and swept motion clearance.

This is actual semantic geometry authoring, not another placement or smoothing
retry. If the seam cannot be established from the available surface/reference,
record that specific missing input. Do not lower QA thresholds or silently
replace the whole character. Face/hair/outfit fidelity remains separate work.

## Tests, preservation and distribution

`scripts/blender/inspect_ch101_attachment_surface.py` accepts `--source`,
`--source-sha256`, `--art-root`, `--output`. It verifies locked refs, refuses
existing output directories, measures regions/overlap and restores material
override and equipment visibility after rendering. Source file hash and mesh
digest are checked. No model is saved or changed by the script.

Three Blender fixture tests verify closed/open topology and empty ROI rejection;
these are diagnostic tests, not a regression claiming the grasp was repaired.
The AI3D and Colab compile validators pass. The reproduction remains red because
semantic authoring is still needed, not because a test was waived.

Source blend SHA256:
`d09d94258c1ff7fd78f28b36060631ba8c394b7ba7e9a36cecdeb4adbc9133c6`.
Pinned art: `b6c9b3128358e061eee6184230929413eba84101`.
The evidence archive retains a byte-identical copy of that blend for reproduction;
it is not a newly modeled hand. Diagnostic files are added to the existing
`ch101-material-clearance-review-v001` prerelease with a separate pointer.

All gates remain locked: `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
`PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
`productionPromotionAllowed=false`, `attachmentApproved=false`.
