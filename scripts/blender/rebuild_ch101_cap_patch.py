"""Boundary-locked replacement of the classified cap micro-crease disk.

This changes real surface triangles, not original body vertices. The full
underarm network and garment sewing/deformation remain unfinished.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_ch101_shoulder_deformation_layout as prior
c, surface, branch = prior.c, prior.surface, prior.branch
SOURCE_SHA = '2eec54b4e8b0a829c94304f7ed54fb93b42eb84b469d4470353d38af39370540'
REPORT_SHA = 'ed9f9e3b5e0451a190401868e230f7c0258561c4a860acc7fd5af5633527d3ea'
RESULT_OBJECT = 'CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION'
STRATEGY = 'CH101_BOUNDARY_LOCKED_CAP_DISK_REPLACEMENT_V001'
MAX_ERROR = .0015
POLICY = 'REMOVE_MICRO_CREASE_IN_CAP_REBUILD'


def probe_underarm_disk(source, report):
    """Read-only rejection evidence for blindly filling the whole fold network."""
    group = next(g for g in report['design']['majorFoldGroups'] if g['policy']=='REDESIGN_UNDERARM_NETWORK')
    old_seeds = {i for e in group['sourceEdges'] for i in e}
    seeds = {i for i,p in enumerate(report['operation']['vertexProvenance'])
             if p['sourceEdge'][0]==p['sourceEdge'][1] and p['sourceEdge'][0] in old_seeds}
    faces = [f.index for f in source.data.polygons if seeds.intersection(f.vertices)]
    vertices = {i for fi in faces for i in source.data.polygons[fi].vertices}
    edges = prior.prior.edge_faces([tuple(source.data.polygons[fi].vertices) for fi in faces])
    border = [e for e,fs in edges.items() if len(fs)==1]
    degrees = defaultdict(int)
    for a,b in border:
        degrees[a] += 1
        degrees[b] += 1
    groups = prior.edge_groups(border)
    courses = {i for row in report['design']['transverseCourses'] for i in row['chartVertices']}
    regions = sorted({source.data.polygons[fi].material_index//4 for fi in faces})
    simple = len(groups)==1 and all(n==2 for n in degrees.values())
    return dict(selectedFaces=len(faces),sourceFaceIndices=faces,sourceVertices=len(vertices),
                boundaryEdges=len(border),boundaryComponentEdgeCounts=sorted([len(g) for g in groups],reverse=True),
                branchingBoundaryVertices=sum(n!=2 for n in degrees.values()),courseVerticesTouched=len(vertices&courses),
                sourceRegions=regions,simpleBoundary=simple,canAutoFillAsOneDisk=simple and regions==[1] and not vertices&courses,
                geometryChanged=False)


def extract(source, report):
    surface.require_locked(source)
    groups = [g for g in report['design']['majorFoldGroups'] if g['policy'] == POLICY]
    if len(groups) != 1 or groups[0]['id'] != 1874:
        raise ValueError('CAP_POLICY_CHANGED')
    old_seeds = {i for e in groups[0]['sourceEdges'] for i in e}
    seeds = {i for i, p in enumerate(report['operation']['vertexProvenance'])
             if p['sourceEdge'][0] == p['sourceEdge'][1] and p['sourceEdge'][0] in old_seeds}
    faces = sorted(f.index for f in source.data.polygons if seeds.intersection(f.vertices))
    selected = [tuple(source.data.polygons[i].vertices) for i in faces]
    edges = prior.prior.edge_faces(selected)
    boundary_edges = {e for e, fs in edges.items() if len(fs) == 1}
    successor = {}
    for face in selected:
        for a, b in zip(face, face[1:] + face[:1]):
            if tuple(sorted((a, b))) in boundary_edges:
                if a in successor:
                    raise ValueError('PATCH_BOUNDARY_NOT_SIMPLE')
                successor[a] = b
    if not successor or len(successor) != len(boundary_edges):
        raise ValueError('PATCH_BOUNDARY_NOT_SIMPLE')
    border = [min(successor)]
    while successor[border[-1]] != border[0]:
        nxt = successor[border[-1]]
        if nxt in border:
            raise ValueError('PATCH_HAS_MULTIPLE_BOUNDARIES')
        border.append(nxt)
    if set(border) != set(successor):
        raise ValueError('PATCH_HAS_MULTIPLE_BOUNDARIES')
    vertices = {i for face in selected for i in face}
    interior = sorted(vertices - set(border))
    global_edges = prior.prior.edge_faces([tuple(f.vertices) for f in source.data.polygons])
    protected = {e for e, fs in global_edges.items() if len(fs) == 1 or len({source.data.polygons[fi].material_index for fi in fs}) > 1}
    if set(interior) & {i for e in protected for i in e}:
        raise ValueError('PATCH_REMOVES_PROTECTED_CONTROL')
    materials = {source.data.polygons[fi].material_index for fi in faces}
    if seeds != set(interior) or materials != {15} or (len(faces), len(border), len(interior)) != (20, 16, 3):
        raise ValueError('CAP_DISK_IDENTITY_CHANGED')
    return dict(removedFaces=faces, removedInteriorVertices=interior, boundaryVertices=border,
                materialIndex=15, protectedEdges=[list(e) for e in sorted(protected)])


def outside_normals(source, operation):
    edges = prior.prior.edge_faces([tuple(f.vertices) for f in source.data.polygons])
    selected = set(operation['removedFaces'])
    border = operation['boundaryVertices']
    result = {}
    for a,b in zip(border,border[1:]+border[:1]):
        edge = tuple(sorted((a,b)))
        outside = [fi for fi in edges[edge] if fi not in selected]
        if len(outside) != 1:
            raise ValueError('PATCH_NOT_INTERIOR_DISK')
        result[edge] = source.data.polygons[outside[0]].normal.copy()
    return result


def triangulate_boundary(points, border, neighbors, shape_only=False):
    """Edge-conditioned DP minimizes real patch + fixed-neighbor bending.

    A root-triangle state retains its normal, so child choices include the
    dihedral cost across their common diagonal rather than an additive proxy.
    """
    polygon = np.array([list(points[i]) for i in border])
    center = polygon.mean(axis=0)
    _, _, axes = np.linalg.svd(polygon - center)
    normal = sum(((points[a]-Vector(center)).cross(points[b]-Vector(center))
                  for a, b in zip(border, border[1:] + border[:1])), Vector()).normalized()
    x_axis = Vector(axes[0])
    y_axis = normal.cross(x_axis)
    xy = np.array([[(p-Vector(center)).dot(x_axis), (p-Vector(center)).dot(y_axis)] for p in (points[i] for i in border)])
    def cross(a, b, d):
        u, v = b-a, d-a
        return float(u[0]*v[1] - u[1]*v[0])
    def inside(p):
        hit = False
        for a, b in zip(xy, np.roll(xy, -1, axis=0)):
            if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
                hit = not hit
        return hit
    n = len(border)
    def valid_edge(i, j):
        if abs(i-j) == 1 or {i, j} == {0, n-1}:
            return True
        if not inside((xy[i]+xy[j])/2):
            return False
        for a in range(n):
            b = (a+1) % n
            if {i, j} & {a, b}:
                continue
            if cross(xy[i], xy[j], xy[a])*cross(xy[i], xy[j], xy[b]) < -1e-20 and cross(xy[a], xy[b], xy[i])*cross(xy[a], xy[b], xy[j]) < -1e-20:
                return False
        return True
    legal = {(i, j): valid_edge(i, j) for i in range(n) for j in range(i+1, n)}
    costs, splits, normals, quality_values = {}, {}, {}, {}
    choices_by_edge = defaultdict(list)
    boundary_set = {tuple(sorted((a,b))) for a,b in zip(border,border[1:]+border[:1])}
    def bending(a, b, normal_a, normal_b):
        angle = normal_a.angle(normal_b)
        if not shape_only and angle > math.radians(55):
            return float('inf')
        return angle*angle*(points[border[a]]-points[border[b]]).length
    for span in range(2, n):
        for i in range(n-span):
            j = i+span
            if not legal[i, j]:
                continue
            for k in range(i+1, j):
                if not legal[i,k] or not legal[k,j] or cross(xy[i], xy[k], xy[j]) <= 1e-12:
                    continue
                a, b, d = (points[border[t]] for t in (i, k, j))
                area = (b-a).cross(d-a).length/2
                if area < 1e-12:
                    continue
                quality = ((b-a).length_squared+(d-b).length_squared+(a-d).length_squared)/(4*math.sqrt(3)*area)
                normal_k = (b-a).cross(d-a).normalized()
                key = (i,j,k)
                total = quality if shape_only else quality*1e-9
                child_states = []
                for a_id,b_id in ((i,k),(k,j),(i,j)):
                    edge = tuple(sorted((border[a_id],border[b_id])))
                    if edge in boundary_set and not shape_only:
                        total += bending(a_id,b_id,normal_k,neighbors[edge])
                for a_id,b_id in ((i,k),(k,j)):
                    if b_id-a_id < 2:
                        continue
                    child_options = [(costs[child] + (0 if shape_only else bending(a_id,b_id,normal_k,normals[child])),child)
                                     for child in choices_by_edge[a_id,b_id]]
                    if not child_options:
                        total = float('inf')
                        break
                    value, child = min(child_options)
                    total += value
                    child_states.append(child)
                if math.isfinite(total):
                    costs[key], splits[key], normals[key], quality_values[key] = total,child_states,normal_k,quality
                    choices_by_edge[i,j].append(key)
    if not choices_by_edge[0,n-1]:
        raise ValueError('NO_SAFE_CAP_BOUNDARY_TRIANGULATION')
    faces = []
    final = min(choices_by_edge[0,n-1],key=lambda key:(costs[key],key))
    def emit(key):
        i,j,k = key
        faces.append((border[i],border[k],border[j]))
        for child in splits[key]:
            emit(child)
    emit(final)
    return faces, dict(method='SHAPE_COST_REJECTED_TRIAL' if shape_only else 'FIXED_PERIMETER_BOUNDARY_AWARE_MINIMUM_DIHEDRAL_DP',
                       objectiveCost=costs[final], planeCenter=center.tolist(), planeNormal=list(normal),
                       maximumBoundaryPlaneResidualMeters=max(abs((p-Vector(center)).dot(normal)) for p in (points[i] for i in border)))


def build(source, report, shape_only=False):
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('CAP_REPLACEMENT_ALREADY_EXISTS')
    operation = extract(source, report)
    points = [source.matrix_world@v.co for v in source.data.vertices]
    replacement, recipe = triangulate_boundary(points, operation['boundaryVertices'],outside_normals(source,operation),shape_only)
    removed_faces, removed_vertices = set(operation['removedFaces']), set(operation['removedInteriorVertices'])
    kept = [i for i in range(len(points)) if i not in removed_vertices]
    lookup = {old:new for new,old in enumerate(kept)}
    faces = [tuple(lookup[i] for i in face.vertices) for face in source.data.polygons if face.index not in removed_faces]
    materials = [face.material_index for face in source.data.polygons if face.index not in removed_faces]
    offset = len(faces)
    faces.extend(tuple(lookup[i] for i in face) for face in replacement)
    materials.extend([operation['materialIndex']]*len(replacement))
    mesh = bpy.data.meshes.new(RESULT_OBJECT)
    mesh.from_pydata([points[i] for i in kept],[],faces)
    mesh.update()
    obj = bpy.data.objects.new(RESULT_OBJECT,mesh)
    bpy.context.scene.collection.objects.link(obj)
    for material in source.data.materials:
        mesh.materials.append(material)
    for face, material in zip(mesh.polygons,materials):
        face.material_index = material
    c.base.mark(obj)
    obj['adoptionAllowed'] = False
    obj['rigBound'] = False
    obj['openUnsewnSurface'] = True
    operation.update(recipe=recipe,keptSourceVertices=kept,replacementSourceTriangles=[list(f) for f in replacement],
                     replacementFaceIndices=list(range(offset,len(faces))),originalBodyMovedVertices=0)
    return obj, operation


def bending_local(obj, selected):
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    faces = [tuple(f.vertices) for f in obj.data.polygons]
    edges = prior.prior.edge_faces(faces)
    selected = set(selected)
    values, maximum, creases = 0., 0., 0
    for (a,b),fs in edges.items():
        if len(fs) != 2 or not selected.intersection(fs):
            continue
        angle = obj.data.polygons[fs[0]].normal.angle(obj.data.polygons[fs[1]].normal)
        values += angle*angle*(points[a]-points[b]).length
        maximum = max(maximum,math.degrees(angle))
        creases += angle > math.radians(55)
    return dict(weightedRadiansSquaredMeters=values,maximumDegrees=maximum,edgesAbove55Degrees=creases)


def audit(obj, source, report, op):
    surface.require_locked(obj)
    required = extract(source,report)
    for key, value in required.items():
        if op[key] != value:
            raise ValueError('CAP_PATCH_IDENTITY_RECORD_CHANGED')
    old_points = [source.matrix_world@v.co for v in source.data.vertices]
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    kept = [i for i in range(len(old_points)) if i not in required['removedInteriorVertices']]
    if op['keptSourceVertices'] != kept or len(points) != len(kept):
        raise ValueError('CAP_VERTEX_MAP_CHANGED')
    mapping = {old:new for new,old in enumerate(kept)}
    move = max((p-old_points[i]).length for p,i in zip(points,kept))
    method = op['recipe']['method']
    if method not in ('SHAPE_COST_REJECTED_TRIAL','FIXED_PERIMETER_BOUNDARY_AWARE_MINIMUM_DIHEDRAL_DP'):
        raise ValueError('UNKNOWN_CAP_REPLACEMENT_METHOD')
    replacement, recipe = triangulate_boundary(old_points,required['boundaryVertices'],outside_normals(source,required),method=='SHAPE_COST_REJECTED_TRIAL')
    if op['replacementSourceTriangles'] != [list(f) for f in replacement] or op['recipe'] != recipe:
        raise ValueError('CAP_TRIANGULATION_RECORD_CHANGED')
    removed = set(required['removedFaces'])
    unchanged = [tuple(mapping[i] for i in f.vertices) for f in source.data.polygons if f.index not in removed]
    expected = unchanged+[tuple(mapping[i] for i in f) for f in replacement]
    expected_materials = [f.material_index for f in source.data.polygons if f.index not in removed]+[15]*len(replacement)
    if [tuple(f.vertices) for f in obj.data.polygons] != expected or [f.material_index for f in obj.data.polygons] != expected_materials:
        raise ValueError('CAP_OUTSIDE_TOPOLOGY_OR_REGION_CHANGED')
    selected = list(range(len(unchanged),len(expected)))
    if op['replacementFaceIndices'] != selected:
        raise ValueError('CAP_FACE_MAP_CHANGED')
    edges = prior.prior.edge_faces(expected)
    if any(tuple(sorted(mapping[i] for i in edge)) not in edges for edge in required['protectedEdges']):
        raise ValueError('PROTECTED_LAYOUT_EDGE_REMOVED')
    before = bending_local(source,required['removedFaces'])
    after = bending_local(obj,selected)
    pairs, triangles = prior.prior.prior.collision_pairs(obj)
    tree = c.fit.bvh(obj)[0]
    chart = bpy.data.objects[branch.RESULT_OBJECT]
    chart_tree,chart_points,chart_triangles = c.fit.bvh(chart)
    samples = points+[sum((points[i] for i in t),Vector())/3 for t in triangles]
    samples += [(points[a]+points[b])/2 for a,b in edges]
    forward = max(chart_tree.find_nearest(p)[3] for p in samples)
    reverse = max(tree.find_nearest(p)[3] for p in chart_points+[sum((chart_points[i] for i in t),Vector())/3 for t in chart_triangles])
    source_tree,_,_ = c.fit.bvh(source)
    cap_samples = [sum((points[i] for i in obj.data.polygons[f].vertices),Vector())/3 for f in selected]
    cap_samples += [(points[a]+points[b])/2 for a,b in edges if set(edges[a,b]).intersection(selected)]
    old_samples = [old_points[i] for i in required['removedInteriorVertices']]
    old_samples += [sum((old_points[i] for i in source.data.polygons[f].vertices),Vector())/3 for f in required['removedFaces']]
    before_global = prior.prior.prior.bending(source,{})
    after_global = prior.prior.prior.bending(obj,{})
    topology = branch.s.prior.prior.boundaries(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    orient = sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
    bm.free()
    qa = dict(vertices=len(points),triangles=len(expected),removedTriangles=len(removed),replacementTriangles=len(replacement),
              removedInteriorVertices=len(required['removedInteriorVertices']),preservedPatchBoundaryVertices=len(required['boundaryVertices']),
              maximumRetainedVertexMoveMeters=move,preservedLayoutEdges=len(required['protectedEdges']),
              capBefore=before,capAfter=after,beforeBending=before_global,afterBending=after_global,
              maximumForwardOriginalChartSampleErrorMeters=forward,maximumReverseOriginalChartSampleErrorMeters=reverse,
              maximumNewCapToSourceStudySampleErrorMeters=max(source_tree.find_nearest(p)[3] for p in cap_samples),
              maximumRemovedCapToNewPatchSampleErrorMeters=max(tree.find_nearest(p)[3] for p in old_samples),
              connectedComponents=len(topology['components']),boundaryLoops=len(topology['boundaryLoops']),euler=topology['euler'],
              nonAdjacentSelfIntersectionPairs=len(pairs),nonContiguousInteriorEdges=orient,zeroAreaFaces=topology['zeroAreaFaces'],
              originalBodyMovedVertices=0,geometryShapeChanged=True,capMicroCreaseRemoved=after['edgesAbove55Degrees']==0,
              fullUnderarmRebuilt=False,majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False)
    qa['eligible'] = move < 1e-8 and not pairs and not orient and not qa['zeroAreaFaces'] and qa['connectedComponents']==1 and qa['boundaryLoops']==2 and qa['euler']==0 and max(forward,reverse)<=MAX_ERROR and after['edgesAbove55Degrees']==0 and after['weightedRadiansSquaredMeters']<before['weightedRadiansSquaredMeters'] and after_global['weightedRadiansSquaredMeters']<before_global['weightedRadiansSquaredMeters']
    return qa


def render_close(folder, source, selected_faces, target, normal):
    scene = bpy.context.scene
    for old in scene.objects:
        if old.type in ('MESH','CURVE'):
            old.hide_render = old != source
    data = bpy.data.curves.new('CapPatchWire_RENDER_ONLY','CURVE')
    data.dimensions = '3D'
    data.bevel_depth = .000025
    data.bevel_resolution = 1
    edges = prior.prior.edge_faces([tuple(source.data.polygons[fi].vertices) for fi in selected_faces])
    for a,b in edges:
        spline = data.splines.new('POLY')
        spline.points.add(1)
        for p,i in zip(spline.points,(a,b)):
            p.co = (*(source.matrix_world@source.data.vertices[i].co),1)
    wire = bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(wire)
    data.materials.append(c.base.material(data.name,surface.linear_color('FFFFFF')))
    records = []
    for label, delta in [('normal',normal*.12),('oblique_wire',normal*.10+Vector((-.05,-.02,.03)))]:
        wire.hide_render = label == 'normal'
        scene.camera.location = target+delta
        scene.camera.data.ortho_scale = .037
        scene.camera.rotation_euler = (target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path = folder/('cap_'+label+'.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records.append(dict(file=path.name,sha256=c.base.sha(path)))
    bpy.data.objects.remove(wire,do_unlink=True)
    bpy.data.curves.remove(data)
    return records


def run(args):
    source_path, output = args.source.resolve(),args.output.resolve()
    if c.base.sha(source_path) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    report_path = source_path.parent/'deformation-layout-report.json'
    if c.base.sha(report_path) != REPORT_SHA:
        raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    turnaround = args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround) != prior.panel.TURNAROUND_SHA:
        raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=prior.panel.TURNAROUND_SHA))
    report = json.loads(report_path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    surface.require_locked(bpy.context.scene)
    originals = [o for o in bpy.context.scene.objects if o.type=='MESH']
    digest = c.guide.digest(originals)
    signatures = {o.name:surface.repair.invariant_signature(o) for o in originals}
    visible = [o for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()]
    old = bpy.data.objects[prior.RESULT_OBJECT]
    obj,op = build(old,report)
    qa = audit(obj,old,report,op)
    print(json.dumps(qa,indent=2),flush=True)
    if not qa['eligible']:
        raise ValueError('CAP_REPLACEMENT_QA_REJECTED')
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        for label,item in [('before',old),('after',obj)]:
            folder = output/label
            folder.mkdir()
            for row in branch.render(folder,item,[]):
                renders.append(dict(file=label+'/'+row['file'],sha256=row['sha256']))
        for label,item,selected in [('before_close',old,op['removedFaces']),('after_close',obj,op['replacementFaceIndices'])]:
            folder = output/label
            folder.mkdir()
            for row in render_close(folder,item,selected,Vector(op['recipe']['planeCenter']),Vector(op['recipe']['planeNormal'])):
                renders.append(dict(file=label+'/'+row['file'],sha256=row['sha256']))
    if digest != c.guide.digest(originals) or any(signatures[o.name] != surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for item in bpy.context.scene.objects:
        if item.type in ('MESH','CURVE'):
            item.hide_render = item not in visible
    obj.hide_set(True)
    bpy.context.preferences.filepaths.save_version = 0
    # Runtime-only: do not attempt a thumbnail cache write outside the workspace.
    bpy.context.preferences.filepaths.file_preview_type = 'NONE'
    blend = output/'CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    result = dict(strategyId=STRATEGY,status='LOCAL_CAP_REPLACEMENT_QA_PASS_PENDING_VISUAL_REVIEW',**c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                  operation=op,qa=qa,originalsPreserved=True,adoptionAllowed=False,completeShoulderPanel=False,
                  rigBound=False,fullCharacterScore=None,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                  limitations=['CAP_MICRO_CREASE_DISK_ONLY_NOT_FULL_SHOULDER_OR_UNDERARM_REBUILD','FINITE_CUMULATIVE_ORIGINAL_CHART_SAMPLES',
                               'OPEN_UNOFFSET_SURFACE_NO_UV_SEWING_THICKNESS_OR_DEFORMATION_APPROVAL'])
    (output/'cap-replacement-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 boundary-locked cap patch replacement — NOT PRODUCTION\nThe classified cap micro-crease disk is replaced with real triangles, keeping its perimeter and all layout boundaries fixed.\nOriginal meshes/UV/materials/weights are unchanged; the new study is hidden and the prior assembly remains visible.\nThis is not full underarm/shoulder rebuilding, a garment, rig or new full-character score. Gate B pending; Unity/production disabled.\n',encoding='utf-8')
    print(json.dumps(dict(blendSha256=result['blendSha256'],qa=qa)),flush=True)
    return result


if __name__=='__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
