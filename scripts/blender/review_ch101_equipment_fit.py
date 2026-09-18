"""Estimated static fit with surface-overlap diagnostics, never final binding."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
import prepare_ch101_landmark_rig_review as guide
import build_ch101_equipment_study as base

STRATEGY='CH101_STATIC_EQUIPMENT_FIT_DIAGNOSTIC_V001'


def geometry(obj):
    mesh=obj.data; mesh.calc_loop_triangles()
    vertices=[obj.matrix_world@v.co for v in mesh.vertices]
    faces=[tuple(t.vertices) for t in mesh.loop_triangles]
    return vertices,faces


def bvh(obj):
    vertices,faces=geometry(obj)
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),vertices,faces


def pose_at_anchor(obj,local_anchor,target,z_axis):
    z=Vector(z_axis).normalized()
    x=Vector((0,-1,0)).cross(z).normalized()
    if x.length<.9: raise ValueError('AMBIGUOUS_POSE_AXIS')
    y=z.cross(x).normalized()
    rotation=Matrix((x,y,z)).transposed()
    matrix=rotation.to_4x4(); matrix.translation=Vector(target)-rotation@Vector(local_anchor)
    obj.matrix_world=matrix
    return matrix


def refine_hand(points,landmarks):
    low=min(p.z for p in points); height=max(p.z for p in points)-low
    cx=(max(p.x for p in points)+min(p.x for p in points))/2
    half=(max(p.x for p in points)-min(p.x for p in points))/2
    chosen=[p for p in points if .48<(p.z-low)/height<.525 and (cx-p.x)/half>.82]
    if len(chosen)<8: raise ValueError('INSUFFICIENT_DISTAL_HAND_SAMPLES')
    center=Vector(tuple(sorted(p[i] for p in chosen)[len(chosen)//2] for i in range(3)))
    elbow=Vector(landmarks['NegX_Elbow']['position'])
    axis=(center-elbow).normalized()
    return dict(position=list(center),sampleCount=len(chosen),forearmDirection=list(axis),
                status='DISTAL_GEOMETRIC_HAND_ESTIMATE_NOT_GRASP_VERIFIED',
                depthExtent=max(p.y for p in chosen)-min(p.y for p in chosen))


def waist_surface(tree,points,faces):
    low=min(p.z for p in points); height=max(p.z for p in points)-low
    cx=(max(p.x for p in points)+min(p.x for p in points))/2
    half=(max(p.x for p in points)-min(p.x for p in points))/2
    # Exclude the outer arm before casting toward the torso. This is still a
    # documented geometric ROI, not semantic waist recognition.
    indices=[i for i,f in enumerate(faces) if all(abs(points[v].x-cx)<half*.55 for v in f)
             and .56<sum(points[v].z-low for v in f)/len(f)/height<.66]
    if not indices: raise ValueError('TORSO_ROI_EMPTY')
    tree=BVHTree.FromPolygons(points,[faces[i] for i in indices],all_triangles=True)
    # Cast from PosX side onto the actual shell. No centroid of front/back surfaces.
    cy=(max(p.y for p in points)+min(p.y for p in points))/2
    origin=Vector((max(p.x for p in points)+.2,cy,low+height*.61))
    hit,normal,index,distance=tree.ray_cast(origin,Vector((-1,0,0)),1.0)
    if hit is None: raise ValueError('WAIST_SURFACE_RAY_MISSED')
    if normal.x<0: normal=-normal
    return dict(position=list(hit),normal=list(normal),triangleIndex=indices[index],
                torsoRoiHalfWidthRatio=.55,excludedOuterArmRegion=True,
                rayOrigin=list(origin),rayDirection=[-1,0,0],
                status='LATERAL_SHELL_HIT_NOT_BELT_ANATOMY_VERIFIED')


def overlap_report(character,objects,hand):
    tree,_,_=bvh(character); result=[]
    hand=Vector(hand)
    for obj in objects:
        other,vertices,faces=bvh(obj)
        pairs=tree.overlap(other)
        triangles=sorted({pair[1] for pair in pairs})
        near=[]; away=[]
        for index in triangles:
            center=sum((vertices[v] for v in faces[index]),Vector())/3
            (near if (center-hand).length<.065 else away).append(index)
        nearest=[tree.find_nearest(v)[3] for v in vertices]
        result.append(dict(object=obj.name,overlapTrianglePairCount=len(pairs),
            uniqueEquipmentTrianglesCrossing=len(triangles),
            nearHandCrossingTriangles=len(near),awayFromHandCrossingTriangles=len(away),
            minimumVertexSurfaceDistance=min(d for d in nearest if d is not None),
            method='BVH_TRIANGLE_SURFACE_OVERLAP_PLUS_VERTEX_DISTANCE',
            limitation='NOT_SOLID_CONTAINMENT_OR_SWEPT_ANIMATION_COLLISION_TEST'))
    return result


def render(output,hand,waist):
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.device='CPU'
    scene.render.resolution_x=900; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    cam=scene.camera; cam.data.type='ORTHO'
    specs=[('front',(0,-4,.84),(0,0,.84),2.15),
           ('three_quarter',(2,-4,1.1),(0,0,.84),2.15),
           ('hand_close',tuple(Vector(hand)+Vector((-.15,-1,.10))),hand,.32),
           ('waist_close',tuple(Vector(waist)+Vector((1,-.7,.13))),waist,.48)]
    renders=[]
    for name,pos,target,scale in specs:
        cam.location=pos; cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.data.ortho_scale=scale; path=output/(name+'.png'); scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(dict(view=name,file=path.name,sha256=base.sha(path)))
    cam.data.ortho_scale=2.15; cam.location=(2,-4,1.1)
    cam.rotation_euler=(Vector((0,0,.84))-cam.location).to_track_quat('-Z','Y').to_euler()
    return renders


def tag_hardware(collection):
    # hide_viewport invalidates Blender's live all_objects iterator. Snapshot
    # object references before changing visibility; do not skip missing items.
    for o in list(collection.all_objects):
        base.mark(o); o['fitStatus']='ESTIMATED_STATIC_FIT_NOT_APPROVED'
        if o.name=='CH101_SignalRibbon_SINGLE' or o.get('equipmentOwner')=='CH101_SignalRibbon_SINGLE' or o.name.startswith('Socket_Ribbon_'):
            o.hide_render=True; o.hide_viewport=True; o['fitStatus']='STAGED_NOT_PLACED'


def run(args):
    source=args.source.resolve(); hardware=args.hardware.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    if base.sha(hardware)!=args.hardware_sha256: raise ValueError('HARDWARE_SHA256_MISMATCH')
    references=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    characters=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('ReviewFloor_')]
    if len(characters)!=1: raise ValueError('EXPECTED_SINGLE_PRESERVED_CHARACTER_MESH')
    character=characters[0]; before=guide.digest(characters)
    tree,points,faces=bvh(character)
    landmarks=guide.estimate(points); hand=refine_hand(points,landmarks); waist=waist_surface(tree,points,faces)
    with bpy.data.libraries.load(str(hardware),link=False) as (available,loaded):
        if 'MODEL_EQUIPMENT' not in available.collections: raise ValueError('HARDWARE_COLLECTION_MISSING')
        loaded.collections=['MODEL_EQUIPMENT']
    collection=loaded.collections[0]; bpy.context.scene.collection.children.link(collection)
    objs={o.name:o for o in collection.all_objects}
    saber=objs['CH101_Saber']; sheath=objs['CH101_Sheath']
    tag_hardware(collection)
    # A bounded static diagnostic, not free-running quality retries or a grasp
    # solver. Keep every trial and do not infer grasp from a collision count.
    saber_objects=[o for o in collection.all_objects if o.type=='MESH' and (o==saber or o.get('equipmentOwner')==saber.name)]
    pose_trials=[]
    axes=[('forearm_aligned',-Vector(hand['forearmDirection'])),
          ('vertical',Vector((0,0,1))),('front_pitched',Vector((0,-.5,.8660254)))]
    for name,axis in axes:
        matrix=pose_at_anchor(saber,(0,0,.82),hand['position'],axis)
        bpy.context.view_layer.update()
        check=overlap_report(character,saber_objects,hand['position'])
        pose_trials.append(dict(name=name,axis=list(axis),matrix=[list(row) for row in matrix],
            awayFromHandCrossingTriangles=sum(r['awayFromHandCrossingTriangles'] for r in check),
            nearHandCrossingTriangles=sum(r['nearHandCrossingTriangles'] for r in check)))
    selected=min(pose_trials,key=lambda r:(r['awayFromHandCrossingTriangles'],r['nearHandCrossingTriangles']))
    saber_matrix=pose_at_anchor(saber,(0,0,.82),hand['position'],selected['axis'])
    waist_target=Vector(waist['position'])+Vector(waist['normal'])*.035
    sheath_matrix=pose_at_anchor(sheath,(0,0,.698),waist_target,Vector((-.1,0,1)))
    bpy.context.view_layer.update()
    visible=[o for o in collection.all_objects if o.type=='MESH' and not o.hide_render]
    overlaps=overlap_report(character,visible,hand['position'])
    grip=objs['Socket_Weapon_R'].matrix_world.translation
    error=(grip-Vector(hand['position'])).length
    if error>1e-5: raise ValueError('GRIP_ANCHOR_TRANSFORM_MISMATCH')
    material_count=len({m.name for o in characters+visible for m in o.data.materials if m})
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    for key,value in {'source_status':base.GATES['sourceStatus'],'gate_b':base.GATES['gateB'],
                      'unity_input_allowed':False,'production_promotion_allowed':False}.items(): bpy.context.scene[key]=value
    output.mkdir(parents=True)
    renders=render(output,hand['position'],waist['position'])
    if guide.digest(characters)!=before: raise ValueError('CHARACTER_CHANGED')
    blend=output/'CH101_StaticEquipmentFit_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256 or base.sha(hardware)!=args.hardware_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='STATIC_FIT_DIAGNOSTIC_NOT_APPROVED',**base.GATES,
        artifactScope='ESTIMATED_ATTACHMENT_DIAGNOSTIC_NOT_PRODUCTION',
        sourceBlendSha256=args.source_sha256,hardwareBlendSha256=args.hardware_sha256,
        artCommit=base.ART_COMMIT,references=references,hand=hand,waist=waist,
        saberMatrix=[list(row) for row in saber_matrix],sheathMatrix=[list(row) for row in sheath_matrix],
        poseTrials=pose_trials,selectedDiagnosticPose=selected['name'],
        gripAnchorErrorMeters=error,combinedMaterialCount=material_count,
        materialBudgetStatus='PASS' if material_count<=6 else 'BLOCKED_COMBINED_MATERIAL_BUDGET',
        surfaceOverlapAudit=overlaps,
        characterGeometryWeightsMaterialsUnchanged=True,skinWeightsApplied=False,
        anatomicalLeftRightConfirmed=False,ribbonPlacement='STAGED_HIDDEN_NOT_PLACED',
        attachmentApproved=False,graspPoseVerified=False,fullCharacterScore=None,
        limitations=['OPEN_HAND_GEOMETRY_NOT_GRIP_POSED','GEOMETRIC_SIDE_LABEL_NOT_VERIFIED_ANATOMY',
                     'STATIC_SURFACE_TEST_NOT_PHYSICS_VALIDATION','WAIST_HIT_MAY_BE_CLOTHING_NOT_BELT'],
        blendFile=blend.name,blendSha256=base.sha(blend),renders=renders)
    (output/'equipment-fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True)
    p.add_argument('--source-sha256',required=True); p.add_argument('--hardware',type=Path,required=True)
    p.add_argument('--hardware-sha256',required=True); p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
