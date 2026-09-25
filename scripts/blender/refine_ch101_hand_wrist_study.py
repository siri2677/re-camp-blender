"""Tapered hand and bounded rigid wrist-fit study. Never cut or merge the body."""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_hand_authoring_study as author
import build_ch101_equipment_study as base
import review_ch101_equipment_fit as fit
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_HAND_TAPER_AND_BOUNDED_WRIST_FIT_V001'


def taper_cage(obj):
    """Wrist-only taper; distal palm, finger paths and thumb tips stay fixed."""
    changed=0
    for vertex in obj.data.vertices:
        z=vertex.co.z
        if z>=.025: continue
        t=max(0,min(1,z/.025)); smooth=t*t*(3-2*t)
        vertex.co.x*=.65+.35*smooth
        vertex.co.y*=.85+.15*smooth
        changed+=1
    obj.data.update()
    return dict(changedVertices=changed,wristWidthScale=.65,wristDepthScale=.85,
                unchangedAtOrAboveLocalZ=.025,fingerPathsChanged=False)


def wrist_sections(body,hand,axis):
    """Triangle-plane sample medians; not anatomical loops or authorized cut seams."""
    points,triangles=fit.geometry(body); result=[]
    for distance in (.03,.045,.06):
        center=Vector(hand)+Vector(axis)*distance; intersections=[]
        for tri in triangles:
            verts=[points[i] for i in tri]
            for a,b in zip(verts,verts[1:]+verts[:1]):
                da=(a-center).dot(axis); db=(b-center).dot(axis)
                if da*db<0:
                    hit=a+(b-a)*(da/(da-db))
                    if (hit-center).length<.06: intersections.append(hit)
        unique={tuple(round(v,7) for v in p) for p in intersections}
        if len(unique)<6: raise ValueError('WRIST_PLANE_INSUFFICIENT_SAMPLES')
        median=Vector(tuple(sorted(p[i] for p in unique)[len(unique)//2] for i in range(3)))
        result.append(dict(offsetTowardElbowMeters=distance,planeCenter=list(center),
            surfaceMedian=list(median),uniqueIntersectionSamples=len(unique),
            axisAlignedExtentMeters=[max(p[i] for p in unique)-min(p[i] for p in unique) for i in range(3)],
            verifiedAnatomicalSeam=False))
    return result


def self_surface_pairs(obj):
    tree,_,faces=fit.bvh(obj)
    return sum(a<b and not set(faces[a])&set(faces[b]) for a,b in tree.overlap(tree))


def rigid_trial(obj,saber,roll,slide):
    author.align_to_saber(obj,saber)
    original=obj.matrix_world.to_3x3(); rotation=original@Matrix.Rotation(math.radians(roll),3,'X')
    anchor=saber.matrix_world@Vector((0,0,.82+slide))
    matrix=rotation.to_4x4(); matrix.translation=anchor-rotation@author.GRIP_CENTER
    obj.matrix_world=matrix; bpy.context.view_layer.update()
    return ((matrix@author.GRIP_CENTER)-anchor).length


def compare_poses(obj,saber,parts,target,axis):
    trials=[]
    for slide in (0,.03):
        for roll in (0,90,-90,180):
            error=rigid_trial(obj,saber,roll,slide)
            overlaps=fit.overlap_report(obj,parts,obj.matrix_world@author.GRIP_CENTER)
            crossings=sum(r['uniqueEquipmentTrianglesCrossing'] for r in overlaps)
            wrist=obj.matrix_world@Vector((0,0,0))
            # Local -z points out of the capped wrist, toward an eventual forearm.
            outward=(obj.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
            angular_error=math.degrees(outward.angle(Vector(axis)))
            trials.append(dict(rollDegrees=roll,slideAlongHandleMeters=slide,
                wristCenter=list(wrist),wristTargetDistanceMeters=(wrist-Vector(target)).length,
                outwardAxisErrorDegrees=angular_error,anchorErrorMeters=error,
                surfaceCrossingTriangles=crossings,eligible=crossings==0 and error<1e-6))
    valid=[r for r in trials if r['eligible']]
    if not valid: raise ValueError('NO_NONCROSSING_WRIST_TRIAL')
    # Distance is the study objective, not a quality/attachment acceptance gate.
    selected=min(valid,key=lambda r:r['wristTargetDistanceMeters'])
    rigid_trial(obj,saber,selected['rollDegrees'],selected['slideAlongHandleMeters'])
    return trials,selected


def context_render(output,body,obj,target):
    scene=bpy.context.scene; camera=scene.camera
    body.hide_render=False
    slots=list(body.data.materials); indices=[p.material_index for p in body.data.polygons]
    material=base.material('Source_context_clay_NOT_EDIT',(.18,.21,.25))
    try:
        body.data.materials.clear(); body.data.materials.append(material)
        for p in body.data.polygons: p.material_index=0
        # Context light is world-aligned so the source surface remains legible.
        data=bpy.data.lights.new('Wrist_context_key','AREA'); data.energy=25; data.size=.4
        light=bpy.data.objects.new(data.name,data); scene.collection.objects.link(light)
        light.location=Vector(target)+Vector((-.3,-.4,.4)); light.rotation_euler=(Vector(target)-light.location).to_track_quat('-Z','Y').to_euler()
        camera.location=Vector(target)+Vector((-.20,-.6,.10))
        camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler(); camera.data.ortho_scale=.34
        path=output/'wrist_context_UNMERGED.png'; scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
    finally:
        body.data.materials.clear()
        for mat in slots: body.data.materials.append(mat)
        for p,index in zip(body.data.polygons,indices): p.material_index=index
        body.hide_render=True
    return dict(file=path.name,sha256=base.sha(path),sourceHandStillPresent=True,merged=False)


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0): raise ValueError('SOURCE_GATE_NOT_FALSE')
    source_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']; before=guide.digest(source_meshes)
    body=bpy.data.objects['geometry_0']; saber=bpy.data.objects['CH101_Saber']
    points,_=fit.geometry(body); hand=fit.refine_hand(points,guide.estimate(points))
    axis=-Vector(hand['forearmDirection']); sections=wrist_sections(body,hand['position'],axis)
    target=sections[1]['surfaceMedian'] # predeclared 45mm geometric slice, not optimized to the new hand
    collection=bpy.data.collections.new('HAND_WRIST_FIT_UNMERGED_STUDY'); bpy.context.scene.collection.children.link(collection)
    obj=author.make_hand(collection); obj.name='CH101_TaperedHand_NOT_PRODUCTION'; taper=taper_cage(obj)
    obj.data.materials.append(base.material('HandFit_Clay',(.32,.42,.44)))
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
    sub=obj.modifiers.new('Study_subdivision','SUBSURF'); sub.levels=1; bpy.ops.object.modifier_apply(modifier=sub.name)
    for p in obj.data.polygons: p.use_smooth=True
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(island_margin=.03); bpy.ops.object.mode_set(mode='OBJECT')
    parts=[o for o in source_meshes if o==saber or o.get('equipmentOwner')==saber.name]
    trials,selected=compare_poses(obj,saber,parts,target,axis)
    audit=author.shape_audit(obj); self_pairs=self_surface_pairs(obj)
    if audit['nonManifoldEdges'] or len(audit['components'])!=1 or audit['zeroAreaFaces'] or self_pairs:
        raise ValueError('HAND_SHAPE_FAILED')
    for old in source_meshes: old.hide_render=old not in parts
    output.mkdir(parents=True); renders=author.render_study(output,obj,saber)
    renders.append(context_render(output,body,obj,target))
    if guide.digest(source_meshes)!=before: raise ValueError('SOURCE_GEOMETRY_CHANGED')
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    blend=output/'CH101_TaperedHandWristStudy_NOT_PRODUCTION_v001.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='HAND_WRIST_FIT_STUDY_NOT_APPROVED',**base.GATES,
        artCommit=base.ART_COMMIT,references=refs,sourceBlendSha256=args.source_sha256,
        taper=taper,surfaceAudit=audit,nonAdjacentSelfSurfaceOverlapPairs=self_pairs,
        geometricWristSections=sections,targetSectionOffsetMeters=.045,poseTrials=trials,selectedPose=selected,
        originalPoseTargetDistanceMeters=trials[0]['wristTargetDistanceMeters'],
        sourceGeometryPreserved=True,sourceHandReplaced=False,wristSeamVerified=False,
        selectionPurpose='DISTANCE_DIAGNOSTIC_NOT_ATTACHMENT_ACCEPTANCE',wristIntegrationAllowed=False,
        sourceBodySurfaceOverlap=fit.overlap_report(body,[obj],saber.matrix_world@Vector((0,0,.82))),
        attachmentApproved=False,graspPoseVerified=False,fullCharacterScore=None,
        limitations=['SLICE_IS_NOT_ANATOMICAL_SEAM','RIGID_DISTANCE_MINIMUM_IS_NOT_ATTACHMENT_APPROVAL',
            'STATIC_SURFACE_TEST_NOT_SOLID_OR_ANIMATION','PALM_FINGERS_STILL_SIMPLIFIED','NO_SOURCE_CUT_OR_MERGE'],
        renders=renders,blendFile=blend.name,blendSha256=base.sha(blend))
    (output/'hand-wrist-fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
