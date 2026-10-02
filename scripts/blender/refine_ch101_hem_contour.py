"""Small, cumulative-envelope-checked contour study on a separate hem copy."""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import round_ch101_hem_binding as prior
c, surface, panel = prior.c, prior.surface, prior.panel
SOURCE_SHA = '39f5e07de24a433a7d74ff51a607219ace089162c916a0c1040c96c9b7b31a20'
RESULT_OBJECT = 'CH101_HemContour_NOT_PRODUCTION'
STRATEGY = 'CH101_BOUNDED_HEM_CONTOUR_V001'
MAX_MOVE = .0001


def centers(obj):
    if len(obj.data.vertices) != 2048 or len(obj.data.polygons) != 2048:
        raise ValueError('UNEXPECTED_ROUNDED_HEM_TOPOLOGY')
    return [sum((obj.matrix_world @ obj.data.vertices[i*16+j].co for j in range(16)), Vector())/16 for i in range(128)]


def contour_metrics(points):
    if len(points) != 128 or not all(math.isfinite(x) for p in points for x in p):
        raise ValueError('INVALID_CONTOUR')
    lengths = [(points[(i+1)%128]-p).length for i, p in enumerate(points)]
    if min(lengths) < 1e-6:
        raise ValueError('COLLAPSED_CONTOUR_SEGMENT')
    angles = [math.degrees((p-points[i-1]).angle(points[(i+1)%128]-p)) for i, p in enumerate(points)]
    return dict(maximumTurnDegrees=max(angles), rmsTurnDegrees=math.sqrt(sum(a*a for a in angles)/128),
                sharpestSection=angles.index(max(angles)), sectionTurnDegrees=angles,
                circumferenceMeters=sum(lengths), minimumSegmentMeters=min(lengths),
                metricIsNotVisualQualityScore=True)


def build(source, max_move=MAX_MOVE):
    surface.require_locked(source)
    if not math.isfinite(max_move) or not 0 < max_move <= MAX_MOVE:
        raise ValueError('UNSAFE_CONTOUR_MOVE')
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('CONTOUR_ALREADY_EXISTS')
    original = centers(source)
    target = [p.copy() for p in original]
    # Three fixed Jacobi steps, bounded against ORIGINAL centers, not per-step.
    # Linear interpolation by edge length avoids drifting unevenly sampled rows.
    for _ in range(3):
        updated = []
        for i, p in enumerate(target):
            a, b = target[i-1], target[(i+1)%128]
            left, right = (p-a).length, (b-p).length
            if left < 1e-6 or right < 1e-6:
                raise ValueError('COLLAPSED_CONTOUR_SEGMENT')
            candidate = p.lerp(a.lerp(b, left/(left+right)), .5)
            delta = candidate-original[i]
            if delta.length > max_move:
                delta *= max_move/delta.length
            updated.append(original[i]+delta)
        target = updated
    obj = source.copy(); obj.data = source.data.copy(); obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    inverse = obj.matrix_world.inverted()
    for i, (old, new) in enumerate(zip(original, target)):
        # Compute the small delta first; p + new - old loses precision near z=1m.
        delta = new-old
        for j in range(16):
            index = 16*i+j
            obj.data.vertices[index].co = inverse @ (source.matrix_world @ source.data.vertices[index].co+delta)
    obj.data.update()
    if surface.repair.invariant_signature(source) != surface.repair.invariant_signature(obj):
        raise ValueError('CONTOUR_NONPOSITION_DATA_CHANGED')
    maximum = max((obj.matrix_world @ a.co-source.matrix_world @ b.co).length for a, b in zip(obj.data.vertices, source.data.vertices))
    if maximum > max_move+1e-7:
        raise ValueError('CONTOUR_STORED_DISPLACEMENT_EXCEEDED')
    ratios = [a.area/b.area for a, b in zip(obj.data.polygons, source.data.polygons)]
    min_dot = min(a.normal.dot(b.normal) for a, b in zip(obj.data.polygons, source.data.polygons))
    if min(ratios) < .75 or max(ratios) > 1.25 or min_dot < .95:
        raise ValueError('CONTOUR_FACE_DISTORTION_REJECTED')
    before, after = contour_metrics(original), contour_metrics(centers(obj))
    if after['maximumTurnDegrees'] >= before['maximumTurnDegrees'] or after['rmsTurnDegrees'] >= before['rmsTurnDegrees']:
        raise ValueError('CONTOUR_TURN_NOT_REDUCED')
    c.base.mark(obj)
    return obj, dict(before=before, after=after, maxMoveMeters=maximum, displacementLimitMeters=max_move,
                     originalRoundedSourceBudgetNotReset=True, sectionTranslations=[list(b-a) for a,b in zip(original,target)],
                     sectionCount=128, crossSectionShapePreserved=True, cornersRerounded=False, bodyMovedVertices=0,
                     faceAreaRatioRange=[min(ratios),max(ratios)], minimumFaceNormalDot=min_dot,
                     topologyMaterialsUVWeightsShadingPreserved=True, attachedOrSewn=False)


def render(output, source, obj, body, parts, frame, section):
    rows = prior.render(output, source, obj, body, parts, *frame[:2])
    center, axis, u = frame
    normal = (axis-u*panel.HEM_SLOPE).normalized()
    focus = centers(source)[section]
    scene = bpy.context.scene
    for part in [body]+parts:
        part.hide_render = True
    scene.camera.data.ortho_scale = .018
    scene.camera.location = focus+normal*.2
    scene.camera.rotation_euler = (focus-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    for label, selected in [('before', source), ('after', obj)]:
        source.hide_render = selected != source; obj.hide_render = selected != obj
        path = output/(label+'_sharp_sector.png')
        scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)
        rows.append(dict(file=path.name, sha256=c.base.sha(path)))
    return rows


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source)); surface.require_locked(bpy.context.scene)
    originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    signatures = {o.name:surface.repair.invariant_signature(o) for o in originals}
    band = bpy.data.objects[prior.RESULT_OBJECT]
    original_binding = bpy.data.objects[prior.prior.RESULT_OBJECT]
    body = bpy.data.objects[panel.RESULT_OBJECT]
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    obj, operation = build(band)
    # Critical: compare to the FIRST rectangular binding, not the rounded copy.
    qa = prior.audit(obj, original_binding, body, parts)
    if not qa['eligible']:
        raise ValueError('CONTOUR_CUMULATIVE_QA_REJECTED:'+json.dumps(qa))
    frame = panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    output.mkdir(parents=True)
    renders = [] if args.no_render else render(output, band, obj, body, parts, frame, operation['before']['sharpestSection'])
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != signatures[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = panel.seam.replacement.configure_review_viewport([body]+parts+[obj])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):
            old.hide_render = old not in [body]+parts+[obj]
    surface.require_locked(bpy.context.scene); bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_HemContour_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    report = dict(strategyId=STRATEGY, status='CONTOUR_STUDY_PENDING_VISUAL_REVIEW', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs, operation=operation,
                  qa=qa, envelopeReferenceObject=original_binding.name, originalsPreserved=True,
                  fullCharacterScore=None, rigBound=False, defaultVisibleMeshObjects=visible,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['FINITE_SAMPLED_ENVELOPE_AND_STATIC_CLEARANCE', 'FLOATING_BINDING_NOT_ATTACHED',
                               'SUBTLE_CONTOUR_CHANGE_NOT_FULL_GARMENT_AUTHORING', 'NO_HUMAN_GATE_B_BAKE_OR_RIG'])
    (output/'hem-contour-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps(dict(status=r['status'],blendSha256=r['blendSha256'],qa=r['qa'],
                         maximumTurnBefore=r['operation']['before']['maximumTurnDegrees'],
                         maximumTurnAfter=r['operation']['after']['maximumTurnDegrees']),indent=2))
