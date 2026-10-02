"""Replace one audited forearm annulus on a copy; retain both real boundary loops."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relax_ch101_upper_transition as transition

contour, seam, surface, c = transition.contour, transition.seam, transition.surface, transition.c
SOURCE_SHA = transition.SOURCE_SHA
STRATEGY = 'CH101_UPPER_PATCH_RETOPOLOGY_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_UpperPatch_NOT_PRODUCTION'
MAX_PROJECTION = .012


def stable_barycentric(point, triangle):
    """Double-precision dominant-plane solve; check, then remove tiny roundoff."""
    q = tuple(point)
    coords = [tuple(p) for p in triangle]
    for i, vertex in enumerate(coords):
        if q == vertex:
            return tuple(float(j == i) for j in range(3))
    a, b, d = coords
    v = tuple(b[k]-a[k] for k in range(3))
    w = tuple(d[k]-a[k] for k in range(3))
    cross = (v[1]*w[2]-v[2]*w[1], v[2]*w[0]-v[0]*w[2], v[0]*w[1]-v[1]*w[0])
    excluded = max(range(3), key=lambda k: abs(cross[k]))
    x, y = [k for k in range(3) if k != excluded]
    denominator = v[x]*w[y]-v[y]*w[x]
    if abs(denominator) < 1e-20:
        raise ValueError('DEGENERATE_TRANSFER_TRIANGLE')
    dx, dy = q[x]-a[x], q[y]-a[y]
    beta = (dx*w[y]-dy*w[x])/denominator
    gamma = (v[x]*dy-v[y]*dx)/denominator
    weights = (1-beta-gamma, beta, gamma)
    if not all(math.isfinite(z) for z in weights) or min(weights) < -1e-5 or max(weights) > 1.00001:
        raise ValueError('PATCH_BARYCENTRIC_EXTRAPOLATION')
    weights = tuple(max(0., min(1., z)) for z in weights)
    total = sum(weights)
    weights = tuple(z/total for z in weights)
    reconstruction = tuple(sum(weight*p[k] for weight, p in zip(weights, coords)) for k in range(3))
    if math.dist(reconstruction, q) > 2e-6:
        raise ValueError('PATCH_PROJECTION_TRIANGLE_MISMATCH')
    return weights


def find_patch(source, center, axis, u):
    if abs(axis.length-1) > 1e-5 or not all(math.isfinite(x) for x in (*center, *axis, *u)):
        raise ValueError('INVALID_PATCH_FRAME')
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    selected = []
    for p in source.data.polygons:
        q = sum((points[i] for i in p.vertices), Vector())/len(p.vertices)
        d = q-center
        height = d.dot(axis)
        radius = (d-axis*height).length
        if (.11001 < height < .195 and radius < .075
                and all((points[i]-center).dot(axis) > .10999 for i in p.vertices)):
            selected.append(p.index)
    if len(selected) != 221:
        raise ValueError('PATCH_FACE_CONTRACT_CHANGED')
    edges = Counter(tuple(sorted((a, b))) for i in selected
                    for a, b in zip(list(source.data.polygons[i].vertices),
                                    list(source.data.polygons[i].vertices)[1:]+list(source.data.polygons[i].vertices)[:1]))
    if any(n not in (1, 2) for n in edges.values()):
        raise ValueError('PATCH_NONMANIFOLD')
    graph = defaultdict(set)
    for (a, b), count in edges.items():
        if count == 1:
            graph[a].add(b)
            graph[b].add(a)
    if not graph or any(len(n) != 2 for n in graph.values()):
        raise ValueError('PATCH_BOUNDARIES_NOT_CYCLES')
    left = set(graph)
    loops = []
    while left:
        start = min(left)
        ids = [start]
        previous, current = start, min(graph[start])
        while current != start:
            if current in ids:
                raise ValueError('PATCH_BOUNDARY_REPEATS')
            ids.append(current)
            previous, current = current, next(i for i in graph[current] if i != previous)
        left.difference_update(ids)
        loops.append(ids)
    vertices = {i for edge in edges for i in edge}
    adjacency = defaultdict(set)
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    visited, stack = set(), [min(vertices)]
    while stack:
        i = stack.pop()
        if i not in visited:
            visited.add(i)
            stack.extend(adjacency[i]-visited)
    if len(loops) != 2 or visited != vertices or len(vertices)-len(edges)+len(selected) != 0:
        raise ValueError('PATCH_NOT_SINGLE_ANNULUS')
    body_rim = contour.group_ids(source, 'BodySeam')
    matching = [r for r in loops if set(r) == body_rim]
    if len(matching) != 1:
        raise ValueError('LOWER_PATCH_BOUNDARY_NOT_BODY_SEAM')
    lower = matching[0]
    upper = next(r for r in loops if set(r) != body_rim)
    if len(upper) != 24 or any(not .175 < (points[i]-center).dot(axis) < .220 for i in upper):
        raise ValueError('UPPER_PATCH_BOUNDARY_CHANGED')
    if any(not (-.40 < points[i].x < -.17 and .91 < points[i].z < 1.14) for i in vertices):
        raise ValueError('PATCH_OUTSIDE_INSPECTED_FOREARM')
    return points, selected, seam.ring(points, lower, center, axis, u), seam.ring(points, upper, center, axis, u)


def sample_ring(points, ring, t):
    ids, params = ring['vertices'], ring['parameters']+[1.]
    for k in range(len(ids)):
        if params[k] <= t < params[k+1]:
            return points[ids[k]].lerp(points[ids[(k+1) % len(ids)]], (t-params[k])/(params[k+1]-params[k]))
    raise ValueError('RING_PARAMETER_OUT_OF_RANGE')


def build(source, center, axis, u, trim_normal, max_projection=MAX_PROJECTION):
    if not 0 < max_projection <= MAX_PROJECTION:
        raise ValueError('UNSAFE_PROJECTION_LIMIT')
    if not all(math.isfinite(x) for x in trim_normal) or abs(trim_normal.length-1) > 1e-5:
        raise ValueError('INVALID_TRIM_NORMAL')
    points, removed, lower, upper = find_patch(source, center, axis, u)
    removed = set(removed)
    mesh = source.data
    retained = [p for p in mesh.polygons if p.index not in removed]
    kept = sorted({i for p in retained for i in p.vertices})
    remap = {old: new for new, old in enumerate(kept)}
    new_points = [points[i].copy() for i in kept]
    rings = [dict(vertices=[remap[i] for i in lower['vertices']], parameters=lower['parameters'])]
    # Uniform rings remove the sliver-constrained interior. Boundary positions stay exact.
    for blend in (.2, .4, .6, .8):
        ids = []
        for j in range(32):
            t = j/32
            q = sample_ring(points, lower, t).lerp(sample_ring(points, upper, t), blend)
            ids.append(len(new_points))
            new_points.append(q)
        rings.append(dict(vertices=ids, parameters=[j/32 for j in range(32)]))
    rings.append(dict(vertices=[remap[i] for i in upper['vertices']], parameters=upper['parameters']))
    patch_faces = []
    for a, b in zip(rings, rings[1:]):
        patch_faces.extend(seam.join.zipper(a, b))
    mesh.calc_loop_triangles()
    source_triangles = [t for t in mesh.loop_triangles if t.polygon_index in removed]
    tree = BVHTree.FromPolygons(points, [list(t.vertices) for t in source_triangles], all_triangles=True)
    source_caps = []
    for i in range(len(kept), len(new_points)):
        nearest, _, _, distance = tree.find_nearest(new_points[i])
        if nearest is None:
            raise ValueError('PATCH_SOURCE_NOT_FOUND')
        if distance > .006:
            new_points[i] = nearest+(new_points[i]-nearest)*(.006/distance)
            source_caps.append(dict(vertex=i, uncappedDistanceMeters=distance, capMeters=.006))
    names = [layer.name for layer in mesh.uv_layers]
    mask_name, distance_name = seam.trim.upper.MASK, seam.trim.DISTANCE
    samples = {}
    def project(point):
        location, _, index, distance = tree.find_nearest(point)
        if location is None or distance > max_projection:
            raise ValueError('PATCH_PROJECTION_OUTSIDE_BOUNDED_SOURCE:'+str(distance))
        triangle = source_triangles[index]
        coords = [points[i] for i in triangle.vertices]
        bary = stable_barycentric(location, coords)
        return triangle, bary, distance
    used_patch = {i for face in patch_faces for i in face}
    for i in sorted(used_patch):
        triangle, bary, distance = project(new_points[i])
        samples[i] = dict(sourceTriangleVertices=list(triangle.vertices), sourcePolygon=triangle.polygon_index,
                          barycentric=list(bary), distanceMeters=distance,
                          uv={name: [sum(w*mesh.uv_layers[name].data[loop].uv[k] for w, loop in zip(bary, triangle.loops))
                                     for k in (0, 1)] for name in names},
                          mask=sum(w*mesh.attributes[mask_name].data[v].value for w, v in zip(bary, triangle.vertices)),
                          projectedTrim=sum(w*mesh.attributes[distance_name].data[v].value for w, v in zip(bary, triangle.vertices)))
    faces = [[remap[i] for i in p.vertices] for p in retained]+patch_faces
    slots = [p.material_index for p in retained]
    for face in patch_faces:
        triangle, _, _ = project(sum((new_points[i] for i in face), Vector())/3)
        slots.append(mesh.polygons[triangle.polygon_index].material_index)
    data = bpy.data.meshes.new('Bounded_upper_patch_shared_boundaries')
    data.from_pydata(new_points, [], faces)
    data.update()
    for material in mesh.materials:
        data.materials.append(material)
    for p, slot in zip(data.polygons, slots):
        p.material_index = slot
        p.use_smooth = retained[p.index].use_smooth if p.index < len(retained) else True
    for name in names:
        layer = data.uv_layers.new(name=name)
        for p in data.polygons:
            if p.index < len(retained):
                values = [mesh.uv_layers[name].data[l].uv for l in retained[p.index].loop_indices]
            else:
                values = [samples[i]['uv'][name] for i in p.vertices]
            for loop, value in zip(p.loop_indices, values):
                layer.data[loop].uv = value
        layer.active_render = mesh.uv_layers[name].active_render
    data.uv_layers.active_index = mesh.uv_layers.active_index
    for name in (mask_name, distance_name):
        field = data.attributes.new(name, 'FLOAT', 'POINT')
        for old, new in remap.items():
            field.data[new].value = mesh.attributes[name].data[old].value
        for i in range(len(kept), len(new_points)):
            sample = samples[i]
            if name == mask_name:
                value = sample['mask']
            else:
                projected = sum((points[v]*w for v, w in zip(sample['sourceTriangleVertices'], sample['barycentric'])), Vector())
                value = sample['projectedTrim']+(new_points[i]-projected).dot(trim_normal)
            field.data[i].value = value
    obj = bpy.data.objects.new(RESULT_OBJECT, data)
    bpy.context.scene.collection.objects.link(obj)
    for group in source.vertex_groups:
        target = obj.vertex_groups.new(name=group.name)
        for vertex in mesh.vertices:
            if vertex.index in remap:
                for membership in vertex.groups:
                    if membership.group == group.index:
                        target.add([remap[vertex.index]], membership.weight, 'REPLACE')
    obj.vertex_groups.new(name='UpperPatchInterior').add(list(range(len(kept), len(new_points))), 1, 'REPLACE')
    c.base.mark(obj)
    obj['bodySleeveSharedBoundary'] = True
    obj['attachmentApproved'] = False
    counts = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, face[1:]+face[:1]))
    boundaries = [(remap[a], remap[b]) for r in (lower, upper)
                  for a, b in zip(r['vertices'], r['vertices'][1:]+r['vertices'][:1])]
    if any(counts[tuple(sorted(e))] != 2 for e in boundaries):
        raise ValueError('NEW_PATCH_NOT_SHARING_BOUNDARIES')
    errors = sum(data.polygons[j].normal.dot(mesh.polygons[p.index].normal) < .999 for j, p in enumerate(retained))
    uv_errors = sum((data.uv_layers[name].data[a].uv-mesh.uv_layers[name].data[b].uv).length > 1e-7
                    for name in names for p, old in zip(data.polygons, retained) for a, b in zip(p.loop_indices, old.loop_indices))
    return obj, dict(removedSourcePolygons=sorted(removed), removedOnCopyOnly=True,
                     sourcePolygonCountRemoved=len(removed), retainedPolygonCount=len(retained),
                     removedOrphanVerticesOnCopy=len(points)-len(kept), newInteriorVertices=128,
                     newPatchTriangles=len(patch_faces), lowerBoundaryVertices=len(lower['vertices']),
                     upperBoundaryVertices=len(upper['vertices']), sharedBoundaryEdges=len(boundaries),
                     lowerBoundarySourceIndices=lower['vertices'], upperBoundarySourceIndices=upper['vertices'],
                     retainedVertexMap=remap, retainedFaceMapping=[p.index for p in retained],
                     retainedNormalMismatches=errors, copiedUVErrors=uv_errors,
                     projectionSource='ONLY_REMOVED_FOREARM_PATCH_TRIANGLES', maxProjectionLimitMeters=max_projection,
                     sourceDeviationCaps=source_caps,
                     maxProjectionDistanceMeters=max(s['distanceMeters'] for s in samples.values()),
                     projectionSamples=samples, keptPositionsExactlyPreserved=all(data.vertices[new].co == points[old] for old, new in remap.items()),
                     copiedBoundaryGroupWeights=True, newInteriorRigWeightsCreated=False,
                     shapeHypothesis='RULED_SURFACE_BETWEEN_LOCKED_SOURCE_BOUNDARIES_NOT_FINAL_TAILORING')


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
    u = hand.matrix_world.to_3x3() @ Vector((1, 0, 0))
    _, normal, _ = seam.trim.trim_plane(bpy.data.objects[surface.RESULT_OBJECT],
        bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
        bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], axis)
    obj, operation = build(body, center, axis, u, normal)
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa = seam.assess(obj, parts, operation)
    if not qa['eligible'] or not operation['keptPositionsExactlyPreserved']:
        raise ValueError('PATCH_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        renders = seam.trim.upper.render(output, body, obj, parts, center, axis)
        renders += transition.clay_comparison(output, body, obj, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != signatures[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_UpperPatch_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    report = dict(strategyId=STRATEGY, status='UPPER_PATCH_STATIC_STUDY_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  operation=operation, qa=qa, originalsPreserved=True, defaultVisibleMeshObjects=visible,
                  fullCharacterScore=None, rigBound=False, attachmentApproved=False,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['LOCKED_BOUNDARY_KINKS_REMAIN_POSSIBLE', 'PROJECTION_UV_NOT_FINAL_ATLAS',
                               'RULED_PATCH_NOT_AUTHORED_CLOTH_FOLDS', 'NO_SKINNING_OR_HUMAN_GATE_B'])
    (output/'upper-patch-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--art-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--no-render', action='store_true')
    r = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: r[k] for k in ('status', 'blendSha256', 'qa')}, indent=2))
