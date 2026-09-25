"""Two inspected directional sleeve lobes; cumulative budget pinned to albedo.

No repeated whole-band field, remeshing, texture edits or semantic approval.
Angles refer to the authored hand frame, not inferred reference-art coordinates.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_ch101_shared_interface as shared

c, seam, surface = shared.c, shared.seam, shared.surface
SOURCE_SHA = '78d3cff27162913ac30283c8ac56ea2f8a57566cb98066cdc3ca2c3b71fe08e2'
BASELINE_DIGEST = '5e4b05c4ed4c58f63460225c283a154bcb3e39ccdbf971741b4095b2fe4adc2a'
STRATEGY = 'CH101_DIRECTIONAL_SECTOR_PROFILE_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_SectorProfile_NOT_PRODUCTION'
SECTORS = ((326.25,50.), (157.5,35.))
AMPLITUDE = .0012
TOTAL_BUDGET = .003
STORAGE_MARGIN = .0000001


def angular_weight(angle, center, width):
    if not all(math.isfinite(x) for x in (angle,center,width)) or not 0 < width < math.pi:
        raise ValueError('INVALID_SECTOR_ANGLE')
    distance = abs((angle-center+math.pi) % (2*math.pi)-math.pi)
    return math.cos(math.pi*distance/(2*width))**2 if distance < width else 0.


def profile_weight(z, angle):
    if .078 < z < .098:
        axial = seam.trim.upper.smoothstep(.078,.098,z)
    elif .098 <= z < .132:
        axial = 1-seam.trim.upper.smoothstep(.098,.132,z)
    else:
        return 0.
    return axial*max(angular_weight(angle,math.radians(a),math.radians(w)) for a,w in SECTORS)


def budgeted_position(original, current, proposed_delta, budget=TOTAL_BUDGET):
    """Project TOTAL displacement into the original ball, not a renewed budget."""
    if not STORAGE_MARGIN < budget <= TOTAL_BUDGET or not all(math.isfinite(v) for p in (original,current,proposed_delta) for v in p):
        raise ValueError('INVALID_CUMULATIVE_BUDGET')
    existing = current-original
    if existing.length > budget:
        raise ValueError('INPUT_ALREADY_EXCEEDS_ORIGINAL_BUDGET')
    total = existing+proposed_delta
    limited = total.length > budget-STORAGE_MARGIN
    if limited:
        total *= (budget-STORAGE_MARGIN)/total.length
    return original+total, limited


def angular_diagnosis(obj, center, axis, u):
    tree, _, _ = c.fit.bvh(obj)
    v = axis.cross(u)
    rows = []
    for i in range(64):
        angle = 2*math.pi*i/64
        direction = u*math.cos(angle)+v*math.sin(angle)
        rr = [shared.outer_radius(tree,center,axis,z,direction) for z in (.083,.098,.110)]
        deviation = rr[1]-(rr[0]*.012+rr[2]*.015)/.027
        rows.append(dict(angleDegrees=i*360/64,radiiMeters=rr,localRidgeExcessMeters=deviation))
    return dict(sampleAngles=64,heightsMeters=[.083,.098,.110],rows=rows,
                metricIsNotVisualScore=True,anglesAreHandFrameNotReferenceArtMeasurements=True)


def distortion(obj, reference, affected):
    ratios = [obj.data.polygons[i].area/reference.data.polygons[i].area for i in affected]
    dot = min(obj.data.polygons[i].normal.dot(reference.data.polygons[i].normal) for i in affected)
    if dot < .90 or min(ratios) < .5 or max(ratios) > 1.5:
        raise ValueError('SECTOR_FACE_DISTORTION_REJECTED')
    return dict(minimumNormalDot=dot,areaRatioRange=[min(ratios),max(ratios)])


def refine(source, baseline, center, axis, u, amplitude=AMPLITUDE):
    if not 0 < amplitude <= AMPLITUDE:
        raise ValueError('UNSAFE_SECTOR_AMPLITUDE')
    if c.guide.digest([baseline]) != BASELINE_DIGEST:
        raise ValueError('ORIGINAL_BUDGET_BASELINE_CHANGED')
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_SECTOR_FRAME')
    if surface.repair.invariant_signature(source) != surface.repair.invariant_signature(baseline):
        raise ValueError('BASELINE_TOPOLOGY_UV_CORRESPONDENCE_CHANGED')
    points = [source.matrix_world@v.co for v in source.data.vertices]
    originals = [baseline.matrix_world@v.co for v in baseline.data.vertices]
    if any((p-q).length>TOTAL_BUDGET for p,q in zip(points,originals)):
        raise ValueError('INPUT_ALREADY_EXCEEDS_ORIGINAL_BUDGET')
    v = axis.cross(u)
    weights, targets, capped = {}, {}, []
    for i, point in enumerate(points):
        d = point-center
        z = d.dot(axis)
        radial = d-axis*z
        if not .015 < radial.length < .075 or not -.40 < point.x < -.17:
            continue
        weight = profile_weight(z,math.atan2(radial.dot(v),radial.dot(u)))
        if weight <= 1e-8:
            continue
        weights[i] = weight
        targets[i], limited = budgeted_position(originals[i],point,-radial.normalized()*amplitude*weight)
        if limited:
            capped.append(i)
    if len(weights)!=138:
        raise ValueError('SECTOR_SUPPORT_CONTRACT_CHANGED')
    selected = set(weights)
    affected = [p.index for p in source.data.polygons if set(p.vertices)&selected]
    support = {i for f in affected for i in source.data.polygons[f].vertices}
    if any(not (-.40 < points[i].x < -.17 and .90 < points[i].z < 1.14) for i in support):
        raise ValueError('SECTOR_AFFECTED_SUPPORT_OUTSIDE_FOREARM')
    obj=source.copy();obj.data=source.data.copy();obj.name=RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    try:
        inverse=obj.matrix_world.inverted()
        for i,p in targets.items():obj.data.vertices[i].co=inverse@p
        obj.data.update()
        actual=[obj.matrix_world@v.co for v in obj.data.vertices]
        total=max((p-q).length for p,q in zip(actual,originals))
        incremental=max((actual[i]-points[i]).length for i in weights)
        axial=max(abs((actual[i]-points[i]).dot(axis)) for i in weights)
        if total>TOTAL_BUDGET or incremental>amplitude+1e-7 or axial>1e-7:
            raise ValueError('SECTOR_STORED_DISPLACEMENT_REJECTED')
        incremental_distortion=distortion(obj,source,affected)
        total_distortion=distortion(obj,baseline,affected)
        shared.verify_preservation(source,obj,selected)
        lower=shared.contour.group_ids(source,'SleeveSeam')
        inner=shared.contour.group_ids(source,'UpperOpening_inner')
        pairs=[(i,min(inner,key=lambda j:(points[i]-points[j]).length)) for i in sorted(lower)]
        if len({j for _,j in pairs})!=32:raise ValueError('RIM_PAIRING_AMBIGUOUS')
        thickness=[(actual[i]-actual[j]).length for i,j in pairs]
        if min(thickness)<.001 or max(abs((actual[i]-actual[j]).length-(points[i]-points[j]).length) for i,j in pairs)>.00025:
            raise ValueError('SECTOR_RIM_THICKNESS_REJECTED')
        before,after=shared.envelope_metrics(source,center,axis,u),shared.envelope_metrics(obj,center,axis,u)
        if after['radialSlopeJumpRms']>=before['radialSlopeJumpRms']:
            raise ValueError('SECTOR_GEOMETRY_DIAGNOSTIC_NOT_IMPROVED')
        unaffected=set(range(len(source.data.polygons)))-set(affected)
        normal_errors=sum(obj.data.polygons[i].normal.dot(source.data.polygons[i].normal)<.999 for i in unaffected)
        c.base.mark(obj);obj['sectorProfileStudy']=True
        return obj,dict(method='TWO_FIXED_DIRECTIONAL_RADIAL_LOBES',sectorsDegrees=list(SECTORS),
                        axialSupportMeters=[.078,.098,.132],amplitudeLimitMeters=amplitude,
                        selectedVertexCount=len(weights),selectedVertexIndices=sorted(selected),supportWeights=weights,
                        actualMovedVertexCount=sum(actual[i]!=points[i] for i in selected),
                        displacementWorld={i:list(actual[i]-points[i]) for i in sorted(selected)},
                        affectedPolygonIndices=affected,budgetClippedVertexIndices=capped,
                        cumulativeBudgetReferenceObject=baseline.name,cumulativeBudgetReferenceDigest=BASELINE_DIGEST,
                        maxCumulativeMoveMeters=total,maxIncrementalMoveMeters=incremental,maxAxialDriftMeters=axial,
                        cumulativeLimitMeters=TOTAL_BUDGET,incrementalDistortion=incremental_distortion,
                        cumulativeDistortion=total_distortion,sampledRimThicknessMeters=[min(thickness),max(thickness)],
                        metricsBefore=before,metricsAfter=after,angleDiagnosisBefore=angular_diagnosis(source,center,axis,u),
                        angleDiagnosisAfter=angular_diagnosis(obj,center,axis,u),
                        topologyUVAtlasMaskWeightsPreserved=True,packedAtlasSha256=shared.atlas_signature(obj),
                        retainedNormalMismatches=normal_errors,copiedUVErrors=0)
    except Exception:
        mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
        raise


def support_render(output,obj,parts,operation,center,axis):
    scene=bpy.context.scene
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    diagnostic=seam.trim.upper.diagnostic_copy(obj)
    attr=diagnostic.data.attributes[seam.trim.upper.MASK]
    weights=operation['supportWeights']
    for i,item in enumerate(attr.data):item.value=weights.get(i,0.)
    diagnostic.hide_render=False
    for part in parts:part.hide_render=False
    target=center+axis*.11
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('SectorSupport','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
        light.location=target+Vector(delta);light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    camera=scene.camera;camera.data.type='ORTHO';camera.data.ortho_scale=.36
    camera.location=target+Vector((-.7,.05,.1));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    path=output/'sector_support.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    diagnostic.hide_render=True
    return dict(file=path.name,sha256=c.base.sha(path),meaning='REQUESTED_SECTOR_WEIGHT_ON_DIAGNOSTIC_COPY_NOT_MATERIAL_MASK_EXPANSION')


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals)
    invariants={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[shared.RESULT_OBJECT];baseline=bpy.data.objects[shared.bake.RESULT_OBJECT]
    source_fields=shared.fields(body)
    center,axis,u=shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=refine(body,baseline,center,axis,u)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=seam.assess(obj,parts,operation)
    if not qa['eligible']:raise ValueError('SECTOR_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[]
    if not args.no_render:
        renders=seam.trim.upper.render(output,body,obj,parts,center,axis)
        renders+=shared.bake.patch.transition.clay_comparison(output,body,obj,center,axis)
        renders.append(support_render(output,obj,parts,operation,center,axis))
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=invariants[o.name] for o in originals) or shared.fields(body)!=source_fields:
        raise ValueError('ORIGINAL_CHANGED')
    visible=seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [obj]+parts
    surface.require_locked(bpy.context.scene);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_SectorProfile_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='BOUNDED_SECTOR_PROFILE_STUDY_NOT_APPROVED',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,attachmentApproved=False,fullCharacterScore=None,
                defaultVisibleMeshObjects=visible,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['GEOMETRY_METRICS_NOT_VISUAL_QUALITY','NO_REFERENCE_EXACT_TAILORING',
                             'ORIGINAL_CUMULATIVE_DISPLACEMENT_BUDGET_NOT_RESET','STATIC_BVH_EXCLUDES_SHARED_VERTICES',
                             'RIM_THICKNESS_SAMPLES_NOT_SOLID_OR_ANIMATION_PROOF','NO_RIG_OR_HUMAN_GATE_B'])
    (output/'sector-profile-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text(
        'CH101 directional sector profile v001 — NOT PRODUCTION\n'
        'New copy only; two inspected angular lobes. Original September 23 albedo mesh remains the TOTAL 3 mm displacement reference.\n'
        'Geometry connectivity, UVs, packed atlas, material masks, trim fields and weights are unchanged.\n'
        'sector_support.png shows requested edit weights on a diagnostic copy; mask_context.png is the inherited material mask.\n'
        'Matched renders and report are review evidence, not a final quality score, rig proof or Gate B approval.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps({k:r[k] for k in ('status','blendSha256')},indent=2))
