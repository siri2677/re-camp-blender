"""Unbound landmark guide on a preserved mesh; never a validated humanoid rig."""
import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_equipment_study as equipment

STRATEGY='CH101_SURFACE_BAND_LANDMARK_GUIDE_V001'


def digest(meshes):
    payload=[dict(name=o.name,vertices=[list(o.matrix_world@v.co) for v in o.data.vertices],
                  polygons=[list(p.vertices) for p in o.data.polygons],
                  groups=[g.name for g in o.vertex_groups],
                  memberships=[[(g.group,g.weight) for g in v.groups] for v in o.data.vertices],
                  materials=[m.name if m else None for m in o.data.materials],
                  materialIndices=[p.material_index for p in o.data.polygons],
                  modifiers=[(m.name,m.type) for m in o.modifiers]) for o in meshes]
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def estimate(points):
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    height=high.z-low.z; half=(high.x-low.x)/2; cx=(high.x+low.x)/2
    if height<=0 or half<=0: raise ValueError('DEGENERATE_MESH_BOUNDS')
    result={}
    # These bands are explicit geometric hypotheses, not semantic landmarks.
    specs={'Hand':(.46,.55,.72,1.05),'Elbow':(.58,.68,.48,.85),
           'Shoulder':(.70,.79,.22,.52),'Waist':(.56,.64,.08,.32)}
    for side,sign in [('NegX',-1),('PosX',1)]:
        for role,(z0,z1,x0,x1) in specs.items():
            selected=[p for p in points if z0<=(p.z-low.z)/height<=z1 and x0<=sign*(p.x-cx)/half<=x1]
            if len(selected)<8: raise ValueError('INSUFFICIENT_SURFACE_SAMPLES:'+side+role)
            center=Vector(tuple(statistics.median(p[i] for p in selected) for i in range(3)))
            spread=[max(p[i] for p in selected)-min(p[i] for p in selected) for i in range(3)]
            result[side+'_'+role]=dict(position=list(center),sampleCount=len(selected),
                sampleExtent=spread,band=dict(height=[z0,z1],signedHalfWidth=[x0,x1]),
                nearestSurfaceVertexDistance=min((p-center).length for p in selected),
                status='GEOMETRIC_BAND_ESTIMATE_NOT_ANATOMY_VERIFIED')
    return result


def guide(landmarks):
    collection=bpy.data.collections.new('REVIEW_LANDMARK_GUIDES_NOT_CHARACTER_GEOMETRY')
    bpy.context.scene.collection.children.link(collection)
    data=bpy.data.armatures.new('CH101_Unbound_LandmarkGuide')
    arm=bpy.data.objects.new('CH101_Unbound_LandmarkGuide_NOT_APPROVED',data)
    collection.objects.link(arm); equipment.mark(arm)
    arm['rig_status']='UNBOUND_GEOMETRIC_GUIDE_NOT_VALIDATED_HUMANOID'
    arm.show_in_front=True
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
    bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
    waist=(Vector(landmarks['NegX_Waist']['position'])+Vector(landmarks['PosX_Waist']['position']))/2
    shoulder=(Vector(landmarks['NegX_Shoulder']['position'])+Vector(landmarks['PosX_Shoulder']['position']))/2
    core=data.edit_bones.new('Guide_Core'); core.head=waist; core.tail=shoulder
    for side in ['NegX','PosX']:
        parent=core
        for name,a,b in [('Shoulder',shoulder,landmarks[side+'_Shoulder']['position']),
                         ('UpperArm',landmarks[side+'_Shoulder']['position'],landmarks[side+'_Elbow']['position']),
                         ('Forearm',landmarks[side+'_Elbow']['position'],landmarks[side+'_Hand']['position'])]:
            bone=data.edit_bones.new('Guide_'+side+'_'+name); bone.head=a; bone.tail=b; bone.parent=parent; parent=bone
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in data.bones: bone.use_deform=False
    for side,color in [('NegX',(1,.15,.02,1)),('PosX',(.02,.7,1,1))]:
        mat=bpy.data.materials.new('Guide_'+side); mat.diffuse_color=color; mat.use_nodes=True
        bsdf=mat.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Base Color'].default_value=color
        bsdf.inputs['Emission Color'].default_value=color; bsdf.inputs['Emission Strength'].default_value=1
        for a,b in [('Shoulder','Elbow'),('Elbow','Hand'),('Waist','Shoulder')]:
            curve=bpy.data.curves.new('DEBUG_LINE_'+side+a,'CURVE'); curve.dimensions='3D'
            curve.bevel_depth=.005; curve.bevel_resolution=0
            spline=curve.splines.new('POLY'); spline.points.add(1)
            for point,role in zip(spline.points,[a,b]): point.co=(*landmarks[side+'_'+role]['position'],1)
            line=bpy.data.objects.new(curve.name,curve); collection.objects.link(line)
            curve.materials.append(mat); line['debugOnly']=True; equipment.mark(line)
        for role in ['Hand','Elbow','Shoulder','Waist']:
            entry=landmarks[side+'_'+role]; pos=Vector(entry['position'])
            anchor=bpy.data.objects.new('ReviewAnchor_'+side+'_'+role,None); collection.objects.link(anchor)
            anchor.location=pos; anchor.empty_display_size=.03; equipment.mark(anchor)
            anchor['landmarkStatus']=entry['status']
            # Spheres are visibly separate debug markers, never model geometry.
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.021,location=pos)
            marker=bpy.context.object; marker.name='DEBUG_MARKER_'+side+'_'+role
            for c in list(marker.users_collection): c.objects.unlink(marker)
            collection.objects.link(marker); marker.data.materials.append(mat)
            marker['debugOnly']=True; equipment.mark(marker)
    return arm


def render(output,meshes):
    scene=bpy.context.scene
    scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.device='CPU'
    scene.render.resolution_x=800; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    cam=scene.camera
    if cam is None:
        data=bpy.data.cameras.new('LandmarkReviewCamera'); cam=bpy.data.objects.new('LandmarkReviewCamera',data)
        scene.collection.objects.link(cam); scene.camera=cam
    cam.data.type='ORTHO'; cam.data.ortho_scale=1.98
    result=[]
    for name,pos in [('front',(0,-4,.84)),('right',(4,0,.84)),('three_quarter',(2,-4,1.1))]:
        cam.location=pos; cam.rotation_euler=(Vector((0,0,.84))-cam.location).to_track_quat('-Z','Y').to_euler()
        file=output/(name+'.png'); scene.render.filepath=str(file)
        bpy.ops.render.render(write_still=True)
        result.append(dict(view=name,file=file.name,sha256=equipment.sha(file)))
    # Explicit x-ray diagnostic, not a new texture or quality render. Restore
    # every source material slot before saving the review Blend.
    originals={o.name:list(o.data.materials) for o in meshes}
    ghost=bpy.data.materials.new('DEBUG_GhostBody'); ghost.use_nodes=True
    nodes=ghost.node_tree.nodes; links=ghost.node_tree.links
    transparent=nodes.new('ShaderNodeBsdfTransparent')
    emission=nodes.new('ShaderNodeEmission'); emission.inputs[0].default_value=(.3,.3,.3,1)
    mix=nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value=.13
    links.new(transparent.outputs[0],mix.inputs[1]); links.new(emission.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],nodes.get('Material Output').inputs['Surface'])
    try:
        for obj in meshes:
            for i in range(len(obj.data.materials)): obj.data.materials[i]=ghost
        cam.location=(0,-4,.84); cam.rotation_euler=(Vector((0,0,.84))-cam.location).to_track_quat('-Z','Y').to_euler()
        file=output/'xray_landmark_map.png'; scene.render.filepath=str(file)
        bpy.ops.render.render(write_still=True)
        result.append(dict(view='xray_landmark_map',file=file.name,sha256=equipment.sha(file),
                           diagnosticOnly=True,markerPositionsUnchanged=True))
    finally:
        for obj in meshes:
            for i,mat in enumerate(originals[obj.name]): obj.data.materials[i]=mat
    return result


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if equipment.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=equipment.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('ReviewFloor_')]
    if not meshes: raise ValueError('NO_SOURCE_MESH')
    before=digest(meshes)
    landmarks=estimate([o.matrix_world@v.co for o in meshes for v in o.data.vertices])
    arm=guide(landmarks)
    if digest(meshes)!=before: raise ValueError('CHARACTER_CHANGED')
    equipment.mark(bpy.context.scene)
    for key,value in {'source_status':equipment.GATES['sourceStatus'],'gate_b':equipment.GATES['gateB'],
                      'unity_input_allowed':False,'production_promotion_allowed':False}.items():
        bpy.context.scene[key]=value
    output.mkdir(parents=True)
    renders=render(output,meshes)
    if digest(meshes)!=before: raise ValueError('CHARACTER_CHANGED_AFTER_RENDER')
    blend=output/'CH101_UnboundLandmarkGuide_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if equipment.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='LANDMARK_GUIDE_CREATED_NEEDS_ANATOMY_REVIEW',
        artifactScope='UNBOUND_RIG_DIAGNOSTIC_NOT_CHARACTER_CANDIDATE',**equipment.GATES,
        sourceBlendSha256=args.source_sha256,sourceGeometryDigest=before,sourceGeometryAndWeightsUnchanged=True,
        artCommit=equipment.ART_COMMIT,references=refs,landmarks=landmarks,boneCount=len(arm.data.bones),
        rigStatus=arm['rig_status'],anatomicalLeftRightConfirmed=False,skinWeightsApplied=False,
        equipmentAttached=False,fullCharacterScore=None,
        limitations=['BANDS_MAY_INCLUDE_CLOTHING_OR_FLOATING_GEOMETRY','CENTROIDS_ARE_NOT_JOINT_CENTERS',
                     'NO_GRIP_POSE_CLEARANCE_OR_DEFORMATION_VERIFICATION','NO_FINAL_HUMANOID_MAPPING'],
        blendFile=blend.name,blendSha256=equipment.sha(blend),renders=renders)
    (output/'landmark-guide-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True); parser.add_argument('--art-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(parser.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
