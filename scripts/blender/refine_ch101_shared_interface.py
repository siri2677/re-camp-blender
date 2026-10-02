"""Coordinated radial field across BOTH shared sleeve rims on a preserved copy.

This is not another locked-rim Laplacian pass. Two locked outer sections define
a ruled target envelope; one continuous radial field moves the patch, shared
rims, bridge and inner sleeve together. Connectivity and baked face UVs stay
exact. Static study only; no claim of tailoring, rig or exhaustive solid QA.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bake_ch101_patch_albedo as bake

seam, surface, c = bake.seam, bake.surface, bake.c
contour = bake.patch.contour
SOURCE_SHA = '84d73be3ada9f946a930c5dd96b7a228fde36fabad7e5320f2597b49e15490e9'
STRATEGY = 'CH101_COORDINATED_SHARED_INTERFACE_FIELD_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_SharedInterface_NOT_PRODUCTION'
LOW, HIGH = .065, .160
STRENGTH, MAX_MOVE = .25, .003


def frame(hand):
    center = hand.matrix_world @ Vector()
    axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    u = hand.matrix_world.to_3x3() @ Vector((1, 0, 0))
    axis, u, _ = seam.join.frame(axis, u)
    return center, axis, u


def outer_radius(tree, center, axis, height, direction):
    """Outer-most hit from outside this inspected forearm, not another limb."""
    hit, _, _, _ = tree.ray_cast(center + axis*height + direction*.09, -direction, .09)
    if hit is None:
        raise ValueError('INTERFACE_RADIAL_RAY_MISSED')
    radius = (hit-center-axis*height).dot(direction)
    if not .015 < radius < .075 or not (-.40 < hit.x < -.17 and .90 < hit.z < 1.14):
        raise ValueError('INTERFACE_HIT_OUTSIDE_FOREARM')
    return radius


def envelope_metrics(obj, center, axis, u):
    tree, _, _ = c.fit.bvh(obj)
    v = axis.cross(u)
    rows = []
    for k in range(32):
        direction = u*math.cos(2*math.pi*k/32) + v*math.sin(2*math.pi*k/32)
        radii = [outer_radius(tree, center, axis, z, direction) for z in (.083, .098, .110, .130)]
        slopes = [(b-a)/(zb-za) for a, b, za, zb in zip(radii, radii[1:], (.083,.098,.110), (.098,.110,.130))]
        rows.append(dict(angleIndex=k, radiiMeters=radii, slopeJumps=[slopes[1]-slopes[0], slopes[2]-slopes[1]]))
    jumps = [j for row in rows for j in row['slopeJumps']]
    return dict(sampleAngles=32, sectionHeightsMeters=[.083,.098,.110,.130], rows=rows,
                radialSlopeJumpRms=math.sqrt(sum(j*j for j in jumps)/len(jumps)),
                metricIsNotVisualQualityScore=True)


def atlas_signature(obj):
    material = obj.data.materials[-1]
    texture = material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].links[0].from_node
    if texture.type != 'TEX_IMAGE' or texture.inputs['Vector'].links[0].from_node.uv_map != bake.ATLAS_UV:
        raise ValueError('ISOLATED_PATCH_ATLAS_NOT_ACTIVE')
    if texture.image.packed_file is None:
        raise ValueError('PATCH_ATLAS_NOT_PACKED')
    return hashlib.sha256(bytes(texture.image.packed_file.data)).hexdigest()


def fields(obj):
    return {name: [d.value for d in obj.data.attributes[name].data]
            for name in (seam.trim.upper.MASK, seam.trim.DISTANCE)}


def verify_preservation(source, obj, selected):
    if surface.repair.invariant_signature(source) != surface.repair.invariant_signature(obj):
        raise ValueError('INTERFACE_CHANGED_TOPOLOGY_UV_MATERIAL_GROUPS')
    if fields(source) != fields(obj):
        raise ValueError('INTERFACE_CHANGED_MASK_OR_TRIM_FIELDS')
    if atlas_signature(source) != atlas_signature(obj):
        raise ValueError('INTERFACE_CHANGED_PACKED_ATLAS')
    if any(v.co != obj.data.vertices[v.index].co for v in source.data.vertices if v.index not in selected):
        raise ValueError('INTERFACE_CHANGED_LOCKED_VERTEX')


def refine(source, center, axis, u, strength=STRENGTH, max_move=MAX_MOVE):
    if not 0 < strength <= STRENGTH or not 0 < max_move <= MAX_MOVE:
        raise ValueError('UNSAFE_INTERFACE_LIMIT')
    if not all(math.isfinite(x) for x in (*center, *axis, *u)) or abs(axis.length-1) > 1e-5 or abs(u.length-1) > 1e-5 or abs(u.dot(axis)) > 1e-5:
        raise ValueError('INVALID_INTERFACE_FRAME')
    tree, points, triangles = c.fit.bvh(source)
    targets, locations = {}, {}
    for i, point in enumerate(points):
        delta = point-center
        z = delta.dot(axis)
        radial = delta-axis*z
        if LOW+1e-6 < z < HIGH-1e-6 and .015 < radial.length < .075 and -.40 < point.x < -.17:
            direction = radial.normalized()
            lower = outer_radius(tree, center, axis, LOW, direction)
            upper = outer_radius(tree, center, axis, HIGH, direction)
            current = outer_radius(tree, center, axis, z, direction)
            target = lower+(upper-lower)*(z-LOW)/(HIGH-LOW)
            weight = seam.trim.upper.smoothstep(LOW, .083, z)*(1-seam.trim.upper.smoothstep(.135, HIGH, z))
            # Same additive radial field for inner/outer surfaces; do not collapse
            # both to the target radius. The axial coordinate remains unchanged.
            targets[i] = direction*(target-current)*weight*strength
            locations[i] = dict(heightMeters=z, radiusMeters=radial.length, envelopeWeight=weight)
    if len(targets) != 320:
        raise ValueError('INTERFACE_SUPPORT_CONTRACT_CHANGED')
    maximum = max(d.length for d in targets.values())
    if not .0001 < maximum <= max_move:
        raise ValueError('INTERFACE_DISPLACEMENT_REJECTED')
    selected = set(targets)
    affected = [p.index for p in source.data.polygons if set(p.vertices) & selected]
    support = {i for f in affected for i in source.data.polygons[f].vertices}
    if any(not (-.40 < points[i].x < -.17 and .90 < points[i].z < 1.14) for i in support):
        raise ValueError('INTERFACE_AFFECTED_SUPPORT_OUTSIDE_FOREARM')
    groups = {name: contour.group_ids(source, name) for name in
              ('SleeveSeam', 'BodySeam', 'SeamContourMidpoints', 'UpperOpening_inner')}
    if any(not ids <= selected for ids in groups.values()):
        raise ValueError('SHARED_INTERFACE_NOT_MOVING_TOGETHER')
    pairs = []
    for i in sorted(groups['SleeveSeam']):
        j = min(groups['UpperOpening_inner'], key=lambda j: (points[i]-points[j]).length)
        pairs.append((i,j))
    if len({j for _,j in pairs}) != 32:
        raise ValueError('INNER_OUTER_PAIRING_AMBIGUOUS')
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    try:
        inverse = obj.matrix_world.inverted()
        for i, delta in targets.items():
            obj.data.vertices[i].co = inverse @ (points[i]+delta)
        obj.data.update()
        actual = [obj.matrix_world @ v.co for v in obj.data.vertices]
        normal_dot = min(obj.data.polygons[i].normal.dot(source.data.polygons[i].normal) for i in affected)
        ratios = [obj.data.polygons[i].area/source.data.polygons[i].area for i in affected]
        if normal_dot < .90 or min(ratios) < .5 or max(ratios) > 1.5:
            raise ValueError('INTERFACE_FACE_DISTORTION_REJECTED')
        moves = [(actual[i]-points[i]).length for i in selected]
        axial = max(abs((actual[i]-points[i]).dot(axis)) for i in selected)
        if max(moves) > max_move+1e-7 or axial > 1e-7:
            raise ValueError('INTERFACE_STORED_MOVE_EXCEEDED')
        before_thickness = [(points[i]-points[j]).length for i,j in pairs]
        after_thickness = [(actual[i]-actual[j]).length for i,j in pairs]
        if min(after_thickness) < .001 or max(abs(a-b) for a,b in zip(before_thickness,after_thickness)) > .00025:
            raise ValueError('INTERFACE_INNER_WALL_DISTORTION')
        verify_preservation(source, obj, selected)
        before_metric, after_metric = envelope_metrics(source, center, axis, u), envelope_metrics(obj, center, axis, u)
        if after_metric['radialSlopeJumpRms'] >= before_metric['radialSlopeJumpRms']:
            raise ValueError('MEASURED_INTERFACE_KINK_NOT_REDUCED')
        c.base.mark(obj)
        obj['coordinatedSharedInterfaceStudy'] = True
        unaffected = set(range(len(source.data.polygons))) - set(affected)
        normal_errors = sum(obj.data.polygons[i].normal.dot(source.data.polygons[i].normal) < .999 for i in unaffected)
        return obj, dict(method='TWO_LOCKED_OUTER_SECTIONS_COORDINATED_RADIAL_FIELD',
                         sectionBoundsMeters=[LOW,HIGH], fieldStrength=strength,
                         movedVertexCount=len(selected), movedVertexIndices=sorted(selected),
                         displacementWorld={i:list(actual[i]-points[i]) for i in sorted(selected)},
                         affectedPolygonIndices=affected, selectedLocalCoordinates=locations,
                         outsideRegionVerticesPreserved=len(points)-len(selected),
                         maxActualMoveMeters=max(moves), maxAllowedMoveMeters=max_move, maxAxialDriftMeters=axial,
                         sharedGroupMovedCounts={name:len(ids) for name,ids in groups.items()},
                         minimumAffectedNormalDot=normal_dot, areaRatioRange=[min(ratios),max(ratios)],
                         sampledRimWallPairCount=32, sampledRimWallBeforeMeters=[min(before_thickness),max(before_thickness)],
                         sampledRimWallAfterMeters=[min(after_thickness),max(after_thickness)],
                         wallCheckIsNotWholeSolidProof=True, topologyUVAtlasWeightsMasksShadingPreserved=True,
                         packedAtlasSha256=atlas_signature(obj), retainedNormalMismatches=normal_errors, copiedUVErrors=0,
                         metricsBefore=before_metric, metricsAfter=after_metric)
    except Exception:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)
        raise


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
    invariants = {o.name:surface.repair.invariant_signature(o) for o in originals}
    body = bpy.data.objects[bake.RESULT_OBJECT]
    original_fields = fields(body)
    center, axis, u = frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj, operation = refine(body, center, axis, u)
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa = seam.assess(obj, parts, operation)
    if not qa['eligible']:
        raise ValueError('INTERFACE_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        renders = seam.trim.upper.render(output, body, obj, parts, center, axis)
        renders += bake.patch.transition.clay_comparison(output, body, obj, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != invariants[o.name] for o in originals) or fields(body) != original_fields:
        raise ValueError('ORIGINAL_CHANGED')
    visible = seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_SharedInterface_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    report = dict(strategyId=STRATEGY, status='COORDINATED_INTERFACE_STATIC_STUDY_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  operation=operation, qa=qa, originalsPreserved=True, fullCharacterScore=None,
                  attachmentApproved=False, rigBound=False, defaultVisibleMeshObjects=visible,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['RULED_ENVELOPE_NOT_REFERENCE_EXACT_CLOTH', 'INHERITED_ATLAS_NOT_REBAKED_CONNECTIVITY_UNCHANGED',
                               'MASK_CONTEXT_SHOWS_PREVIOUS_MATERIAL_MASK_NOT_EDIT_SUPPORT',
                               'STATIC_BVH_EXCLUDES_SHARED_VERTEX_PAIRS', 'NO_SWEPT_MOTION_SOLID_OR_RIG_PROOF',
                               'WHOLE_CHARACTER_UNFINISHED_NO_HUMAN_GATE_B'])
    (output/'shared-interface-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text(
        'CH101 coordinated shared-interface study — NOT PRODUCTION\n'
        'A new copy moves the upper patch, both shared rims and lower sleeve together; wrist and distant body stay fixed.\n'
        'Topology, face order, UVs, packed albedo, masks, trim fields and groups/weights remain unchanged.\n'
        'No new AI inference, no score, no rig/Unity/Gate B approval. See report and matched texture/clay renders.\n'
        'mask_context.png shows the inherited material mask, NOT the geometric edit region.\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    result = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:result[k] for k in ('status','blendSha256','qa')},indent=2))
