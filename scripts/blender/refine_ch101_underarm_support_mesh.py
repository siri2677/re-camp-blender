"""Finite multi-knot replacement search on the latest preserved underarm mesh."""
import argparse
import copy
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import rebuild_ch101_underarm_panels as prior
c,surface,branch=prior.c,prior.surface,prior.branch
SOURCE_SHA='48844f26a0182f6243081fbbfb036269c8436a8dd9ec79dc129addaf184ad362'
RESULT_OBJECT='CH101_MultiKnotUnderarmSupportMesh_NOT_PRODUCTION'
STRATEGY='CH101_ERROR_DRIVEN_MULTI_KNOT_UNDERARM_V001'
MAX_KNOTS=4
TARGETS=(.00145,.00135,.0012)
LIMIT=prior.LIMIT
REPORT_SHAS=('74a762ba537fb6f1b2ee7d22cffd130ea36d427b8c689cfff431f9d8a712fa6a',
             '47df4f246311d2eea4166216787e110d9365c8fb26677b98b182fc670f162415',
             'ed9f9e3b5e0451a190401868e230f7c0258561c4a860acc7fd5af5633527d3ea',
             '9fabffce970e35917ff320751fa219c27f83108e9b3f1180aa48fe0f3a13b689',
             'bca22576a8edcfff93034d194fcd686f396aa25a6e56da53fa353ccf3e765a61')
GUIDE_PREFIX='BIDIRECTIONAL_UNDERARM_BOUNDARY_'


def context(source,reports):
    disk,cap,layout,curves,previous=reports
    surface.require_locked(source)
    for report in reports:surface.require_locked(report)
    old=bpy.data.objects[prior.prior.RESULT_OBJECT]
    ctx=prior.context(old,disk,cap,layout,curves)
    op=previous['operation'];kept=op['keptSourceVertices']
    if len(set(kept))!=len(kept) or len(kept)+sum(map(len,op['addedSupportVertices']))!=len(source.data.vertices):
        raise ValueError('PREVIOUS_PANEL_VERTEX_MAP_CHANGED')
    if len(op['patchFaceIndices'])!=1 or len(op['patchFaceIndices'][0])!=17:
        raise ValueError('PREVIOUS_PANEL_PATCH_CHANGED')
    mapping={old:new for new,old in enumerate(kept)}
    faces=[tuple(f.vertices) for f in source.data.polygons]
    edges=prior.edgeflow.edge_faces(faces)
    protected={e for e,fs in edges.items() if len(fs)==1 or len({source.data.polygons[i].material_index for i in fs})>1}
    preserved={i for i,old_index in enumerate(op['unchangedSourceFaceIndices']) if old_index in ctx['preservedFaces']}
    preserved.update(i for fs in op['patchFaceIndices'] for i in fs)
    if len(protected)!=907 or len(preserved)!=67:
        raise ValueError('PREVIOUS_PANEL_PRESERVATION_SET_CHANGED')
    neighbors=defaultdict(set);vf=defaultdict(set)
    for i,f in enumerate(faces):
        for v in f:vf[v].add(i)
    for e,fs in edges.items():
        if len(fs)==2 and e not in protected and not set(fs)&preserved:
            a,b=fs;neighbors[a].add(b);neighbors[b].add(a)
    return dict(faces=faces,edges=edges,protectedEdges=protected,preservedFaces=preserved,
                seeds=[mapping[i] for i in ctx['seeds'] if i in mapping],neighbors=neighbors,vertexFaces=vf,
                points=[source.matrix_world@v.co for v in source.data.vertices],
                guideProximity={mapping[i]:gap for i,gap in ctx['guideProximity'].items() if i in mapping})


def insert_knot(ctx,row,qa,target):
    """Split actual witness triangle/edge; existing controls never move."""
    points=ctx['points']+[Vector(p) for p in row.get('supportPoints',[])]
    count=len(row.get('supportPoints',[]))
    if count>=MAX_KNOTS or target not in TARGETS:
        raise ValueError('MULTI_KNOT_BUDGET_OR_TARGET_INVALID')
    forward=qa.get('correctionForwardErrorMeters',qa['maximumForwardOriginalChartSampleErrorMeters'])
    reverse=qa.get('correctionReverseErrorMeters',qa['maximumReverseOriginalChartSampleErrorMeters'])
    if forward>LIMIT and forward>=reverse:
        witness=qa['correctionForwardWitness'] if 'correctionForwardWitness' in qa else qa['maximumForwardWitness'];direction='FORWARD_PATCH_TO_CHART'
    else:
        witness=qa.get('correctionReverseWitness',qa['maximumReverseWitness']);direction='REVERSE_CHART_TO_PATCH'
    first=len(ctx['faces'])-len(row['removedFaces'])
    index=witness['triangleIndex']-first
    triangles=[tuple(t) for t in row['replacementSourceTriangles']]
    if not 0<=index<len(triangles):raise ValueError('WITNESS_OUTSIDE_REPLACEMENT')
    hit,q=Vector(witness['nearestPoint']),Vector(witness['point'])
    distance=(q-hit).length
    if not math.isfinite(distance) or distance<=LIMIT:raise ValueError('NO_CORRECTION_BOUND_ERROR')
    a,b,d=(points[i] for i in triangles[index]);u,v,w=b-a,d-a,hit-a
    aa,bb,cc,dd,ee=u.dot(u),u.dot(v),v.dot(v),u.dot(w),v.dot(w)
    denom=aa*cc-bb*bb
    if denom<=1e-24:raise ValueError('DEGENERATE_WITNESS_TRIANGLE')
    y,z=(cc*dd-bb*ee)/denom,(aa*ee-bb*dd)/denom;bary=[1-y-z,y,z]
    if min(bary)<-1e-4 or sum(x<=1e-5 for x in bary)>1:raise ValueError('WITNESS_AT_EXISTING_VERTEX')
    new=hit.lerp(q,(distance-target)/distance);vertex=len(points)
    if min(bary)>1e-5:
        removed={index};ids=triangles[index]
        replacements=[(ids[0],ids[1],vertex),(ids[1],ids[2],vertex),(ids[2],ids[0],vertex)]
    else:
        ids=triangles[index];zero=min(range(3),key=lambda i:bary[i]);edge={ids[(zero+1)%3],ids[(zero+2)%3]}
        removed={i for i,t in enumerate(triangles) if edge<=set(t)}
        if len(removed)!=2:raise ValueError('WITNESS_SPLIT_WOULD_MOVE_BOUNDARY')
        replacements=[]
        for i in sorted(removed):
            ids=triangles[i];start=next(j for j in range(3) if {ids[j],ids[(j+1)%3]}==edge)
            a,b,d=ids[start],ids[(start+1)%3],ids[(start+2)%3]
            replacements.extend(((a,vertex,d),(vertex,b,d)))
    result=copy.deepcopy(row)
    result['replacementSourceTriangles']=[list(t) for i,t in enumerate(triangles) if i not in removed]+[list(t) for t in replacements]
    result['supportPoints']=result.get('supportPoints',[])+[list(new)]
    result['supportSteps']=result.get('supportSteps',[])+[dict(targetMeters=target,witness=witness,direction=direction,
        barycentric=bary,sourceTrianglesSplit=sorted(removed),point=list(new),offsetMeters=(new-hit).length)]
    return result


def measure_row(source,ctx,row):
    obj,op=prior.compose(source,ctx,[row],RESULT_OBJECT+'_TRIAL')
    try:
        qa=prior.measure(obj,source,ctx,op)
        reference=c.fit.bvh(bpy.data.objects[branch.RESULT_OBJECT])[0]
        points=[obj.matrix_world@v.co for v in obj.data.vertices];witness=None
        for fi in op['patchFaceIndices'][0]:
            ids=tuple(obj.data.polygons[fi].vertices);a,b,d=(points[i] for i in ids)
            for kind,p in [('CENTROID',(a+b+d)/3),('EDGE_AB',(a+b)/2),('EDGE_BC',(b+d)/2),('EDGE_CA',(d+a)/2),('VERTEX_A',a),('VERTEX_B',b),('VERTEX_C',d)]:
                hit=reference.find_nearest(p)
                if witness is None or hit[3]>witness['distanceMeters']:
                    witness=dict(point=list(hit[0]),nearestPoint=list(p),triangleIndex=fi,
                        referenceTriangleIndex=hit[2],sampleKind=kind,distanceMeters=hit[3])
        qa['maximumForwardWitness']=witness
        if 'densePatchQA' in qa and not qa['densePatchQA']['eligible']:
            tree,points,triangles=c.fit.bvh(obj)
            old_tree=c.fit.bvh(source)[0]
            reference,ref_points,ref_triangles=c.fit.bvh(bpy.data.objects[branch.RESULT_OBJECT])
            grid=12;weights=[(i/grid,j/grid,1-(i+j)/grid) for i in range(grid+1) for j in range(grid+1-i)]
            fw=dict(witness);rw=dict(qa['maximumReverseWitness']);rw['distanceMeters']=qa['maximumReverseOriginalChartSampleErrorMeters']
            for fi in op['patchFaceIndices'][0]:
                a,b,d=(points[i] for i in obj.data.polygons[fi].vertices)
                for u,v,w in weights:
                    p=a*u+b*v+d*w;hit=reference.find_nearest(p)
                    if hit[3]>fw['distanceMeters']:
                        fw=dict(point=list(hit[0]),nearestPoint=list(p),triangleIndex=fi,referenceTriangleIndex=hit[2],sampleKind='DENSE_BARYCENTRIC',distanceMeters=hit[3])
            removed=set(row['removedFaces'])
            for fi,ids in enumerate(ref_triangles):
                a,b,d=(ref_points[i] for i in ids)
                for u,v,w in weights:
                    p=a*u+b*v+d*w
                    if old_tree.find_nearest(p)[2] not in removed:continue
                    hit=tree.find_nearest(p)
                    if hit[3]>rw['distanceMeters']:
                        rw=dict(point=list(p),nearestPoint=list(hit[0]),triangleIndex=hit[2],referenceTriangleIndex=fi,sampleKind='DENSE_BARYCENTRIC',distanceMeters=hit[3])
            qa.update(correctionForwardErrorMeters=max(qa['maximumForwardOriginalChartSampleErrorMeters'],fw['distanceMeters']),
                      correctionReverseErrorMeters=rw['distanceMeters'],correctionForwardWitness=fw,correctionReverseWitness=rw)
        return qa
    finally:prior.prior.discard(obj)


def search(source,reports):
    ctx=context(source,reports);rows,rejections=prior.candidates(source,ctx)
    trials=[];passing=[]
    for index,partition in enumerate(rows):
        try:root=prior.triangulate(source,ctx,partition)
        except ValueError as error:
            rejections.append(dict(seedVertex=partition['seedVertex'],domain=partition['domain'],faceRings=partition['faceRings'],reason=str(error)));continue
        root_qa=measure_row(source,ctx,root)
        for target in TARGETS:
            row=copy.deepcopy(root);qa=root_qa
            for knots in range(MAX_KNOTS+1):
                trial=dict(seedVertex=row['seedVertex'],domain=row['domain'],faceRings=row['faceRings'],targetMeters=target,
                    knotCount=len(row.get('supportPoints',[])),eligible=qa['eligible'],
                    forward=qa['maximumForwardOriginalChartSampleErrorMeters'],reverse=qa['maximumReverseOriginalChartSampleErrorMeters'],
                    maximumLocalDegrees=qa['patches'][0]['after']['maximumDegrees'],
                    bending=qa['afterBending']['weightedRadiansSquaredMeters'])
                trials.append(trial);print('MULTI_KNOT_TRIAL',json.dumps(trial),flush=True)
                if qa['eligible']:
                    passing.append(dict(recipe=copy.deepcopy(row),qa=qa));break
                if knots==MAX_KNOTS:break
                try:row=insert_knot(ctx,row,qa,target)
                except ValueError as error:
                    trials[-1]['stopReason']=str(error);break
                qa=measure_row(source,ctx,row)
        print('PARTITION_PROGRESS',index+1,len(rows),flush=True)
    roots={(r['seedVertex'],r['domain'],r['faceRings']) for r in trials}
    return dict(partitionCount=len(rows),decisions=rejections,trials=trials,passing=passing,
                actualGeometryMeasurements=len(trials)-2*len(roots),
                maxKnots=MAX_KNOTS,targetsMeters=list(TARGETS),seedCount=len(ctx['seeds']))


def input_reports(args):
    if c.base.sha(args.source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    paths=(args.disk_report,args.cap_report,args.layout_report,args.curve_report,args.source.parent/'underarm-panels-report.json')
    reports=[]
    for path,expected in zip(paths,REPORT_SHAS):
        if c.base.sha(path)!=expected:raise ValueError('UPSTREAM_REPORT_SHA256_MISMATCH:'+path.name)
        report=json.loads(path.read_text(encoding='utf-8'));surface.require_locked(report)
        if report['artCommit']!=c.base.ART_COMMIT:raise ValueError('UPSTREAM_ART_COMMIT_MISMATCH')
        reports.append(report)
    if reports[-1]['blendSha256']!=SOURCE_SHA:raise ValueError('PREVIOUS_PANEL_SOURCE_MISMATCH')
    return reports


def build(source,reports):
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('SUPPORT_MESH_ALREADY_EXISTS')
    selection=search(source,reports)
    if not selection['passing']:raise ValueError('NO_BIDIRECTIONAL_PANEL_PASSES_UNCHANGED_QA')
    chosen=min(selection['passing'],key=lambda r:(r['qa']['afterBending']['weightedRadiansSquaredMeters'],r['recipe']['seedVertex'],r['recipe']['supportSteps'][0]['targetMeters']))
    selection['selectedIdentity']=dict(seedVertex=chosen['recipe']['seedVertex'],domain=chosen['recipe']['domain'],faceRings=chosen['recipe']['faceRings'],targetMeters=chosen['recipe']['supportSteps'][0]['targetMeters'])
    obj,op=prior.compose(source,context(source,reports),[chosen['recipe']],RESULT_OBJECT)
    return obj,op,selection


def replay(source,ctx,row):
    rows,_=prior.candidates(source,ctx)
    matches=[r for r in rows if (r['seedVertex'],r['domain'],r['faceRings'])==(row['seedVertex'],row['domain'],row['faceRings'])]
    if len(matches)!=1:raise ValueError('SUPPORT_PARTITION_PROVENANCE_CHANGED')
    expected=prior.triangulate(source,ctx,matches[0])
    if not 1<=len(row.get('supportSteps',[]))<=MAX_KNOTS:raise ValueError('SUPPORT_STEP_BUDGET_INVALID')
    for step in row['supportSteps']:
        expected=insert_knot(ctx,expected,measure_row(source,ctx,expected),step['targetMeters'])
    if expected!=row:raise ValueError('SUPPORT_RECIPE_PROVENANCE_CHANGED')


def audit(obj,source,reports,op):
    surface.require_locked(obj);surface.require_locked(source)
    ctx=context(source,reports)
    if len(op['panels'])!=1:raise ValueError('EXPECTED_ONE_NEW_PRESERVED_PANEL')
    replay(source,ctx,op['panels'][0])
    expected,expected_op=prior.compose(source,ctx,op['panels'],RESULT_OBJECT+'_EXPECTED')
    try:
        if op!=expected_op:raise ValueError('SUPPORT_VERTEX_OR_FACE_MAP_CHANGED')
        if [tuple(f.vertices) for f in obj.data.polygons]!=[tuple(f.vertices) for f in expected.data.polygons] or [f.material_index for f in obj.data.polygons]!=[f.material_index for f in expected.data.polygons]:
            raise ValueError('SUPPORT_TOPOLOGY_OR_REGION_CHANGED')
        if len(obj.data.vertices)!=len(expected.data.vertices):raise ValueError('SUPPORT_VERTEX_COUNT_CHANGED')
        if list(obj.data.materials)!=list(expected.data.materials):raise ValueError('SUPPORT_MATERIAL_SET_CHANGED')
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        if any(not math.isfinite(x) for p in points for x in p):raise ValueError('NONFINITE_SUPPORT_VERTEX')
        if max((p-(expected.matrix_world@v.co)).length for p,v in zip(points,expected.data.vertices))>1e-8:
            raise ValueError('SUPPORT_VERTEX_POSITION_CHANGED')
    finally:prior.prior.discard(expected)
    edges=prior.edgeflow.edge_faces([tuple(f.vertices) for f in obj.data.polygons]);mapping={j:i for i,j in enumerate(op['keptSourceVertices'])}
    if any(tuple(sorted(mapping[i] for i in e)) not in edges for e in ctx['protectedEdges']):raise ValueError('PROTECTED_LAYOUT_EDGE_REMOVED')
    qa=prior.measure(obj,source,ctx,op)
    qa.update(preservedLayoutEdges=len(ctx['protectedEdges']),preservedPreviousPatchFaces=len(ctx['preservedFaces']),
              maximumRetainedVertexMoveMeters=max((points[i]-ctx['points'][j]).length for i,j in enumerate(op['keptSourceVertices'])),
              removedInteriorVertices=len(op['panels'][0]['removedInteriorVertices']),addedSupportVertices=len(op['panels'][0]['supportPoints']),
              originalBodyMovedVertices=0,fullUnderarmRebuilt=False,garmentStaticQA=False,deformationValidated=False)
    return qa


def guide(source,row):
    return branch.curve(GUIDE_PREFIX+'0',[source.matrix_world@source.data.vertices[j].co for j in row['boundaryVertices']],'42C7DA',True)


def audit_guide(source,row):
    actual=[o for o in bpy.context.scene.objects if o.name.startswith(GUIDE_PREFIX)]
    if len(actual)!=1:raise ValueError('SUPPORT_GUIDE_SET_CHANGED')
    obj=actual[0];surface.require_locked(obj)
    if obj.type!='CURVE' or not obj.get('guideOnly') or len(obj.data.splines)!=1:raise ValueError('SUPPORT_GUIDE_STRUCTURE_CHANGED')
    spline=obj.data.splines[0]
    if spline.type!='POLY' or not spline.use_cyclic_u or len(spline.points)!=len(row['boundaryVertices']):raise ValueError('SUPPORT_GUIDE_STRUCTURE_CHANGED')
    for p,i in zip(spline.points,row['boundaryVertices']):
        gap=(obj.matrix_world@Vector(p.co[:3])-(source.matrix_world@source.data.vertices[i].co)).length
        if not math.isfinite(gap) or gap>1e-6:raise ValueError('SUPPORT_GUIDE_POSITION_CHANGED')
    return dict(guideCount=1,closed=True)


def crease_constraints(obj,source,reports,op):
    """Classify remaining folds against exact retained design edges; no edits."""
    ctx=context(source,reports);mapping={j:i for i,j in enumerate(op['keptSourceVertices'])}
    protected={tuple(sorted(mapping[i] for i in e)) for e in ctx['protectedEdges']}
    faces=[tuple(f.vertices) for f in obj.data.polygons];edges=prior.edgeflow.edge_faces(faces)
    points=[obj.matrix_world@v.co for v in obj.data.vertices];rows=[]
    for edge,fs in edges.items():
        if len(fs)!=2:continue
        angle=math.degrees(obj.data.polygons[fs[0]].normal.angle(obj.data.polygons[fs[1]].normal))
        if angle<=55:continue
        rows.append(dict(edge=list(edge),degrees=angle,protectedDesignEdge=edge in protected,
            domains=[obj.data.polygons[i].material_index for i in fs],points=[list(points[i]) for i in edge]))
    rows.sort(key=lambda r:(-r['degrees'],r['edge']))
    return dict(status='READ_ONLY_REMAINING_FOLD_CONSTRAINTS',**c.base.GATES,thresholdDegrees=55,
        majorEdgeCount=len(rows),protectedMajorEdgeCount=sum(r['protectedDesignEdge'] for r in rows),
        unprotectedMajorEdgeCount=sum(not r['protectedDesignEdge'] for r in rows),edges=rows,
        boundaryRelocationApplied=False,impossibilityProved=False)


def render(output,source,obj,op,lines):
    records=[]
    for label,item in [('before',source),('after',obj)]:
        folder=output/label;folder.mkdir()
        records.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in branch.render(folder,item,[]))
    ghost,material=prior.layout.fold_review_ghost(obj)
    folder=output/'location';folder.mkdir()
    records.extend(dict(file='location/'+r['file'],sha256=r['sha256']) for r in branch.render(folder,ghost,lines))
    mesh=ghost.data;bpy.data.objects.remove(ghost,do_unlink=True);bpy.data.meshes.remove(mesh);bpy.data.materials.remove(material)
    records.append(prior.render_comparison(output,source,obj,op))
    records.extend(prior.render_focus_pairs(output,source,obj,op))
    return records


def run(args):
    reports=input_reports(args);output=args.output.resolve()
    if getattr(args,'inspect_saved',False):
        report=json.loads((output/'support-mesh-report.json').read_text(encoding='utf-8'));surface.require_locked(report)
        blend=output/report['blendFile']
        if report['strategyId']!=STRATEGY or report['sourceBlendSha256']!=SOURCE_SHA or c.base.sha(blend)!=report['blendSha256']:raise ValueError('SAVED_ARTIFACT_IDENTITY_CHANGED')
        for row in report['renders']:
            if c.base.sha(output/row['file'])!=row['sha256']:raise ValueError('SAVED_RENDER_HASH_CHANGED')
        bpy.ops.wm.open_mainfile(filepath=str(blend));surface.require_locked(bpy.context.scene)
        obj=bpy.data.objects[RESULT_OBJECT];source=bpy.data.objects[prior.RESULT_OBJECT]
        if audit(obj,source,reports,report['operation'])!=report['qa']:raise ValueError('SAVED_QA_CHANGED')
        result=crease_constraints(obj,source,reports,report['operation'])
        target=output/'remaining-crease-report.json'
        if target.exists():raise ValueError('CONSTRAINT_REPORT_ALREADY_EXISTS')
        target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()));surface.require_locked(bpy.context.scene)
    source=bpy.data.objects[prior.RESULT_OBJECT]
    if args.probe:
        result=dict(strategyId=STRATEGY,status='FINITE_SUPPORT_MESH_SEARCH_NOT_GARMENT_APPROVAL',**c.base.GATES,
                    sourceBlendSha256=SOURCE_SHA,search=search(source,reports))
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result
    refs=c.base.verify_references(args.art_root.resolve())
    turn=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turn)!=prior.layout.panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turn.resolve()),sha256=prior.layout.panel.TURNAROUND_SHA))
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    curves={o.name:prior.curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE'}
    visibility={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')}
    obj,op,selection=build(source,reports);qa=audit(obj,source,reports,op)
    if not qa['eligible']:raise ValueError('FINAL_SUPPORT_MESH_QA_FAILED')
    line=guide(source,op['panels'][0]);guide_qa=audit_guide(source,op['panels'][0])
    output.mkdir(parents=True);renders=[] if args.no_render else render(output,source,obj,op,[line])
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):raise ValueError('ORIGINAL_MESH_UV_MATERIAL_OR_WEIGHTS_CHANGED')
    if curves!={n:prior.curve_snapshot(bpy.data.objects[n]) for n in curves}:raise ValueError('UPSTREAM_GUIDE_CHANGED')
    for name,(hidden,render_hidden) in visibility.items():bpy.data.objects[name].hide_set(hidden);bpy.data.objects[name].hide_render=render_hidden
    for o in (obj,line):o.hide_set(True);o.hide_render=True
    bpy.context.preferences.filepaths.save_version=0;bpy.context.preferences.filepaths.file_preview_type='NONE'
    blend=output/'CH101_MultiKnotUnderarmSupportMesh_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(args.source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    result=dict(strategyId=STRATEGY,status='ADDITIONAL_FORWARD_CORRECTED_PANEL_QA_PASS_NOT_FULL_UNDERARM',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,inputReportSha256=list(REPORT_SHAS),artCommit=c.base.ART_COMMIT,references=refs,
                runtime=dict(blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),device='CPU'),
                operation=op,selection=selection,qa=qa,guideQA=guide_qa,originalsPreserved=True,originalBodyMovedVertices=0,
                originalBodyCumulativeMaximumMoveMeters=.002999919,geometryShapeChanged=True,topologyChanged=True,
                fullUnderarmRebuilt=False,majorFoldShapeRedesigned=False,garmentStaticQA=False,deformationValidated=False,
                courseBoundaryRelocationApplied=False,adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['ONE_ADDITIONAL_28_MM_PANEL_WITH_ONE_SELECTED_SUPPORT_NOT_WHOLE_UNDERARM',
                             'GLOBAL_134_76_DEGREE_FOLD_AND_907_PROTECTED_EDGES_UNCHANGED',
                             'CUMULATIVE_ORIGINAL_CHART_1_5_MM_FINITE_SAMPLES_NOT_CONTINUOUS_BOUND',
                             'OPEN_UNOFFSET_STUDY_NO_UV_SEWING_THICKNESS_RIG_OR_HUMAN_GATE_B'])
    (output/'support-mesh-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def parser():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    for name in ('disk-report','cap-report','layout-report','curve-report'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--art-root',type=Path);p.add_argument('--probe',action='store_true');p.add_argument('--no-render',action='store_true')
    p.add_argument('--inspect-saved',action='store_true',help='Verify existing artifact and add a read-only remaining-fold classification')
    return p


if __name__=='__main__':
    p=parser();args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output is None or (not args.probe and not args.inspect_saved and args.art_root is None):p.error('--output and (unless probing/inspecting) --art-root are required')
    run(args)
