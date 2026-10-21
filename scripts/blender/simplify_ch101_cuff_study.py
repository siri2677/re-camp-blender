"""Bounded, reversible cuff decimation; static part checks never open production gates."""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_cuff_interface_study as cuff

RATIOS=(.5,.25,.125,.0625)
MAX_SAMPLED_ERROR=.00015
STRATEGY='CH101_BOUNDED_CUFF_SIMPLIFICATION_V001'

def simplify(source,ratio):
    if not 0<ratio<1: raise ValueError('INVALID_DECIMATION_RATIO')
    obj=source.copy();obj.data=source.data.copy()
    obj.name=f'CUFF_REDUCTION_{ratio:g}_NOT_PRODUCTION'
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    modifier=obj.modifiers.new('Bounded_collapse','DECIMATE')
    modifier.decimate_type='COLLAPSE';modifier.ratio=ratio;modifier.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    for key in ('ringVertexCount','intermediateSections','maxOutwardCorrectionMeters'):
        if key in obj:
            obj['source_'+key]=obj[key];del obj[key]
    obj['topologyStage']='DECIMATED_COPY_NOT_STRUCTURED_RINGS'
    cuff.base.mark(obj);obj['designApproved']=False;obj['attachmentApproved']=False
    obj['sourceReplacementAllowed']=False
    return obj

def samples(obj):
    points,faces=cuff.fit.geometry(obj)
    yield from points
    for face in faces:
        a,b,c=(points[i] for i in face)
        yield (a+b+c)/3
        yield (a+b)/2;yield (b+c)/2;yield (c+a)/2

def directed_error(source,target):
    tree,_,_=cuff.fit.bvh(target);count=0;maximum=0
    for point in samples(source):
        hit=tree.find_nearest(point)
        if hit is None or hit[0] is None:raise ValueError('SURFACE_DISTANCE_UNAVAILABLE')
        maximum=max(maximum,float(hit[3]));count+=1
    return dict(sampleCount=count,maxMeters=maximum)

def reversed_normal_samples(reference,obj):
    tree,_,_=cuff.fit.bvh(reference);points,faces=cuff.fit.geometry(obj);reversed_count=0
    for face in faces:
        a,b,c=(points[i] for i in face);normal=(b-a).cross(c-a).normalized()
        hit=tree.find_nearest((a+b+c)/3)
        if hit[1] is None or normal.dot(hit[1])<=0:reversed_count+=1
    return reversed_count

def assess(reference,obj,hand,equipment=()):
    audit=cuff.author.shape_audit(obj)
    euler=len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons)
    self_pairs=cuff.wrist.self_surface_pairs(obj)
    hand_pairs=cuff.fit.overlap_report(hand,[obj],hand.matrix_world@Vector())[0]
    equipment_pairs=[cuff.fit.overlap_report(part,[obj],part.matrix_world@Vector())[0] for part in equipment]
    forward=directed_error(reference,obj);reverse=directed_error(obj,reference)
    normal_reversals=reversed_normal_samples(reference,obj)
    uv=obj.data.uv_layers.active
    finite_uv=uv is not None and all(math.isfinite(x) for loop in uv.data for x in loop.uv)
    reasons=[]
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or len(audit['components'])!=1 or euler!=0:reasons.append('TOPOLOGY_INVALID')
    if self_pairs:reasons.append('SELF_SURFACE_CROSSING')
    if hand_pairs['uniqueEquipmentTrianglesCrossing']:reasons.append('HAND_SURFACE_CROSSING')
    if any(r['uniqueEquipmentTrianglesCrossing'] for r in equipment_pairs):reasons.append('EQUIPMENT_SURFACE_CROSSING')
    if max(forward['maxMeters'],reverse['maxMeters'])>MAX_SAMPLED_ERROR:reasons.append('SAMPLED_SURFACE_ERROR_EXCEEDED')
    if not finite_uv:reasons.append('UV_MISSING_OR_NONFINITE')
    if normal_reversals:reasons.append('SAMPLED_NORMAL_ORIENTATION_MISMATCH')
    if audit['triangles']>=cuff.author.shape_audit(reference)['triangles']:reasons.append('NO_TRIANGLE_REDUCTION')
    if any(obj.get(k) not in (False,0) for k in ('unityInputAllowed','productionPromotionAllowed')):reasons.append('PROMOTION_GATE_NOT_FALSE')
    return dict(eligible=not reasons,rejectionReasons=reasons,topology=audit,eulerCharacteristic=euler,
        selfSurfacePairs=self_pairs,handSurfaceOverlap=hand_pairs,equipmentSurfaceOverlaps=equipment_pairs,
        referenceToTrialSamples=forward,trialToReferenceSamples=reverse,
        maxSampledErrorLimitMeters=MAX_SAMPLED_ERROR,finiteUV=finite_uv,reversedNormalSamples=normal_reversals,
        limitations=['SAMPLED_DISTANCE_NOT_CONTINUOUS_HAUSDORFF_BOUND','NO_CONTAINMENT_OR_ANIMATION_PROOF','UV_LAYOUT_NOT_FINAL_ATLAS'])

def run(args):
    source=args.source.resolve();output=args.output.resolve()
    if cuff.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=cuff.base.verify_references(args.art_root.resolve())
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0):raise ValueError('SOURCE_GATE_NOT_FALSE')
    sources=[o for o in bpy.context.scene.objects if o.type=='MESH'];before=cuff.guide.digest(sources)
    reference=bpy.data.objects['CH101_HollowCuff_HYPOTHESIS_NOT_PRODUCTION']
    hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'];body=bpy.data.objects['geometry_0']
    equipment=[o for o in sources if o.name.startswith('PAIR_STUDY_') and o!=hand]
    trials=[];objects=[]
    for ratio in RATIOS:
        obj=simplify(reference,ratio);objects.append(obj)
        trial=dict(ratio=ratio,object=obj.name,**assess(reference,obj,hand,equipment));trials.append(trial)
        obj.hide_render=True
    eligible=[i for i,t in enumerate(trials) if t['eligible']]
    report=dict(strategyId=STRATEGY,**cuff.base.GATES,sourceBlendSha256=args.source_sha256,
        references=refs,artCommit=cuff.base.ART_COMMIT,sourceTriangles=cuff.author.shape_audit(reference)['triangles'],
        trials=trials,sourceHandReplaced=False,anatomicalSeamVerified=False,wristIntegrationAllowed=False,
        attachmentApproved=False,designApproved=False,fullCharacterScore=None)
    output.mkdir(parents=True)
    if not eligible:
        report['status']='NO_ELIGIBLE_SIMPLIFICATION'
    else:
        selected=min(eligible,key=lambda i:trials[i]['topology']['triangles']);obj=objects[selected]
        for old in sources:old.hide_render=not old.name.startswith('PAIR_STUDY_')
        obj.hide_render=False
        center=hand.matrix_world@Vector();axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
        loops=cuff.pair.closed_section(body,center,axis)
        renders=cuff.pair.render_views(output,body,hand,center,axis,loops)
        if cuff.guide.digest(sources)!=before:raise ValueError('SOURCE_GEOMETRY_CHANGED')
        for key,value in cuff.base.GATES.items():bpy.context.scene[key]=value
        blend=output/'CH101_ReducedCuff_NOT_PRODUCTION_v001.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        report.update(status='REDUCED_STATIC_CUFF_STUDY_NOT_APPROVED',selectedTrial=selected,
            sourceGeometryPreserved=True,renders=renders,blendFile=blend.name,blendSha256=cuff.base.sha(blend),
            cuffVsPreservedBody=cuff.fit.overlap_report(body,[obj],center),
            sourceCuffPreservedHidden=True,unselectedTrialsPreservedHidden=True)
    if cuff.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_FILE_CHANGED')
    (output/'cuff-reduction-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
