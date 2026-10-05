"""UV audit and rejected face-chart experiment; use bounded albedo bake instead."""
from collections import defaultdict
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_ch101_upper_patch as patch

seam, surface, c = patch.seam, patch.surface, patch.c
SOURCE_SHA = '9d55a8f2e470c5a844e09e78eab6cda4d36afdaa28c7f8fd86632e6f0ddc22d1'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_PatchUV_NOT_PRODUCTION'
STRATEGY = 'CH101_FACE_CORNER_UV_CHART_TRANSFER_V001'


def edge_faces(obj):
    edges = defaultdict(list)
    for p in obj.data.polygons:
        ids = list(p.vertices)
        for a, b in zip(ids, ids[1:]+ids[:1]):
            edges[tuple(sorted((a, b)))].append(p.index)
    return edges


def corner_uv(obj, face, vertex, name='UVMap'):
    p = obj.data.polygons[face]
    loop = next(l for i, l in zip(p.vertices, p.loop_indices) if i == vertex)
    return obj.data.uv_layers[name].data[loop].uv.copy()


def chart_data(source, operation):
    removed = set(operation['removedSourcePolygons'])
    graph = {i: set() for i in removed}
    edges = edge_faces(source)
    for (a, b), faces in edges.items():
        if len(faces) != 2 or not set(faces) <= removed:
            continue
        p, q = faces
        if (source.data.polygons[p].material_index == source.data.polygons[q].material_index
                and all((corner_uv(source, p, i)-corner_uv(source, q, i)).length < 1e-6 for i in (a, b))):
            graph[p].add(q)
            graph[q].add(p)
    labels, groups, left = {}, [], set(graph)
    while left:
        seen, stack = set(), [min(left)]
        while stack:
            i = stack.pop()
            if i not in seen:
                seen.add(i)
                stack.extend(graph[i]-seen)
        for i in seen:
            labels[i] = len(groups)
        groups.append(sorted(seen))
        left -= seen
    return labels, groups, edges


def audit(source, target, operation):
    labels, groups, edges = chart_data(source, operation)
    removed = set(operation['removedSourcePolygons'])
    remap = {int(k): v for k, v in operation['retainedVertexMap'].items()}
    new_edges = edge_faces(target)
    discontinuities, original_seams, continuous = [], 0, 0
    for (a, b), faces in edges.items():
        if len(faces) != 2 or sum(i in removed for i in faces) != 1:
            continue
        original = max((corner_uv(source, faces[0], i)-corner_uv(source, faces[1], i)).length for i in (a, b))
        new_faces = new_edges[tuple(sorted((remap[a], remap[b]))) ]
        if len(new_faces) != 2:
            raise ValueError('PATCH_BOUNDARY_NOT_SHARED')
        error = max((corner_uv(target, new_faces[0], remap[i])-corner_uv(target, new_faces[1], remap[i])).length for i in (a, b))
        if original < 1e-6:
            continuous += 1
            if error > 1e-6:
                discontinuities.append(dict(sourceEdge=[a, b], error=error))
        else:
            original_seams += 1
    mixed = 0
    for p in target.data.polygons[operation['retainedPolygonCount']:]:
        if len({labels[operation['projectionSamples'][str(i)]['sourcePolygon']] for i in p.vertices}) > 1:
            mixed += 1
    return dict(sourceChartCount=len(groups), sourceChartFaceCounts=[len(g) for g in groups],
                originalContinuousBoundaryEdges=continuous, originalSeamBoundaryEdges=original_seams,
                newBoundaryDiscontinuities=discontinuities,
                originalPerVertexMappingMixedChartTriangles=mixed)


def attempt_face_chart_transfer(source, target, operation):
    labels, groups, source_edges = chart_data(source, operation)
    removed = set(operation['removedSourcePolygons'])
    remap = {int(k): v for k, v in operation['retainedVertexMap'].items()}
    inverse = {v: k for k, v in remap.items()}
    first = operation['retainedPolygonCount']
    if len(target.data.polygons)-first != 321 or len(groups) != 7:
        raise ValueError('PATCH_UV_CONTRACT_CHANGED')
    boundaries = {}
    for edge, faces in source_edges.items():
        if len(faces) == 2 and sum(i in removed for i in faces) == 1:
            boundaries[tuple(sorted(remap[v] for v in edge))] = next(i for i in faces if i in removed)
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    source.data.calc_loop_triangles()
    triangles = [t for t in source.data.loop_triangles if t.polygon_index in removed]
    all_tree = BVHTree.FromPolygons(points, [list(t.vertices) for t in triangles], all_triangles=True)
    chart_triangles = [[t for t in triangles if t.polygon_index in group] for group in groups]
    trees = [BVHTree.FromPolygons(points, [list(t.vertices) for t in row], all_triangles=True) for row in chart_triangles]
    edits, provenance = [], []
    for face in target.data.polygons[first:]:
        ids = list(face.vertices)
        boundary_faces = {boundaries[tuple(sorted((a, b)))] for a, b in zip(ids, ids[1:]+ids[:1])
                          if tuple(sorted((a, b))) in boundaries}
        boundary_labels = {labels[i] for i in boundary_faces}
        if len(boundary_labels) > 1:
            raise ValueError('FACE_SPANS_CONFLICTING_BOUNDARY_CHARTS')
        coords = [target.matrix_world @ target.data.vertices[i].co for i in ids]
        if boundary_faces:
            source_face = min(boundary_faces)
        else:
            nearest, _, index, distance = all_tree.find_nearest(sum(coords, Vector())/3)
            if nearest is None or distance > patch.MAX_PROJECTION:
                raise ValueError('FACE_CENTER_OUTSIDE_SOURCE_PATCH')
            source_face = triangles[index].polygon_index
        chart = labels[source_face]
        slot = source.data.polygons[source_face].material_index
        corner_rows = []
        for vertex, loop, point in zip(ids, face.loop_indices, coords):
            exact = [i for i in boundary_faces if inverse.get(vertex) in source.data.polygons[i].vertices]
            if exact:
                uv = corner_uv(source, exact[0], inverse[vertex])
                record = dict(vertex=vertex, sourcePolygon=exact[0], sourceChart=chart, distanceMeters=0., exactBoundary=True)
            else:
                nearest, _, index, distance = trees[chart].find_nearest(point)
                if nearest is None or distance > patch.MAX_PROJECTION:
                    raise ValueError('CORNER_OUTSIDE_SOURCE_CHART:'+json.dumps(dict(face=face.index, vertex=vertex, chart=chart, distance=distance)))
                tri = chart_triangles[chart][index]
                bary = patch.stable_barycentric(nearest, [points[i] for i in tri.vertices])
                uv = Vector(tuple(sum(w*source.data.uv_layers['UVMap'].data[i].uv[k] for w, i in zip(bary, tri.loops)) for k in (0, 1)))
                record = dict(vertex=vertex, sourcePolygon=tri.polygon_index, sourceChart=chart,
                              distanceMeters=distance, exactBoundary=False, barycentric=list(bary))
            edits.append((loop, uv))
            corner_rows.append(record)
        provenance.append(dict(face=face.index, sourceChart=chart, materialSlot=slot, corners=corner_rows))
    obj = target.copy()
    obj.data = target.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    for loop, coordinate in edits:
        obj.data.uv_layers['UVMap'].data[loop].uv = coordinate
    for row in provenance:
        obj.data.polygons[row['face']].material_index = row['materialSlot']
    c.base.mark(obj)
    return obj, dict(before=audit(source, target, operation), after=audit(source, obj, operation),
                     faceCornerProvenance=provenance, mappedMixedChartTriangles=0,
                     maxCornerProjectionMeters=max(c['distanceMeters'] for r in provenance for c in r['corners']))
