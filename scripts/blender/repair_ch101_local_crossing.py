"""Bounded one-vertex repair of the inspected distal-replacement review copy.

No remeshing, component deletion, UV edits, anatomical approval or rig binding.
BVH checks exclude triangle pairs sharing vertices; they are not exhaustive
solid-validity or deformation proofs. Independent finite edge/triangle hits
confirm that the original reported pairs really cross before a repair is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replace_ch101_distal_source_study as replacement

c = replacement.c
STRATEGY = 'CH101_BOUNDED_LOCAL_CROSSING_REPAIR_V001'
SOURCE_SHA = '0fbf9820bd66cc3b2eb8c41d36358aa490f3451a84a673b2913c7db793060c2b'
SOURCE_OBJECT = 'CH101_SourceBody_DistalReplacement_COPY_NOT_PRODUCTION'
PATCH_VERTEX = 3432
DIRECTION_TRIANGLE = 10105
MOVE_DISTANCE = .00005
MAX_MOVE = .0005


def crossing_pairs(obj):
    tree, points, faces = c.fit.bvh(obj)
    pairs = sorted({(a, b) for a, b in tree.overlap(tree)
                    if a < b and not set(faces[a]) & set(faces[b])})
    return points, faces, pairs


def finite_crossing_hits(first, second, epsilon=1e-8):
    """Unique finite edge/triangle intersections; not a coplanar overlap solver."""
    hits = []
    for a, b in ((first, second), (second, first)):
        for start, end in zip(a, a[1:] + a[:1]):
            edge = end - start
            length = edge.length
            if length <= epsilon:
                continue
            direction = edge / length
            hit = intersect_ray_tri(*b, direction, start, True)
            if hit is None:
                continue
            distance = (hit - start).dot(direction)
            if epsilon < distance < length - epsilon and all((hit - p).length > epsilon for p in hits):
                hits.append(hit)
    return hits


def invariant_signature(obj):
    """Everything in the mesh except coordinates/normals must stay unchanged."""
    mesh = obj.data
    data = dict(edges=[list(e.vertices) for e in mesh.edges],
                polygons=[(list(p.vertices), p.material_index, p.use_smooth) for p in mesh.polygons],
                materials=[m.name if m else None for m in mesh.materials],
                uv=[(layer.name, [list(loop.uv) for loop in layer.data]) for layer in mesh.uv_layers],
                groups=[g.name for g in obj.vertex_groups],
                weights=[[(g.group, g.weight) for g in v.groups] for v in mesh.vertices],
                transform=[list(row) for row in obj.matrix_world])
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def components(obj):
    points, faces = c.fit.geometry(obj)
    graph = {i: set() for i in range(len(points))}
    for edge in obj.data.edges:
        a, b = edge.vertices
        graph[a].add(b)
        graph[b].add(a)
    remaining, groups = set(graph), []
    while remaining:
        found, stack = set(), [min(remaining)]
        while stack:
            v = stack.pop()
            if v not in found:
                found.add(v)
                stack.extend(graph[v] - found)
        remaining -= found
        groups.append(sorted(found))
    groups.sort(key=lambda group: (-len(group), group[0]))
    report = []
    for group in groups:
        selected = set(group)
        report.append(dict(vertexCount=len(group), vertexIndices=group,
                           triangleCount=sum(f[0] in selected for f in faces),
                           center=list(sum((points[i] for i in group), Vector()) / len(group)),
                           bounds=[[min(points[i][k] for i in group), max(points[i][k] for i in group)] for k in range(3)]))
    return report


def bounded_repair(source, vertex_index, distance=MOVE_DISTANCE, max_move=MAX_MOVE,
                   direction_triangle=DIRECTION_TRIANGLE):
    if not 0 < distance <= .0005 or not 0 < max_move <= .0005:
        raise ValueError('UNSAFE_REPAIR_LIMIT')
    points, faces, pairs = crossing_pairs(source)
    if not pairs:
        raise ValueError('NO_CROSSING_TO_REPAIR')
    involved = {v for pair in pairs for t in pair for v in faces[t]}
    if vertex_index not in involved:
        raise ValueError('VERTEX_OUTSIDE_CROSSING_PATCH')
    confirmed = []
    for a, b in pairs:
        hits = finite_crossing_hits([points[i] for i in faces[a]], [points[i] for i in faces[b]])
        if len(hits) < 2:
            raise ValueError('CROSSING_NOT_CONFIRMED_BY_FINITE_EDGES')
        confirmed.append(dict(triangleIndices=[a, b], vertexIndices=[list(faces[a]), list(faces[b])],
                              segmentHits=[list(p) for p in hits]))
    if direction_triangle < 0 or direction_triangle >= len(faces) or vertex_index not in faces[direction_triangle]:
        raise ValueError('DIRECTION_TRIANGLE_NOT_INCIDENT')
    a, b, d = (points[i] for i in faces[direction_triangle])
    direction = (b-a).cross(d-a).normalized()
    delta = direction * distance
    if not 1e-8 < delta.length <= max_move:
        raise ValueError('DISPLACEMENT_LIMIT_EXCEEDED')
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = 'CH101_SourceBody_DistalReplacement_TopologyRepair_NOT_PRODUCTION'
    bpy.context.scene.collection.objects.link(obj)
    success = False
    try:
        obj.data.vertices[vertex_index].co = obj.matrix_world.inverted() @ (points[vertex_index] + delta)
        obj.data.update()
        after_points, after_faces, after_pairs = crossing_pairs(obj)
        if after_pairs:
            raise ValueError('REPAIR_LEFT_OR_INTRODUCED_CROSSINGS')
        if after_faces != faces or invariant_signature(obj) != invariant_signature(source):
            raise ValueError('TOPOLOGY_UV_MATERIAL_OR_WEIGHTS_CHANGED')
        changed = [i for i, (a, b) in enumerate(zip(points, after_points)) if a != b]
        actual_delta = after_points[vertex_index] - points[vertex_index]
        if changed != [vertex_index] or actual_delta.length > max_move:
            raise ValueError('UNEXPECTED_VERTEX_CHANGE')
        incident, normal_dots, area_ratios = [], [], []
        for index, face in enumerate(faces):
            if vertex_index not in face:
                continue
            incident.append(index)
            a, b, d = (points[i] for i in face)
            old_normal = (b-a).cross(d-a)
            a, b, d = (after_points[i] for i in face)
            new_normal = (b-a).cross(d-a)
            normal_dots.append(old_normal.normalized().dot(new_normal.normalized()))
            area_ratios.append(new_normal.length / old_normal.length)
        if min(normal_dots) < .95 or min(area_ratios) < .5 or max(area_ratios) > 2:
            raise ValueError('INCIDENT_FACE_DISTORTION_REJECTED:' + json.dumps(dict(normalDots=normal_dots, areaRatios=area_ratios)))
        audit = c.author.shape_audit(obj)
        audit['selfIntersectionTestPerformed'] = True
        audit['selfIntersectionTestScope'] = 'NON_ADJACENT_TRIANGLE_BVH_SHARED_VERTEX_PAIRS_EXCLUDED'
        before_audit = c.author.shape_audit(source)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        winding = sum(not edge.is_contiguous for edge in bm.edges)
        volume = bm.calc_volume(signed=True)
        bm.free()
        if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or winding or volume <= 0 or audit['components'] != before_audit['components']:
            raise ValueError('REPAIR_TOPOLOGY_REJECTED')
        c.base.mark(obj)
        obj['originalSourceModified'] = False
        obj['localCrossingRepairOnCopy'] = True
        success = True
        return obj, dict(beforePairs=confirmed, afterNonAdjacentPairs=0,
                         changedVertexIndices=changed, unchangedVertexCount=len(points)-len(changed),
                         method='INSPECTED_INCIDENT_TRIANGLE_NORMAL_SINGLE_VERTEX_OFFSET',
                         directionTriangleIndex=direction_triangle, directionWorld=list(direction),
                         requestedDisplacementMeters=distance,
                         beforePosition=list(points[vertex_index]), afterPosition=list(after_points[vertex_index]),
                         actualDisplacementMeters=actual_delta.length, maxAllowedDisplacementMeters=max_move,
                         deltaWorld=list(actual_delta), affectedTriangleIndices=incident,
                         minimumIncidentNormalDot=min(normal_dots), incidentAreaRatioRange=[min(area_ratios), max(area_ratios)],
                         topologyUVMaterialsWeightsUnchanged=True, topology=audit,
                         inconsistentWindingEdges=winding, signedVolumeCubicMeters=volume)
    finally:
        if not success:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)


def diagnostic_copy(source, patch_polygons, small_vertices):
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = 'DIAGNOSTIC_COPY_' + source.name
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.clear()
    for name, rgb in [('Context', (.22, .25, .28)), ('Crossing_patch', (.8, .025, .035)), ('Retained_component', (.95, .38, .025))]:
        obj.data.materials.append(c.base.material('TopologyDiagnostic_' + name, rgb))
    for polygon in obj.data.polygons:
        polygon.material_index = 2 if set(polygon.vertices) <= small_vertices else (1 if polygon.index in patch_polygons else 0)
    c.base.mark(obj)
    obj['diagnosticOnly'] = True
    return obj


def render_review(output, before, after, parts, operation, component_report):
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type in ('MESH', 'CURVE', 'LIGHT'):
            obj.hide_render = True
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 24
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.view_settings.exposure = -.5
    camera = scene.camera
    camera.data.type = 'ORTHO'
    lights = []
    for name, offset, energy in [('key', (-.4, -.5, .6), 65), ('fill', (.3, .4, .3), 40)]:
        data = bpy.data.lights.new('TopologyReview_' + name, 'AREA')
        data.energy, data.size = energy, .4
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        lights.append((obj, Vector(offset)))
    points, _, _ = crossing_pairs(before)
    patch_vertices = {v for pair in operation['beforePairs'] for f in pair['vertexIndices'] for v in f}
    patch_center = sum((points[i] for i in patch_vertices), Vector()) / len(patch_vertices)
    small_center = Vector(component_report[-1]['center'])
    patch_polygons = {before.data.loop_triangles[t].polygon_index for pair in operation['beforePairs'] for t in pair['triangleIndices']}
    small = set(component_report[-1]['vertexIndices'])
    diagnostic_before = diagnostic_copy(before, patch_polygons, small)
    diagnostic_after = diagnostic_copy(after, patch_polygons, small)
    renders = []
    def shot(name, objects, target, offset, scale):
        for obj in [before, after, diagnostic_before, diagnostic_after] + parts:
            obj.hide_render = obj not in objects
        for light, light_offset in lights:
            light.location = target + light_offset
            light.rotation_euler = (target-light.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = scale
        camera.location = target + Vector(offset)
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        path = output / (name + '.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(dict(file=path.name, sha256=c.base.sha(path)))
    for name, obj in [('before', diagnostic_before), ('after', diagnostic_after)]:
        shot('patch_' + name, [obj], patch_center, (-.3, .7, .2), .085)
    for name, obj in [('before', before), ('after', after)]:
        shot('textured_patch_' + name, [obj] + parts, patch_center, (-.3, .7, .2), .24)
    shot('component_back_context', [diagnostic_after] + parts, small_center, (.25, .7, .1), .55)
    shot('component_side_context', [diagnostic_after] + parts, small_center, (.7, .15, .1), .45)
    shot('assembly_front', [after] + parts, Vector((0, 0, .84)), (0, -3, .1), 1.95)
    for obj in (diagnostic_before, diagnostic_after):
        obj.hide_render = True
    return renders


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    refs = c.base.verify_references(args.art_root.resolve())
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    if any(scene.get(k) not in (False, 0) for k in ('unityInputAllowed', 'productionPromotionAllowed')):
        raise ValueError('SOURCE_GATE_NOT_FALSE')
    originals = [o for o in scene.objects if o.type == 'MESH']
    original_digest = c.guide.digest(originals)
    original_invariants = {o.name: invariant_signature(o) for o in originals}
    body = bpy.data.objects[SOURCE_OBJECT]
    parts = [bpy.data.objects['CH101_UpperSleeveFit_STUDY_NOT_PRODUCTION']]
    parts += [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    repaired, operation = bounded_repair(body, PATCH_VERTEX)
    before_components, after_components = components(body), components(repaired)
    for previous, current in zip(before_components[1:], after_components[1:]):
        if previous != current:
            raise ValueError('UNRELATED_COMPONENT_CHANGED')
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    overlaps = c.fit.overlap_report(repaired, parts, hand.matrix_world @ Vector())
    if any(row['uniqueEquipmentTrianglesCrossing'] for row in overlaps):
        raise ValueError('AUTHORED_PART_CROSSING_INTRODUCED')
    pts, faces = c.fit.geometry(repaired)
    small_ids = set(after_components[-1]['vertexIndices'])
    main_tree = BVHTree.FromPolygons(pts, [f for f in faces if f[0] not in small_ids], all_triangles=True)
    small_distances = [main_tree.find_nearest(pts[i])[3] for i in small_ids]
    component_note = dict(status='RETAINED_UNCHANGED_SEMANTIC_IDENTITY_UNCONFIRMED',
                          vertexCount=len(small_ids), surfaceCrossingPairsWithMain=0,
                          nearestVertexToMainSurfaceMeters=min(small_distances),
                          nearestDistanceIsVertexSampleNotExactSurfaceGap=True,
                          deletionAuthorizedBySize=False, rigBindingVerified=False)
    output.mkdir(parents=True)
    renders = [] if args.no_render else render_review(output, body, repaired, parts, operation, after_components)
    if c.guide.digest(originals) != original_digest or any(invariant_signature(o) != original_invariants[o.name] for o in originals) or c.base.sha(source) != SOURCE_SHA:
        raise ValueError('ORIGINAL_CHANGED')
    for key, value in c.base.GATES.items():
        scene[key] = value
    scene['localCrossingRepairOnCopy'] = True
    visible = replacement.configure_review_viewport([repaired] + parts)
    for obj in scene.objects:
        if obj.type in ('MESH', 'CURVE'):
            obj.hide_render = obj not in [repaired] + parts
    bpy.context.preferences.filepaths.save_version = 0
    blend = output / 'CH101_LocalTopologyRepair_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='LOCAL_STATIC_CROSSING_REPAIRED_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  operation=operation, componentsBefore=before_components, componentsAfter=after_components,
                  retainedSmallComponent=component_note, bodyPartOverlapAfter=overlaps,
                  originalSourcePreserved=True, defaultVisibleMeshObjects=visible,
                  weldedToSleeve=False, rigBound=False, designApproved=False, attachmentApproved=False,
                  fullCharacterScore=None, blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['BVH_TEST_EXCLUDES_SHARED_VERTEX_PAIRS', 'NOT_A_SOLID_CONTAINMENT_OR_DEFORMATION_PROOF',
                               'SEPARATE_COMPONENT_SEMANTIC_IDENTITY_UNCONFIRMED', 'LAYERED_UNWELDED_TEMPORARY_CAP',
                               'PROVISIONAL_MATERIALS_AND_PROJECTED_TEXTURE', 'NO_RIG_ANIMATION_OR_UNITY_ACCEPTANCE'])
    (output / 'local-topology-repair-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (output / 'READ_ME_FIRST.txt').write_text(
        'CH101 local topology repair v001 — NOT PRODUCTION\n'
        'One vertex moved by at most 0.5 mm on a new body copy. Original sources remain hidden, not deleted.\n'
        'Three finite-edge-confirmed non-adjacent surface crossings become zero; this is not a comprehensive solid-validity proof.\n'
        'UVs/materials/topology/weights and the separate 48-vertex component remain unchanged.\n'
        'Orange diagnostic geometry is a retained, semantically unconfirmed component; red is the same before/after patch.\n'
        'No rig/deformation/Unity acceptance, no full-character score, no human Gate B approval.\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--art-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-render', action='store_true')
    result = run(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: result[k] for k in ('status', 'operation', 'retainedSmallComponent', 'blendSha256')}, indent=2))
