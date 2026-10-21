"""Boundary-locked multi-interior underarm panels, not one-vertex stars."""
import argparse
import copy
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import design_ch101_underarm_support_curves as support

prior=support.prior
cap,c,surface,branch=prior.cap,prior.c,prior.surface,prior.branch
layout,fair,edgeflow=prior.layout,prior.fair,prior.edgeflow
SOURCE_SHA='ef10dda26d6d54770b8a3f45d2919f96a39782825ad9121d93053024bc0d0930'
REPORT_SHA='9fabffce970e35917ff320751fa219c27f83108e9b3f1180aa48fe0f3a13b689'
RESULT_OBJECT='CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION'
STRATEGY='CH101_BOUNDARY_LOCKED_MULTI_INTERIOR_UNDERARM_PANELS_V001'
LIMIT=.0015
MAX_BOUNDARY=32
GUIDE_PREFIX='UNDERARM_PANEL_BOUNDARY_'


def context(source,disk_report,cap_report,layout_report,curve_report):
    surface.require_locked(source)
    faces=[tuple(f.vertices) for f in source.data.polygons]
    ef=edgeflow.edge_faces(faces)
    protected={e for e,fs in ef.items() if len(fs)==1 or len({source.data.polygons[fi].material_index for fi in fs})>1}
    preserved={i for group in disk_report['operation']['patchFaceIndices'] for i in group}
    cap_faces=set(cap_report['operation']['replacementFaceIndices'])
    preserved.update(i for i,j in enumerate(disk_report['operation']['unchangedSourceFaceIndices']) if j in cap_faces)
    if len(protected)!=907 or len(preserved)!=50:
        raise ValueError('UPSTREAM_PRESERVATION_SET_CHANGED')
    old_fold=next(g for g in layout_report['design']['majorFoldGroups'] if g['id']==193)
    fold_vertices={i for e in old_fold['sourceEdges'] for i in e}
    dmap=disk_report['operation']['keptSourceVertices']
    cmap=cap_report['operation']['keptSourceVertices']
    if len(dmap)!=len(source.data.vertices) or len(set(dmap))!=len(dmap):
        raise ValueError('INVALID_UPSTREAM_VERTEX_MAP')
    records=layout_report['operation']['vertexProvenance']
    seeds=[]
    for i,j in enumerate(dmap):
        rec=records[cmap[j]]
        if rec['sourceEdge'][0]==rec['sourceEdge'][1] and rec['sourceEdge'][0] in fold_vertices:
            seeds.append(i)
    if len(seeds)!=40:
        raise ValueError('UNDERARM_SEED_PROVENANCE_CHANGED')
    neighbors=defaultdict(set)
    vf=defaultdict(set)
    for f in source.data.polygons:
        for i in f.vertices:
            vf[i].add(f.index)
    for e,fs in ef.items():
        if len(fs)==2 and e not in protected and not set(fs)&preserved:
            a,b=fs
            neighbors[a].add(b)
            neighbors[b].add(a)
    points=[source.matrix_world@v.co for v in source.data.vertices]
    curves=[row['selectedPoints'] for row in curve_report['design']['courses']]
    proximity={i:min(support.distances([list(points[i])],curve)[0] for curve in curves) for i in seeds}
    return dict(faces=faces,edges=ef,protectedEdges=protected,preservedFaces=preserved,
                seeds=seeds,neighbors=neighbors,vertexFaces=vf,points=points,guideProximity=proximity)


def boundary(source,ctx,selected):
    selected=sorted(set(selected))
    if set(selected)&ctx['preservedFaces']:
        raise ValueError('PREVIOUS_PATCH_TOUCHED')
    materials={source.data.polygons[i].material_index for i in selected}
    if len(materials)!=1 or not materials<={4,5,6,7}:
        raise ValueError('PATCH_CROSSES_DOMAIN')
    faces=[ctx['faces'][i] for i in selected]
    ef=edgeflow.edge_faces(faces)
    if any(len(fs)>2 for fs in ef.values()):
        raise ValueError('PATCH_NONMANIFOLD')
    border_edges={e for e,fs in ef.items() if len(fs)==1}
    successor={}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            if tuple(sorted((a,b))) in border_edges:
                if a in successor:
                    raise ValueError('PATCH_BOUNDARY_BRANCH')
                successor[a]=b
    if not successor or len(successor)!=len(border_edges):
        raise ValueError('PATCH_BOUNDARY_INVALID')
    border=[min(successor)]
    while successor[border[-1]]!=border[0]:
        nxt=successor[border[-1]]
        if nxt in border:
            raise ValueError('PATCH_BOUNDARY_LOOP')
        border.append(nxt)
    vertices={i for face in faces for i in face}
    interior=sorted(vertices-set(border))
    if set(border)!=set(successor) or len(vertices)-len(ef)+len(faces)!=1:
        raise ValueError('PATCH_NOT_ONE_DISK')
    if set(interior)&{i for e in ctx['protectedEdges'] for i in e}:
        raise ValueError('PATCH_REMOVES_PROTECTED_CONTROL')
    if any(len(ctx['edges'][tuple(sorted((a,b)))])!=2 for a,b in zip(border,border[1:]+border[:1])):
        raise ValueError('PATCH_TOUCHES_OPEN_BORDER')
    extent=max((ctx['points'][a]-ctx['points'][b]).length for a in vertices for b in vertices)
    if len(interior)<3 or len(selected)<20 or extent<.025:
        raise ValueError('NOT_MULTI_INTERIOR_PANEL')
    if len(border)>MAX_BOUNDARY:
        raise ValueError('BOUNDARY_EXCEEDS_DECLARED_DP_BUDGET')
    return dict(removedFaces=selected,removedInteriorVertices=interior,boundaryVertices=border,
                domain=next(iter(materials)),extentMeters=extent,
                sourceBending=cap.bending_local(source,selected))


def candidates(source,ctx):
    seen=set()
    rows=[]
    rejected=[]
    for seed in ctx['seeds']:
        for domain in sorted({source.data.polygons[i].material_index for i in ctx['vertexFaces'][seed]}&{4,5,6,7}):
            selected={fi for fi in ctx['vertexFaces'][seed] if source.data.polygons[fi].material_index==domain}
            if selected&ctx['preservedFaces'] or ctx['guideProximity'][seed]>.035:
                continue
            for ring in range(1,5):
                selected.update(j for i in list(selected) for j in ctx['neighbors'][i])
                key=tuple(sorted(selected))
                if key in seen:
                    continue
                seen.add(key)
                rec=dict(seedVertex=seed,domain=domain,faceRings=ring,
                         nearestBoundedGuideMeters=ctx['guideProximity'][seed])
                try:
                    row=boundary(source,ctx,selected)
                    row.update(rec)
                    rows.append(row)
                except ValueError as error:
                    rejected.append(dict(**rec,status='REJECTED_PARTITION',reason=str(error)))
    rows.sort(key=lambda r:(-r['sourceBending']['weightedRadiansSquaredMeters'],r['seedVertex'],r['domain'],r['faceRings']))
    return rows,rejected


def triangulate(source,ctx,row):
    triangles,recipe=cap.triangulate_boundary(ctx['points'],row['boundaryVertices'],cap.outside_normals(source,row))
    gain=row['sourceBending']['weightedRadiansSquaredMeters']-recipe['objectiveCost']
    if gain<=1e-7:
        raise ValueError('NO_PREDICTED_PANEL_BENDING_GAIN')
    return dict(**row,replacementSourceTriangles=[list(f) for f in triangles],recipe=recipe,predictedGain=gain)


def probe(source,disk_report,cap_report,layout_report,curve_report):
    ctx=context(source,disk_report,cap_report,layout_report,curve_report)
    rows,rejections=candidates(source,ctx)
    successes=[]
    for index,row in enumerate(rows):
        try:
            result=triangulate(source,ctx,row)
            obj,op=compose(source,ctx,[result])
            try:
                result['singlePanelQA']=measure(obj,source,ctx,op)
            finally:
                prior.discard(obj)
            successes.append(result)
            log_trial(result)
            if result['singlePanelQA']['maximumReverseOriginalChartSampleErrorMeters']>LIMIT:
                for target in (.00145,.00135,.0012):
                    try:
                        repaired=insert_support(source,ctx,result,target)
                        trial,operation=compose(source,ctx,[repaired])
                        try:
                            repaired['singlePanelQA']=measure(trial,source,ctx,operation)
                        finally:
                            prior.discard(trial)
                        successes.append(repaired)
                        log_trial(repaired)
                    except ValueError as error:
                        rejections.append(dict(seedVertex=row['seedVertex'],domain=row['domain'],faceRings=row['faceRings'],targetMeters=target,status='REJECTED_SUPPORT_INSERTION',reason=str(error)))
        except ValueError as error:
            rejections.append(dict(seedVertex=row['seedVertex'],domain=row['domain'],faceRings=row['faceRings'],status='REJECTED_TRIANGULATION',reason=str(error)))
        print('PANEL_PROGRESS',index+1,len(rows),flush=True)
    return dict(candidates=successes,decisions=rejections,partitionCandidateCount=len(rows))


def log_trial(row):
    qa=row['singlePanelQA']
    print('PANEL_TRIAL',json.dumps(dict(seed=row['seedVertex'],rings=row['faceRings'],
          supportTarget=row.get('supportInsertion',{}).get('targetMeters'),eligible=qa['eligible'],
          forward=qa['maximumForwardOriginalChartSampleErrorMeters'],reverse=qa['maximumReverseOriginalChartSampleErrorMeters'],
          maximumLocalDegrees=qa['patches'][0]['after']['maximumDegrees'])),flush=True)


def compose(source,ctx,panels,name=RESULT_OBJECT):
    if not panels or bpy.data.objects.get(name):
        raise ValueError('NO_PANELS_OR_OUTPUT_OBJECT_ALREADY_EXISTS')
    removed_faces={i for row in panels for i in row['removedFaces']}
    removed_vertices={i for row in panels for i in row['removedInteriorVertices']}
    kept=[i for i in range(len(ctx['points'])) if i not in removed_vertices]
    mapping={old:new for new,old in enumerate(kept)}
    source_faces=[i for i in range(len(ctx['faces'])) if i not in removed_faces]
    faces=[tuple(mapping[i] for i in ctx['faces'][fi]) for fi in source_faces]
    materials=[source.data.polygons[fi].material_index for fi in source_faces]
    patch_faces=[]
    new_points=[ctx['points'][i] for i in kept]
    added=[]
    for row in panels:
        first=len(faces)
        local_map=dict(mapping)
        added.append(list(range(len(new_points),len(new_points)+len(row.get('supportPoints',[])))))
        local_map.update({len(ctx['points'])+j:len(new_points)+j for j in range(len(row.get('supportPoints',[])))})
        new_points.extend(Vector(p) for p in row.get('supportPoints',[]))
        faces.extend(tuple(local_map[i] for i in f) for f in row['replacementSourceTriangles'])
        materials.extend([row['domain']]*len(row['replacementSourceTriangles']))
        patch_faces.append(list(range(first,len(faces))))
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(new_points,[],faces)
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
    op=dict(panels=panels,keptSourceVertices=kept,unchangedSourceFaceIndices=source_faces,
            patchFaceIndices=patch_faces,addedSupportVertices=added,protectedSourceEdges=[list(e) for e in sorted(ctx['protectedEdges'])])
    return obj,op


def insert_support(source,ctx,row,target):
    """Insert one error-driven interior knot; never move a protected boundary."""
    if row.get('supportPoints') or target not in (.00145,.00135,.0012):
        raise ValueError('INVALID_SUPPORT_INSERTION_RECIPE')
    witness=row['singlePanelQA']['maximumReverseWitness']
    first=len(ctx['faces'])-len(row['removedFaces'])
    index=witness['triangleIndex']-first
    triangles=[tuple(f) for f in row['replacementSourceTriangles']]
    if not 0<=index<len(triangles):
        raise ValueError('REVERSE_WITNESS_OUTSIDE_PANEL')
    hit,q=Vector(witness['nearestPoint']),Vector(witness['point'])
    distance=(q-hit).length
    if distance<=LIMIT:
        raise ValueError('NO_REVERSE_ERROR_TO_CORRECT')
    a,b,d=(ctx['points'][i] for i in triangles[index])
    u,v,w=b-a,d-a,hit-a
    aa,bb,cc,dd,ee=u.dot(u),u.dot(v),v.dot(v),u.dot(w),v.dot(w)
    denominator=aa*cc-bb*bb
    if denominator<=1e-24:
        raise ValueError('DEGENERATE_SUPPORT_SOURCE_TRIANGLE')
    y,z=(cc*dd-bb*ee)/denominator,(aa*ee-bb*dd)/denominator
    bary=[1-y-z,y,z]
    if min(bary)<-1e-4 or sum(x<=1e-5 for x in bary)>1:
        raise ValueError('SUPPORT_INSERTION_AT_EXISTING_VERTEX')
    new=hit.lerp(q,(distance-target)/distance)
    vertex=len(ctx['points'])
    if min(bary)>1e-5:
        remove={index}
        ids=triangles[index]
        replacements=[(ids[0],ids[1],vertex),(ids[1],ids[2],vertex),(ids[2],ids[0],vertex)]
    else:
        ids=triangles[index]
        zero=min(range(3),key=lambda i:bary[i])
        edge={ids[(zero+1)%3],ids[(zero+2)%3]}
        remove={i for i,t in enumerate(triangles) if edge<=set(t)}
        if len(remove)!=2:
            raise ValueError('SUPPORT_INSERTION_WOULD_MOVE_BOUNDARY')
        replacements=[]
        for i in sorted(remove):
            ids=triangles[i]
            start=next(j for j in range(3) if {ids[j],ids[(j+1)%3]}==edge)
            a,b,d=ids[start],ids[(start+1)%3],ids[(start+2)%3]
            replacements.extend([(a,vertex,d),(vertex,b,d)])
    result=copy.deepcopy(row)
    result.pop('singlePanelQA',None)
    result['replacementSourceTriangles']=[list(t) for i,t in enumerate(triangles) if i not in remove]+[list(t) for t in replacements]
    result['supportPoints']=[list(new)]
    result['supportInsertion']=dict(method='ONE_REVERSE_ORIGINAL_CHART_WITNESS_INTERIOR_KNOT',targetMeters=target,
                                    originalWitness=witness,barycentric=bary,sourceTrianglesSplit=sorted(remove),
                                    pointOffsetFromUncorrectedPanelMeters=(new-hit).length)
    return result


def measure(obj,source,ctx,op):
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    ef=edgeflow.edge_faces([tuple(f.vertices) for f in obj.data.polygons])
    tree,_,triangles=c.fit.bvh(obj)
    chart=bpy.data.objects[branch.RESULT_OBJECT]
    reference,reference_points,reference_triangles=c.fit.bvh(chart)
    samples=points+[sum((points[i] for i in t),Vector())/3 for t in triangles]
    samples.extend((points[a]+points[b])/2 for a,b in ef)
    reverse_samples=reference_points+[sum((reference_points[i] for i in t),Vector())/3 for t in reference_triangles]
    forward_record=max(((reference.find_nearest(p)[3],i) for i,p in enumerate(samples)))
    reverse_record=max(((tree.find_nearest(p)[3],i) for i,p in enumerate(reverse_samples)))
    forward=forward_record[0]
    reverse=reverse_record[0]
    reverse_point=reverse_samples[reverse_record[1]]
    reverse_hit=tree.find_nearest(reverse_point)
    pairs,_=fair.collision_pairs(obj)
    topology=branch.s.prior.prior.boundaries(obj)
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    orientation=sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
    bm.free()
    patch_qa=[]
    for row,fs in zip(op['panels'],op['patchFaceIndices']):
        after=cap.bending_local(obj,fs)
        before=cap.bending_local(source,row['removedFaces'])
        patch_qa.append(dict(seedVertex=row['seedVertex'],domain=row['domain'],
                             removedTriangles=len(row['removedFaces']),replacementTriangles=len(fs),
                             removedInteriorVertices=len(row['removedInteriorVertices']),extentMeters=row['extentMeters'],
                             before=before,after=after,eligible=after['maximumDegrees']<=55+1e-4 and after['edgesAbove55Degrees']==0
                             and after['weightedRadiansSquaredMeters']<before['weightedRadiansSquaredMeters']-1e-7))
    before_global=fair.bending(source,{})
    after_global=fair.bending(obj,{})
    qa=dict(vertices=len(points),triangles=len(triangles),patches=patch_qa,
            maximumForwardOriginalChartSampleErrorMeters=forward,maximumReverseOriginalChartSampleErrorMeters=reverse,
            forwardSampleCount=len(samples),reverseSampleCount=len(reverse_samples),
            maximumReverseWitness=dict(referenceSampleIndex=reverse_record[1],point=list(reverse_point),
                                       nearestPoint=list(reverse_hit[0]),triangleIndex=reverse_hit[2]),
            nonAdjacentSelfIntersectionPairs=len(pairs),nonContiguousInteriorEdges=orientation,
            zeroAreaFaces=topology['zeroAreaFaces'],connectedComponents=len(topology['components']),
            boundaryLoops=len(topology['boundaryLoops']),euler=topology['euler'],
            beforeBending=before_global,afterBending=after_global)
    qa['eligible']=all(r['eligible'] for r in patch_qa) and max(forward,reverse)<=LIMIT and not pairs and not orientation and not qa['zeroAreaFaces'] and qa['connectedComponents']==1 and qa['boundaryLoops']==2 and qa['euler']==0 and after_global['weightedRadiansSquaredMeters']<before_global['weightedRadiansSquaredMeters']-1e-7
    if qa['eligible']:
        qa['densePatchQA']=dense_patch_qa(obj,source,op)
        qa['eligible']=qa['densePatchQA']['eligible']
    return qa


def dense_patch_qa(obj,source,op):
    """Additional patch-local barycentric probes, not a continuous proof."""
    tree,points,_=c.fit.bvh(obj)
    old_tree,_,_=c.fit.bvh(source)
    reference,ref_points,ref_triangles=c.fit.bvh(bpy.data.objects[branch.RESULT_OBJECT])
    removed={i for row in op['panels'] for i in row['removedFaces']}
    grid=12
    weights=[(i/grid,j/grid,1-(i+j)/grid) for i in range(grid+1) for j in range(grid+1-i)]
    forward=[]
    for group in op['patchFaceIndices']:
        for fi in group:
            a,b,d=(points[i] for i in obj.data.polygons[fi].vertices)
            forward.extend(reference.find_nearest(a*u+b*v+d*w)[3] for u,v,w in weights)
    reverse=[]
    for triangle in ref_triangles:
        a,b,d=(ref_points[i] for i in triangle)
        for u,v,w in weights:
            q=a*u+b*v+d*w
            if old_tree.find_nearest(q)[2] in removed:
                reverse.append(tree.find_nearest(q)[3])
    return dict(barycentricGridDivisions=grid,forwardSamples=len(forward),reverseLocalOriginalSamples=len(reverse),
                maximumForwardPatchToOriginalChartMeters=max(forward),
                maximumReverseAssignedOriginalChartToPatchMeters=max(reverse),
                reverseAssignment='NEAREST_TRIANGLE_ON_UNMODIFIED_STUDY_BELONGS_TO_REMOVED_PANEL',
                continuousBoundProved=False,eligible=max(max(forward),max(reverse))<=LIMIT)


def replay_panel(source,ctx,row):
    rows,_=candidates(source,ctx)
    matches=[r for r in rows if (r['seedVertex'],r['domain'],r['faceRings'])==(row['seedVertex'],row['domain'],row['faceRings'])]
    if len(matches)!=1:
        raise ValueError('PANEL_PARTITION_PROVENANCE_CHANGED')
    expected=triangulate(source,ctx,matches[0])
    if row.get('supportInsertion'):
        trial,op=compose(source,ctx,[expected],RESULT_OBJECT+'_REPLAY')
        try:
            expected['singlePanelQA']=measure(trial,source,ctx,op)
        finally:
            prior.discard(trial)
        expected=insert_support(source,ctx,expected,row['supportInsertion']['targetMeters'])
    if row!=expected:
        raise ValueError('PANEL_RECIPE_OR_SUPPORT_PROVENANCE_CHANGED')


def audit(obj,source,reports,op):
    surface.require_locked(obj)
    ctx=context(source,*reports)
    if len(op['panels'])!=1:
        raise ValueError('EXPECTED_ONE_BEST_MULTI_INTERIOR_PANEL')
    replay_panel(source,ctx,op['panels'][0])
    expected,expected_op=compose(source,ctx,op['panels'],RESULT_OBJECT+'_EXPECTED')
    try:
        if op!=expected_op:
            raise ValueError('PANEL_VERTEX_OR_FACE_MAP_CHANGED')
        if [tuple(f.vertices) for f in obj.data.polygons]!=[tuple(f.vertices) for f in expected.data.polygons] or [f.material_index for f in obj.data.polygons]!=[f.material_index for f in expected.data.polygons]:
            raise ValueError('PANEL_TOPOLOGY_OR_REGION_CHANGED')
        if len(obj.data.vertices)!=len(expected.data.vertices):
            raise ValueError('PANEL_VERTEX_COUNT_CHANGED')
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        if any(not math.isfinite(x) for p in points for x in p):
            raise ValueError('NONFINITE_PANEL_VERTEX')
        error=max((p-(expected.matrix_world@v.co)).length for p,v in zip(points,expected.data.vertices))
        if error>1e-8:
            raise ValueError('PANEL_VERTEX_POSITION_CHANGED')
    finally:
        prior.discard(expected)
    mapping={old:new for new,old in enumerate(op['keptSourceVertices'])}
    edges=edgeflow.edge_faces([tuple(f.vertices) for f in obj.data.polygons])
    if any(tuple(sorted(mapping[i] for i in e)) not in edges for e in ctx['protectedEdges']):
        raise ValueError('PROTECTED_LAYOUT_EDGE_REMOVED')
    if {i for r in op['panels'] for i in r['removedFaces']}&ctx['preservedFaces']:
        raise ValueError('PREVIOUS_PATCH_CHANGED')
    qa=measure(obj,source,ctx,op)
    qa.update(panelCount=1,preservedLayoutEdges=len(ctx['protectedEdges']),preservedPreviousPatchFaces=len(ctx['preservedFaces']),
              removedInteriorVertices=sum(len(r['removedInteriorVertices']) for r in op['panels']),
              addedSupportVertices=sum(len(r.get('supportPoints',[])) for r in op['panels']),
              maximumRetainedVertexMoveMeters=max((points[i]-ctx['points'][j]).length for i,j in enumerate(op['keptSourceVertices'])),
              originalBodyMovedVertices=0,previousCapAndUnderarmDisksPreserved=True,geometryShapeChanged=True,
              fullUnderarmRebuilt=False,majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False)
    return qa


def build(source,reports):
    diagnostics=probe(source,*reports)
    eligible=[r for r in diagnostics['candidates'] if r['singlePanelQA']['eligible']]
    if not eligible:
        raise ValueError('NO_MULTI_INTERIOR_PANEL_PASSES_ORIGINAL_BOUND')
    selected=min(eligible,key=lambda r:(r['singlePanelQA']['afterBending']['weightedRadiansSquaredMeters'],r['seedVertex'],r.get('supportInsertion',{}).get('targetMeters',0)))
    row={k:v for k,v in selected.items() if k!='singlePanelQA'}
    ctx=context(source,*reports)
    obj,op=compose(source,ctx,[row])
    diagnostics['selectionMethod']='ONE_LOWEST_GLOBAL_BENDING_FULL_QA_PASSING_PANEL_FROM_DECLARED_FAMILY'
    diagnostics['selectedIdentity']=dict(seedVertex=row['seedVertex'],domain=row['domain'],faceRings=row['faceRings'],supportTargetMeters=row.get('supportInsertion',{}).get('targetMeters'))
    return obj,op,diagnostics


def guides(source,op):
    return [branch.curve(GUIDE_PREFIX+str(i),[source.matrix_world@source.data.vertices[j].co for j in row['boundaryVertices']],'42C7DA',True)
            for i,row in enumerate(op['panels'])]


def audit_guides(source,op):
    actual={o.name:o for o in bpy.context.scene.objects if o.name.startswith(GUIDE_PREFIX)}
    if set(actual)!={GUIDE_PREFIX+str(i) for i in range(len(op['panels']))}:
        raise ValueError('PANEL_GUIDE_SET_CHANGED')
    maximum=0.
    for i,row in enumerate(op['panels']):
        obj=actual[GUIDE_PREFIX+str(i)]
        surface.require_locked(obj)
        if obj.type!='CURVE' or not obj.get('guideOnly') or len(obj.data.splines)!=1:
            raise ValueError('PANEL_GUIDE_STRUCTURE_CHANGED')
        s=obj.data.splines[0]
        if s.type!='POLY' or not s.use_cyclic_u or len(s.points)!=len(row['boundaryVertices']):
            raise ValueError('PANEL_GUIDE_STRUCTURE_CHANGED')
        for p,j in zip(s.points,row['boundaryVertices']):
            error=(obj.matrix_world@Vector(p.co[:3])-(source.matrix_world@source.data.vertices[j].co)).length
            if not math.isfinite(error) or error>1e-6:
                raise ValueError('PANEL_GUIDE_POSITION_CHANGED')
            maximum=max(maximum,error)
    return dict(guideCount=len(actual),maximumPositionErrorMeters=maximum)


def curve_snapshot(obj):
    return dict(matrix=list(map(list,obj.matrix_world)),
                splines=[dict(type=s.type,cyclic=s.use_cyclic_u,points=[list(p.co) for p in s.points]) for s in obj.data.splines])


def render_comparison(output,source,obj,op):
    """Actual saved geometry rendered twice; no generated/retouched illustration."""
    scene=bpy.context.scene
    existing=set(bpy.data.objects)
    light_visibility={o:o.hide_render for o in scene.objects if o.type=='LIGHT'}
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT','FONT'):
            old.hide_render=True
    row=op['panels'][0]
    target=sum((source.matrix_world@source.data.vertices[i].co for i in row['boundaryVertices']),Vector())/len(row['boundaryVertices'])
    normal=sum((source.data.polygons[i].normal*source.data.polygons[i].area for i in row['removedFaces']),Vector()).normalized()
    rotation=(-normal).to_track_quat('-Z','Y')
    right,up=rotation@Vector((1,0,0)),rotation@Vector((0,1,0))
    material=c.base.material('PanelCompare_RENDER_ONLY',(.44,.53,.58))
    wire_material=c.base.material('PanelWire_RENDER_ONLY',(.025,.16,.20))
    label_material=c.base.material('PanelLabel_RENDER_ONLY',(.85,.92,.96))
    label_material.use_nodes=True
    label_shader=label_material.node_tree.nodes.get('Principled BSDF')
    label_shader.inputs['Emission Color'].default_value=(.85,.92,.96,1)
    label_shader.inputs['Emission Strength'].default_value=1.
    new_materials=[material,wire_material,label_material]
    old_caption=f"{len(row['removedFaces'])} TRIANGLES"
    count=len(row.get('supportPoints',[]))
    new_caption=f"{len(op['patchFaceIndices'][0])} TRIANGLES + {count} SUPPORT"+('S' if count!=1 else '')
    for sign,item,selected,label,caption in [(-1,source,row['removedFaces'],'BEFORE',old_caption),(1,obj,op['patchFaceIndices'][0],'AFTER',new_caption)]:
        offset=right*(sign*.035)
        ids=sorted({i for fi in selected for i in item.data.polygons[fi].vertices})
        mapping={j:i for i,j in enumerate(ids)}
        vertices=[item.matrix_world@item.data.vertices[i].co+offset for i in ids]
        faces=[tuple(mapping[i] for i in item.data.polygons[fi].vertices) for fi in selected]
        mesh=bpy.data.meshes.new('PanelCompare_RENDER_ONLY')
        mesh.from_pydata(vertices,[],faces)
        mesh.materials.append(material)
        mesh.update()
        patch=bpy.data.objects.new(mesh.name,mesh)
        scene.collection.objects.link(patch)
        data=bpy.data.curves.new('PanelWire_RENDER_ONLY','CURVE')
        data.dimensions='3D'
        data.bevel_depth=.000075
        data.bevel_resolution=1
        for a,b in edgeflow.edge_faces(faces):
            spline=data.splines.new('POLY')
            spline.points.add(1)
            for p,co in zip(spline.points,(vertices[a]+normal*.00004,vertices[b]+normal*.00004)):
                p.co=(*co,1)
        data.materials.append(wire_material)
        wire=bpy.data.objects.new(data.name,data)
        scene.collection.objects.link(wire)
        for text,height,size in [(label,.031,.0048),(caption,.024,.0021)]:
            font=bpy.data.curves.new('PanelLabel_RENDER_ONLY','FONT')
            font.body=text
            font.align_x='CENTER'
            font.size=size
            font.materials.append(label_material)
            text_obj=bpy.data.objects.new(font.name,font)
            scene.collection.objects.link(text_obj)
            text_obj.location=target+offset+up*height+normal*.005
            text_obj.rotation_euler=rotation.to_euler()
    for delta,energy in [(normal*.25+right*.12+up*.10,18),(normal*.20-right*.10,8)]:
        light_data=bpy.data.lights.new('PanelCompareLight_RENDER_ONLY','AREA')
        light_data.energy=energy
        light_data.size=.3
        light=bpy.data.objects.new(light_data.name,light_data)
        scene.collection.objects.link(light)
        light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.location=target+normal*.35
    scene.camera.rotation_euler=rotation.to_euler()
    scene.camera.data.type='ORTHO'
    scene.camera.data.ortho_scale=.145
    scene.render.resolution_x=1600
    scene.render.resolution_y=900
    scene.cycles.samples=48
    path=output/'panel_before_after.png'
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    for item in set(bpy.data.objects)-existing:
        data=item.data
        kind=item.type
        bpy.data.objects.remove(item,do_unlink=True)
        if data.users==0:
            {'MESH':bpy.data.meshes,'CURVE':bpy.data.curves,'FONT':bpy.data.curves,'LIGHT':bpy.data.lights}[kind].remove(data)
    for mat in new_materials:
        bpy.data.materials.remove(mat)
    for light,hidden in light_visibility.items():
        light.hide_render=hidden
    return dict(file=path.name,sha256=c.base.sha(path))


def render_focus_pairs(output,source,obj,op):
    scene=bpy.context.scene
    light_visibility={o:o.hide_render for o in scene.objects if o.type=='LIGHT'}
    for light in light_visibility:
        light.hide_render=True
    target=sum((source.matrix_world@source.data.vertices[i].co for i in op['panels'][0]['boundaryVertices']),Vector())/len(op['panels'][0]['boundaryVertices'])
    lights=[]
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('PanelFocusLight_RENDER_ONLY','AREA')
        data.energy=energy
        data.size=.4
        light=bpy.data.objects.new(data.name,data)
        scene.collection.objects.link(light)
        light.location=Vector((-.17,0,1.2))+Vector(delta)
        light.rotation_euler=(Vector((-.17,0,1.2))-light.location).to_track_quat('-Z','Y').to_euler()
        lights.append(light)
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=24
    scene.render.resolution_x=900
    scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    scene.view_settings.exposure=-1
    records=[]
    for label,item,selected in [('before_close',source,op['panels'][0]['removedFaces']),('after_close',obj,op['patchFaceIndices'][0])]:
        folder=output/label
        folder.mkdir(exist_ok=True)
        ghost,material=layout.fold_review_ghost(item)
        records.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in prior.render_focus(folder,ghost,selected,target))
        mesh=ghost.data
        bpy.data.objects.remove(ghost,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.materials.remove(material)
    for light in lights:
        data=light.data
        bpy.data.objects.remove(light,do_unlink=True)
        bpy.data.lights.remove(data)
    for light,hidden in light_visibility.items():
        light.hide_render=hidden
    return records


def input_reports(args):
    paths=[(args.source,SOURCE_SHA,'SOURCE'),(args.source.parent/'support-curves-report.json',REPORT_SHA,'CURVE_REPORT'),
           (args.disk_report,support.REPORT_SHA,'DISK_REPORT'),(args.cap_report,support.CAP_REPORT_SHA,'CAP_REPORT'),
           (args.layout_report,support.LAYOUT_SHA,'LAYOUT_REPORT')]
    for path,sha,label in paths:
        if c.base.sha(path)!=sha:
            raise ValueError(label+'_SHA256_MISMATCH')
    curve,disk,cap_report,layout_report=[json.loads(p.read_text()) for p,_,_ in paths[1:]]
    return disk,cap_report,layout_report,curve


def run(args):
    reports=input_reports(args)
    output=args.output.resolve()
    if getattr(args,'rerender_comparison',False):
        report_path=output/'underarm-panels-report.json'
        result=json.loads(report_path.read_text())
        surface.require_locked(result)
        blend=output/result['blendFile']
        if result['strategyId']!=STRATEGY or result['sourceBlendSha256']!=SOURCE_SHA or c.base.sha(blend)!=result['blendSha256']:
            raise ValueError('SAVED_ARTIFACT_HASH_OR_IDENTITY_CHANGED')
        for row in result['renders']:
            if c.base.sha(output/row['file'])!=row['sha256']:
                raise ValueError('SAVED_RENDER_HASH_CHANGED')
        if sum(r['file']=='panel_before_after.png' for r in result['renders'])!=1:
            raise ValueError('SAVED_RENDER_SET_CHANGED')
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        surface.require_locked(bpy.context.scene)
        qa=audit(bpy.data.objects[RESULT_OBJECT],bpy.data.objects[prior.RESULT_OBJECT],reports,result['operation'])
        if qa!=result['qa'] or not qa['eligible']:
            raise ValueError('SAVED_PANEL_QA_CHANGED')
        image_record=render_comparison(output,bpy.data.objects[prior.RESULT_OBJECT],bpy.data.objects[RESULT_OBJECT],result['operation'])
        refreshed=[image_record]+render_focus_pairs(output,bpy.data.objects[prior.RESULT_OBJECT],bpy.data.objects[RESULT_OBJECT],result['operation'])
        by_file={r['file']:r for r in refreshed}
        result['renders']=[by_file.get(r['file'],r) for r in result['renders']]
        report_path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    if args.probe:
        bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
        result=probe(bpy.data.objects[prior.RESULT_OBJECT],*reports)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=layout.panel.TURNAROUND_SHA:
        raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=layout.panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    old_curves={o.name:curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE'}
    visibility={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')}
    source=bpy.data.objects[prior.RESULT_OBJECT]
    obj,op,selection=build(source,reports)
    qa=audit(obj,source,reports,op)
    if not qa['eligible']:
        raise ValueError('FINAL_MULTI_INTERIOR_PANEL_QA_FAILED')
    lines=guides(source,op)
    guide_qa=audit_guides(source,op)
    output.mkdir(parents=True)
    renders=[]
    if not args.no_render:
        for label,item in [('before',source),('after',obj)]:
            folder=output/label
            folder.mkdir()
            renders.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in branch.render(folder,item,[]))
        ghost,material=layout.fold_review_ghost(obj)
        folder=output/'location'
        folder.mkdir()
        renders.extend(dict(file='location/'+r['file'],sha256=r['sha256']) for r in branch.render(folder,ghost,lines))
        mesh=ghost.data
        bpy.data.objects.remove(ghost,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.materials.remove(material)
        renders.append(render_comparison(output,source,obj,op))
        renders.extend(render_focus_pairs(output,source,obj,op))
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_MESH_UV_MATERIAL_OR_WEIGHT_CHANGED')
    if old_curves!={name:curve_snapshot(bpy.data.objects[name]) for name in old_curves}:
        raise ValueError('UPSTREAM_GUIDE_CHANGED')
    for name,(hidden,render_hidden) in visibility.items():
        bpy.data.objects[name].hide_set(hidden)
        bpy.data.objects[name].hide_render=render_hidden
    for item in [obj]+lines:
        item.hide_set(True)
        item.hide_render=True
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.preferences.filepaths.file_preview_type='NONE'
    blend=output/'CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    result=dict(strategyId=STRATEGY,status='ONE_MULTI_INTERIOR_PANEL_QA_PASS_NOT_FULL_UNDERARM',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,curveReportSha256=REPORT_SHA,diskReportSha256=support.REPORT_SHA,
                capReportSha256=support.CAP_REPORT_SHA,layoutReportSha256=support.LAYOUT_SHA,
                artCommit=c.base.ART_COMMIT,references=refs,operation=op,selection=selection,qa=qa,guideQA=guide_qa,
                originalsPreserved=True,geometryShapeChanged=True,courseBoundaryRelocationApplied=False,
                adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                fullUnderarmRebuilt=False,majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False,
                originalBodyMovedVertices=0,originalBodyCumulativeMaximumMoveMeters=.002999919,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['ONE_42_MM_DOMAIN_LOCKED_PANEL_NOT_FULL_UNDERARM_OR_MAJOR_FOLD_REDESIGN',
                             'ORIGINAL_CHART_CUMULATIVE_1_5_MM_FINITE_SAMPLES_NOT_CONTINUOUS_PROOF',
                             'SELF_INTERSECTION_EXCLUDES_TRIANGLES_SHARING_ANY_VERTEX',
                             'OPEN_UNOFFSET_SURFACE_NO_UV_THICKNESS_SEWING_RIG_OR_GARMENT_APPROVAL'])
    (output/'underarm-panels-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 one boundary-locked multi-interior underarm panel — NOT PRODUCTION\n21 old triangles / 3 interior vertices become 17 triangles / 1 error-driven support knot. The 42 mm patch is a real face replacement, not a one-vertex star deletion or only a curve proposal.\nAll 907 layout edges, previous cap + 5 disks, original meshes/UV/materials/weights, inherited guides and default visible assembly remain fixed. The new hidden study is not adopted as visual baseline.\nActual Blender renders include a labeled before/after isolated-patch diagnostic, not a finished character or generated illustration. Global 134.76 degree folds and torso clip remain.\nFinite cumulative original-chart bound stays 1.5 mm; body cumulative 2.999919 mm / 3 mm stays. Gate B pending; adoption, Unity and production disabled. No new SPAR3D inference or full-character score.\n',encoding='utf-8')
    print('SAVED_PANELS',json.dumps(dict(blendSha256=result['blendSha256'],qa=qa)),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--disk-report',type=Path,required=True)
    p.add_argument('--cap-report',type=Path,required=True)
    p.add_argument('--layout-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--art-root',type=Path)
    p.add_argument('--probe',action='store_true')
    p.add_argument('--no-render',action='store_true')
    p.add_argument('--rerender-comparison',action='store_true',help='Verify a saved artifact and refresh comparison + four focus PNGs; never resave its Blend')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not args.probe and args.art_root is None:
        p.error('--art-root is required for saved artifacts')
    run(args)
