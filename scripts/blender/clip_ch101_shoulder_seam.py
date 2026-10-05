"""Exact source chart clipping and ordered seam mapping, not clothing."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_shoulder_domain as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='e8faa8b846b838bfb24164ee6d19b89384dedc05371346e213bd160da001ad67'
RESULT_OBJECT='CH101_ClippedShoulderReferenceChart_NOT_PRODUCTION'
STRATEGY='CH101_EXACT_SHOULDER_CLIP_SEAM_PARAMETER_V001'
SEAM_Q=.036


def clip_polygon(poly,normal,offset):
    if not poly:return []
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da,db=normal.dot(a[0])-offset,normal.dot(b[0])-offset
        if da>=0:result.append(a)
        if (da>=0)!=(db>=0):
            t=da/(da-db);result.append((a[0].lerp(b[0],t),a[1].lerp(b[1],t)))
    return result


def boundaries(obj):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();neighbors=defaultdict(list)
    for edge in bm.edges:
        if len(edge.link_faces)==1:
            a,b=[v.index for v in edge.verts];neighbors[a].append(b);neighbors[b].append(a)
        elif len(edge.link_faces)!=2:bm.free();raise ValueError('CHART_NON_MANIFOLD_INTERIOR')
    if any(len(ns)!=2 for ns in neighbors.values()):bm.free();raise ValueError('CHART_BRANCHED_BOUNDARY')
    remaining=set(neighbors);loops=[]
    while remaining:
        start=min(remaining);loop=[start];remaining.remove(start);previous=None;current=start
        while True:
            following=next(i for i in sorted(neighbors[current]) if i!=previous)
            if following==start:break
            if following not in remaining:bm.free();raise ValueError('CHART_NONSIMPLE_BOUNDARY')
            loop.append(following);remaining.remove(following);previous,current=current,following
        loops.append(loop)
    unseen=set(bm.verts);components=[]
    while unseen:
        stack=[unseen.pop()];count=0
        while stack:
            v=stack.pop();count+=1
            for e in v.link_edges:
                other=e.other_vert(v)
                if other in unseen:unseen.remove(other);stack.append(other)
        components.append(count)
    report=dict(boundaryLoops=loops,components=components,euler=len(bm.verts)-len(bm.edges)+len(bm.faces),zeroAreaFaces=sum(f.calc_area()<1e-12 for f in bm.faces))
    bm.free();return report


def build(body,frame):
    surface.require_locked(body)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('CLIPPED_CHART_ALREADY_EXISTS')
    center,axis,u=frame
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:raise ValueError('INVALID_CLIP_FRAME')
    normal=axis-panel.HEM_SLOPE*u
    planes=[(Vector((1,0,0)),-.265),(Vector((-1,0,0)),.085),(Vector((0,0,1)),1.09),
            (Vector((0,0,-1)),-1.31),(Vector((0,1,0)),-.115),(Vector((0,-1,0)),-.115),
            (normal,normal.dot(center)+panel.HEM_HEIGHT+SEAM_Q)]
    points=[body.matrix_world@v.co for v in body.data.vertices];body.data.calc_loop_triangles()
    vertices=[];faces=[];records=[];lookup={}
    for tri in body.data.loop_triangles:
        poly=[(points[i],Vector(tuple(float(j==k) for j in range(3)))) for k,i in enumerate(tri.vertices)]
        for n,d in planes:poly=clip_polygon(poly,n,d)
        if len(poly)<3:continue
        area=sum((poly[j][0]-poly[0][0]).cross(poly[j+1][0]-poly[0][0]).length*.5 for j in range(1,len(poly)-1))
        if area<1e-12:continue
        ids=[]
        for point,weights in poly:
            key=tuple(round(x,6) for x in point)
            if key not in lookup:lookup[key]=len(vertices);vertices.append(point)
            ids.append(lookup[key])
        if len(set(ids))!=len(ids):raise ValueError('CLIP_WELD_COLLAPSES_FACE')
        faces.append(ids);records.append(dict(sourceTriangle=tri.index,sourceFace=tri.polygon_index,sourceVertices=list(tri.vertices),sourceLoops=list(tri.loops),barycentric=[list(w) for _,w in poly]))
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj)
    for mat in body.data.materials:mesh.materials.append(mat)
    for face,r in zip(mesh.polygons,records):
        original=body.data.polygons[r['sourceFace']];face.material_index=original.material_index;face.use_smooth=original.use_smooth
    for layer in body.data.uv_layers:
        uv=mesh.uv_layers.new(name=layer.name);uv.active_render=layer.active_render
        for face,r in zip(mesh.polygons,records):
            for loop,weights in zip(face.loop_indices,r['barycentric']):uv.data[loop].uv=sum((layer.data[i].uv*w for i,w in zip(r['sourceLoops'],weights)),Vector((0,0)))
    mesh.uv_layers.active_index=body.data.uv_layers.active_index
    for field in body.data.attributes:
        if field.domain!='POINT' or field.data_type!='FLOAT':continue
        new=mesh.attributes.new(field.name,'FLOAT','POINT')
        for face,r in zip(mesh.polygons,records):
            for vertex,weights in zip(face.vertices,r['barycentric']):new.data[vertex].value=sum(field.data[i].value*w for i,w in zip(r['sourceVertices'],weights))
    c.base.mark(obj);obj['referenceChartOnly']=True;obj['adoptionAllowed']=False
    topology=boundaries(obj)
    if len(topology['components'])!=1 or len(topology['boundaryLoops'])!=2 or topology['euler']!=0 or topology['zeroAreaFaces']:raise ValueError('CLIPPED_CHART_NOT_ANNULUS:'+json.dumps(topology))
    def q(p):return (p-center).dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*(p-center).dot(u)
    seamloops=[loop for loop in topology['boundaryLoops'] if max(abs(q(vertices[i])-SEAM_Q) for i in loop)<1e-6]
    if len(seamloops)!=1:raise ValueError('CLIP_HAS_NO_UNIQUE_PLANAR_SEAM')
    return obj,dict(planes=[dict(normal=list(n),offset=d) for n,d in planes],topology=topology,seamLoop=seamloops[0],cornerProvenance=records,sourceBodyMovedVertices=0,geometryOffsetMeters=0,openReferenceChart=True,completeGarment=False)


def verify_chart(body,obj,operation,frame):
    """Check source provenance, UV corner interpolation and all clip inequalities."""
    if list(body.data.materials)!=list(obj.data.materials):raise ValueError('CHART_MATERIAL_CHANGED')
    if [u.name for u in body.data.uv_layers]!=[u.name for u in obj.data.uv_layers]:raise ValueError('CHART_UV_LAYERS_CHANGED')
    if len(obj.data.polygons)!=len(operation['cornerProvenance']):raise ValueError('CHART_FACE_COUNT_CHANGED')
    body_points=[body.matrix_world@v.co for v in body.data.vertices]
    errors=[];uv_errors=[];plane_errors=[]
    for face,r in zip(obj.data.polygons,operation['cornerProvenance']):
        if face.material_index!=body.data.polygons[r['sourceFace']].material_index:raise ValueError('CHART_MATERIAL_ASSIGNMENT_CHANGED')
        for i,loop,weights in zip(face.vertices,face.loop_indices,r['barycentric']):
            if abs(sum(weights)-1)>1e-6 or min(weights)<-1e-6:raise ValueError('CHART_INVALID_BARYCENTRIC')
            point=obj.matrix_world@obj.data.vertices[i].co
            reconstructed=sum((body_points[j]*w for j,w in zip(r['sourceVertices'],weights)),Vector())
            errors.append((point-reconstructed).length)
            plane_errors.extend(max(0,p['offset']-Vector(p['normal']).dot(point)) for p in operation['planes'])
            for old,new in zip(body.data.uv_layers,obj.data.uv_layers):
                want=sum((old.data[j].uv*w for j,w in zip(r['sourceLoops'],weights)),Vector((0,0)))
                uv_errors.append((want-new.data[loop].uv).length)
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    center,axis,u=frame
    seam_errors=[abs((points[i]-center).dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*(points[i]-center).dot(u)-SEAM_Q) for i in operation['seamLoop']]
    tree,_,faces=c.fit.bvh(obj)
    crossings=len({(a,b) for a,b in tree.overlap(tree) if a<b and not set(faces[a])&set(faces[b])})
    qa=dict(vertices=len(points),faces=len(obj.data.polygons),triangles=len(obj.data.loop_triangles),
            maximumProvenancePositionErrorMeters=max(errors),maximumUVCornerError=max(uv_errors),
            maximumClipPlaneViolationMeters=max(plane_errors),maximumSeamPlaneErrorMeters=max(seam_errors),
            nonAdjacentSelfIntersectionPairs=crossings,topology=boundaries(obj),openReferenceChart=True,
            weldCoordinateBucketMeters=.000001,sourceSurfaceClearanceRequired=False)
    t=qa['topology']
    qa['eligible']=max(errors)<1e-6 and max(uv_errors)<1e-6 and max(plane_errors)<1e-6 and max(seam_errors)<1e-6 and crossings==0 and len(t['components'])==1 and len(t['boundaryLoops'])==2 and t['euler']==0 and t['zeroAreaFaces']==0
    if not qa['eligible']:raise ValueError('CHART_PROVENANCE_QA_REJECTED:'+json.dumps(qa))
    return qa


def seam_map(obj,interface,frame,loop):
    surface.require_locked(obj);surface.require_locked(interface)
    center,axis,u=frame;v=axis.cross(u);points=[obj.matrix_world@p.co for p in obj.data.vertices]
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    rows=[];n=prior.prior.EXT_N
    for k in range(n):
        angle=math.tau*k/n;direction=(math.cos(angle),math.sin(angle));hits=[]
        for a,b in zip(loop,loop[1:]+loop[:1]):
            d0,d1=points[a]-center,points[b]-center;p=(d0.dot(u),d0.dot(v));delta=(d1.dot(u)-p[0],d1.dot(v)-p[1]);den=cross(direction,delta)
            if abs(den)<1e-12:continue
            radius=cross(p,delta)/den;t=cross(p,direction)/den
            if radius>0 and -1e-6<=t<=1+1e-6:
                hit=points[a].lerp(points[b],max(0,min(1,t)))
                if not any((hit-h[0]).length<1e-6 for h in hits):hits.append((hit,a,b,t))
        if len(hits)!=1:raise ValueError('SEAM_PARAMETER_NOT_SINGLE_VALUED:'+str(k))
        hit,a,b,t=hits[0];index=prior.prior.idx(1,prior.prior.M-1,k);target=interface.matrix_world@interface.data.vertices[index].co
        d=target-center
        if abs(d.dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*d.dot(u)-SEAM_Q)>1e-6 or abs(d.dot(u)*direction[1]-d.dot(v)*direction[0])>1e-6:
            raise ValueError('INTERFACE_DOES_NOT_MATCH_COMMON_SEAM_PARAMETER')
        rows.append(dict(parameter=k/n,angleIndex=k,chartEdge=[a,b],edgeT=max(0,min(1,t)),chartPoint=list(hit),interfaceVertex=index,interfacePoint=list(target),gapMeters=(hit-target).length))
    return dict(method='COMMON_HAND_ANGLE_AT_EXACT_SIGNED_HEM_PLANE',signedHemMeters=SEAM_Q,samples=rows,
                counts=dict(chartBoundaryVertices=len(loop),interfaceSamples=n),gapRangeMeters=[min(r['gapMeters'] for r in rows),max(r['gapMeters'] for r in rows)],
                automaticWeldAllowed=False,sewnOrWelded=False,gapMeasuresReferenceSurfaceToOuterSleeve=True)


def render(output,obj,body,interface,operation,mapping):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=Vector((-.18,0,1.2))
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('ClipReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';rows=[]
    def capture(name,at,delta,scale):
        scene.camera.location=at+Vector(delta);scene.camera.data.ortho_scale=scale
        scene.camera.rotation_euler=(at-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path=output/(name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        rows.append(dict(file=path.name,sha256=c.base.sha(path)))
    original=bpy.data.objects[prior.RESULT_OBJECT]
    for label,chart in [('prior_raw_domain',original),('clipped_chart',obj)]:
        original.hide_render=chart!=original;obj.hide_render=chart!=obj
        for name,delta in [('front',(0,-.7,.08)),('side',(-.7,0,.08)),('back',(0,.7,.08))]:
            capture(label+'_'+name,target,delta,.35)
    curves=[]
    def curve(name,points,color,cyclic=True):
        data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=.00035;data.bevel_resolution=2
        spline=data.splines.new('POLY');spline.points.add(len(points)-1);spline.use_cyclic_u=cyclic
        for p,co in zip(spline.points,points):p.co=(*co,1)
        item=bpy.data.objects.new(name,data);scene.collection.objects.link(item)
        data.materials.append(c.base.material(name,surface.linear_color(color)));c.base.mark(item);curves.append(item)
    for i,loop in enumerate(operation['topology']['boundaryLoops']):
        curve('DIAGNOSTIC_ClipBoundary_'+str(i),[obj.matrix_world@obj.data.vertices[j].co for j in loop],'36CDE0')
    capture('clipped_boundary_diagnostic',target,(-.7,-.3,.08),.35)
    for old in curves:old.hide_render=True
    obj.hide_render=True;body.hide_render=True;interface.hide_render=True
    samples=mapping['samples'];curve('DIAGNOSTIC_SourceSeam',[r['chartPoint'] for r in samples],'36CDE0')
    curve('DIAGNOSTIC_SleeveSeam',[r['interfacePoint'] for r in samples],'DDAA36')
    for r in samples[::8]:curve('DIAGNOSTIC_Gap_'+str(r['angleIndex']),[r['chartPoint'],r['interfacePoint']],'F06DCE',False)
    seamcenter=sum((Vector(r['chartPoint']) for r in samples),Vector())/len(samples)
    _,axis,u=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    capture('seam_correspondence_diagnostic',seamcenter,(axis-panel.HEM_SLOPE*u).normalized()*.6+u*.2,.14)
    for old in curves:old.hide_render=True;old.hide_set(True)
    return rows


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals);inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT];interface=bpy.data.objects[prior.prior.RESULT_OBJECT]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=build(body,frame);mapping=seam_map(obj,interface,frame,operation['seamLoop'])
    qa=verify_chart(body,obj,operation,frame)
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,obj,body,interface,operation,mapping)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[interface])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [body]+parts+[interface]
    obj.hide_set(True);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_ClippedShoulderSeam_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='EXACT_CLIP_AND_SEAM_MAP_DIAGNOSTIC',**c.base.GATES,sourceBlendSha256=SOURCE_SHA,
                artCommit=c.base.ART_COMMIT,references=refs,operation=operation,seamMapping=mapping,qa=qa,originalsPreserved=True,
                adoptionAllowed=False,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                runtime=dict(blenderVersion=bpy.app.version_string,buildHash=bpy.app.build_hash.decode()),
                limitations=['OPEN_REFERENCE_CHART_NOT_THICK_GARMENT','SOURCE_FOLDS_RETAINED','NO_SEWING_OR_WELD','WORLD_CLIP_ENVELOPE_NOT_APPROVED_SEWING_PATTERN','NO_HUMAN_GATE_B_OR_ANIMATION_TEST'])
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    (output/'clipped-shoulder-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 clipped shoulder reference chart / seam correspondence\nNOT PRODUCTION\nOpen chart coincides with original source surface, with interpolated UVs.\nIt is a reference for authoring a new panel, not a thickness or collision-safe garment.\nThe 128 shared-angle samples measure about 2.8 mm to the existing outer sleeve. No automatic weld or sewing.\nOriginal assembly stays visible; new chart stays hidden by default.\n',encoding='utf-8')
    print(json.dumps(dict(topology=operation['topology'],seamCounts=mapping['counts'],gap=mapping['gapRangeMeters']),indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
