"""Connected palm/finger topology study, not a source-hand replacement or rig."""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_equipment_study as base
import review_ch101_equipment_fit as fit
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_CONNECTED_HAND_AUTHORING_V001'
GRIP_CENTER=Vector((0,-.034,.068))


def make_hand(collection,pose='grip'):
    if pose not in ('grip','open'): raise ValueError('UNKNOWN_HAND_POSE')
    verts=[]; faces=[]; lookup={}; parts={}
    def vertex(co):
        key=tuple(round(float(v),8) for v in co)
        if key not in lookup: lookup[key]=len(verts); verts.append(key)
        return lookup[key]
    def face(points): faces.append(tuple(vertex(p) for p in points))
    xs=[-.034,-.032,-.017,-.015,0,.002,.017,.019,.032,.034]
    zs=[0,.025,.050,.068]; depth=.012
    # Front/back grid and side walls share exact vertices with finger holes.
    for x0,x1 in zip(xs,xs[1:]):
        for z0,z1 in zip(zs,zs[1:]):
            for y in (-depth,depth): face([(x0,y,z0),(x1,y,z0),(x1,y,z1),(x0,y,z1)])
        face([(x0,-depth,0),(x1,-depth,0),(x1,depth,0),(x0,depth,0)])
    for x in (xs[0],xs[-1]):
        for z0,z1 in zip(zs,zs[1:]):
            if x==xs[0] and z0==.025: continue # thumb root shares this hole
            face([(x,-depth,z0),(x,depth,z0),(x,depth,z1),(x,-depth,z1)])
    for i,(x0,x1) in enumerate(zip(xs,xs[1:])):
        if i not in (1,3,5,7): face([(x0,-depth,zs[-1]),(x1,-depth,zs[-1]),(x1,depth,zs[-1]),(x0,depth,zs[-1])])
    parts['Palm']=list(range(len(verts)))

    def bridge(previous,current):
        for j in range(4): faces.append((previous[j],previous[(j+1)%4],current[(j+1)%4],current[j]))
    def digit(name,root,path,widths,thicknesses,side):
        previous=[vertex(p) for p in root]; selected=set(previous)
        for i,center in enumerate(path):
            prior=Vector(tuple(sum(p[a] for p in root)/4 for a in range(3))) if i==0 else Vector(path[i-1])
            tangent=(Vector(center)-prior).normalized()
            normal=tangent.cross(Vector(side)).normalized()
            if normal.length<.9: raise ValueError('INVALID_DIGIT_FRAME')
            ring=[Vector(center)+Vector(side)*u*widths[i]+normal*v*thicknesses[i] for u,v in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            current=[vertex(p) for p in ring]; bridge(previous,current); selected.update(current); previous=current
        faces.append(tuple(previous)); parts[name]=sorted(selected)
    names=['Index','Middle','Ring','Little']
    for n,slot in enumerate((1,3,5,7)):
        x0,x1=xs[slot:slot+2]; x=(x0+x1)/2
        root=[(x0,-depth,.068),(x1,-depth,.068),(x1,depth,.068),(x0,depth,.068)]
        if pose=='grip':
            end=[220,250,240,205][n]
            angles=[20,50,85,120,155,185,end]
            path=[(x,-.034+.036*math.cos(math.radians(a)),.068+.036*math.sin(math.radians(a))) for a in angles]
        else:
            length=[.071,.078,.073,.057][n]
            path=[(x,0,.068+length*t) for t in (.12,.28,.45,.6,.76,.9,1)]
        digit(names[n],root,path,[(x1-x0)/2*t for t in (1,1,.96,.93,.88,.80,.62)],
              [.009,.009,.0085,.008,.0075,.007,.0055],(1,0,0))
    # Thumb root orientation matches side-wall hole. Side vector is local z.
    root=[(-.034,-depth,.025),(-.034,-depth,.050),(-.034,depth,.050),(-.034,depth,.025)]
    # Keep the thumb below the handle cross-section, rather than cutting through
    # it. Only this path's z coordinates change; the hand/saber anchors stay fixed.
    path=[(-.043,-.006,.032),(-.049,-.023,.032),(-.041,-.051,.032),(-.022,-.064,.035),(-.005,-.063,.040)]
    if pose=='open': path=[(-.045,-.002,.040),(-.055,-.006,.047),(-.067,-.010,.055),(-.078,-.012,.061),(-.086,-.012,.064)]
    digit('Thumb',root,path,[.012,.012,.011,.009,.006],[.010,.009,.0085,.007,.005],(0,0,1))
    mesh=bpy.data.meshes.new('CH101_HandConnectedCage_'+pose); mesh.from_pydata(verts,[],faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    obj=bpy.data.objects.new('CH101_HandAuthoring_'+pose+'_NOT_PRODUCTION',mesh); collection.objects.link(obj)
    for name,indices in parts.items(): obj.vertex_groups.new(name=name).add(indices,1,'REPLACE')
    base.mark(obj); obj['sourceReplacementAllowed']=False; obj['anatomicalFitVerified']=False
    obj['studyPose']=pose; obj['semanticParts']='Palm,Thumb,Index,Middle,Ring,Little'
    return obj


def shape_audit(obj):
    mesh=obj.data; mesh.calc_loop_triangles(); bm=bmesh.new(); bm.from_mesh(mesh)
    remaining=set(bm.verts); sizes=[]
    while remaining:
        stack=[remaining.pop()]; count=0
        while stack:
            v=stack.pop(); count+=1
            for e in v.link_edges:
                other=e.other_vert(v)
                if other in remaining: remaining.remove(other); stack.append(other)
        sizes.append(count)
    report=dict(vertices=len(mesh.vertices),triangles=len(mesh.loop_triangles),
        components=sorted(sizes,reverse=True),nonManifoldEdges=sum(not e.is_manifold for e in bm.edges),
        zeroAreaFaces=sum(f.calc_area()<1e-12 for f in bm.faces),semanticGroups=[g.name for g in obj.vertex_groups],
        selfIntersectionTestPerformed=False,rigOrWeightsValidated=False)
    bm.free(); return report


def align_to_saber(obj,saber):
    basis=saber.matrix_world.to_3x3()
    rotation=Matrix((basis.col[2],basis.col[0],basis.col[1])).transposed()
    matrix=rotation.to_4x4(); anchor=saber.matrix_world@Vector((0,0,.82))
    matrix.translation=anchor-rotation@GRIP_CENTER; obj.matrix_world=matrix
    return ((matrix@GRIP_CENTER)-anchor).length


def render_study(output,obj,saber):
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=32
    scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'; scene.view_settings.exposure=-1
    for light in [o for o in scene.objects if o.type=='LIGHT']: light.hide_render=True
    center=obj.matrix_world@GRIP_CENTER; rotation=obj.matrix_world.to_3x3()
    for name,local,energy in [('Key',(.3,-.4,.4),12),('Fill',(-.3,.3,.2),7)]:
        data=bpy.data.lights.new('HandStudy_'+name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=.3
        light=bpy.data.objects.new(data.name,data); scene.collection.objects.link(light)
        light.location=center+rotation@Vector(local); light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    cam=scene.camera; cam.data.type='ORTHO'; cam.data.ortho_scale=.23
    equipment=[o for o in scene.objects if o.name=='CH101_Saber' or o.get('equipmentOwner')=='CH101_Saber']
    states=[(o,o.hide_render) for o in equipment]; result=[]
    for name,direction,with_saber in [('grip_front',(0,-.6,.3),True),('grip_back',(0,.6,.3),True),
                                     ('bare_front',(0,-.6,.3),False),('bare_side',(.6,0,.2),False)]:
        for o,hidden in states: o.hide_render=hidden or not with_saber
        cam.location=center+rotation@Vector(direction); cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        path=output/(name+'.png'); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
        result.append(dict(file=path.name,sha256=base.sha(path),saberVisible=with_saber))
    for o,hidden in states: o.hide_render=hidden
    return result


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0): raise ValueError('SOURCE_GATE_NOT_FALSE')
    source_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']; before=guide.digest(source_meshes)
    collection=bpy.data.collections.new('HAND_AUTHORING_STUDY_NOT_SOURCE_REPLACEMENT'); bpy.context.scene.collection.children.link(collection)
    obj=make_hand(collection); cage_audit=shape_audit(obj)
    if cage_audit['nonManifoldEdges'] or len(cage_audit['components'])!=1: raise ValueError('HAND_CAGE_NOT_CONNECTED_MANIFOLD')
    obj.data.materials.append(base.material('HandStudy_Clay',(.28,.32,.35)))
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
    sub=obj.modifiers.new('Study_surface_subdivision','SUBSURF'); sub.levels=1; bpy.ops.object.modifier_apply(modifier=sub.name)
    for poly in obj.data.polygons: poly.use_smooth=True
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(island_margin=.03); bpy.ops.object.mode_set(mode='OBJECT')
    saber=bpy.data.objects['CH101_Saber']; anchor_error=align_to_saber(obj,saber); bpy.context.view_layer.update()
    audit=shape_audit(obj)
    if audit['nonManifoldEdges'] or len(audit['components'])!=1 or audit['zeroAreaFaces']: raise ValueError('HAND_SURFACE_INVALID')
    overlaps=fit.overlap_report(obj,[o for o in source_meshes if o==saber or o.get('equipmentOwner')==saber.name],obj.matrix_world@GRIP_CENTER)
    # The source body is preserved, NOT cut or merged. Only show the part study.
    for o in source_meshes:
        if o!=saber and o.get('equipmentOwner')!=saber.name: o.hide_render=True
    wrist_world=obj.matrix_world@Vector((0,0,0))
    wrist_distance=fit.bvh(bpy.data.objects['geometry_0'])[0].find_nearest(wrist_world)[3]
    output.mkdir(parents=True); renders=render_study(output,obj,saber)
    if guide.digest(source_meshes)!=before: raise ValueError('SOURCE_GEOMETRY_CHANGED')
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    blend=output/'CH101_ConnectedHandStudy_NOT_PRODUCTION_v001.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='CONNECTED_HAND_PART_STUDY_NOT_APPROVED',**base.GATES,
        artCommit=base.ART_COMMIT,references=refs,sourceBlendSha256=args.source_sha256,
        cageAudit=cage_audit,surfaceAudit=audit,handleAnchorErrorMeters=anchor_error,
        localCorrection='THUMB_PATH_BELOW_HANDLE_CROSS_SECTION_V002',
        equipmentSurfaceOverlap=overlaps,estimatedWristNearestSourceDistanceMeters=wrist_distance,
        sourceGeometryPreserved=True,sourceBodyHiddenForStudy=True,sourceHandReplaced=False,
        wristSeamVerified=False,graspPoseVerified=False,attachmentApproved=False,uvStatus='SMART_PROJECT_STUDY_NOT_FINAL_ATLAS',
        limitations=['DIMENSIONS_AND_GRIP_AUTHORED_ESTIMATES','NO_ANATOMICAL_SEAM_OR_SKIN_WEIGHTS',
            'NO_SELF_INTERSECTION_OR_ANIMATED_COLLISION_TEST','PART_STUDY_NOT_FULL_CHARACTER_QUALITY_PASS'],
        fullCharacterScore=None,renders=renders,blendFile=blend.name,blendSha256=base.sha(blend))
    (output/'hand-authoring-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
