"""Bounded face-bending descent between pinned panel seams, borders and creases."""
import argparse
from collections import defaultdict
import json
import math
import numpy as np
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import retopologize_ch101_shoulder_regions as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='075374b9849adb29a4162d4f020382da4a2eb929ffe4c8db71b3ff4d6afdc01a'
REPORT_SHA='7019af8733ec5591fee3711b9a583ca27d4c8377b503f88db9aff932e9f5bed8'
RESULT_OBJECT='CH101_CreaseAwareShoulderFairing_NOT_PRODUCTION'
STRATEGY='CH101_PINNED_PANEL_CREASE_FAIRING_V001'
MAX_MOVE=.00145
MAX_SURFACE_ERROR=.0015
MAJOR_CREASE=math.radians(55)
ITERATIONS=5
STEP=.00035


def topology(source):
    source.data.calc_loop_triangles()
    adjacency=defaultdict(set);edge_faces=defaultdict(list)
    for edge in source.data.edges:
        a,b=edge.vertices;adjacency[a].add(b);adjacency[b].add(a)
    for face in source.data.polygons:
        ids=list(face.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):edge_faces[tuple(sorted((a,b)))].append(face.index)
    pinned=set();major=[];seams=[];borders=[]
    for edge,fs in edge_faces.items():
        if len(fs)==1:borders.append(edge);pinned.update(edge)
        elif len(fs)!=2:raise ValueError('UNEXPECTED_SOURCE_EDGE_FACES')
        elif source.data.polygons[fs[0]].material_index!=source.data.polygons[fs[1]].material_index:
            seams.append(edge);pinned.update(edge)
        elif source.data.polygons[fs[0]].normal.angle(source.data.polygons[fs[1]].normal)>MAJOR_CREASE:
            major.append(edge);pinned.update(edge)
    # Pin the immediate neighbors of major creases: no movement across the
    # coarse fold's two sides while its crease itself remains unchanged.
    pinned.update(j for edge in major for i in edge for j in adjacency[i])
    return adjacency,edge_faces,pinned,dict(majorCreaseEdges=[list(e) for e in major],
                                         sharedSeamEdges=[list(e) for e in seams],borderEdges=[list(e) for e in borders])


def bending(obj,edges):
    obj.data.update()
    obj.data.calc_loop_triangles()
    edges=defaultdict(list)
    normals=[]
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    for index,triangle in enumerate(obj.data.loop_triangles):
        ids=list(triangle.vertices)
        a,b,d=(points[i] for i in ids)
        normals.append((b-a).cross(d-a).normalized())
        for a,b in zip(ids,ids[1:]+ids[:1]):edges[tuple(sorted((a,b)))].append(index)
    value=0;angles=[]
    for (a,b),fs in edges.items():
        if len(fs)!=2:continue
        angle=normals[fs[0]].angle(normals[fs[1]])
        value+=angle*angle*(points[a]-points[b]).length;angles.append(angle)
    return dict(measurement='RENDER_TRIANGLE_DIHEDRAL_BENDING',weightedRadiansSquaredMeters=value,
                maximumDegrees=math.degrees(max(angles)),interiorEdgeCount=len(angles))


def move_points(obj,original,adjacency,pinned,maximum_move=None,point_constraint=None,iterations=None,refresh_triangles=False):
    """Descent on render triangles, including each quad's internal diagonal.

    Default to source tessellation for the original five-iteration recipe.
    Reconnection callers can refresh Blender tessellation on each iteration;
    the final audit independently measures post-movement render triangles.
    """
    base=np.array([list(p) for p in original],dtype=np.float64);points=base.copy()
    maximum_move=MAX_MOVE if maximum_move is None else maximum_move
    for vertex,point in zip(obj.data.vertices,original):vertex.co=point
    obj.data.update();obj.data.calc_loop_triangles()
    faces=np.array([tuple(f.vertices) for f in obj.data.loop_triangles])
    edge_faces=defaultdict(list)
    vertex_faces=defaultdict(set)
    for fi,face in enumerate(faces):
        for i in face:vertex_faces[int(i)].add(fi)
        for a,b in zip(face,np.roll(face,-1)):edge_faces[tuple(sorted((int(a),int(b))))].append(fi)
    pairs=[(edge,fs) for edge,fs in edge_faces.items() if len(fs)==2]
    edge_ids=np.array([e for e,_ in pairs]);face_pairs=np.array([fs for _,fs in pairs])
    face_edges=defaultdict(set)
    for ei,fs in enumerate(face_pairs):
        for fi in fs:face_edges[int(fi)].add(ei)
    def normals(p,ids):
        vertices=p[faces[ids]]
        vertices=vertices-vertices.mean(axis=1,keepdims=True)
        area=np.cross(vertices,np.roll(vertices,-1,axis=1)).sum(axis=1)
        lengths=np.linalg.norm(area,axis=1)
        return area/np.maximum(lengths[:,None],1e-20)
    def energy(p,n,ids=None):
        pairs=face_pairs if ids is None else face_pairs[ids]
        edges=edge_ids if ids is None else edge_ids[ids]
        dot=np.einsum('ij,ij->i',n[pairs[:,0]],n[pairs[:,1]])
        angles=np.arccos(np.clip(dot,-1,1))
        lengths=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)
        return angles*angles*lengths
    records=[]
    local_steps=np.array([min(STEP,.1*min(np.linalg.norm(base[i]-base[j]) for j in adjacency[i])) for i in range(len(base))])
    for iteration in range(ITERATIONS if iterations is None else iterations):
        if refresh_triangles:
            for vertex,point in zip(obj.data.vertices,points):vertex.co=point
            obj.data.update();obj.data.calc_loop_triangles()
            faces=np.array([tuple(f.vertices) for f in obj.data.loop_triangles])
            edge_faces=defaultdict(list);vertex_faces=defaultdict(set)
            for fi,face in enumerate(faces):
                for i in face:vertex_faces[int(i)].add(fi)
                for a,b in zip(face,np.roll(face,-1)):edge_faces[tuple(sorted((int(a),int(b))))].append(fi)
            pairs=[(edge,fs) for edge,fs in edge_faces.items() if len(fs)==2]
            edge_ids=np.array([e for e,_ in pairs]);face_pairs=np.array([fs for _,fs in pairs])
            face_edges=defaultdict(set)
            for ei,fs in enumerate(face_pairs):
                for fi in fs:face_edges[int(fi)].add(ei)
        n=normals(points,np.arange(len(faces)));current=float(energy(points,n).sum())
        accepted_vertices=0;maximum_step=0
        for i in range(len(points)):
            if i in pinned:continue
            affected_faces=np.array(sorted(vertex_faces[i]))
            affected_edges=np.array(sorted({e for fi in affected_faces for e in face_edges[int(fi)]}))
            epsilon=max(1e-8,min(.000005,local_steps[i]))
            gradient=np.zeros(3)
            local_current=float(energy(points,n,affected_edges).sum())
            for axis in range(3):
                values=[]
                for sign in (-1,1):
                    trial=points.copy();trial[i,axis]+=sign*epsilon
                    trial_normals=n.copy();trial_normals[affected_faces]=normals(trial,affected_faces)
                    values.append(float(energy(trial,trial_normals,affected_edges).sum()))
                gradient[axis]=(values[1]-values[0])/(2*epsilon)
            length=np.linalg.norm(gradient)
            if length<1e-12:continue
            direction=-gradient/length
            for backtrack in range(10):
                trial=points.copy();trial[i]+=direction*(local_steps[i]/2**backtrack)
                delta=trial[i]-base[i];distance=np.linalg.norm(delta)
                if distance>maximum_move:trial[i]=base[i]+delta*(maximum_move/distance)
                if point_constraint is not None:
                    trial[i]=point_constraint(i,trial[i])
                    if np.linalg.norm(trial[i]-base[i])>maximum_move+1e-10:continue
                trial_normals=n.copy();trial_normals[affected_faces]=normals(trial,affected_faces)
                value=float(energy(trial,trial_normals,affected_edges).sum())
                if value<local_current-1e-12:
                    maximum_step=max(maximum_step,float(np.linalg.norm(trial[i]-points[i])))
                    points[i]=trial[i];n[affected_faces]=trial_normals[affected_faces];accepted_vertices+=1;break
        value=float(energy(points,n).sum())
        records.append(dict(iteration=iteration,beforeEnergy=current,afterEnergy=value,
                            accepted=accepted_vertices>0,acceptedVertices=accepted_vertices,maximumStepMeters=maximum_step))
        if not accepted_vertices:break
    for vertex,point in zip(obj.data.vertices,points):vertex.co=point
    obj.data.update()
    return records


def collision_pairs(obj):
    tree,_,triangles=c.fit.bvh(obj)
    return [(a,b) for a,b in tree.overlap(tree) if a<b and not set(triangles[a])&set(triangles[b])],triangles


def build(source):
    surface.require_locked(source)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('FAIRING_ALREADY_EXISTS')
    obj=source.copy();obj.data=source.data.copy();obj.name=RESULT_OBJECT;bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj);obj['adoptionAllowed']=False;obj['rigBound']=False
    original=[v.co.copy() for v in source.data.vertices]
    adjacency,edges,pinned,features=topology(source);initial=set(pinned)
    attempts=[]
    for attempt in range(6):
        optimization=move_points(obj,original,adjacency,pinned)
        pairs,triangles=collision_pairs(obj)
        reversed_faces=[f for f,old in zip(obj.data.polygons,source.data.polygons) if f.normal.dot(old.normal)<.25]
        attempts.append(dict(attempt=attempt,intersectionPairs=len(pairs),orientationFailureFaces=len(reversed_faces),pinnedVertexCount=len(pinned)))
        if not pairs and not reversed_faces:break
        failed={i for a,b in pairs for t in (a,b) for i in triangles[t]}
        failed.update(i for face in reversed_faces for i in face.vertices)
        pinned.update(failed);pinned.update(j for i in failed for j in adjacency[i])
    else:raise ValueError('FAIRING_COLLISIONS_UNRESOLVED')
    operation=dict(method='WEIGHTED_RENDER_TRIANGLE_BENDING_DESCENT_WITH_PINNED_MAJOR_CREASES',features=features,
                   initialPinnedVertices=sorted(initial),pinnedVertices=sorted(pinned),collisionAttempts=attempts,
                   maximumSourceMoveMeters=MAX_MOVE,maximumSourceSurfaceErrorMeters=MAX_SURFACE_ERROR,
                   iterations=ITERATIONS,step=STEP,majorCreaseDegrees=math.degrees(MAJOR_CREASE),
                   optimization=optimization,
                   topologyChanged=False,originalBodyMovedVertices=0,garmentStaticQA=False,
                   beforeBending=bending(source,edges),afterBending=bending(obj,edges))
    return obj,operation


def audit(obj,source,operation):
    surface.require_locked(obj);surface.require_locked(source)
    if len(obj.data.vertices)!=len(source.data.vertices) or [tuple(f.vertices) for f in obj.data.polygons]!=[tuple(f.vertices) for f in source.data.polygons]:
        raise ValueError('FAIRING_TOPOLOGY_CHANGED')
    if [f.material_index for f in obj.data.polygons]!=[f.material_index for f in source.data.polygons]:
        raise ValueError('FAIRING_REGIONS_CHANGED')
    _,edges,required,features=topology(source)
    if operation['features']!=features or not required<=set(operation['pinnedVertices']):raise ValueError('FAIRING_FEATURE_PINS_CHANGED')
    deltas=[(obj.matrix_world@v.co-source.matrix_world@old.co).length for v,old in zip(obj.data.vertices,source.data.vertices)]
    pinned_move=max(deltas[i] for i in operation['pinnedVertices'])
    pairs,triangles=collision_pairs(obj)
    chart=bpy.data.objects[prior.prior.RESULT_OBJECT]
    tree=c.fit.bvh(obj)[0];chart_tree,chart_points,chart_tris=c.fit.bvh(chart)
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    samples=points+[sum((points[i] for i in t),Vector())/3 for t in triangles]
    samples +=[(points[e.vertices[0]]+points[e.vertices[1]])/2 for e in obj.data.edges]
    forward=[chart_tree.find_nearest(p)[3] for p in samples]
    reverse_samples=chart_points+[sum((chart_points[i] for i in t),Vector())/3 for t in chart_tris]
    reverse=[tree.find_nearest(p)[3] for p in reverse_samples]
    bm=bmesh.new();bm.from_mesh(obj.data);orient=sum(e.is_manifold and not e.is_contiguous for e in bm.edges);zero=sum(f.calc_area()<1e-12 for f in bm.faces);bm.free()
    minimum_normal_dot=min(f.normal.dot(old.normal) for f,old in zip(obj.data.polygons,source.data.polygons))
    before=bending(source,edges);after=bending(obj,edges)
    reduction=1-after['weightedRadiansSquaredMeters']/before['weightedRadiansSquaredMeters']
    qa=dict(vertices=len(points),quads=len(obj.data.polygons),movedVertices=sum(d>1e-8 for d in deltas),
            maximumMoveMeters=max(deltas),maximumPinnedMoveMeters=pinned_move,pinnedVertexCount=len(operation['pinnedVertices']),
            nonAdjacentSelfIntersectionPairs=len(pairs),nonContiguousInteriorEdges=orient,zeroAreaFaces=zero,
            minimumSourceFaceNormalDot=minimum_normal_dot,
            maximumForwardSampleErrorMeters=max(forward),maximumReverseSampleErrorMeters=max(reverse),
            forwardSampleCount=len(samples),reverseSampleCount=len(reverse_samples),
            beforeBending=before,afterBending=after,weightedBendingReductionFraction=reduction,
            sharedSeamEdges=len(features['sharedSeamEdges']),topologyChanged=False,originalBodyMovedVertices=0,garmentStaticQA=False)
    qa['eligible']=qa['movedVertices']>0 and max(deltas)<=MAX_MOVE+1e-7 and pinned_move<1e-8 and not pairs and orient==0 and zero==0 and minimum_normal_dot>=.25 and max(forward+reverse)<=MAX_SURFACE_ERROR and reduction>.001
    if not qa['eligible']:raise ValueError('FAIRING_QA_REJECTED:'+json.dumps(qa))
    return qa


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if c.base.sha(source.parent/'quad-cage-report.json')!=REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals};visible=[o for o in originals if not o.hide_get()]
    old=bpy.data.objects[prior.RESULT_OBJECT];obj,op=build(old);qa=audit(obj,old,op)
    output.mkdir(parents=True);renders=[]
    if not args.no_render:
        for label,item in [('before',old),('after',obj)]:
            folder=output/label;folder.mkdir();rows=prior.prior.render(folder,item,[])
            renders.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in rows)
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in visible
    obj.hide_set(True);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_CreaseAwareShoulderFairing_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='LOCAL_CREASE_FAIRING_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                runtime=dict(blenderVersion=bpy.app.version_string,device='CPU'),operation=op,qa=qa,
                originalsPreserved=True,adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['LOCAL_MINOR_FOLD_FAIRING_MAJOR_FOLDS_RETAINED','EDGE_FLOW_AND_VERTEX_VALENCE_UNCHANGED',
                             'OPEN_UNOFFSET_SURFACE_NO_GARMENT_CLEARANCE_THICKNESS_OR_SEWING','FINITE_ERROR_SAMPLES',
                             'NO_UV_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'crease-fairing-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 bounded crease-aware shoulder fairing — NOT PRODUCTION\nMinor folds between pinned panel seams, borders and major creases are faired. Topology and major folds remain.\nNew study stays hidden; previous visible assembly is preserved. No thickness, sewing, rig or full-character score.\n',encoding='utf-8')
    print(json.dumps(qa,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
