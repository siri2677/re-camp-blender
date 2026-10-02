"""Separate reference-guided sleeve end. No source surgery or anatomical approval."""
import argparse,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_cuff_interface_study as c

STRATEGY='CH101_SEPARATE_SLEEVE_END_AUTHORING_V001'
# z above authored wrist, ellipse radii. Authored estimates, not recovered measurements.
PROFILES=((.002,.023,.034),(.008,.024,.0345),(.018,.027,.036),(.030,.030,.036),(.047,.0315,.037),(.065,.033,.0375),(.083,.034,.038),(.098,.035,.038))
WALL=.0015

def build(center,axis,u,profiles=PROFILES):
    center=Vector(center);axis=Vector(axis).normalized();u=Vector(u);u=(u-axis*u.dot(axis)).normalized()
    if axis.length<.9 or u.length<.9:raise ValueError('INVALID_SLEEVE_FRAME')
    if len(profiles)<2 or any(min(rx,ry)<=WALL for _,rx,ry in profiles):raise ValueError('INVALID_SLEEVE_PROFILE')
    if any(b[0]<=a[0] for a,b in zip(profiles,profiles[1:])):raise ValueError('PROFILE_ORDER_INVALID')
    v=axis.cross(u);n=32;outer=[];inner=[]
    for k,(z,rx,ry) in enumerate(profiles):
        # Small geometric folds inside the sleeve span, zero at both openings.
        envelope=math.sin(math.pi*k/(len(profiles)-1))**2
        ro=[];ri=[]
        for j in range(n):
            angle=2*math.pi*j/n;fold=.0007*envelope*math.cos(4*angle+.5*k)
            direction=u*math.cos(angle)+v*math.sin(angle)
            p=center+axis*z+u*(rx*math.cos(angle))+v*(ry*math.sin(angle))+direction*fold
            ro.append(p);ri.append(p-direction*WALL)
        outer.append(ro);inner.append(ri)
    rings=outer+list(reversed(inner));verts=[tuple(p) for ring in rings for p in ring];faces=[];slots=[];m=len(rings)
    for k in range(m):
        for j in range(n):
            a,b,d,e=k*n+j,k*n+(j+1)%n,((k+1)%m)*n+(j+1)%n,((k+1)%m)*n+j
            faces.extend(((a,b,e),(b,d,e)) if len(profiles)-1<k<m-1 else ((a,b,d),(a,d,e)))
            # Two narrow woven trim lanes, not separate floating strips.
            slots.extend([int(k<len(profiles)-1 and j in (3,19))]*2)
    mesh=bpy.data.meshes.new('Sleeve_end_hollow_loft');mesh.from_pydata(verts,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new('CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION',mesh);bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(c.base.material('SleeveStudy_graphite_fabric',(.012,.015,.021)))
    mesh.materials.append(c.base.material('SleeveStudy_gold_woven_trim',(.40,.24,.055),.1))
    for p,slot in zip(mesh.polygons,slots):p.material_index=slot
    c.base.mark(obj);obj['designApproved']=False;obj['sourceReplacementAllowed']=False;obj['attachedToBody']=False
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.03);bpy.ops.object.mode_set(mode='OBJECT')
    return obj

def render(output,body,hand,sleeve,cuff,center,axis):
    scene=bpy.context.scene
    for o in scene.objects:
        if o.type in ('MESH','CURVE','LIGHT'):o.hide_render=True
    for o in scene.objects:
        if o.type=='MESH' and o.name.startswith('PAIR_STUDY_'):o.hide_render=False
    sleeve.hide_render=False;cuff.hide_render=False
    context=body.copy();context.data=body.data.copy();context.name='SLEEVE_CONTEXT_BODY_UNMERGED';scene.collection.objects.link(context)
    context.data.materials.clear();context.data.materials.append(c.base.material('Sleeve_context_clay',(.18,.20,.23)))
    for p in context.data.polygons:p.material_index=0
    c.base.mark(context);context['diagnosticCopy']=True
    light_data=bpy.data.lights.new('Sleeve_review_light','AREA');light_data.energy=45;light_data.size=.4
    light=bpy.data.objects.new(light_data.name,light_data);scene.collection.objects.link(light)
    light.location=center+Vector((-.3,-.4,.5));light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.view_settings.exposure=-.7
    camera=scene.camera;camera.data.type='ORTHO';camera.data.ortho_scale=.38;renders=[]
    for mode in ('context','isolated'):
        context.hide_render=mode!='context'
        for name,offset in [('front',(-.25,-.7,.15)),('side',(-.7,.05,.1)),('back',(.25,.7,.15))]:
            aim=center-axis*.008;camera.location=aim+Vector(offset);camera.rotation_euler=(aim-camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/f'{mode}_{name}_UNMERGED.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            renders.append(dict(file=path.name,sha256=c.base.sha(path),sourceBodyShown=mode=='context',sourceHandStillExists=True,merged=False))
    return renders

def run(args):
    source=args.source.resolve();output=args.output.resolve()
    if c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=c.base.verify_references(args.art_root.resolve())
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if scene.get(key) not in (False,0):raise ValueError('SOURCE_GATE_NOT_FALSE')
    sources=[o for o in scene.objects if o.type=='MESH'];before=c.guide.digest(sources)
    hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'];body=bpy.data.objects['geometry_0'];cuff=bpy.data.objects['CUFF_REDUCTION_0.5_NOT_PRODUCTION']
    center=hand.matrix_world@Vector();axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized();u=hand.matrix_world.to_3x3()@Vector((1,0,0))
    sleeve=build(center,axis,u);audit=c.author.shape_audit(sleeve);self_pairs=c.wrist.self_surface_pairs(sleeve)
    euler=len(sleeve.data.vertices)-len(sleeve.data.edges)+len(sleeve.data.polygons)
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or len(audit['components'])!=1 or euler!=0 or self_pairs:raise ValueError('SLEEVE_TOPOLOGY_INVALID')
    others=[o for o in sources if o.name.startswith('PAIR_STUDY_')]+[cuff]
    collisions=[dict(target=o.name,**c.fit.overlap_report(o,[sleeve],center)[0]) for o in others]
    if any(r['uniqueEquipmentTrianglesCrossing'] for r in collisions):raise ValueError('SLEEVE_STUDY_PART_INTERSECTION')
    output.mkdir(parents=True);renders=render(output,body,hand,sleeve,cuff,center,axis)
    if c.guide.digest(sources)!=before:raise ValueError('SOURCE_GEOMETRY_CHANGED')
    for key,value in c.base.GATES.items():scene[key]=value
    blend=output/'CH101_SleeveEndStudy_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='SEPARATE_SLEEVE_END_DESIGN_HYPOTHESIS',**c.base.GATES,
        sourceBlendSha256=args.source_sha256,artCommit=c.base.ART_COMMIT,references=refs,
        profilesMeters=PROFILES,radialWallOffsetMeters=WALL,foldAmplitudeMeters=.0007,
        placementMethod='HAND_LOCAL_FRAME_AUTHORED_DIMENSIONS_NOT_ANATOMICAL_REGISTRATION',
        axialGapAboveWristReferenceMeters=.002,topology=audit,eulerCharacteristic=euler,selfSurfacePairs=self_pairs,
        studyPartCollisions=collisions,sourceBodyOverlap=c.fit.overlap_report(body,[sleeve],center),
        sourceGeometryPreserved=True,sourceHandReplaced=False,anatomicalSeamVerified=False,
        sleeveCuffWelded=False,designApproved=False,attachmentApproved=False,wristIntegrationAllowed=False,
        fullCharacterScore=None,limitations=['AUTHORED_DIMENSIONS_NOT_MEASURED_FROM_ORTHOGRAPHIC_ART','UPPER_OPENING_NOT_ATTACHED',
            'TWO_MM_REFERENCE_PLANE_GAP_IS_NOT_MINIMUM_SURFACE_CLEARANCE','SOURCE_HAND_REMAINS','NO_FINAL_ATLAS_SKINNING_OR_ANIMATION'],
        renders=renders,blendFile=blend.name,blendSha256=c.base.sha(blend))
    (output/'sleeve-end-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps({k:r[k] for k in ('status','topology','blendSha256','sourceBodyOverlap')},indent=2))
