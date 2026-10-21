"""Connected shoulder topology experiment; reject unsafe offsets/geometry.

The current pinned input FAILS static QA. --save-rejected-diagnostic persists
that failure for cross-environment debugging, but NEVER makes the CLI succeed.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
import clip_ch101_shoulder_seam as prior
import build_ch101_hem_binding as geometry
c,surface,panel=prior.c,prior.surface,prior.panel
interface_module=prior.prior.prior
SOURCE_SHA='b50dc04b7d4568a71d71da9b8840a0b5383a78083cb676cd1054cbb746bd83ca'
SOURCE_REPORT_SHA='03c0907d85b4cac9ccfc6740fab4adc4a42cfa36d2f628dec894bc34e72cc904'
RESULT_OBJECT='CH101_ConnectedShoulderPanel_NOT_PRODUCTION'
STRATEGY='CH101_CONNECTED_SHOULDER_QUAD_PANEL_V001'
N=128
ROWS=32
WALL=.0008
STANDOFF=.002
MAX_NEW_OFFSET=.006
SMOOTH_LIMIT=.0015
PARAMETER_OUTER_RADIUS=20.0


def chart_parameter(chart,operation,frame):
    """Positive-weight harmonic chart with ordered annulus boundaries."""
    center,axis,u=frame;v=axis.cross(u)
    points=[chart.matrix_world@p.co for p in chart.data.vertices]
    inner=operation['seamLoop'];outer=next(loop for loop in operation['topology']['boundaryLoops'] if loop!=inner)
    coords=np.zeros((len(points),2));fixed=set(inner+outer)
    for i in inner:
        d=points[i]-center;a=math.atan2(d.dot(v),d.dot(u));coords[i]=[math.cos(a),math.sin(a)]
    def projected_area(loop):
        xy=[((points[i]-center).dot(u),(points[i]-center).dot(v)) for i in loop]
        return sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(xy,xy[1:]+xy[:1]))
    if projected_area(outer)<0:outer=list(reversed(outer))
    lengths=[(points[outer[(j+1)%len(outer)]]-points[i]).length for j,i in enumerate(outer)]
    fractions=[];acc=0
    for length in lengths:fractions.append(acc/sum(lengths));acc+=length
    correlation=sum(complex(math.cos(math.atan2((points[i]-center).dot(v),(points[i]-center).dot(u))-math.tau*t),
                            math.sin(math.atan2((points[i]-center).dot(v),(points[i]-center).dot(u))-math.tau*t)) for i,t in zip(outer,fractions))
    phase=math.atan2(correlation.imag,correlation.real)
    # This dimensionless radius belongs to the parameter domain, not the model.
    # Radius 2 folds this coarse annulus near its hole (88 inverted triangles).
    # A wider annulus is accepted only if EVERY source triangle retains its sign.
    for i,t in zip(outer,fractions):
        a=math.tau*t+phase;coords[i]=[PARAMETER_OUTER_RADIUS*math.cos(a),PARAMETER_OUTER_RADIUS*math.sin(a)]
    adjacency=[set() for _ in points]
    for edge in chart.data.edges:
        a,b=edge.vertices;adjacency[a].add(b);adjacency[b].add(a)
    unknown=[i for i in range(len(points)) if i not in fixed];lookup={i:j for j,i in enumerate(unknown)}
    matrix=np.zeros((len(unknown),len(unknown)));rhs=np.zeros((len(unknown),2))
    for i in unknown:
        row=lookup[i];matrix[row,row]=len(adjacency[i])
        for j in adjacency[i]:
            if j in fixed:rhs[row]+=coords[j]
            else:matrix[row,lookup[j]]-=1
    coords[unknown]=np.linalg.solve(matrix,rhs)
    chart.data.calc_loop_triangles();triangles=[tuple(t.vertices) for t in chart.data.loop_triangles]
    areas=[float(np.linalg.det(np.array([coords[b]-coords[a],coords[d]-coords[a]]))) for a,b,d in triangles]
    if min(abs(a) for a in areas)<1e-10 or not (all(a>0 for a in areas) or all(a<0 for a in areas)):
        raise ValueError('HARMONIC_CHART_FOLDS:'+json.dumps(dict(minArea=min(areas),maxArea=max(areas))))
    return points,coords,triangles,inner,outer,dict(outerPhaseRadians=phase,outerParameterRadius=PARAMETER_OUTER_RADIUS,unknownVertices=len(unknown),minimumAbsoluteParameterTriangleArea=min(abs(a) for a in areas))


def ring_hit(coords,loop,angle):
    direction=np.array([math.cos(angle),math.sin(angle)]);hits=[]
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    for i,j in zip(loop,loop[1:]+loop[:1]):
        p=coords[i];delta=coords[j]-p;den=cross(direction,delta)
        if abs(den)<1e-12:continue
        radius=cross(p,delta)/den;t=cross(p,direction)/den
        if radius>0 and -1e-7<=t<=1+1e-7:
            hit=direction*radius
            if not any(np.linalg.norm(hit-other)<1e-7 for other in hits):hits.append(hit)
    if len(hits)!=1:raise ValueError('PARAMETER_BOUNDARY_NOT_SINGLE_VALUED')
    return hits[0]


def grid_targets(chart,operation,frame,source):
    points,coords,triangles,inner,outer,report=chart_parameter(chart,operation,frame)
    matrices=[]
    for a,b,d in triangles:
        matrices.append(np.linalg.inv(np.column_stack((coords[b]-coords[a],coords[d]-coords[a]))))
    matrices=np.array(matrices);origins=coords[np.array(triangles)[:,0]]
    seam_mapping=prior.seam_map(chart,source,frame,inner)
    radial_limits=[]
    for sample in seam_mapping['samples']:
        a,b=sample['chartEdge'];fraction=sample['edgeT']
        start=coords[a]*(1-fraction)+coords[b]*fraction
        # Preserve the actual source-edge interpolation, not a second angular
        # interpolation on a circle, which would move the 3D seam target.
        angle=math.atan2(start[1],start[0])
        radial_limits.append((start,ring_hit(coords,outer,angle)))
    result=[];provenance=[]
    for row in range(ROWS+1):
        for k in range(N):
            t=(PARAMETER_OUTER_RADIUS**(row/ROWS)-1)/(PARAMETER_OUTER_RADIUS-1)
            uv=radial_limits[k][0]*(1-t)+radial_limits[k][1]*t
            xy=np.einsum('ijk,ik->ij',matrices,uv-origins)
            all_weights=np.column_stack((1-xy.sum(axis=1),xy))
            candidates=np.flatnonzero(all_weights.min(axis=1)>=-1e-6)
            if not len(candidates):raise ValueError('GRID_OUTSIDE_PARAMETER_CHART')
            index=int(candidates[0]);weights=all_weights[index];face=triangles[index]
            result.append(sum((points[i]*float(w) for i,w in zip(face,weights)),Vector()))
            provenance.append(dict(parameter=[float(x) for x in uv],chartTriangle=index,weights=[float(w) for w in weights]))
    error=max((result[k]-Vector(sample['chartPoint'])).length for k,sample in enumerate(seam_mapping['samples']))
    if error>1e-6:raise ValueError('GRID_SEAM_TARGET_MISMATCH')
    return result,dict(parameterization=report,gridProvenance=provenance,maximumGridSeamTargetErrorMeters=error)


def build(source,body,chart,operation,frame):
    for obj in (source,body,chart):surface.require_locked(obj)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('CONNECTED_SHOULDER_ALREADY_EXISTS')
    if len(source.data.vertices)!=2*interface_module.VERTS_PER_LAYER:raise ValueError('UNEXPECTED_INTERFACE_TOPOLOGY')
    center,axis,u=frame
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_CONNECTED_PANEL_FRAME')
    targets,report=grid_targets(chart,operation,frame,source)
    old=[source.matrix_world@p.co for p in source.data.vertices];body_tree=c.fit.bvh(body)[0]
    # Control the new panel's flow on an independent uniform grid. Keep the seam
    # and upper authored boundary fixed while smoothing interior reference folds.
    shaped=[p.copy() for p in targets]
    for _ in range(4):
        previous=[p.copy() for p in shaped]
        for row in range(1,ROWS):
            for k in range(N):
                i=row*N+k;average=(previous[row*N+(k-1)%N]+previous[row*N+(k+1)%N]+previous[i-N]+previous[i+N])/4
                delta=previous[i].lerp(average,.35)-targets[i]
                if delta.length>SMOOTH_LIMIT:delta*=SMOOTH_LIMIT/delta.length
                shaped[i]=targets[i]+delta
    # Use a continuous grid normal field. Nearest-face normals jump across the
    # coarse source folds and made adjacent offset samples cross in the trial.
    chart.data.calc_loop_triangles();directions=[]
    for record in report['gridProvenance']:
        tri=chart.data.loop_triangles[record['chartTriangle']]
        normal=sum((chart.data.vertices[j].normal*w for j,w in zip(tri.vertices,record['weights'])),Vector()).normalized()
        directions.append(normal)
    for _ in range(4):
        previous=list(directions)
        for row in range(1,ROWS+1):
            for k in range(N):
                i=row*N+k
                directions[i]=(previous[i]*4+previous[row*N+(k-1)%N]+previous[row*N+(k+1)%N]+previous[i-N]+previous[min(row+1,ROWS)*N+k]).normalized()
    inner_points=[];normals=[];offsets=[];constraint_failures=[]
    for row in range(1,ROWS+1):
        for k in range(N):
            i=row*N+k;point=shaped[i]
            normal=directions[i];inner=point.copy()
            for _ in range(12):
                hit,face_normal,_,_=body_tree.find_nearest(inner)
                gap=(inner-hit).dot(face_normal)
                if gap>=STANDOFF-1e-7:break
                cosine=normal.dot(face_normal)
                if cosine<=.1:
                    constraint_failures.append(dict(row=row,column=k,reason='OFFSET_DIRECTION_GRAZES_BODY',cosine=cosine))
                    break
                inner+=normal*(STANDOFF-gap)/cosine
                delta=inner-targets[i]
                # Reserve the wall thickness inside the same NEW-panel budget.
                # A bounded but unsatisfied point is retained for diagnosis only;
                # it necessarily fails eligibility below, never widens the limit.
                if delta.length>MAX_NEW_OFFSET-WALL:
                    constraint_failures.append(dict(row=row,column=k,reason='OFFSET_BUDGET_INSUFFICIENT',requestedInnerOffsetMeters=delta.length))
                    inner=targets[i]+delta.normalized()*(MAX_NEW_OFFSET-WALL)
                    break
            hit,face_normal,_,_=body_tree.find_nearest(inner)
            gap=(inner-hit).dot(face_normal)
            if gap<STANDOFF-1e-6:
                constraint_failures.append(dict(row=row,column=k,reason='UNSATISFIED_POINT_CLEARANCE',signedGapMeters=gap))
            inner_points.append(inner);normals.append(normal);offsets.append((inner-targets[i]).length)
    vertices=[p.copy() for p in old];index_map={}
    for layer in (0,1):
        for row in range(ROWS+1):
            for k in range(N):
                if row==0:index_map[layer,row,k]=interface_module.idx(layer,interface_module.M-1,k)
                else:
                    j=(row-1)*N+k;index_map[layer,row,k]=len(vertices)
                    vertices.append(inner_points[j]+normals[j]*WALL*layer)
    seam=set(index_map[layer,0,k] for layer in (0,1) for k in range(N))
    faces=[];materials=[];smooth=[];removed=0
    for face in source.data.polygons:
        if set(face.vertices)<=seam:removed+=1;continue
        faces.append(tuple(face.vertices));materials.append(face.material_index);smooth.append(face.use_smooth)
    if removed!=N:raise ValueError('UPPER_END_WALL_REMOVAL_MISMATCH')
    for layer in (0,1):
        for row in range(ROWS):
            for k in range(N):
                faces.append(tuple(index_map[layer,r,j%N] for r,j in ((row,k),(row,k+1),(row+1,k+1),(row+1,k))));materials.append(0);smooth.append(True)
    for k in range(N):
        faces.append(tuple(index_map[layer,ROWS,j%N] for layer,j in ((0,k),(0,k+1),(1,k+1),(1,k))));materials.append(0);smooth.append(True)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for mat in source.data.materials:mesh.materials.append(mat)
    for f,m,s in zip(mesh.polygons,materials,smooth):f.material_index=m;f.use_smooth=s
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    obj['rigBound']=False;obj['joinedToSourceBodyTopology']=False;obj['adoptionAllowed']=False
    report.update(sourceVerticesRetained=len(old),sourceVertexMoveMeters=max((vertices[i]-p).length for i,p in enumerate(old)),
                  sharedSeamIndices=[index_map[1,0,k] for k in range(N)],removedUpperWallFaces=removed,
                  innerPanelOffsetRangeMeters=[min(offsets),max(offsets)],newPanelOffsetLimitMeters=MAX_NEW_OFFSET,
                  smoothingLimitMeters=SMOOTH_LIMIT,newPanelUVAuthored=False,sourceTextureTransferred=False,
                  newPanelAppearance='WHITE_GEOMETRY_STUDY',rows=ROWS,angularColumns=N,
                  constraintFailures=constraint_failures,newPanelUVReady=False,
                  sourceBodyMovedVertices=0,originalCumulativeDisplacementBudgetReset=False)
    return obj,report,index_map


def audit(obj,body,parts,operation,index_map):
    for subject in (obj,body,*parts):surface.require_locked(subject)
    qa=geometry.audit(obj,body,parts,expected_vertices=2*interface_module.VERTS_PER_LAYER+2*ROWS*N)
    obj.data.calc_loop_triangles();points=[obj.matrix_world@v.co for v in obj.data.vertices]
    skins=[]
    for layer in (0,1):
        ids=set(index_map[layer,r,k] for r in range(ROWS+1) for k in range(N))
        skins.append([tuple(t.vertices) for t in obj.data.loop_triangles if set(t.vertices)<=ids])
    distances=[]
    for layer in (0,1):
        tree=BVHTree.FromPolygons(points,skins[1-layer],all_triangles=True)
        samples=[points[index_map[layer,r,k]] for r in range(ROWS+1) for k in range(N)]
        samples += [sum((points[i] for i in tri),Vector())/3 for tri in skins[layer]]
        distances.extend(tree.find_nearest(p)[3] for p in samples)
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();edge_counts=[];joined=True
    for layer in (0,1):
        seam=set(interface_module.idx(layer,interface_module.M-1,k) for k in range(N))
        edges=[e for e in bm.edges if all(v.index in seam for v in e.verts)]
        edge_counts.append(len(edges));joined=joined and len(edges)==N and all(len(e.link_faces)==2 for e in edges)
    bm.free()
    source=bpy.data.objects[interface_module.RESULT_OBJECT]
    preserved_move=max((points[v.index]-source.matrix_world@v.co).length for v in source.data.vertices)
    qa.update(newPanelWallRangeMeters=[min(distances),max(distances)],wallSamples=len(distances),
              sharedSeamEdgeCount=edge_counts[1],sharedSeamEdgeCountsInnerOuter=edge_counts,seamManifold=joined,bodyMovedVertices=0,sourceVertexMoveMeters=preserved_move)
    qa['constraintFailureCount']=len(operation['constraintFailures'])
    qa['eligible']=qa['eligible'] and joined and min(distances)>.0002 and max(distances)<.0012 and preserved_move==0 and not operation['constraintFailures']
    tree,_,triangles=c.fit.bvh(obj)
    body_pairs=tree.overlap(c.fit.bvh(body)[0])
    self_pairs=sorted({(a,b) for a,b in tree.overlap(tree) if a<b and not set(triangles[a])&set(triangles[b])})
    qa['diagnosticBodyPairs']=[list(pair) for pair in body_pairs]
    qa['diagnosticSelfPairs']=[list(pair) for pair in self_pairs]
    qa['diagnosticPairIndexDomain']='LOOP_TRIANGLE_INDEX_NOT_POLYGON_INDEX'
    reverse_index={i:(layer,row,k) for (layer,row,k),i in index_map.items()}
    bad=set(a for a,b in body_pairs)|set(i for pair in self_pairs for i in pair)
    rows={};layers={}
    for tri in bad:
        affected={reverse_index[i][:2] for i in triangles[tri] if i in reverse_index}
        for row in {row for layer,row in affected}:rows[str(row)]=rows.get(str(row),0)+1
        for layer in {layer for layer,row in affected}:layers[str(layer)]=layers.get(str(layer),0)+1
    qa['collidingTriangleCountsByPanelRow']=rows;qa['collidingTriangleCountsByLayer']=layers
    qa['failedCriteria']=[name for name,failed in (
        ('NON_ADJACENT_SELF_INTERSECTION',qa['nonAdjacentSelfIntersectionPairs']>0),
        ('BODY_OR_EQUIPMENT_INTERSECTION',any(qa['intersectionPairsByObject'].values())),
        ('SAMPLED_WALL_OUT_OF_RANGE',min(distances)<=.0002 or max(distances)>=.0012),
        ('SAMPLED_BODY_GAP_TOO_SMALL',qa['minimumSampledBodyGapMeters']<=.0002),
        ('BOUNDED_POINT_CONSTRAINT_UNSATISFIED',bool(operation['constraintFailures'])),
        ('SOURCE_VERTEX_CHANGED',preserved_move!=0),('SEAM_NOT_MANIFOLD',not joined),
        ('TOPOLOGY_INVALID',qa['nonManifoldEdges']>0 or qa['nonContiguousEdges']>0 or qa['zeroAreaFaces']>0 or qa['euler']!=0)) if failed]
    return qa


def render(output,source,obj,body,parts,qa):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=Vector((-.18,0,1.2))
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('ConnectedPanelReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';records=[]
    def capture(name,delta,scale=.38):
        scene.camera.location=target+Vector(delta);scene.camera.data.ortho_scale=scale
        scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path=output/(name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        records.append(dict(file=path.name,sha256=c.base.sha(path)))
    for state,shell in [('before',source),('trial',obj)]:
        source.hide_render=shell!=source;obj.hide_render=shell!=obj
        for part in [body]+parts:part.hide_render=False
        for name,delta in [('front',(0,-.7,.08)),('side',(-.7,0,.08)),('back',(0,.7,.08))]:
            capture(state+'_'+name,delta)
    for part in [body]+parts:part.hide_render=True
    capture('trial_isolated',(-.7,-.3,.08))
    # A COPY carries diagnostic materials; do not mutate candidate/source slots.
    diag=obj.copy();diag.data=obj.data.copy();scene.collection.objects.link(diag)
    diag.name='DIAGNOSTIC_ConnectedPanel_CollidingFaces';c.base.mark(diag)
    obj.hide_render=True;diag.hide_render=False;diag.data.calc_loop_triangles()
    bad=set(a for a,b in qa['diagnosticBodyPairs'])
    bad.update(i for pair in qa['diagnosticSelfPairs'] for i in pair)
    diagnostic_material=len(diag.data.materials)
    diag.data.materials.append(c.base.material('DiagnosticIntersectingFace',surface.linear_color('F02B85')))
    for i in bad:diag.data.polygons[diag.data.loop_triangles[i].polygon_index].material_index=diagnostic_material
    capture('collision_diagnostic',(-.7,-.3,.08))
    bpy.data.objects.remove(diag,do_unlink=True)
    return records


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    metadata=source.parent/'clipped-shoulder-report.json'
    if c.base.sha(metadata)!=SOURCE_REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    old=bpy.data.objects[interface_module.RESULT_OBJECT];body=bpy.data.objects[panel.RESULT_OBJECT];chart=bpy.data.objects[prior.RESULT_OBJECT]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    # Reconstruct the pinned chart metadata and check correspondence before use.
    original_report=json.loads(metadata.read_text(encoding='utf-8'))
    operation=original_report['operation'];prior.verify_chart(body,chart,operation,frame);prior.seam_map(chart,old,frame,operation['seamLoop'])
    obj,operation,index_map=build(old,body,chart,operation,frame)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    oldband=bpy.data.objects[interface_module.prior.prior.prior.RESULT_OBJECT]
    qa=audit(obj,body,parts+[oldband],operation,index_map)
    print(json.dumps({k:v for k,v in qa.items() if not k.startswith('diagnostic')},indent=2))
    if not qa['eligible'] and not getattr(args,'save_rejected_diagnostic',False):raise ValueError('CONNECTED_PANEL_QA_REJECTED')
    obj['staticQAEligible']=qa['eligible'];obj['diagnosticOnly']=not qa['eligible']
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,old,obj,body,parts,qa)
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[old])
    for o in bpy.context.scene.objects:
        if o.type in ('MESH','CURVE'):o.hide_render=o not in [body]+parts+[old]
    obj.hide_set(True);bpy.context.preferences.filepaths.save_version=0
    blend=output/('CH101_ConnectedShoulderPanel_NOT_PRODUCTION_v001.blend' if qa['eligible'] else 'CH101_ConnectedShoulder_REJECTED_DIAGNOSTIC_v001.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='CONNECTED_PANEL_PENDING_VISUAL_REVIEW' if qa['eligible'] else 'CONNECTED_PANEL_REJECTED_DIAGNOSTIC',**c.base.GATES,sourceBlendSha256=SOURCE_SHA,sourceReportSha256=SOURCE_REPORT_SHA,
                operation=operation,qa=qa,artCommit=c.base.ART_COMMIT,references=refs,originalsPreserved=True,
                adoptionAllowed=False,diagnosticOnly=not qa['eligible'],rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                runtime=dict(blenderVersion=bpy.app.version_string,buildHash=bpy.app.build_hash.decode(),device='CPU'),
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['WHITE_GEOMETRY_STUDY_NO_NEW_PANEL_UV_OR_STRAP_TEXTURE','UPPER_BOUNDARY_ATTACHMENT_PENDING',
                             'NEW_PANEL_JOINED_TO_SLEEVE_NOT_SOURCE_BODY','STATIC_SAMPLES_NOT_ANIMATION_PROOF','NO_HUMAN_GATE_B'])
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    (output/'connected-shoulder-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 connected shoulder — NOT PRODUCTION\nStatus: '+report['status']+'\nStatic QA eligible: '+str(qa['eligible'])+'\nThis is a saved diagnostic, NOT an approved replacement. The trial object is hidden; the previous assembly is visible.\nNew panel is white with no authored UV or transferred strap texture. No original mesh moves.\nSee connected-shoulder-report.json and collision_diagnostic.png before editing. Pink marks tested intersections, not approved materials.\nNo rig, full-character score, Unity input, production promotion or human Gate B approval.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    p.add_argument('--save-rejected-diagnostic',action='store_true',help='Save rejected geometry for debugging; still exits with failure')
    report=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    if not report['qa']['eligible']:raise SystemExit(1)
