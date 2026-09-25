"""Bounded radial geometry relaxation above a locked CH101 sleeve seam."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refine_ch101_seam_contour as contour

seam, surface, c = contour.seam, contour.surface, contour.c
SOURCE_SHA = '3979e9c6929659ae8d462eceecfa89cd63fd73882f3d0e82581e0991523c4b4d'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_UpperTransition_NOT_PRODUCTION'
STRATEGY = 'CH101_BOUNDED_UPPER_TRANSITION_RADIAL_V001'
MAX_MOVE = .003
WINDOW = (.1101, .130, .170, .195)


def select_region(source, center, axis):
    if not all(math.isfinite(x) for x in (*center, *axis)) or abs(axis.length-1) > 1e-5:
        raise ValueError('INVALID_REGION_FRAME')
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    locked = set().union(*(contour.group_ids(source, name) for name in
                          ('BodySeam', 'SleeveSeam', 'SeamContourMidpoints')))
    mask = source.data.attributes[seam.trim.upper.MASK]
    weights = {}
    for i, point in enumerate(points):
        d = point-center
        z = d.dot(axis)
        r = (d-axis*z).length
        weight = (seam.trim.upper.smoothstep(WINDOW[0], WINDOW[1], z)
                  * (1-seam.trim.upper.smoothstep(WINDOW[2], WINDOW[3], z))
                  * (1-seam.trim.upper.smoothstep(.060, .075, r)))
        if weight > 0 and i not in locked and mask.data[i].value > 0:
            weights[i] = weight
    if not 50 <= len(weights) <= 160:
        raise ValueError('UNEXPECTED_TRANSITION_REGION')
    graph = {i: set() for i in range(len(points))}
    for e in source.data.edges:
        a, b = e.vertices
        graph[a].add(b)
        graph[b].add(a)
    selected = set(weights)
    seen, stack = set(), [min(selected)]
    while stack:
        i = stack.pop()
        if i not in seen:
            seen.add(i)
            stack.extend((graph[i] & selected)-seen)
    if seen != selected:
        raise ValueError('DISCONNECTED_TRANSITION_REGION')
    affected = [p.index for p in source.data.polygons if set(p.vertices) & selected]
    support = {i for p in affected for i in source.data.polygons[p].vertices}
    if any(not (-.40 < points[i].x < -.17 and .91 < points[i].z < 1.14) for i in support):
        raise ValueError('TRANSITION_SUPPORT_OUTSIDE_FOREARM')
    return points, graph, weights, affected, locked


def radial_energy(points, graph, weights, axis):
    values = []
    for i in weights:
        d = sum((points[j] for j in graph[i]), Vector())/len(graph[i])-points[i]
        d -= axis*d.dot(axis)
        values.append(d.length_squared)
    return math.sqrt(sum(values)/len(values))


def relax(source, center, axis, trim_normal, max_move=MAX_MOVE):
    if not 0 < max_move <= MAX_MOVE:
        raise ValueError('UNSAFE_TRANSITION_MOVE')
    if not all(math.isfinite(x) for x in trim_normal) or abs(trim_normal.length-1) > 1e-5:
        raise ValueError('INVALID_TRIM_NORMAL')
    points, graph, weights, affected, locked = select_region(source, center, axis)
    signature = surface.repair.invariant_signature(source)
    # Protect thin source triangles locally instead of letting one sliver shrink
    # the entire proposal. Use actual loop triangles, including clipped n-gons.
    source.data.calc_loop_triangles()
    local_caps = {i: max_move*weight for i, weight in weights.items()}
    for triangle in source.data.loop_triangles:
        ids = list(triangle.vertices)
        q = [points[i] for i in ids]
        altitude = (q[1]-q[0]).cross(q[2]-q[0]).length/max(
            (b-a).length for a, b in zip(q, q[1:]+q[:1]))
        for i in set(ids) & set(weights):
            local_caps[i] = min(local_caps[i], .10*altitude)
    target = [p.copy() for p in points]
    # A fixed eight-step Jacobi proposal; no generation/score retry loop.
    for _ in range(8):
        updated = [p.copy() for p in target]
        for i, weight in weights.items():
            laplacian = sum((target[j] for j in graph[i]), Vector())/len(graph[i])-target[i]
            laplacian -= axis*laplacian.dot(axis)
            delta = target[i]+laplacian*(.35*weight)-points[i]
            # Reproject the TOTAL displacement to avoid accumulated float drift.
            delta -= axis*delta.dot(axis)
            bound = local_caps[i]
            if delta.length > bound:
                delta *= bound/delta.length
            updated[i] = points[i]+delta
        target = updated
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    inverse = obj.matrix_world.inverted()
    attempts = []
    try:
        # Geometric line search only: fixed limits, finite attempts, no QA relaxation.
        for exponent in range(7):
            scale = .5**exponent
            for i in weights:
                obj.data.vertices[i].co = inverse @ (points[i]+(target[i]-points[i])*scale)
            obj.data.update()
            normal_dot = min(obj.data.polygons[i].normal.dot(source.data.polygons[i].normal) for i in affected)
            ratios = [obj.data.polygons[i].area/source.data.polygons[i].area for i in affected]
            attempts.append(dict(scale=scale, minimumNormalDot=normal_dot, areaRatioRange=[min(ratios), max(ratios)]))
            if normal_dot >= .90 and min(ratios) >= .5 and max(ratios) <= 1.5:
                break
        else:
            raise ValueError('TRANSITION_DISTORTION_REJECTED')
        actual = [obj.matrix_world @ v.co for v in obj.data.vertices]
        moved = [i for i in weights if (actual[i]-points[i]).length > 1e-8]
        max_actual = max((actual[i]-points[i]).length for i in moved)
        if max_actual < .0001:
            raise ValueError('NEGLIGIBLE_GEOMETRY_CHANGE')
        if any((actual[i]-points[i]).length > local_caps[i]+1e-7
               or abs((actual[i]-points[i]).dot(axis)) > 1e-7 for i in weights):
            raise ValueError('STORED_MOVE_BOUND_EXCEEDED')
        if any(actual[i] != points[i] for i in range(len(points)) if i not in weights):
            raise ValueError('OUTSIDE_REGION_CHANGED')
        if signature != surface.repair.invariant_signature(obj):
            raise ValueError('TOPOLOGY_UV_GROUP_OR_SHADING_CHANGED')
        # Maintain the existing plane-based trim after geometry moves; mask stays fixed.
        distance = obj.data.attributes[seam.trim.DISTANCE]
        for i in weights:
            distance.data[i].value += (actual[i]-points[i]).dot(trim_normal)
        unaffected = set(range(len(source.data.polygons)))-set(affected)
        errors = sum(obj.data.polygons[i].normal.dot(source.data.polygons[i].normal) < .999 for i in unaffected)
        before_energy = radial_energy(points, graph, weights, axis)
        after_energy = radial_energy(actual, graph, weights, axis)
        if after_energy >= before_energy:
            raise ValueError('RADIAL_ROUGHNESS_NOT_REDUCED')
        c.base.mark(obj)
        return obj, dict(selectedVertices=len(weights), movedVertices=len(moved), vertexIndices=moved,
                         affectedPolygons=len(affected), affectedPolygonIndices=affected,
                         boundsWorld=[[min(actual[i][k] for i in weights), max(actual[i][k] for i in weights)] for k in range(3)],
                         axialWindowMeters=list(WINDOW), maxMoveMeters=max_actual, maxAllowedMoveMeters=max_move,
                         lockedSeamVertexCount=len(locked), topologyUVGroupsMaterialsShadingPreserved=True,
                         maskValuesPreserved=True, trimDistanceUpdatedForMovedVertices=True,
                         positionsOutsideRegionExactlyPreserved=True,
                         maxAxialDriftMeters=max(abs((actual[i]-points[i]).dot(axis)) for i in weights),
                         perVertexMoveCapsMeters=local_caps, localTriangleAltitudeFraction=.10,
                         lineSearch=attempts, radialLaplacianRmsBeforeMeters=before_energy,
                         radialLaplacianRmsAfterMeters=after_energy, metricIsNotVisualQualityScore=True,
                         retainedNormalMismatches=errors, copiedUVErrors=0)
    except Exception:
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        raise


def clay_comparison(output, before, after, center, axis):
    """Same camera, lighting, flat/smooth flags and neutral material on both copies."""
    scene = bpy.context.scene
    camera = scene.camera
    target = center+axis*.14
    for obj in scene.objects:
        if obj.type in ('MESH', 'CURVE', 'LIGHT'):
            obj.hide_render = True
    lights = []
    for delta, energy in [((-.4, -.5, .6), 65), ((.3, .4, .3), 40)]:
        data = bpy.data.lights.new('TransitionClay', 'AREA')
        data.energy, data.size = energy, .4
        light = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(light)
        light.location = target+Vector(delta)
        light.rotation_euler = (target-light.location).to_track_quat('-Z', 'Y').to_euler()
        lights.append(light)
    camera.data.type, camera.data.ortho_scale = 'ORTHO', .28
    camera.location = target+Vector((-.7, .05, .1))
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
    mat = c.base.material('TransitionClay_neutral_NOT_FINAL', (.22, .22, .22))
    mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .75
    rows = []
    for label, source in [('before', before), ('after', after)]:
        obj = source.copy()
        obj.data = source.data.copy()
        scene.collection.objects.link(obj)
        obj.hide_render = False
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
        path = output/('clay_'+label+'_side.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        rows.append(dict(file=path.name, sha256=c.base.sha(path)))
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    for light in lights:
        light.hide_render = True
    return rows


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    signatures = {o.name: surface.repair.invariant_signature(o) for o in originals}
    body = bpy.data.objects[contour.RESULT_OBJECT]
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center = hand.matrix_world @ Vector()
    axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    _, normal, _ = seam.trim.trim_plane(bpy.data.objects[surface.RESULT_OBJECT],
        bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
        bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], axis)
    obj, operation = relax(body, center, axis, normal)
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa = seam.assess(obj, parts, operation)
    if not qa['eligible']:
        raise ValueError('TRANSITION_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        renders = seam.trim.upper.render(output, body, obj, parts, center, axis)
        renders += clay_comparison(output, body, obj, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != signatures[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_UpperTransition_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    report = dict(strategyId=STRATEGY, status='BOUNDED_TRANSITION_GEOMETRY_STUDY_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  operation=operation, qa=qa, originalsPreserved=True, defaultVisibleMeshObjects=visible,
                  fullCharacterScore=None, rigBound=False, attachmentApproved=False,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['LOCKED_SEAM_LIMITS_FOLD_REMOVAL', 'NOT_REFERENCE_EXACT_OR_FULL_CHARACTER_PASS',
                               'STATIC_BVH_NOT_SWEPT_MOTION_OR_SOLID_VALIDITY', 'NO_RIG_FINAL_ATLAS_OR_UNITY_APPROVAL'])
    (output/'upper-transition-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--art-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--no-render', action='store_true')
    result = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: result[k] for k in ('status', 'blendSha256', 'operation')}, indent=2))
