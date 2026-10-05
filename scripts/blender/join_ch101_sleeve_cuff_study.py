"""Bridge explicit authored sleeve/cuff rims on a new mesh, preserving sources."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ch101_sleeve_end_study as sleeve

c = sleeve.c
STRATEGY = 'CH101_AUTHORED_SLEEVE_CUFF_TRANSITION_V001'
# Decimation leaves micrometre-scale plane drift. No vertex is snapped or moved.
TOLERANCE = 1e-5


def frame(axis, u):
    axis = Vector(axis).normalized()
    u = Vector(u) - axis * Vector(u).dot(axis)
    u.normalize()
    if axis.length < .9 or u.length < .9:
        raise ValueError('INVALID_TRANSITION_FRAME')
    return axis, u, axis.cross(u)


def open_rim(obj, center, axis, u, height):
    """Select a planar annular cap; require exactly two simple boundary cycles."""
    axis, u, v = frame(axis, u)
    center = Vector(center)
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    cap = [p.index for p in obj.data.polygons
           if all(abs((points[i] - center).dot(axis) - height) < TOLERANCE
                  for i in p.vertices)]
    if not cap:
        raise ValueError('EXPLICIT_CAP_NOT_FOUND:' + obj.name)
    edges = Counter()
    for index in cap:
        ids = list(obj.data.polygons[index].vertices)
        edges.update(tuple(sorted((a, b))) for a, b in zip(ids, ids[1:] + ids[:1]))
    cap_vertices = {i for edge in edges for i in edge}
    graph = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    reached, stack = set(), [min(cap_vertices)]
    while stack:
        node = stack.pop()
        if node not in reached:
            reached.add(node)
            stack.extend(graph[node]-reached)
    if len(reached) != len(cap_vertices) or len(cap_vertices)-len(edges)+len(cap) != 0:
        raise ValueError('CAP_NOT_ONE_CONNECTED_ANNULUS')
    neighbors = defaultdict(set)
    for (a, b), count in edges.items():
        if count == 1:
            neighbors[a].add(b)
            neighbors[b].add(a)
        elif count != 2:
            raise ValueError('CAP_NONMANIFOLD')
    if not neighbors or any(len(n) != 2 for n in neighbors.values()):
        raise ValueError('CAP_BOUNDARY_NOT_CYCLES')
    unseen = set(neighbors)
    rings = []
    while unseen:
        start = min(unseen)
        ids = [start]
        previous, current = start, min(neighbors[start])
        while current != start:
            if current in ids:
                raise ValueError('BOUNDARY_CYCLE_REPEATS')
            ids.append(current)
            previous, current = current, next(i for i in neighbors[current] if i != previous)
        unseen.difference_update(ids)
        def angle(i):
            delta = points[i] - center
            return math.atan2(delta.dot(v), delta.dot(u)) % (2 * math.pi)
        area = sum((points[a]-center).dot(u)*(points[b]-center).dot(v)
                       - (points[b]-center).dot(u)*(points[a]-center).dot(v)
                       for a, b in zip(ids, ids[1:] + ids[:1])) / 2
        if abs(area) < 1e-10:
            raise ValueError('DEGENERATE_RING')
        if area < 0:
            ids.reverse()
        anchor = min(range(len(ids)), key=lambda i: min(angle(ids[i]), 2*math.pi-angle(ids[i])))
        ids = ids[anchor:] + ids[:anchor]
        lengths = [(points[b]-points[a]).length for a, b in zip(ids, ids[1:]+ids[:1])]
        if min(lengths) < 1e-8:
            raise ValueError('ZERO_LENGTH_BOUNDARY_EDGE')
        perimeter = sum(lengths)
        parameters = [0.0]
        for length in lengths[:-1]:
            parameters.append(parameters[-1]+length/perimeter)
        rings.append(dict(vertices=ids, parameters=parameters, areaMeters2=abs(area),
                          perimeterMeters=perimeter, anchorAngleRadians=angle(ids[0])))
    if len(rings) != 2:
        raise ValueError('EXPECTED_INNER_AND_OUTER_RING')
    rings.sort(key=lambda r: r['areaMeters2'], reverse=True)
    return dict(object=obj.name, heightMeters=height, planeToleranceMeters=TOLERANCE,
                maxCapPlaneErrorMeters=max(abs((points[i]-center).dot(axis)-height) for i in cap_vertices),
                removedCapFaces=cap,
                outer=rings[0], inner=rings[1]), points


def zipper(lower, upper):
    """Sweep boundary arc length from the +u seam, retaining actual edge order."""
    def cycle(ring):
        ids, parameters = ring['vertices'], ring['parameters']
        return ids + [ids[0]], parameters + [1.0]
    a, aa = cycle(lower)
    b, bb = cycle(upper)
    i = j = 0
    faces = []
    while i < len(a)-1 or j < len(b)-1:
        na = aa[i+1] if i < len(a)-1 else math.inf
        nb = bb[j+1] if j < len(b)-1 else math.inf
        if na <= nb:
            faces.append((a[i], a[i+1], b[j]))
            i += 1
        else:
            faces.append((a[i], b[j+1], b[j]))
            j += 1
    return faces


def join_parts(cuff, cloth, center, axis, u, cuff_height=0, sleeve_height=.002):
    axis, u, v = frame(axis, u)
    center = Vector(center)
    if sleeve_height-cuff_height <= 10*TOLERANCE:
        raise ValueError('TRANSITION_PLANES_REVERSED_OR_TOO_CLOSE')
    specs = []
    vertices, faces, slots, uvs, materials = [], [], [], [], []
    expected_normals = []
    for obj, height in ((cuff, cuff_height), (cloth, sleeve_height)):
        spec, points = open_rim(obj, center, axis, u, height)
        offset = len(vertices)
        vertices.extend(points)
        cap = set(spec['removedCapFaces'])
        material_offset = len(materials)
        materials.extend(obj.data.materials)
        uv = obj.data.uv_layers.active
        if uv is None:
            raise ValueError('SOURCE_UV_REQUIRED')
        normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
        for p in obj.data.polygons:
            if p.index in cap:
                continue
            faces.append(tuple(offset+i for i in p.vertices))
            slots.append(material_offset+p.material_index)
            uvs.append([tuple(uv.data[i].uv) for i in p.loop_indices])
            expected_normals.append((normal_matrix @ p.normal).normalized())
        for key in ('outer', 'inner'):
            spec[key]['outputVertices'] = [offset+i for i in spec[key]['vertices']]
        specs.append(spec)
    retained = len(faces)
    bridge_ranges = {}
    for key in ('outer', 'inner'):
        rings = [dict(vertices=s[key]['outputVertices'], parameters=s[key]['parameters']) for s in specs]
        bridge = zipper(*rings)
        if key == 'inner':
            bridge = [tuple(reversed(f)) for f in bridge]
        start = len(faces)
        faces.extend(bridge)
        slots.extend([len(cuff.data.materials)] * len(bridge))
        for face in bridge:
            coords = [(math.atan2((vertices[i]-center).dot(v), (vertices[i]-center).dot(u))
                       % (2*math.pi)/(2*math.pi),
                       ((vertices[i]-center).dot(axis)-cuff_height)/(sleeve_height-cuff_height))
                      for i in face]
            if max(p[0] for p in coords)-min(p[0] for p in coords) > .5:
                coords = [(x+1 if x < .5 else x, y) for x, y in coords]
            uvs.append(coords)
        bridge_ranges[key] = (start, len(faces))
    mesh = bpy.data.meshes.new('Authored_sleeve_cuff_shared_boundary_mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for mat in materials:
        mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name='StudyUV')
    for p, slot, coords in zip(mesh.polygons, slots, uvs):
        p.material_index = slot
        for loop, coordinate in zip(p.loop_indices, coords):
            uv.data[loop].uv = coordinate
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new('CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION', mesh)
    bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj)
    for key in ('designApproved', 'attachmentApproved', 'sourceReplacementAllowed', 'attachedToBody'):
        obj[key] = False
    obj['authoredSleeveCuffJoined'] = True
    for spec, prefix in zip(specs, ('CuffProximal', 'SleeveDistal')):
        for key in ('outer', 'inner'):
            obj.vertex_groups.new(name=prefix+'_'+key).add(spec[key]['outputVertices'], 1, 'REPLACE')
    normal_mismatches = sum(p.normal.dot(n) < .999 for p, n in zip(mesh.polygons[:retained], expected_normals))
    inward = {}
    for key, (start, end) in bridge_ranges.items():
        count = 0
        for p in mesh.polygons[start:end]:
            delta = p.center-center
            radial = delta-axis*delta.dot(axis)
            sign = 1 if key == 'outer' else -1
            if sign*p.normal.dot(radial) <= 0:
                count += 1
        inward[key] = count
    return obj, dict(boundaries=specs, retainedFaces=retained,
                     transitionFaces=len(faces)-retained, transitionFaceRanges=bridge_ranges,
                     retainedNormalMismatches=normal_mismatches, reversedTransitionFaces=inward,
                     sourceVertexPositionsCopiedExactly=True, retainedUVsCopied=True,
                     method='EXPLICIT_PLANAR_CAP_REMOVAL_AND_TOPOLOGICAL_ARCLENGTH_ZIPPER')


def assess(obj, report, hand, equipment):
    audit = c.author.shape_audit(obj)
    euler = len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons)
    self_pairs = c.wrist.self_surface_pairs(obj)
    collisions = [dict(target=o.name, **c.fit.overlap_report(o, [obj], Vector())[0])
                  for o in [hand]+list(equipment)]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    inconsistent = sum(not e.is_contiguous for e in bm.edges)
    signed_volume = bm.calc_volume(signed=True)
    bm.free()
    finite_uv = all(math.isfinite(x) for loop in obj.data.uv_layers.active.data for x in loop.uv)
    reasons = []
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or len(audit['components']) != 1 or euler != 0:
        reasons.append('TOPOLOGY_INVALID')
    if self_pairs:
        reasons.append('SELF_SURFACE_CROSSING')
    if inconsistent or signed_volume <= 0 or report['retainedNormalMismatches'] or any(report['reversedTransitionFaces'].values()):
        reasons.append('NORMAL_ORIENTATION_INVALID')
    if any(row['uniqueEquipmentTrianglesCrossing'] for row in collisions):
        reasons.append('HAND_OR_EQUIPMENT_SURFACE_CROSSING')
    if not finite_uv:
        reasons.append('NONFINITE_UV')
    return dict(eligible=not reasons, rejectionReasons=reasons, topology=audit,
                eulerCharacteristic=euler, selfSurfacePairs=self_pairs,
                inconsistentWindingEdges=inconsistent, signedVolumeCubicMeters=signed_volume,
                finiteUV=finite_uv, studyPartCollisions=collisions)


def render(output, body, joined, center, axis):
    # Reuse the same camera/light setup for a directly comparable six-view study.
    renders = sleeve.render(output, body, None, joined, joined, center, axis)
    for row in renders:
        row['authoredSleeveCuffJoined'] = True
        row['sourceBodyJoined'] = False
    return renders


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != args.source_sha256:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    refs = c.base.verify_references(args.art_root.resolve())
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    for key in ('unityInputAllowed', 'productionPromotionAllowed'):
        if scene.get(key) not in (False, 0):
            raise ValueError('SOURCE_GATE_NOT_FALSE')
    originals = [o for o in scene.objects if o.type == 'MESH']
    before = c.guide.digest(originals)
    cuff = bpy.data.objects['CUFF_REDUCTION_0.5_NOT_PRODUCTION']
    cloth = bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION']
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    body = bpy.data.objects['geometry_0']
    center = hand.matrix_world @ Vector()
    axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    u = hand.matrix_world.to_3x3() @ Vector((1, 0, 0))
    joined, transition = join_parts(cuff, cloth, center, axis, u)
    equipment = [o for o in originals if o.name.startswith('PAIR_STUDY_') and o != hand]
    qa = assess(joined, transition, hand, equipment)
    if not qa['eligible']:
        raise ValueError('TRANSITION_REJECTED:' + json.dumps(qa))
    output.mkdir(parents=True)
    renders = [] if args.no_render else render(output, body, joined, center, axis)
    if c.guide.digest(originals) != before or c.base.sha(source) != args.source_sha256:
        raise ValueError('SOURCE_CHANGED')
    for key, value in c.base.GATES.items():
        scene[key] = value
    scene['authoredSleeveCuffJoined'] = True
    scene['sourceHandReplaced'] = False
    blend = output/'CH101_SleeveCuffTransition_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='AUTHORED_PARTS_JOINED_STATIC_STUDY_NOT_APPROVED',
                  **c.base.GATES, sourceBlendSha256=args.source_sha256,
                  artCommit=c.base.ART_COMMIT, references=refs, transition=transition, qa=qa,
                  sourceBodyOverlap=c.fit.overlap_report(body, [joined], center),
                  sourceGeometryPreserved=True, sourceHandReplaced=False,
                  authoredSleeveCuffJoined=True, anatomicalSeamVerified=False,
                  wristIntegrationAllowed=False, attachmentApproved=False, designApproved=False,
                  fullCharacterScore=None, renders=renders, blendFile=blend.name,
                  blendSha256=c.base.sha(blend),
                  limitations=['ORIGINAL_BODY_INTERSECTIONS_REMAIN', 'UPPER_OPENING_UNATTACHED',
                               'STATIC_SURFACE_TEST_NOT_CONTAINMENT_OR_ANIMATION_PROOF',
                               'STUDY_UV_NOT_FINAL_ATLAS', 'NO_SKINNING_OR_UNITY_IMPORT',
                               'EARLY_CLOTH_SHAPE_NOT_FINAL_DESIGN'])
    (output/'sleeve-cuff-transition-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--art-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-render', action='store_true')
    result = run(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({key: result[key] for key in ('status', 'qa', 'blendSha256')}, indent=2))
