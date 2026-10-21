"""Feature-locked quad reconnection, not smoothing or a complete shoulder rig."""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fair_ch101_shoulder_panels as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='fda96bec01f2ddbab72c559effb7f61e8471340e9730cd34870d31847199908b'
REPORT_SHA='7c44b13a16966a04c4cebc9ccead1b02ee31aced1cee28fe0b96eedb9e52f715'
RESULT_OBJECT='CH101_FeatureLockedShoulderEdgeFlow_NOT_PRODUCTION'
STRATEGY='CH101_FEATURE_LOCKED_QUAD_RECONNECTION_V001'
MAX_SURFACE_ERROR=.0015
MAX_PATCH_ANGLE=math.radians(15)
PASSES=8
MAX_NEW_MOVE=.0012
MAX_TOTAL_MOVE=.00148
CORRECTION_ITERATIONS=50
# Pinned source-specific faces whose trial triangle-centroid errors exceeded
# the original chart cap. Preserve their quads AND vertices, not just the pins.
GEOMETRY_GUARD_FACES={164,421}
MAX_LOCAL_BENDING_RISE=.002


def edge_faces(faces):
    result=defaultdict(list)
    for fi,face in enumerate(faces):
        for a,b in zip(face,face[1:]+face[:1]):result[tuple(sorted((a,b)))].append(fi)
    return result


def degree_map(edges,vertex_count):
    degrees=[0]*vertex_count
    for a,b in edges:degrees[a]+=1;degrees[b]+=1
    return degrees


def valence(degrees,border):
    counts=Counter(degrees[i] for i in range(len(degrees)) if i not in border)
    return dict(interiorVertexCount=sum(counts.values()),regularInteriorVertices=counts[4],
                irregularInteriorVertices=sum(n for k,n in counts.items() if k!=4),
                squaredValenceError=sum((k-4)**2*n for k,n in counts.items()),
                interiorValenceCounts={str(k):v for k,v in sorted(counts.items())})


def alternatives(first,second):
    """Two oriented quad splits of the same simple six-edge disk."""
    edges=edge_faces([first,second]);shared=[e for e,fs in edges.items() if len(fs)==2]
    if len(shared)!=1:return []
    boundary=[(a,b) for f in (first,second) for a,b in zip(f,f[1:]+f[:1]) if tuple(sorted((a,b)))!=shared[0]]
    successor={a:b for a,b in boundary}
    if len(successor)!=6 or len(set(successor.values()))!=6:return []
    a=shared[0][0];loop=[a]
    for _ in range(5):
        if loop[-1] not in successor:return []
        loop.append(successor[loop[-1]])
    if len(set(loop))!=6 or successor.get(loop[-1])!=a:return []
    if set((loop[0],loop[3]))!=set(shared[0]):return []
    return [(tuple(loop[k:]+loop[:k])[:4],tuple((loop[k:]+loop[:k])[3:]+(loop[k:]+loop[:k])[:1])) for k in (1,2)]


def polygon_normal(points,face):
    center=sum((points[i] for i in face),Vector())/len(face)
    p=[points[i]-center for i in face]
    return sum((a.cross(b) for a,b in zip(p,p[1:]+p[:1])),Vector()).normalized()


def triangulate(points,face):
    # Blender's mesh tessellation differs from mathutils.tessellate_polygon
    # for many nonplanar quads. Use the actual renderer's mesh implementation.
    mesh=bpy.data.meshes.new('EdgeFlowTriangleProbe')
    try:
        mesh.from_pydata([points[i] for i in face],[],[tuple(range(len(face)))])
        mesh.calc_loop_triangles()
        return [tuple(face[i] for i in t.vertices) for t in mesh.loop_triangles]
    finally:bpy.data.meshes.remove(mesh)


def local_bending(points,faces,cache=None):
    edges=defaultdict(list);normals=[]
    for face in faces:
        if cache is None:triangles=triangulate(points,face)
        else:
            if face not in cache:cache[face]=triangulate(points,face)
            triangles=cache[face]
        for tri in triangles:
            a,b,d=(points[i] for i in tri);index=len(normals)
            normals.append((b-a).cross(d-a).normalized())
            for a,b in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((a,b)))].append(index)
    return sum(normals[fs[0]].angle(normals[fs[1]])**2*(points[a]-points[b]).length
               for (a,b),fs in edges.items() if len(fs)==2)


def patch_safe(points,pair,old_pair,source_tree):
    old_normal=sum((polygon_normal(points,f) for f in old_pair),Vector()).normalized()
    samples=[]
    for face in pair:
        p=[points[i] for i in face]
        normal=polygon_normal(points,face)
        if normal.length<.99 or normal.dot(old_normal)<.5:return False
        for a,b,d in ((p[0],p[1],p[2]),(p[0],p[2],p[3]),(p[0],p[1],p[3]),(p[1],p[2],p[3])):
            area=(b-a).cross(d-a)
            if area.length<2e-12 or area.normalized().dot(normal)<.5:return False
            samples.append((a+b+d)/3)
        samples.extend((a+b)/2 for a,b in zip(p,p[1:]+p[:1]))
    return all(source_tree.find_nearest(p)[3]<=MAX_SURFACE_ERROR for p in samples)


def reconnect(source,blocked_faces=()):
    points=[source.matrix_world@v.co for v in source.data.vertices]
    faces=[tuple(f.vertices) for f in source.data.polygons]
    if any(len(f)!=4 for f in faces):raise ValueError('SOURCE_NOT_QUADS')
    _,initial_edges,_,features=prior.topology(source)
    protected={tuple(e) for group in features.values() for e in group}
    border={i for e in features['borderEdges'] for i in e}
    locked=set(blocked_faces)|GEOMETRY_GUARD_FACES|{fi for edge in features['majorCreaseEdges'] for fi in initial_edges[tuple(edge)]}
    degrees=degree_map(initial_edges,len(points));before=valence(degrees,border)
    chart=bpy.data.objects[prior.prior.prior.RESULT_OBJECT];source_tree=c.fit.bvh(chart)[0]
    rotations=[];passes=[]
    triangle_cache={}
    for iteration in range(PASSES):
        edges=edge_faces(faces);changed=0;used=set()
        for edge,fs in sorted(edges.items()):
            if len(fs)!=2 or edge in protected or set(fs)&(locked|used):continue
            a,b=fs
            if source.data.polygons[a].material_index!=source.data.polygons[b].material_index:continue
            old_pair=(faces[a],faces[b])
            if polygon_normal(points,old_pair[0]).angle(polygon_normal(points,old_pair[1]))>MAX_PATCH_ANGLE:continue
            perimeter=[e for e,ids in edge_faces(old_pair).items() if len(ids)==1]
            neighbors=sorted({fi for e in perimeter for fi in edges[e]}-{a,b})
            surrounding=[faces[fi] for fi in neighbors]
            old_bending=local_bending(points,list(old_pair)+surrounding,triangle_cache)
            choices=[]
            for pair in alternatives(*old_pair):
                internal=[e for e,ids in edge_faces(pair).items() if len(ids)==2]
                if len(internal)!=1 or internal[0] in edges:continue
                new_edge=internal[0];delta=Counter({i:-1 for i in edge});delta.update(new_edge)
                gain=sum((degrees[i]+d-4)**2-(degrees[i]-4)**2 for i,d in delta.items() if i not in border)
                count_gain=sum(int(degrees[i]+d!=4)-int(degrees[i]!=4) for i,d in delta.items() if i not in border)
                if gain>=0 or not patch_safe(points,pair,old_pair,source_tree):continue
                new_bending=local_bending(points,list(pair)+surrounding,triangle_cache)
                if new_bending-old_bending>MAX_LOCAL_BENDING_RISE:continue
                choices.append((gain,count_gain,new_edge,pair,delta,new_bending))
            if not choices:continue
            gain,count_gain,new_edge,pair,delta,new_bending=min(choices,key=lambda row:row[:3])
            faces[a],faces[b]=pair
            del edges[edge];edges[new_edge]=[a,b]
            # Correct incident face IDs on the six unchanged perimeter edges.
            for e,ids in edge_faces(pair).items():
                if e!=new_edge:edges[e]=[fi for fi in edges[e] if fi not in (a,b)]+[a if ids[0]==0 else b]
            for i,d in delta.items():degrees[i]+=d
            rotations.append(dict(iteration=iteration,faceIndices=fs,oldFaces=[list(f) for f in old_pair],
                                  newFaces=[list(f) for f in pair],removedEdge=list(edge),addedEdge=list(new_edge),
                                  squaredValenceErrorChange=gain,beforeLocalBending=old_bending,afterLocalBending=new_bending))
            changed+=1;used.update(fs)
        passes.append(dict(iteration=iteration,rotations=changed,**valence(degrees,border)))
        if not changed:break
    # Recompute from actual connectivity instead of trusting incremental counts.
    after=valence(degree_map(edge_faces(faces),len(points)),border)
    return points,faces,dict(method='FEATURE_LOCKED_ORIENTED_HEXAGON_QUAD_RECONNECTION',features=features,
                            lockedFaceIndices=sorted(locked),rotations=rotations,passes=passes,
                            beforeValence=before,afterValence=after,maximumPatchAngleDegrees=math.degrees(MAX_PATCH_ANGLE),
                            maximumLocalBendingRise=MAX_LOCAL_BENDING_RISE,
                            sourceSurfaceErrorLimitMeters=MAX_SURFACE_ERROR,sourceVerticesMoved=0,
                            majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False)


def build(source,blocked_faces=()):
    surface.require_locked(source)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('EDGE_FLOW_ALREADY_EXISTS')
    points,faces,op=reconnect(source,blocked_faces)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(points,[],faces);mesh.update()
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    for mat in source.data.materials:mesh.materials.append(mat)
    for new,old in zip(mesh.polygons,source.data.polygons):new.material_index=old.material_index;new.use_smooth=False
    obj['adoptionAllowed']=False;obj['rigBound']=False;obj['openUnsewnSurface']=True
    # Connectivity is solved first; its geometric side effects are then
    # corrected on the new topology without exceeding the ORIGINAL chart cap.
    _,_,pinned,_=prior.topology(source)
    pinned.update(i for fi in op['lockedFaceIndices'] for i in source.data.polygons[fi].vertices)
    adjacency=defaultdict(set)
    for a,b in edge_faces(faces):adjacency[a].add(b);adjacency[b].add(a)
    tree=c.fit.bvh(bpy.data.objects[prior.prior.prior.RESULT_OBJECT])[0]
    original_quad=bpy.data.objects[prior.prior.RESULT_OBJECT]
    original_points=[original_quad.matrix_world@v.co for v in original_quad.data.vertices]
    def constrain(i,point):
        p=Vector(list(point));nearest,_,_,distance=tree.find_nearest(p)
        if distance>MAX_SURFACE_ERROR-.00002:p=nearest+(p-nearest)*((MAX_SURFACE_ERROR-.00002)/distance)
        delta=p-original_points[i]
        if delta.length>MAX_TOTAL_MOVE:p=original_points[i]+delta.normalized()*MAX_TOTAL_MOVE
        return list(p)
    op['geometryCorrection']=prior.move_points(obj,points,adjacency,pinned,maximum_move=MAX_NEW_MOVE,point_constraint=constrain,iterations=CORRECTION_ITERATIONS,refresh_triangles=True) if op['rotations'] else []
    op['refreshRenderTrianglesEachIteration']=True
    op['pinnedVertices']=sorted(pinned);op['maximumAdditionalVertexMoveMeters']=MAX_NEW_MOVE
    op['maximumCumulativeQuadVertexMoveMeters']=MAX_TOTAL_MOVE
    return obj,op


def audit(obj,source,op):
    surface.require_locked(obj);surface.require_locked(source)
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    originals=[source.matrix_world@v.co for v in source.data.vertices]
    faces=[tuple(f.vertices) for f in obj.data.polygons];old_faces=[tuple(f.vertices) for f in source.data.polygons]
    if len(points)!=len(originals) or len(faces)!=len(old_faces):raise ValueError('EDGE_FLOW_COUNTS_CHANGED')
    required_pinned=prior.topology(source)[2]
    if not required_pinned<=set(op['pinnedVertices']):raise ValueError('FEATURE_VERTEX_PINS_CHANGED')
    move=max((a-b).length for a,b in zip(points,originals))
    pinned_move=max((points[i]-originals[i]).length for i in op['pinnedVertices'])
    original_quad=bpy.data.objects[prior.prior.RESULT_OBJECT]
    total_move=max((point-original_quad.matrix_world@v.co).length for point,v in zip(points,original_quad.data.vertices))
    if [f.material_index for f in obj.data.polygons]!=[f.material_index for f in source.data.polygons]:raise ValueError('REGIONS_CHANGED')
    _,_,_,features=prior.topology(source)
    if features!=op['features']:raise ValueError('PROTECTED_FEATURE_RECORD_CHANGED')
    edges=edge_faces(faces);old_edges=edge_faces(old_faces)
    protected={tuple(e) for group in features.values() for e in group}
    required_major={fi for edge in features['majorCreaseEdges'] for fi in old_edges[tuple(edge)]}
    required_locked=required_major|GEOMETRY_GUARD_FACES
    if not required_locked<=set(op['lockedFaceIndices']):raise ValueError('MAJOR_FOLD_LOCKS_CHANGED')
    if not protected<=set(edges):raise ValueError('PROTECTED_FEATURE_EDGE_REMOVED')
    if {e for e,fs in edges.items() if len(fs)==1}!={e for e,fs in old_edges.items() if len(fs)==1}:raise ValueError('OPEN_BORDER_CHANGED')
    if any(faces[fi]!=old_faces[fi] for fi in op['lockedFaceIndices']):raise ValueError('MAJOR_FOLD_FACE_CHANGED')
    # Every edit must be a replayable two-quad disk with the same perimeter.
    replay=list(old_faces)
    for record in op['rotations']:
        a,b=record['faceIndices'];old=(replay[a],replay[b]);new=tuple(tuple(f) for f in record['newFaces'])
        if [list(f) for f in old]!=record['oldFaces'] or new not in alternatives(*old):raise ValueError('INVALID_ROTATION_PROVENANCE')
        removed=next(e for e,fs in edge_faces(old).items() if len(fs)==2)
        added=next(e for e,fs in edge_faces(new).items() if len(fs)==2)
        if list(removed)!=record['removedEdge'] or list(added)!=record['addedEdge']:raise ValueError('ROTATION_EDGE_RECORD_CHANGED')
        if removed in protected or {a,b}&set(op['lockedFaceIndices']) or source.data.polygons[a].material_index!=source.data.polygons[b].material_index:raise ValueError('ROTATION_CROSSES_FEATURE_LOCK')
        replay[a],replay[b]=new
    if replay!=faces:raise ValueError('ROTATION_REPLAY_MISMATCH')
    topology=prior.prior.prior.s.prior.prior.boundaries(obj)
    pairs,triangles=prior.collision_pairs(obj);tree=c.fit.bvh(obj)[0]
    chart=bpy.data.objects[prior.prior.prior.RESULT_OBJECT];chart_tree,chart_points,chart_tris=c.fit.bvh(chart)
    samples=[(p,None) for p in points]
    samples.extend((sum((points[i] for i in t.vertices),Vector())/3,t.polygon_index) for t in obj.data.loop_triangles)
    samples.extend(((points[a]+points[b])/2,edges[tuple(sorted((a,b)))][0]) for a,b in edges)
    forward=[chart_tree.find_nearest(p)[3] for p,_ in samples]
    reverse_samples=chart_points+[sum((chart_points[i] for i in t),Vector())/3 for t in chart_tris]
    reverse_hits=[tree.find_nearest(p) for p in reverse_samples]
    reverse=[hit[3] for hit in reverse_hits]
    failed_faces={obj.data.loop_triangles[t].polygon_index for pair in pairs for t in pair}
    failed_faces.update(fi for (_,fi),distance in zip(samples,forward) if fi is not None and distance>MAX_SURFACE_ERROR)
    failed_faces.update(obj.data.loop_triangles[hit[2]].polygon_index for hit in reverse_hits if hit[3]>MAX_SURFACE_ERROR)
    bm=bmesh.new();bm.from_mesh(obj.data);orient=sum(e.is_manifold and not e.is_contiguous for e in bm.edges);bm.free()
    border={i for e in features['borderEdges'] for i in e}
    before=valence(degree_map(old_edges,len(points)),border);after=valence(degree_map(edges,len(points)),border)
    if op['beforeValence']!=before or op['afterValence']!=after:raise ValueError('VALENCE_RECORD_CHANGED')
    before_bending=prior.bending(source,{});after_bending=prior.bending(obj,{})
    qa=dict(vertices=len(points),quads=len(faces),rotations=len(op['rotations']),changedFaces=sum(a!=b for a,b in zip(faces,old_faces)),
            maximumSourceVertexMoveMeters=move,maximumPinnedVertexMoveMeters=pinned_move,
            maximumCumulativeQuadVertexMoveMeters=total_move,
            movedStudyVertices=sum((a-b).length>1e-8 for a,b in zip(points,originals)),
            beforeValence=before,afterValence=after,
            beforeBending=before_bending,afterBending=after_bending,
            preservedSharedBranchEdges=len(features['sharedSeamEdges']),preservedMajorCreaseEdges=len(features['majorCreaseEdges']),
            lockedMajorFoldFaces=len(required_major),additionalBlockedFaces=len(op['lockedFaceIndices'])-len(required_major),
            pinnedStudyVertices=len(op['pinnedVertices']),nonAdjacentSelfIntersectionPairs=len(pairs),
            nonContiguousInteriorEdges=orient,zeroAreaFaces=topology['zeroAreaFaces'],
            maximumForwardSampleErrorMeters=max(forward),maximumReverseSampleErrorMeters=max(reverse),
            forwardSampleCount=len(samples),reverseSampleCount=len(reverse_samples),
            connectedComponents=len(topology['components']),boundaryLoops=len(topology['boundaryLoops']),euler=topology['euler'],
            majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False,originalBodyMovedVertices=0,
            failedFaces=sorted(failed_faces))
    qa['eligible']=move<=MAX_NEW_MOVE+1e-7 and total_move<=MAX_TOTAL_MOVE+1e-7 and pinned_move<1e-8 and qa['rotations']>0 and all(len(f)==4 for f in faces) and after['squaredValenceError']<before['squaredValenceError'] and after['irregularInteriorVertices']<before['irregularInteriorVertices'] and after_bending['weightedRadiansSquaredMeters']<=before_bending['weightedRadiansSquaredMeters']+1e-5 and not pairs and orient==0 and topology['zeroAreaFaces']==0 and qa['connectedComponents']==1 and qa['boundaryLoops']==2 and qa['euler']==0 and max(forward+reverse)<=MAX_SURFACE_ERROR
    return qa


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if c.base.sha(source.parent/'crease-fairing-report.json')!=REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals};visible=[o for o in originals if not o.hide_get()]
    old=bpy.data.objects[prior.RESULT_OBJECT];blocked=set();attempts=[]
    for attempt in range(4):
        obj,op=build(old,blocked);qa=audit(obj,old,op);attempts.append(dict(attempt=attempt,qa=qa))
        print(json.dumps(qa),flush=True)
        if qa['eligible']:break
        blocked.update(qa['failedFaces']);bpy.data.objects.remove(obj,do_unlink=True)
        if not qa['failedFaces']:raise ValueError('EDGE_FLOW_QA_REJECTED:'+json.dumps(qa))
    else:raise ValueError('EDGE_FLOW_RETRIES_EXHAUSTED')
    output.mkdir(parents=True);renders=[]
    if not args.no_render:
        for label,item in [('before',old),('after',obj)]:
            folder=output/label;folder.mkdir();rows=prior.prior.prior.render(folder,item,[])
            renders.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in rows)
        wire=prior.prior.prior.curve('EdgeFlowWireReview',[Vector(),Vector((.001,0,0))],'FFFFFF')
        wire.data.splines.clear();wire.data.bevel_depth=.000075;wire.data.bevel_resolution=1
        for edge in obj.data.edges:
            spline=wire.data.splines.new('POLY');spline.points.add(1)
            for p,i in zip(spline.points,edge.vertices):p.co=(*obj.data.vertices[i].co,1)
        folder=output/'wire';folder.mkdir();rows=prior.prior.prior.render(folder,obj,[wire])
        renders.extend(dict(file='wire/'+r['file'],sha256=r['sha256']) for r in rows)
        bpy.data.objects.remove(wire,do_unlink=True)
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):raise ValueError('ORIGINAL_CHANGED')
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in visible
    obj.hide_set(True);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_FeatureLockedShoulderEdgeFlow_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='LOCAL_EDGE_FLOW_TOPOLOGY_PASS_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                runtime=dict(blenderVersion=bpy.app.version_string,device='CPU'),operation=op,qa=qa,attempts=attempts,
                originalsPreserved=True,adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['LOCAL_VALENCE_RECONNECTION_NOT_COMPLETE_DEFORMATION_EDGE_FLOW','MAJOR_FOLD_SHAPE_AND_PROVISIONAL_TORSO_BORDER_UNCHANGED',
                             'OPEN_UNOFFSET_SURFACE_NO_GARMENT_QA','FINITE_SOURCE_ERROR_SAMPLES','NO_NEW_UV_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'edge-flow-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 feature-locked quad reconnection — NOT PRODUCTION\nActual quad edges change; bounded geometric correction keeps pinned boundaries and major fold faces fixed.\nThe original chart remains the 1.5 mm cumulative surface reference. Body meshes remain untouched.\nThis is not major-fold redesign, full deformation-ready retopology, a sewn garment, a rig or a new full-character score.\nPrevious assembly stays visible; the new study is hidden. Gate B pending; Unity/production disabled.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
