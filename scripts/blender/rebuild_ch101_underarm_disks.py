"""Independent, domain-locked underarm disks; not complete shoulder rebuilding."""
import argparse
from collections import defaultdict, Counter
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import rebuild_ch101_cap_patch as cap
c,surface,branch = cap.c,cap.surface,cap.branch
layout,edgeflow,fair = cap.prior,cap.prior.prior,cap.prior.prior.prior
SOURCE_SHA = '7ece194c1fd5d7ea3f02c46f54cf38aeaf9538403af3ebd945b676afa4331cd0'
REPORT_SHA = '47df4f246311d2eea4166216787e110d9365c8fb26677b98b182fc670f162415'
LAYOUT_SHA = 'ed9f9e3b5e0451a190401868e230f7c0258561c4a860acc7fd5af5633527d3ea'
RESULT_OBJECT = 'CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION'
STRATEGY = 'CH101_DOMAIN_LOCKED_UNDERARM_DISK_REPLACEMENT_V001'
MAX_ERROR = .0015
GUIDE_PREFIX = 'UNDERARM_DISK_GUIDE_'


def context(source,cap_report,layout_report):
    surface.require_locked(source)
    source_faces = [tuple(f.vertices) for f in source.data.polygons]
    edges = edgeflow.edge_faces(source_faces)
    protected = {e for e,fs in edges.items() if len(fs)==1 or len({source.data.polygons[i].material_index for i in fs})>1}
    protected_vertices = {i for e in protected for i in e}
    maps = cap_report['operation']['keptSourceVertices']
    if len(maps)!=len(source.data.vertices) or len(set(maps))!=len(maps):
        raise ValueError('UPSTREAM_VERTEX_MAP_CHANGED')
    groups = [g for g in layout_report['design']['majorFoldGroups'] if g['policy']=='REDESIGN_UNDERARM_NETWORK']
    if len(groups)!=1 or groups[0]['id']!=193 or len(groups[0]['sourceEdges'])!=44:
        raise ValueError('UNDERARM_POLICY_CHANGED')
    old_seeds = {i for e in groups[0]['sourceEdges'] for i in e}
    seeds = []
    for i,j in enumerate(maps):
        p = layout_report['operation']['vertexProvenance'][j]
        if p['sourceEdge'][0]==p['sourceEdge'][1] and p['sourceEdge'][0] in old_seeds:
            seeds.append(i)
    if len(seeds)!=45:
        raise ValueError('UNDERARM_SEED_MAP_CHANGED')
    vertex_faces = defaultdict(set)
    neighbors = defaultdict(set)
    for f in source.data.polygons:
        for i in f.vertices:
            vertex_faces[i].add(f.index)
    for fs in edges.values():
        if len(fs)==2:
            a,b=fs
            neighbors[a].add(b)
            neighbors[b].add(a)
    return dict(faces=source_faces,edges=edges,protectedEdges=protected,
                protectedVertices=protected_vertices,seeds=seeds,vertexFaces=vertex_faces,neighbors=neighbors)


def disk(source,ctx,seed):
    if seed not in ctx['seeds']:
        raise ValueError('NOT_AN_UNDERARM_SEED')
    if seed in ctx['protectedVertices']:
        raise ValueError('PROTECTED_LAYOUT_VERTEX')
    selected = sorted(ctx['vertexFaces'][seed])
    materials = {source.data.polygons[i].material_index for i in selected}
    if len(materials)!=1 or not materials<={4,5,6,7}:
        raise ValueError('DISK_CROSSES_DOMAIN')
    faces = [ctx['faces'][i] for i in selected]
    edges = edgeflow.edge_faces(faces)
    border_edges = {e for e,fs in edges.items() if len(fs)==1}
    successor = {}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            if tuple(sorted((a,b))) in border_edges:
                if a in successor:
                    raise ValueError('DISK_BOUNDARY_BRANCH')
                successor[a]=b
    if len(successor)!=len(border_edges) or not successor:
        raise ValueError('DISK_BOUNDARY_INVALID')
    border=[min(successor)]
    while successor[border[-1]]!=border[0]:
        nxt=successor[border[-1]]
        if nxt in border:
            raise ValueError('DISK_BOUNDARY_LOOP')
        border.append(nxt)
    vertices={i for f in faces for i in f}
    if set(border)!=set(successor) or vertices-set(border)!={seed} or len(vertices)-len(edges)+len(faces)!=1:
        raise ValueError('NOT_ONE_INTERIOR_VERTEX_DISK')
    points=[source.matrix_world@v.co for v in source.data.vertices]
    triangles,recipe=cap.triangulate_boundary(points,border,cap.outside_normals(source,dict(removedFaces=selected,boundaryVertices=border)))
    before=cap.bending_local(source,selected)
    if before['weightedRadiansSquaredMeters']-recipe['objectiveCost']<=1e-7:
        raise ValueError('NO_PREDICTED_BENDING_IMPROVEMENT')
    return dict(seedVertex=seed,domain=next(iter(materials)),removedFaces=selected,boundaryVertices=border,
                replacementSourceTriangles=[list(f) for f in triangles],recipe=recipe,
                sourceBending=before,predictedGain=before['weightedRadiansSquaredMeters']-recipe['objectiveCost'])


def validate_disks(source,ctx,disks):
    if not disks:
        raise ValueError('NO_REPLACEMENT_DISKS')
    blocked=set()
    seeds=set()
    for row in disks:
        if row!=disk(source,ctx,row['seedVertex']):
            raise ValueError('DISK_PROVENANCE_CHANGED')
        selected=set(row['removedFaces'])
        if row['seedVertex'] in seeds or selected&blocked:
            raise ValueError('DISK_NEIGHBORHOODS_OVERLAP')
        seeds.add(row['seedVertex'])
        blocked.update(selected)
        blocked.update(j for i in selected for j in ctx['neighbors'][i])


def compose(source,ctx,disks,name=RESULT_OBJECT):
    validate_disks(source,ctx,disks)
    if bpy.data.objects.get(name):
        raise ValueError('UNDERARM_OBJECT_ALREADY_EXISTS')
    removed_faces={i for row in disks for i in row['removedFaces']}
    removed_vertices={row['seedVertex'] for row in disks}
    kept=[i for i in range(len(source.data.vertices)) if i not in removed_vertices]
    mapping={old:new for new,old in enumerate(kept)}
    source_face_map=[i for i in range(len(source.data.polygons)) if i not in removed_faces]
    faces=[tuple(mapping[i] for i in ctx['faces'][fi]) for fi in source_face_map]
    materials=[source.data.polygons[fi].material_index for fi in source_face_map]
    patch_faces=[]
    for row in disks:
        first=len(faces)
        faces.extend(tuple(mapping[i] for i in f) for f in row['replacementSourceTriangles'])
        materials.extend([row['domain']]*len(row['replacementSourceTriangles']))
        patch_faces.append(list(range(first,len(faces))))
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([source.matrix_world@source.data.vertices[i].co for i in kept],[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.scene.collection.objects.link(obj)
    for material in source.data.materials:
        mesh.materials.append(material)
    for face,material in zip(mesh.polygons,materials):
        face.material_index=material
    c.base.mark(obj)
    obj['adoptionAllowed']=False
    obj['rigBound']=False
    obj['openUnsewnSurface']=True
    op=dict(disks=disks,keptSourceVertices=kept,unchangedSourceFaceIndices=source_face_map,
            patchFaceIndices=patch_faces,protectedSourceEdges=[list(e) for e in sorted(ctx['protectedEdges'])])
    return obj,op


def audit(obj,source,cap_report,layout_report,op,require_selection=False):
    surface.require_locked(obj)
    ctx=context(source,cap_report,layout_report)
    disks=op['disks']
    validate_disks(source,ctx,disks)
    if require_selection:
        decisions=op.get('selectionDecisions')
        if decisions is None:
            raise ValueError('MISSING_SELECTION_RECORD')
        allowed={'REJECTED_CANDIDATE','SKIPPED_NEIGHBOR_OVERLAP','REJECTED_GLOBAL_QA','ACCEPTED'}
        if op.get('candidateSeedCount')!=len(ctx['seeds']) or sorted(r['seedVertex'] for r in decisions)!=sorted(ctx['seeds']) or any(r['status'] not in allowed for r in decisions):
            raise ValueError('SELECTION_RECORD_CHANGED')
        if {r['seedVertex'] for r in decisions if r['status']=='ACCEPTED'}!={r['seedVertex'] for r in disks}:
            raise ValueError('SELECTION_RECORD_CHANGED')
        for row in decisions:
            if row['status']=='ACCEPTED' and (not row['patchQAPassed'] or row['nonAdjacentSelfIntersectionPairs']!=0 or any(not math.isfinite(row[k]) or row[k]>MAX_ERROR for k in ('maximumForwardOriginalChartSampleErrorMeters','maximumReverseOriginalChartSampleErrorMeters'))):
                raise ValueError('ACCEPTED_DECISION_EXCEEDS_QA')
    removed_faces={i for row in disks for i in row['removedFaces']}
    removed_vertices={row['seedVertex'] for row in disks}
    kept=[i for i in range(len(source.data.vertices)) if i not in removed_vertices]
    if op['keptSourceVertices']!=kept or op['protectedSourceEdges']!=[list(e) for e in sorted(ctx['protectedEdges'])]:
        raise ValueError('UNDERARM_SOURCE_MAP_CHANGED')
    mapping={old:new for new,old in enumerate(kept)}
    original_face_map=[i for i in range(len(ctx['faces'])) if i not in removed_faces]
    expected=[tuple(mapping[i] for i in ctx['faces'][fi]) for fi in original_face_map]
    materials=[source.data.polygons[fi].material_index for fi in original_face_map]
    expected_patches=[]
    for row in disks:
        start=len(expected)
        expected.extend(tuple(mapping[i] for i in f) for f in row['replacementSourceTriangles'])
        materials.extend([row['domain']]*len(row['replacementSourceTriangles']))
        expected_patches.append(list(range(start,len(expected))))
    if op['unchangedSourceFaceIndices']!=original_face_map or op['patchFaceIndices']!=expected_patches:
        raise ValueError('UNDERARM_FACE_MAP_CHANGED')
    if [tuple(f.vertices) for f in obj.data.polygons]!=expected or [f.material_index for f in obj.data.polygons]!=materials:
        raise ValueError('UNDERARM_OUTSIDE_TOPOLOGY_OR_REGION_CHANGED')
    if len(obj.data.vertices)!=len(kept):
        raise ValueError('UNDERARM_VERTEX_COUNT_CHANGED')
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    old_points=[source.matrix_world@v.co for v in source.data.vertices]
    if any(not math.isfinite(value) for point in points for value in point):
        raise ValueError('NONFINITE_UNDERARM_VERTEX')
    move=max((p-old_points[i]).length for p,i in zip(points,kept))
    edges=edgeflow.edge_faces(expected)
    if any(tuple(sorted(mapping[i] for i in e)) not in edges for e in ctx['protectedEdges']):
        raise ValueError('PROTECTED_LAYOUT_EDGE_REMOVED')
    if removed_faces&set(cap_report['operation']['replacementFaceIndices']):
        raise ValueError('PREVIOUS_CAP_PATCH_CHANGED')
    patch_qa=[]
    for row,new_faces in zip(disks,expected_patches):
        after=cap.bending_local(obj,new_faces)
        before=cap.bending_local(source,row['removedFaces'])
        patch_qa.append(dict(seedVertex=row['seedVertex'],domain=row['domain'],
                             sourceTriangles=len(row['removedFaces']),replacementTriangles=len(new_faces),
                             boundaryVertices=len(row['boundaryVertices']),before=before,after=after,
                             eligible=after['maximumDegrees']<=55+1e-4 and after['edgesAbove55Degrees']==0
                                      and after['weightedRadiansSquaredMeters']<before['weightedRadiansSquaredMeters']-1e-7))
    pairs,triangles=fair.collision_pairs(obj)
    tree=c.fit.bvh(obj)[0]
    chart=bpy.data.objects[branch.RESULT_OBJECT]
    reference,reference_points,reference_triangles=c.fit.bvh(chart)
    samples=points+[sum((points[i] for i in t),Vector())/3 for t in triangles]
    samples.extend((points[a]+points[b])/2 for a,b in edges)
    forward=max(reference.find_nearest(p)[3] for p in samples)
    reverse_samples=reference_points+[sum((reference_points[i] for i in t),Vector())/3 for t in reference_triangles]
    reverse=max(tree.find_nearest(p)[3] for p in reverse_samples)
    old_tree=c.fit.bvh(source)[0]
    new_patch_samples=[sum((points[i] for i in obj.data.polygons[fi].vertices),Vector())/3 for group in expected_patches for fi in group]
    changed_faces={i for group in expected_patches for i in group}
    new_patch_samples.extend((points[a]+points[b])/2 for a,b in edges if set(edges[a,b])&changed_faces)
    old_patch_samples=[old_points[i] for i in removed_vertices]
    old_patch_samples.extend(sum((old_points[i] for i in source.data.polygons[fi].vertices),Vector())/3 for fi in removed_faces)
    before_global=fair.bending(source,{})
    after_global=fair.bending(obj,{})
    topology=branch.s.prior.prior.boundaries(obj)
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    orient=sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
    bm.free()
    qa=dict(vertices=len(points),triangles=len(expected),patchCount=len(disks),removedInteriorVertices=len(removed_vertices),
            removedTriangles=len(removed_faces),replacementTriangles=sum(len(g) for g in expected_patches),
            touchedDomains=sorted({row['domain'] for row in disks}),preservedLayoutEdges=len(ctx['protectedEdges']),
            maximumRetainedVertexMoveMeters=move,patches=patch_qa,beforeBending=before_global,afterBending=after_global,
            maximumForwardOriginalChartSampleErrorMeters=forward,maximumReverseOriginalChartSampleErrorMeters=reverse,
            forwardSampleCount=len(samples),reverseSampleCount=len(reverse_samples),
            maximumNewPatchToSourceStudySampleErrorMeters=max(old_tree.find_nearest(p)[3] for p in new_patch_samples),
            maximumRemovedPatchToNewSurfaceSampleErrorMeters=max(tree.find_nearest(p)[3] for p in old_patch_samples),
            nonAdjacentSelfIntersectionPairs=len(pairs),nonContiguousInteriorEdges=orient,zeroAreaFaces=topology['zeroAreaFaces'],
            connectedComponents=len(topology['components']),boundaryLoops=len(topology['boundaryLoops']),euler=topology['euler'],
            previousCapPatchPreserved=True,originalBodyMovedVertices=0,geometryShapeChanged=True,fullUnderarmRebuilt=False,
            majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False)
    qa['eligible']=move<1e-8 and all(r['eligible'] for r in patch_qa) and not pairs and not orient and not qa['zeroAreaFaces'] and qa['connectedComponents']==1 and qa['boundaryLoops']==2 and qa['euler']==0 and max(forward,reverse)<=MAX_ERROR and after_global['weightedRadiansSquaredMeters']<before_global['weightedRadiansSquaredMeters']-1e-7
    return qa


def discard(obj):
    mesh=obj.data
    bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.meshes.remove(mesh)


def build(source,cap_report,layout_report):
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('UNDERARM_OBJECT_ALREADY_EXISTS')
    ctx=context(source,cap_report,layout_report)
    candidates,decisions=[],[]
    for seed in ctx['seeds']:
        try:
            candidates.append(disk(source,ctx,seed))
        except ValueError as error:
            decisions.append(dict(seedVertex=seed,status='REJECTED_CANDIDATE',reason=str(error)))
    candidates.sort(key=lambda row:(-row['predictedGain'],row['seedVertex']))
    accepted=[]
    blocked=set()
    for row in candidates:
        if set(row['removedFaces'])&blocked:
            decisions.append(dict(seedVertex=row['seedVertex'],status='SKIPPED_NEIGHBOR_OVERLAP'))
            continue
        trial,op=compose(source,ctx,accepted+[row],RESULT_OBJECT+'_TRIAL')
        try:
            qa=audit(trial,source,cap_report,layout_report,op)
        finally:
            discard(trial)
        decisions.append(dict(seedVertex=row['seedVertex'],status='ACCEPTED' if qa['eligible'] else 'REJECTED_GLOBAL_QA',
                              maximumForwardOriginalChartSampleErrorMeters=qa['maximumForwardOriginalChartSampleErrorMeters'],
                              maximumReverseOriginalChartSampleErrorMeters=qa['maximumReverseOriginalChartSampleErrorMeters'],
                              nonAdjacentSelfIntersectionPairs=qa['nonAdjacentSelfIntersectionPairs'],
                              patchQAPassed=all(p['eligible'] for p in qa['patches'])))
        print('DISK_DECISION',json.dumps(decisions[-1]),flush=True)
        if qa['eligible']:
            accepted.append(row)
            selected=set(row['removedFaces'])
            blocked.update(selected)
            blocked.update(j for i in selected for j in ctx['neighbors'][i])
    if not accepted:
        raise ValueError('NO_UNDERARM_DISK_PASSES:'+json.dumps(decisions))
    obj,op=compose(source,ctx,accepted)
    op['selectionDecisions']=decisions
    op['candidateSeedCount']=len(ctx['seeds'])
    op['selectionMethod']='DESCENDING_LOCAL_GAIN_WITH_DISJOINT_ONE_FACE_GUARD_AND_FULL_CUMULATIVE_QA'
    return obj,op


def guides(source,op):
    result=[]
    colors=['E9AD46','42C7DA','D863B5','85D05B']
    for row in op['disks']:
        points=[source.matrix_world@source.data.vertices[i].co for i in row['boundaryVertices']]
        obj=branch.curve(GUIDE_PREFIX+str(row['seedVertex']),points,colors[row['domain']-4],True)
        result.append(obj)
    return result


def audit_guides(source,op):
    expected={GUIDE_PREFIX+str(row['seedVertex']):row for row in op['disks']}
    actual={o.name:o for o in bpy.context.scene.objects if o.name.startswith(GUIDE_PREFIX)}
    if set(actual)!=set(expected):
        raise ValueError('UNDERARM_GUIDE_SET_CHANGED')
    maximum=0.
    for name,row in expected.items():
        obj=actual[name]
        surface.require_locked(obj)
        if obj.type!='CURVE' or not obj.get('guideOnly') or len(obj.data.splines)!=1:
            raise ValueError('UNDERARM_GUIDE_STRUCTURE_CHANGED')
        spline=obj.data.splines[0]
        if spline.type!='POLY' or not spline.use_cyclic_u or len(spline.points)!=len(row['boundaryVertices']):
            raise ValueError('UNDERARM_GUIDE_STRUCTURE_CHANGED')
        for p,i in zip(spline.points,row['boundaryVertices']):
            target=source.matrix_world@source.data.vertices[i].co
            distance=(obj.matrix_world@Vector(p.co[:3])-target).length
            if not math.isfinite(distance):
                raise ValueError('UNDERARM_GUIDE_POSITION_CHANGED')
            maximum=max(maximum,distance)
    if maximum>1e-6:
        raise ValueError('UNDERARM_GUIDE_POSITION_CHANGED')
    return dict(guideCount=len(actual),maximumPositionErrorMeters=maximum)


def render_focus(folder,obj,selected,target):
    scene=bpy.context.scene
    for old in scene.objects:
        if old.type in ('MESH','CURVE'):
            old.hide_render=old!=obj
    data=bpy.data.curves.new('UnderarmWire_RENDER_ONLY','CURVE')
    data.dimensions='3D'
    data.bevel_depth=.00007
    data.bevel_resolution=1
    edges=edgeflow.edge_faces([tuple(obj.data.polygons[fi].vertices) for fi in selected])
    for a,b in edges:
        spline=data.splines.new('POLY')
        spline.points.add(1)
        for p,i in zip(spline.points,(a,b)):
            p.co=(*(obj.matrix_world@obj.data.vertices[i].co),1)
    wire=bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(wire)
    material=c.base.material(data.name,surface.linear_color('FFFFFF'))
    data.materials.append(material)
    records=[]
    for name,delta in [('side_wire',Vector((-.5,0,.03))),('back_wire',Vector((0,.5,.03)))]:
        scene.camera.location=target+delta
        scene.camera.data.ortho_scale=.16
        scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path=folder/(name+'.png')
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        records.append(dict(file=path.name,sha256=c.base.sha(path)))
    bpy.data.objects.remove(wire,do_unlink=True)
    bpy.data.curves.remove(data)
    bpy.data.materials.remove(material)
    return records


def run(args):
    source_path,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source_path)!=SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    report_path=source_path.parent/'cap-replacement-report.json'
    if c.base.sha(report_path)!=REPORT_SHA:
        raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if c.base.sha(args.layout_report)!=LAYOUT_SHA:
        raise ValueError('LAYOUT_REPORT_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=layout.panel.TURNAROUND_SHA:
        raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=layout.panel.TURNAROUND_SHA))
    cap_report=json.loads(report_path.read_text())
    layout_report=json.loads(args.layout_report.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    visible=[o for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()]
    old=bpy.data.objects[cap.RESULT_OBJECT]
    obj,op=build(old,cap_report,layout_report)
    qa=audit(obj,old,cap_report,layout_report,op,require_selection=True)
    if not qa['eligible']:
        raise ValueError('FINAL_UNDERARM_QA_REJECTED')
    lines=guides(old,op)
    guide_qa=audit_guides(old,op)
    output.mkdir(parents=True)
    renders=[]
    if not args.no_render:
        for label,item in [('before',old),('after',obj)]:
            folder=output/label
            folder.mkdir()
            for row in branch.render(folder,item,[]):
                renders.append(dict(file=label+'/'+row['file'],sha256=row['sha256']))
        ghost,material=layout.fold_review_ghost(obj)
        folder=output/'patches'
        folder.mkdir()
        for row in branch.render(folder,ghost,lines):
            renders.append(dict(file='patches/'+row['file'],sha256=row['sha256']))
        mesh=ghost.data
        bpy.data.objects.remove(ghost,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.materials.remove(material)
        target=sum((old.matrix_world@old.data.vertices[row['seedVertex']].co for row in op['disks']),Vector())/len(op['disks'])
        for label,item,selected in [('before_close',old,[i for row in op['disks'] for i in row['removedFaces']]),
                                    ('after_close',obj,[i for group in op['patchFaceIndices'] for i in group])]:
            folder=output/label
            folder.mkdir()
            for row in render_focus(folder,item,selected,target):
                renders.append(dict(file=label+'/'+row['file'],sha256=row['sha256']))
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for item in bpy.context.scene.objects:
        if item.type in ('MESH','CURVE'):
            item.hide_render=item not in visible
    obj.hide_set(True)
    for line in lines:
        line.hide_set(True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.preferences.filepaths.file_preview_type='NONE'
    blend=output/'CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    result=dict(strategyId=STRATEGY,status='LOCAL_UNDERARM_DISKS_QA_PASS_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,layoutReportSha256=LAYOUT_SHA,
                artCommit=c.base.ART_COMMIT,references=refs,operation=op,qa=qa,guideQA=guide_qa,originalsPreserved=True,
                adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['INDEPENDENT_LOCAL_DISKS_NOT_BROAD_UNDERARM_SUPPORT_CURVE_REBUILD','RESIDUAL_MAJOR_FOLDS_AND_PROVISIONAL_TORSO_BORDER',
                             'FINITE_CUMULATIVE_SOURCE_SAMPLES','OPEN_UNOFFSET_SURFACE_NO_UV_THICKNESS_RIG_OR_GARMENT_APPROVAL'])
    (output/'underarm-disks-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 domain-locked local underarm disk replacement — NOT PRODUCTION\nIndependent disks preserve all course/domain borders and the preceding cap patch. The cumulative original-chart surface bound remains 1.5 mm.\nOriginal geometry/UV/materials/weights remain untouched. Prior assembly stays visible; new study and UNDERARM_DISK_GUIDE_* curves are hidden.\nThis is not broad underarm/shoulder rebuilding, a sewn garment, rig/deformation approval or a full-character quality score. Gate B pending; Unity/production disabled.\n',encoding='utf-8')
    print(json.dumps(dict(blendSha256=result['blendSha256'],qa=qa),indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--layout-report',type=Path,required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
