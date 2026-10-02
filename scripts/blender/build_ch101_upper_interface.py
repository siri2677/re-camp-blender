"""Extend the preserved lower cage into a fitted upper sleeve interface."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import author_ch101_panel_cage as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='b310f0671bf9a695d60fa671a772dc3a14a30b1a8c905863f7d5d9f62358d5fc'
RESULT_OBJECT='CH101_FittedUpperSleeveInterface_NOT_PRODUCTION'
STRATEGY='CH101_FITTED_UPPER_SLEEVE_INTERFACE_V001'
ADDED_HEIGHTS=(.030,.032,.034,.036)
HEIGHTS=prior.HEIGHTS+ADDED_HEIGHTS
N,M=prior.N,len(HEIGHTS)
EXT_N=128
VERTS_PER_LAYER=prior.M*N+len(ADDED_HEIGHTS)*EXT_N
END_CLEARANCE=.002
MAX_EXPANSION=prior.MAX_EXPANSION


def idx(layer,row,angle):
    if row<prior.M:return layer*VERTS_PER_LAYER+row*N+angle%N
    return layer*VERTS_PER_LAYER+prior.M*N+(row-prior.M)*EXT_N+angle%EXT_N


def ray_hit(body_tree,center,axis,u,q,angle):
    if not math.isfinite(q) or not math.isfinite(angle) or not prior.HEIGHTS[-1]<=q<=ADDED_HEIGHTS[-1]:
        raise ValueError('UPPER_INTERFACE_HEIGHT_OUTSIDE_SCOPE')
    v=axis.cross(u)
    direction=(u*math.cos(angle)+v*math.sin(angle)+axis*panel.HEM_SLOPE*math.cos(angle)).normalized()
    origin=center+axis*(panel.HEM_HEIGHT+q)+direction*.1
    hit,normal,triangle,_=body_tree.ray_cast(origin,-direction,.1)
    if hit is None:raise ValueError('UPPER_INTERFACE_RAY_MISSED_BODY')
    d=hit-center;radius=math.hypot(d.dot(u),d.dot(v))
    if not (.02<radius<.07 and -.36<hit.x<-.12 and -.105<hit.y<.09 and .95<hit.z<1.22 and normal.dot(direction)>.25):
        raise ValueError('UPPER_INTERFACE_OUTSIDE_LOCAL_SLEEVE')
    if abs(d.dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*d.dot(u)-q)>1e-6:
        raise ValueError('UPPER_INTERFACE_PLANE_MISMATCH')
    return hit,direction,triangle


def build(source,body,center,axis,u):
    for subject in (source,body):surface.require_locked(subject)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('UPPER_INTERFACE_ALREADY_EXISTS')
    if len(source.data.vertices)!=2*prior.N*prior.M or len(source.data.polygons)!=2*prior.N*prior.M:
        raise ValueError('UNEXPECTED_SOURCE_CAGE_TOPOLOGY')
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_UPPER_INTERFACE_FRAME')
    tree=c.fit.bvh(body)[0];v=axis.cross(u)
    old=[source.matrix_world@p.co for p in source.data.vertices]
    new_points=[[],[]];samples=[];expansions=[]
    for row,q in enumerate(ADDED_HEIGHTS):
        t=(q-prior.HEIGHTS[-1])/(ADDED_HEIGHTS[-1]-prior.HEIGHTS[-1]);weight=t*t*(3-2*t)
        for i in range(EXT_N):
            hit,direction,triangle=ray_hit(tree,center,axis,u,q,math.tau*i/EXT_N)
            source_angle=i*N/EXT_N;j=math.floor(source_angle);fraction=source_angle-j
            bottom=old[prior.idx(0,prior.M-1,j)].lerp(old[prior.idx(0,prior.M-1,(j+1)%N)],fraction)
            extruded=bottom+axis*(q-prior.HEIGHTS[-1])
            inner=extruded.lerp(hit+direction*END_CLEARANCE,weight)
            # A safety constraint for the actual loft point (not only its target).
            d=inner-center;angle=math.atan2(d.dot(v),d.dot(u))
            constraint,normal_ray,target_triangle=ray_hit(tree,center,axis,u,q,angle)
            origin=center+axis*(panel.HEM_HEIGHT+q)
            expansion=(inner-origin).length-(constraint-origin).length
            if expansion<END_CLEARANCE:
                inner=constraint+normal_ray*END_CLEARANCE;expansion=END_CLEARANCE
            if expansion>MAX_EXPANSION:raise ValueError('UPPER_INTERFACE_EXPANSION_REJECTED')
            outer=inner+normal_ray*prior.WALL
            new_points[0].append(inner);new_points[1].append(outer);expansions.append(expansion)
            samples.append(dict(q=q,angleIndex=i,targetTriangle=triangle,constraintTriangle=target_triangle,
                                targetHit=list(hit),constraintHit=list(constraint),blendWeight=weight,
                                innerRayExpansionMeters=expansion))
    vertices=[];source_map={}
    for layer in range(2):
        for row in range(prior.M):
            for i in range(N):
                old_index=prior.idx(layer,row,i);source_map[old_index]=len(vertices);vertices.append(old[old_index])
        vertices.extend(new_points[layer])
    faces=[];material_indices=[]
    for layer in range(2):
        for row in range(prior.M-1):
            for i in range(N):
                faces.append((idx(layer,row,i),idx(layer,row,i+1),idx(layer,row+1,i+1),idx(layer,row+1,i)))
                material_indices.append(1 if row==0 else 0)
        # The 64 original outer/inner loop edges are retained. Three triangles
        # connect each edge to two 128-point intervals; no duplicated seam verts.
        for i in range(N):
            a,b=idx(layer,prior.M-1,i),idx(layer,prior.M-1,i+1)
            c0,d,e=idx(layer,prior.M,2*i),idx(layer,prior.M,2*i+1),idx(layer,prior.M,2*i+2)
            faces.extend(((a,b,d),(b,e,d),(a,d,c0)));material_indices.extend((0,0,0))
        for row in range(prior.M,M-1):
            for i in range(EXT_N):
                faces.append((idx(layer,row,i),idx(layer,row,i+1),idx(layer,row+1,i+1),idx(layer,row+1,i)))
                material_indices.append(0)
    # Remove the old upper end wall on this NEW object; replace it at the fitted end.
    for row in (0,M-1):
        for i in range(N if row==0 else EXT_N):
            faces.append((idx(0,row,i),idx(0,row,i+1),idx(1,row,i+1),idx(1,row,i)))
            material_indices.append(1 if row==0 else 0)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for mat in source.data.materials:mesh.materials.append(mat)
    for face,material in zip(mesh.polygons,material_indices):face.material_index=material;face.use_smooth=True
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj);obj['rigBound']=False;obj['attachedOrSewn']=False
    obj['integratedHemTopology']=True;obj['integratedUpperBridgeTopology']=True
    obj['joinedToSourceBodyTopology']=False
    max_preserved_move=max((obj.matrix_world@mesh.vertices[new].co-old[old_index]).length for old_index,new in source_map.items())
    if max_preserved_move>1e-7:raise ValueError('PRESERVED_CAGE_VERTICES_CHANGED')
    return obj,dict(addedSignedHemRows=list(ADDED_HEIGHTS),sourceVertexToNewIndex=source_map,
                    preservedAngularColumns=N,addedAngularColumns=EXT_N,
                    sourceVerticesRetained=len(old),maximumRetainedVertexMoveMeters=max_preserved_move,
                    addedInnerRayExpansionRangeMeters=[min(expansions),max(expansions)],
                    addedExpansionLimitMeters=MAX_EXPANSION,surfaceTargets=samples,
                    oldUpperEndWallRemovedOnNewCopyOnly=True,joinedToSourceBodyTopology=False,
                    upperInterfaceAuthoredHypothesis=True)


def upper_gap(obj,indices,body):
    points=[obj.matrix_world@obj.data.vertices[i].co for i in indices];n=len(points)
    points += [(points[i]+points[(i+1)%n])*.5 for i in range(n)]
    tree=c.fit.bvh(body)[0];distances=[tree.find_nearest(p)[3] for p in points]
    return dict(minMeters=min(distances),maxMeters=max(distances),meanMeters=sum(distances)/len(distances),samples=len(points))


def audit(obj,source,body,parts,oldband):
    qa=prior.prior.prior.prior.audit(obj,body,parts+[oldband],expected_vertices=2*VERTS_PER_LAYER)
    from mathutils.bvhtree import BVHTree
    points=[obj.matrix_world@v.co for v in obj.data.vertices];count=VERTS_PER_LAYER;obj.data.calc_loop_triangles()
    sides=[[tuple(t.vertices) for t in obj.data.loop_triangles if all((i<count)==(layer==0) for i in t.vertices)] for layer in range(2)]
    distances=[]
    for layer in range(2):
        tree=BVHTree.FromPolygons(points,sides[1-layer],all_triangles=True)
        samples=points[layer*count:(layer+1)*count]+[sum((points[i] for i in f),Vector())/3 for f in sides[layer]]
        distances.extend(tree.find_nearest(p)[3] for p in samples)
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table()
    interface_edges=[e for e in bm.edges if all(count+(prior.M-1)*N<=v.index<count+prior.M*N for v in e.verts)]
    shared=len(interface_edges)==N and all(len(e.link_faces)==2 for e in interface_edges);bm.free()
    old_gap=upper_gap(source,[prior.idx(1,prior.M-1,i) for i in range(N)],body)
    new_gap=upper_gap(obj,[idx(1,M-1,i) for i in range(EXT_N)],body)
    qa.update(sampledWallRangeMeters=[min(distances),max(distances)],thicknessSampleCount=len(distances),
              sharedUpperBridgeOuterEdges=len(interface_edges),upperBridgeEdgeManifold=shared,
              oldUpperEdgeBodyGap=old_gap,newUpperEdgeBodyGap=new_gap,
              continuousThicknessProven=False,joinedToSourceBodyTopology=False,bodyMovedVertices=0)
    qa['eligible']=qa['eligible'] and shared and min(distances)>.0002 and max(distances)<.0012 and new_gap['maxMeters']<.003 and new_gap['maxMeters']<old_gap['maxMeters']
    return qa


def render(output,source,obj,body,parts,center,axis):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=center+axis*(panel.HEM_HEIGHT+.025)
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('UpperInterfaceReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';records=[]
    views=[('front',Vector((0,-.7,.08)),.22),('side',Vector((-.7,0,.08)),.22),
           ('back',Vector((0,.7,.08)),.22),('context',Vector((-.7,-.3,.08)),.35)]
    for state,shell in [('before',source),('after',obj)]:
        source.hide_render=shell!=source;obj.hide_render=shell!=obj
        for name,delta,scale in views:
            for part in [body]+parts:part.hide_render=False
            scene.camera.location=target+delta;scene.camera.data.ortho_scale=scale
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/(state+'_'+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            records.append(dict(file=path.name,sha256=c.base.sha(path)))
    for part in [body]+parts:part.hide_render=True
    scene.camera.location=target-axis*.6+Vector((0,-.25,0));scene.camera.data.ortho_scale=.13
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    path=output/'after_isolated.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    records.append(dict(file=path.name,sha256=c.base.sha(path)))
    return records


def run(args):
    source_path,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source_path)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source_path));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    source=bpy.data.objects[prior.RESULT_OBJECT];body=bpy.data.objects[panel.RESULT_OBJECT]
    oldband=bpy.data.objects[prior.prior.prior.RESULT_OBJECT]
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=build(source,body,*frame);qa=audit(obj,source,body,parts,oldband)
    if not qa['eligible']:raise ValueError('UPPER_INTERFACE_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,source,obj,body,parts,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[obj])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [body]+parts+[obj]
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_FittedUpperSleeveInterface_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source_path)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='UPPER_INTERFACE_PENDING_VISUAL_REVIEW',**c.base.GATES,
                runtime=dict(blenderVersion=bpy.app.version_string,device='CPU'),sourceBlendSha256=SOURCE_SHA,
                artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['FITTED_INTERFACE_IS_SEPARATE_FROM_SOURCE_BODY_TOPOLOGY','LOCAL_ARM_ONLY_NOT_SHOULDER_PATTERN',
                             'OLD_LOWER_CAGE_STANDOFF_UNCHANGED','SURFACE_FIT_USES_COARSE_SOURCE_FOLDS',
                             'STATIC_SAMPLES_NOT_ANIMATION_OR_CONTINUOUS_PROOF','NO_UV_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'upper-interface-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))['qa'],indent=2))
