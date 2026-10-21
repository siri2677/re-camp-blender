"""Editable course/fold layout on the existing surface, not a finished garment.

The original render triangles are split at three harmonic courses. This adds
real shared chart edges without inventing straight quads across coarse folds.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
import author_ch101_shoulder_edge_flow as prior
c, surface, panel = prior.c, prior.surface, prior.panel
branch = prior.prior.prior.prior
SOURCE_SHA = '4710695635be734c20d469d8c60f3bb6c94ffae6fb8fe51e9818cb8b86a2da55'
REPORT_SHA = '7b8efeac91bbf493a4fbcc5663e4425767a50ae9db119ccff0526d3618c1caac'
RESULT_OBJECT = 'CH101_ShoulderDeformationLayoutChart_NOT_PRODUCTION'
STRATEGY = 'CH101_SHARED_COURSE_AND_FOLD_LAYOUT_V001'
LEVELS = (.25, .5, .75)
# These policies are a source-specific design hypothesis after reference review.
# None authorizes moving the prior study or interpreting its clipped border as
# a sewing line. The long underarm network is deliberately NOT smoothed here.
FOLD_POLICIES = {
    141: ('DEFER_TORSO_BORDER', 'E9AD46'),
    193: ('REDESIGN_UNDERARM_NETWORK', 'F06464'),
    611: ('DEFER_TORSO_BORDER', 'E9AD46'),
    932: ('DEFER_TORSO_BORDER', 'E9AD46'),
    1874: ('REMOVE_MICRO_CREASE_IN_CAP_REBUILD', '85D05B'),
}
GUIDE_PREFIX = 'DEFORMATION_LAYOUT_'


def edge_groups(edges):
    remaining = {tuple(sorted(e)) for e in edges}
    groups = []
    while remaining:
        group = {min(remaining)}
        vertices = set(next(iter(group)))
        while True:
            new = {e for e in remaining - group if vertices.intersection(e)}
            if not new:
                break
            group.update(new)
            vertices.update(i for e in new for i in e)
        remaining -= group
        groups.append(sorted(group))
    return groups


def ordered_path(edges, cyclic=False):
    adjacency = defaultdict(list)
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    ends = sorted(i for i, neighbors in adjacency.items() if len(neighbors) == 1)
    if cyclic:
        if not adjacency or any(len(ns) != 2 for ns in adjacency.values()):
            raise ValueError('COURSE_NOT_SIMPLE_CYCLE')
        start = min(adjacency)
    else:
        if len(ends) != 2 or any(len(ns) not in (1, 2) for ns in adjacency.values()):
            raise ValueError('BRANCH_NOT_SIMPLE_PATH')
        start = ends[0]
    path, previous, current = [], None, start
    while True:
        path.append(current)
        choices = sorted(i for i in adjacency[current] if i != previous)
        if not choices:
            break
        nxt = choices[0]
        if nxt == start and cyclic:
            break
        if nxt in path:
            raise ValueError('REPEATED_ROUTE_VERTEX')
        previous, current = current, nxt
    if set(path) != set(adjacency):
        raise ValueError('DISCONNECTED_ROUTE')
    return path


def field(source):
    surface.require_locked(source)
    adjacency, _, _, features = prior.prior.topology(source)
    topology = branch.s.prior.prior.boundaries(source)
    if len(topology['components']) != 1 or len(topology['boundaryLoops']) != 2:
        raise ValueError('SOURCE_NOT_ANNULUS')
    # The source hash fixes which border is the preserved arm-entry ring.
    loops = topology['boundaryLoops']
    lower, outer = min(loops, key=len), max(loops, key=len)
    if (len(lower), len(outer)) != (76, 282):
        raise ValueError('SOURCE_BOUNDARY_IDENTITY_CHANGED')
    fixed = {i: 0. for i in lower}
    fixed.update({i: 1. for i in outer})
    unknown = [i for i in range(len(source.data.vertices)) if i not in fixed]
    lookup = {i: j for j, i in enumerate(unknown)}
    matrix = np.zeros((len(unknown), len(unknown)))
    rhs = np.zeros(len(unknown))
    for i in unknown:
        row = lookup[i]
        matrix[row, row] = len(adjacency[i])
        for j in adjacency[i]:
            if j in lookup:
                matrix[row, lookup[j]] -= 1
            else:
                rhs[row] += fixed[j]
    solution = np.linalg.solve(matrix, rhs)
    values = [fixed[i] if i in fixed else float(solution[lookup[i]])
              for i in range(len(source.data.vertices))]
    residual = max(abs(values[i] - sum(values[j] for j in adjacency[i]) / len(adjacency[i]))
                   for i in unknown)
    if residual > 1e-10 or min(values) < 0 or max(values) > 1:
        raise ValueError('INVALID_HARMONIC_FIELD')
    return values, lower, outer, features, residual


def split_chart(source, values):
    """Split each actual source triangle with shared, source-edge keyed cuts."""
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    source.data.calc_loop_triangles()
    vertices, records, lookup, faces, source_triangles, regions, bands = [], [], {}, [], [], [], []

    def put(weights, level=None):
        ids = sorted(i for i, w in weights.items() if w > 1e-12)
        if len(ids) == 1:
            key = ('vertex', ids[0])
            rec = dict(sourceEdge=[ids[0], ids[0]], edgeT=0.)
        elif len(ids) == 2 and level is not None:
            a, b = ids
            t = (LEVELS[level] - values[a]) / (values[b] - values[a])
            key = ('edge', a, b, level)
            rec = dict(sourceEdge=[a, b], edgeT=t, courseIndex=level)
        else:
            raise ValueError('CUT_NOT_ON_SOURCE_EDGE')
        if key not in lookup:
            a, b = rec['sourceEdge']
            lookup[key] = len(vertices)
            vertices.append(points[a].lerp(points[b], rec['edgeT']))
            records.append(rec)
        return lookup[key]

    def clip(poly, threshold, keep_above, level):
        result = []
        for (wa, ta, la), (wb, tb, lb) in zip(poly, poly[1:] + poly[:1]):
            inside_a = ta >= threshold if keep_above else ta <= threshold
            inside_b = tb >= threshold if keep_above else tb <= threshold
            if inside_a:
                result.append((wa, ta, la))
            if inside_a != inside_b:
                f = (threshold - ta) / (tb - ta)
                weights = {i: wa.get(i, 0) * (1 - f) + wb.get(i, 0) * f for i in wa.keys() | wb.keys()}
                result.append((weights, threshold, level))
        return result

    for tri in source.data.loop_triangles:
        base = [({i: 1.}, values[i], None) for i in tri.vertices]
        for band in range(4):
            poly = base
            if band > 0:
                poly = clip(poly, LEVELS[band - 1], True, band - 1)
            if band < 3 and poly:
                poly = clip(poly, LEVELS[band], False, band)
            ids = [put(w, level) for w, _, level in poly]
            # Exact-level coincidences are deduplicated before triangulation.
            ids = list(dict.fromkeys(ids))
            for j in range(1, len(ids) - 1):
                face = (ids[0], ids[j], ids[j + 1])
                if (vertices[face[1]] - vertices[face[0]]).cross(vertices[face[2]] - vertices[face[0]]).length < 1e-12:
                    raise ValueError('DEGENERATE_COURSE_CUT')
                faces.append(face)
                source_triangles.append(tri.index)
                regions.append(source.data.polygons[tri.polygon_index].material_index)
                bands.append(band)
    mesh = bpy.data.meshes.new(RESULT_OBJECT)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(RESULT_OBJECT, mesh)
    bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj)
    obj['designChartOnly'] = True
    obj['adoptionAllowed'] = False
    obj['rigBound'] = False
    for region, color in enumerate(branch.COLORS.values()):
        rgb = surface.linear_color(color)
        for band in range(4):
            shaded = tuple(float(v) * (.6 + .13 * band) for v in rgb[:3])
            mesh.materials.append(c.base.material('CourseRegion_' + str(region) + '_' + str(band), shaded))
    for face, region, band in zip(mesh.polygons, regions, bands):
        face.material_index = region * 4 + band
    return obj, dict(vertexProvenance=records, sourceTriangles=source_triangles, regions=regions, bands=bands)


def layout(source, obj, operation, values, lower, outer, features):
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    chart_points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    groups = edge_groups(features['sharedSeamEdges'])
    if len(groups) != 4:
        raise ValueError('EXPECTED_FOUR_LONGITUDINAL_ROUTES')
    routes = []
    for group in groups:
        path = ordered_path(group)
        if path[0] in outer:
            path.reverse()
        if path[0] not in lower or path[-1] not in outer:
            raise ValueError('LONGITUDINAL_BOUNDARY_MISMATCH')
        name = min(branch.TARGETS, key=lambda k: (points[path[-1]] - Vector(branch.TARGETS[k])).length)
        routes.append(dict(name=name, sourceVertices=path, edges=[list(e) for e in group]))
    if len({r['name'] for r in routes}) != 4:
        raise ValueError('LONGITUDINAL_NAMES_AMBIGUOUS')
    ef = prior.edge_faces([tuple(f.vertices) for f in obj.data.polygons])
    courses = []
    records = operation['vertexProvenance']
    for index, level in enumerate(LEVELS):
        nodes = {i for i, rec in enumerate(records) if rec.get('courseIndex') == index}
        edges = [e for e in ef if set(e) <= nodes]
        path = ordered_path(edges, cyclic=True)
        if any(len(ef[e]) != 2 for e in edges):
            raise ValueError('COURSE_EDGES_NOT_SHARED')
        crossings = []
        for route in routes:
            route_edges = {tuple(e) for e in route['edges']}
            hits = [i for i in nodes if tuple(records[i]['sourceEdge']) in route_edges]
            if len(hits) != 1:
                raise ValueError('COURSE_MUST_CROSS_EACH_BRANCH_ONCE')
            crossings.append(dict(route=route['name'], chartVertex=hits[0], sourceEdge=records[hits[0]]['sourceEdge']))
        courses.append(dict(index=index, level=level, chartVertices=path, sharedEdges=[list(e) for e in edges],
                            branchCrossings=crossings,
                            lengthMeters=sum((chart_points[a] - chart_points[b]).length for a, b in edges)))
    folds = []
    for edges in edge_groups(features['majorCreaseEdges']):
        vertices = sorted({i for e in edges for i in e})
        key = min(vertices)
        if key not in FOLD_POLICIES:
            raise ValueError('UNCLASSIFIED_MAJOR_FOLD')
        policy, color = FOLD_POLICIES[key]
        folds.append(dict(id=key, policy=policy, color=color, sourceEdges=[list(e) for e in edges],
                          lengthMeters=sum((points[a] - points[b]).length for a, b in edges),
                          touchesOuterClip=bool(set(vertices) & set(outer)),
                          sourceFaces=sorted({fi for e in edges for fi in prior.edge_faces([tuple(f.vertices) for f in source.data.polygons])[e]})))
    return dict(longitudinalRoutes=routes, transverseCourses=courses, majorFoldGroups=folds,
                lowerLoop=lower, provisionalOuterLoop=outer, designHypothesisOnly=True,
                macroDomainCount=16, majorFoldShapeRedesigned=False, deformationValidated=False)


def audit(source, obj, operation, design, values, residual):
    surface.require_locked(source)
    surface.require_locked(obj)
    expected, lower, outer, _, expected_residual = field(source)
    if not np.isfinite(values).all() or not np.isfinite(residual) or len(values) != len(expected) or any(abs(a - b) > 1e-12 for a, b in zip(values, expected)) or abs(residual - expected_residual) > 1e-12:
        raise ValueError('HARMONIC_FIELD_RECORD_CHANGED')
    if design['lowerLoop'] != lower or design['provisionalOuterLoop'] != outer:
        raise ValueError('BOUNDARY_ROLE_CHANGED')
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    chart_points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if len(operation['vertexProvenance']) != len(chart_points):
        raise ValueError('CHART_PROVENANCE_COUNT_CHANGED')
    errors = []
    for p, rec in zip(chart_points, operation['vertexProvenance']):
        a, b = rec['sourceEdge']
        t = rec['edgeT']
        if not 0 <= t <= 1:
            raise ValueError('INVALID_SOURCE_EDGE_T')
        errors.append((p - points[a].lerp(points[b], t)).length)
    _, _, _, features = prior.prior.topology(source)
    rebuilt = layout(source, obj, operation, values, design['lowerLoop'], design['provisionalOuterLoop'], features)
    if design != rebuilt:
        raise ValueError('LAYOUT_RECORD_CHANGED')
    source.data.calc_loop_triangles()
    if not all(len(operation[k]) == len(obj.data.polygons) for k in ('sourceTriangles', 'regions', 'bands')):
        raise ValueError('FACE_PROVENANCE_COUNT_CHANGED')
    graph = defaultdict(set)
    ef = prior.edge_faces([tuple(f.vertices) for f in obj.data.polygons])
    for fs in ef.values():
        if len(fs) == 2:
            a, b = fs
            if obj.data.polygons[a].material_index == obj.data.polygons[b].material_index:
                graph[a].add(b)
                graph[b].add(a)
    domain_counts = []
    for domain in range(16):
        unseen = {f.index for f in obj.data.polygons if f.material_index == domain}
        count, size = 0, len(unseen)
        while unseen:
            stack = [min(unseen)]
            count += 1
            while stack:
                i = stack.pop()
                if i in unseen:
                    unseen.remove(i)
                    stack.extend(graph[i] & unseen)
        domain_counts.append(dict(domain=domain, faces=size, components=count))
    orientation = 0
    triangle_areas = defaultdict(float)
    area_before = sum(t.area for t in source.data.loop_triangles)
    for face, triangle, region, band in zip(obj.data.polygons, operation['sourceTriangles'], operation['regions'], operation['bands']):
        tri = source.data.loop_triangles[triangle]
        triangle_areas[triangle] += face.area
        if face.material_index != region * 4 + band or region != source.data.polygons[tri.polygon_index].material_index:
            raise ValueError('DOMAIN_REGION_CHANGED')
        if not all(set(operation['vertexProvenance'][i]['sourceEdge']) <= set(tri.vertices) for i in face.vertices):
            raise ValueError('FACE_LEAVES_SOURCE_TRIANGLE')
        source_normal = (points[tri.vertices[1]] - points[tri.vertices[0]]).cross(points[tri.vertices[2]] - points[tri.vertices[0]]).normalized()
        if face.normal.dot(source_normal) < .999:
            orientation += 1
        for i in face.vertices:
            rec = operation['vertexProvenance'][i]
            a, b = rec['sourceEdge']
            u = values[a] * (1 - rec['edgeT']) + values[b] * rec['edgeT']
            bounds = (0.,) + LEVELS + (1.,)
            if not bounds[band] - 1e-10 <= u <= bounds[band + 1] + 1e-10:
                raise ValueError('FACE_LEAVES_COURSE_BAND')
    topology = branch.s.prior.prior.boundaries(obj)
    tree, _, rendered = c.fit.bvh(obj)
    pairs = {(a, b) for a, b in tree.overlap(tree) if a < b and not set(rendered[a]) & set(rendered[b])}
    area_after = sum(f.area for f in obj.data.polygons)
    # A global area sum could conceal a missing source triangle and a duplicate
    # elsewhere. Every actual source triangle must independently be covered.
    maximum_triangle_area_error = max(abs(triangle_areas[t.index] - t.area) / t.area for t in source.data.loop_triangles)
    qa = dict(vertices=len(chart_points),triangles=len(obj.data.polygons),courseCount=3,
              courseSharedEdgeCounts=[len(r['sharedEdges']) for r in design['transverseCourses']],
              longitudinalRouteCount=4,courseBranchCrossings=12,domainCounts=domain_counts,
              majorFoldGroupCount=len(design['majorFoldGroups']),
              classifiedMajorFoldEdges=sum(len(g['sourceEdges']) for g in design['majorFoldGroups']),
              harmonicResidual=residual,maximumSourceEdgeErrorMeters=max(errors),
              sourceSurfaceAreaSquareMeters=area_before,chartSurfaceAreaSquareMeters=area_after,
              relativeAreaError=abs(area_after - area_before) / area_before,
              maximumSourceTriangleRelativeAreaError=maximum_triangle_area_error,
              connectedComponents=len(topology['components']),boundaryLoops=len(topology['boundaryLoops']),
              euler=topology['euler'],zeroAreaFaces=topology['zeroAreaFaces'],orientationErrors=orientation,
              nonAdjacentSelfIntersectionPairs=len(pairs),originalBodyMovedVertices=0,
              geometryShapeChanged=False,majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False)
    qa['eligible'] = max(errors) < 1e-6 and qa['relativeAreaError'] < 1e-5 and maximum_triangle_area_error < 1e-3 and not pairs and not orientation and not qa['zeroAreaFaces'] and qa['connectedComponents'] == 1 and qa['boundaryLoops'] == 2 and qa['euler'] == 0 and all(d['faces'] > 0 and d['components'] == 1 for d in domain_counts)
    return qa


def guides(source, obj, design):
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    chart_points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    network, folds = [], []
    for route in design['longitudinalRoutes']:
        network.append(branch.curve(GUIDE_PREFIX + 'branch_' + route['name'], [points[i] for i in route['sourceVertices']], 'FFFFFF'))
    for course in design['transverseCourses']:
        network.append(branch.curve(GUIDE_PREFIX + 'course_' + str(course['index']), [chart_points[i] for i in course['chartVertices']], 'FFFFFF', True))
    for group in design['majorFoldGroups']:
        # One editable poly segment per feature edge; no synthetic curve across
        # branches in a fold network. Their source IDs remain in the report.
        data = bpy.data.curves.new(GUIDE_PREFIX + 'fold_' + str(group['id']), 'CURVE')
        data.dimensions = '3D'
        data.bevel_depth = .0007
        data.bevel_resolution = 2
        for a, b in group['sourceEdges']:
            spline = data.splines.new('POLY')
            spline.points.add(1)
            for p, co in zip(spline.points, (points[a], points[b])):
                p.co = (*co, 1)
        guide = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(guide)
        data.materials.append(c.base.material(data.name, surface.linear_color(group['color'])))
        c.base.mark(guide)
        guide['guideOnly'] = True
        guide['foldPolicy'] = group['policy']
        folds.append(guide)
    return network, folds


def fold_review_ghost(source):
    """Render-only translucent copy to expose the otherwise occluded underarm."""
    mesh = source.data.copy()
    mesh.materials.clear()
    mat = bpy.data.materials.new('FoldReviewGhostMaterial')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = .12
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    diffuse = nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.inputs['Color'].default_value = (.6, .65, .7, 1)
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(diffuse.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
    mesh.materials.append(mat)
    for face in mesh.polygons:
        face.material_index = 0
    ghost = bpy.data.objects.new('FoldReviewGhost_RENDER_ONLY', mesh)
    ghost.matrix_world = source.matrix_world.copy()
    bpy.context.scene.collection.objects.link(ghost)
    return ghost, mat


def audit_guides(source, obj, design):
    """Check saved editable curves, independently of the chart's QA report."""
    points = [source.matrix_world @ v.co for v in source.data.vertices]
    chart_points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    expected = {}
    for route in design['longitudinalRoutes']:
        expected[GUIDE_PREFIX + 'branch_' + route['name']] = ([[points[i] for i in route['sourceVertices']]], False, None)
    for course in design['transverseCourses']:
        expected[GUIDE_PREFIX + 'course_' + str(course['index'])] = ([[chart_points[i] for i in course['chartVertices']]], True, None)
    for group in design['majorFoldGroups']:
        expected[GUIDE_PREFIX + 'fold_' + str(group['id'])] = ([[points[a], points[b]] for a, b in group['sourceEdges']], False, group['policy'])
    actual = {o.name: o for o in bpy.context.scene.objects if o.name.startswith(GUIDE_PREFIX)}
    if set(actual) != set(expected):
        raise ValueError('GUIDE_SET_CHANGED')
    maximum = 0.
    for name, (paths, cyclic, policy) in expected.items():
        guide = actual[name]
        surface.require_locked(guide)
        if guide.type != 'CURVE' or not guide.get('guideOnly') or len(guide.data.splines) != len(paths):
            raise ValueError('GUIDE_STRUCTURE_CHANGED')
        if policy is not None and guide.get('foldPolicy') != policy:
            raise ValueError('GUIDE_FOLD_POLICY_CHANGED')
        for spline, path in zip(guide.data.splines, paths):
            if spline.type != 'POLY' or spline.use_cyclic_u != cyclic or len(spline.points) != len(path):
                raise ValueError('GUIDE_STRUCTURE_CHANGED')
            for p, target in zip(spline.points, path):
                maximum = max(maximum, (guide.matrix_world @ Vector(p.co[:3]) - target).length)
    if maximum > 1e-6:
        raise ValueError('GUIDE_POSITION_CHANGED')
    return dict(guideCount=len(actual), maximumGuidePositionErrorMeters=maximum)


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if c.base.sha(source.parent / 'edge-flow-report.json') != REPORT_SHA:
        raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    turnaround = args.art_root / 'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround) != panel.TURNAROUND_SHA:
        raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()), sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('LAYOUT_ALREADY_EXISTS')
    old = bpy.data.objects[prior.RESULT_OBJECT]
    originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    invariants = {o.name: surface.repair.invariant_signature(o) for o in originals}
    visible = [o for o in bpy.context.scene.objects if o.type in ('MESH', 'CURVE') and not o.hide_get()]
    values, lower, outer, features, residual = field(old)
    obj, op = split_chart(old, values)
    design = layout(old, obj, op, values, lower, outer, features)
    qa = audit(old, obj, op, design, values, residual)
    if not qa['eligible']:
        raise ValueError('LAYOUT_QA_REJECTED:' + json.dumps(qa))
    network, folds = guides(old, obj, design)
    audit_guides(old, obj, design)
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        ghost, ghost_material = fold_review_ghost(old)
        for name, item, lines in [('source', old, []), ('courses', obj, network), ('folds', ghost, folds)]:
            folder = output / name
            folder.mkdir()
            rows = branch.render(folder, item, lines)
            renders.extend(dict(file=name + '/' + row['file'], sha256=row['sha256']) for row in rows)
        ghost_mesh = ghost.data
        bpy.data.objects.remove(ghost, do_unlink=True)
        bpy.data.meshes.remove(ghost_mesh)
        bpy.data.materials.remove(ghost_material)
    if digest != c.guide.digest(originals) or any(invariants[o.name] != surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for item in bpy.context.scene.objects:
        if item.type in ('MESH', 'CURVE'):
            item.hide_render = item not in visible
    obj.hide_set(True)
    for guide in network + folds:
        guide.hide_set(True)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output / 'CH101_ShoulderDeformationLayout_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY,status='COURSE_FOLD_DESIGN_CHART_NOT_GARMENT',**c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                  operation=op,design=design,harmonicField=values,qa=qa,originalsPreserved=True,
                  adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                  blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                  referenceDecision='White cap should read as broad cloth, not the inherited dense underarm crease network. This is an authored hypothesis, not approved fold correspondence.',
                  foldReviewDisplay='RENDER_ONLY_TRANSLUCENT_SOURCE_COPY_TO_EXPOSE_OCCLUDED_UNDERARM',
                  limitations=['SHARED_EDGES_ON_DESIGN_CHART_NOT_FINAL_QUADS','SOURCE_FOLD_SHAPE_UNCHANGED',
                               'PROVISIONAL_OUTER_CLIP_NOT_SEWING_BOUNDARY','NO_UV_THICKNESS_RIG_OR_DEFORMATION_VALIDATION'])
    (output / 'deformation-layout-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output / 'READ_ME_FIRST.txt').write_text('CH101 course/fold design chart — NOT PRODUCTION\nThree real shared transverse courses and four preserved longitudinal routes divide the source surface into 16 connected design domains.\nFold policy colors: red = underarm network redesign; orange = defer until torso attachment boundary; green = remove cap micro-crease in future rebuild. These are hypotheses, not automatic geometry edits.\nUnhide CH101_ShoulderDeformationLayoutChart_NOT_PRODUCTION and DEFORMATION_LAYOUT_* curves to inspect/edit. Prior assembly remains visible; all new study objects are hidden.\nNo shape improvement, new full-character score, garment/animation approval, human Gate B or Unity promotion.\n',encoding='utf-8')
    print(json.dumps(dict(blendSha256=report['blendSha256'],qa=qa),indent=2),flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
