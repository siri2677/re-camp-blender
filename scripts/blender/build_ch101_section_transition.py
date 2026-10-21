"""Split arm section loops from open torso paths before building a local bridge.

This is a bounded shoulder-entry panel, not replacement of the entire rejected
shoulder sheet. No ray is cast through the whole body to select a farther torso.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
import author_ch101_connected_shoulder as prior
c,surface,panel=prior.c,prior.surface,prior.panel
interface=prior.interface_module
SOURCE_SHA='4436c48177612dd0de663eb3d5b1522211848b5265de55b873a7ab186b1f019e'
SOURCE_REPORT_SHA='c5a908aca8c0739160093e2b00072d056497483772029b9b1475a4c059397461'
RESULT_OBJECT='CH101_SectionGuidedShoulderEntry_NOT_PRODUCTION'
STRATEGY='CH101_SECTION_GUIDED_SHOULDER_ENTRY_V001'
N,ROWS=prior.N,prior.ROWS
SPAN=.012
RAY_CLEARANCE=.002
ADDITIONAL_CLEARANCE=.0015
CLEARANCE_TRANSITION_SPAN=.002
WALL=prior.WALL
MAX_NEW_OFFSET=prior.MAX_NEW_OFFSET


def idx(layer,row,k):
    return interface.idx(layer,interface.M-1,k) if row==0 else 2*interface.VERTS_PER_LAYER+layer*ROWS*N+(row-1)*N+k


def signed_height(point,frame):
    center,axis,u=frame
    return (point-center).dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*(point-center).dot(u)-prior.prior.SEAM_Q


def section_paths(chart,frame,height):
    """Use shared source EDGE IDs, not rounded positions, for cut connectivity."""
    if not math.isfinite(height) or not 0<height<=SPAN:raise ValueError('SECTION_HEIGHT_OUTSIDE_SCOPE')
    chart.data.calc_loop_triangles();points=[chart.matrix_world@v.co for v in chart.data.vertices]
    signed=[signed_height(p,frame)-height for p in points]
    adjacency=defaultdict(set);lookup={};vertices=[];provenance=[]
    for tri in chart.data.loop_triangles:
        cuts=[];ids=list(tri.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):
            da,db=signed[a],signed[b]
            if abs(da)<1e-12:key=('v',a);point=points[a];record=dict(sourceEdge=[a,a],edgeT=0)
            elif da*db<0:
                a,b=sorted((a,b));da,db=signed[a],signed[b];t=da/(da-db)
                key=('e',a,b);point=points[a].lerp(points[b],t);record=dict(sourceEdge=[a,b],edgeT=t)
            else:continue
            if key not in lookup:lookup[key]=len(vertices);vertices.append(point);provenance.append(record)
            if lookup[key] not in cuts:cuts.append(lookup[key])
        if len(cuts)==2:
            a,b=cuts;adjacency[a].add(b);adjacency[b].add(a)
        elif len(cuts)>2:raise ValueError('COPLANAR_SECTION_TRIANGLE')
    if any(len(ns)>2 for ns in adjacency.values()):raise ValueError('BRANCHED_SECTION')
    remaining=set(adjacency);paths=[]
    while remaining:
        seed=min(remaining);component=set();stack=[seed]
        while stack:
            i=stack.pop()
            if i in component:continue
            component.add(i);stack.extend(adjacency[i]-component)
        remaining-=component;ends=sorted(i for i in component if len(adjacency[i])==1)
        if len(ends) not in (0,2):raise ValueError('INVALID_SECTION_ENDPOINTS')
        start=ends[0] if ends else min(component);order=[start];previous=None;current=start
        while True:
            following=sorted(i for i in adjacency[current] if i!=previous)
            if not following or following[0]==start:break
            nxt=following[0]
            if nxt in order:raise ValueError('NONSIMPLE_SECTION')
            order.append(nxt);previous,current=current,nxt
        if set(order)!=component:raise ValueError('SECTION_TRAVERSAL_INCOMPLETE')
        paths.append(dict(indices=order,closed=not ends))
    return vertices,paths,provenance


def angular_hit(vertices,loop,frame,k):
    center,axis,u=frame;v=axis.cross(u);angle=math.tau*k/N;direction=(math.cos(angle),math.sin(angle));hits=[]
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    for a,b in zip(loop,loop[1:]+loop[:1]):
        da,db=vertices[a]-center,vertices[b]-center;p=(da.dot(u),da.dot(v));delta=(db.dot(u)-p[0],db.dot(v)-p[1]);den=cross(direction,delta)
        if abs(den)<1e-12:continue
        radius=cross(p,delta)/den;t=cross(p,direction)/den
        if radius>0 and -1e-7<=t<=1+1e-7:
            point=vertices[a].lerp(vertices[b],max(0,min(1,t)))
            if not any((point-row[0]).length<1e-7 for row in hits):hits.append((point,a,b,max(0,min(1,t))))
    if len(hits)!=1:raise ValueError('SECTION_NOT_SINGLE_VALUED:'+str(k))
    return hits[0]


def triangulate_strip_quad(quad,vertices,body_tree):
    """Resolve non-planar quads explicitly; avoid arbitrary Blender diagonals."""
    local=[vertices[i] for i in quad]
    options=[((0,1,2),(0,2,3)),((0,1,3),(1,2,3))]
    scores=[]
    for triangles in options:
        tree=BVHTree.FromPolygons(local,triangles,all_triangles=True)
        samples=[sum((local[i] for i in tri),Vector())/3 for tri in triangles]
        diagonal=sorted(set(triangles[0])&set(triangles[1]))
        samples.append((local[diagonal[0]]+local[diagonal[1]])/2)
        scores.append((-len(tree.overlap(body_tree)),min(body_tree.find_nearest(p)[3] for p in samples)))
    selected=max(range(2),key=lambda i:scores[i])
    return [tuple(quad[i] for i in tri) for tri in options[selected]],selected


def build(source,chart,frame,body):
    for subject in (source,chart,body):surface.require_locked(subject)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('SECTION_TRANSITION_ALREADY_EXISTS')
    center,axis,u=frame;v=axis.cross(u)
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_SECTION_FRAME')
    if len(source.data.vertices)!=2*interface.VERTS_PER_LAYER:raise ValueError('UNEXPECTED_SOURCE_INTERFACE')
    vertices=[source.matrix_world@p.co for p in source.data.vertices];new=[[],[]];sections=[];max_offset=0
    for row in range(1,ROWS+1):
        height=SPAN*row/ROWS;points,paths,provenance=section_paths(chart,frame,height)
        candidates=[]
        for path in paths:
            if not path['closed']:continue
            try:hits=[angular_hit(points,path['indices'],frame,k) for k in range(N)]
            except ValueError:continue
            candidates.append((path,hits))
        if len(candidates)!=1:raise ValueError('NO_UNIQUE_CLOSED_ARM_SECTION:'+str(row))
        path,hits=candidates[0];records=[]
        for k,(hit,a,b,t) in enumerate(hits):
            d=hit-center;radius=math.hypot(d.dot(u),d.dot(v))
            if not (.02<radius<.08 and -.28<hit.x<-.1 and -.11<hit.y<.11 and 1.07<hit.z<1.26):
                raise ValueError('SECTION_OUTSIDE_LOCAL_ARM')
            angle=math.tau*k/N;direction=(u*math.cos(angle)+v*math.sin(angle)+axis*panel.HEM_SLOPE*math.cos(angle)).normalized()
            blend=min(1,height/CLEARANCE_TRANSITION_SPAN);blend=blend*blend*(3-2*blend)
            clearance=RAY_CLEARANCE+ADDITIONAL_CLEARANCE*blend
            for layer in (0,1):
                point=hit+direction*(clearance+WALL*layer);new[layer].append(point)
                max_offset=max(max_offset,(point-hit).length)
            records.append(dict(angleIndex=k,sectionEdge=[a,b],edgeT=t,sourcePoint=list(hit),innerRayClearanceMeters=clearance))
        sections.append(dict(row=row,heightMeters=height,closedPathCount=sum(p['closed'] for p in paths),
                             excludedOpenPaths=[p['indices'] for p in paths if not p['closed']],
                             selectedLoop=path['indices'],points=[list(p) for p in points],sourceEdgeProvenance=provenance,samples=records))
    vertices+=new[0]+new[1]
    seam=set(idx(layer,0,k) for layer in (0,1) for k in range(N));faces=[];materials=[];removed=0
    for f in source.data.polygons:
        if set(f.vertices)<=seam:removed+=1;continue
        faces.append(tuple(f.vertices));materials.append(f.material_index)
    if removed!=N:raise ValueError('SEAM_CAP_REMOVAL_MISMATCH')
    body_tree=c.fit.bvh(body)[0];diagonal_counts=[0,0]
    for layer in (0,1):
        for row in range(ROWS):
            for k in range(N):
                quad=tuple(idx(layer,r,j%N) for r,j in ((row,k),(row,k+1),(row+1,k+1),(row+1,k)))
                triangles,diagonal=triangulate_strip_quad(quad,vertices,body_tree)
                faces.extend(triangles);materials.extend((0,0));diagonal_counts[diagonal]+=1
    for k in range(N):faces.append(tuple(idx(layer,ROWS,j%N) for layer,j in ((0,k),(0,k+1),(1,k+1),(1,k))));materials.append(0)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for mat in source.data.materials:mesh.materials.append(mat)
    for f,m in zip(mesh.polygons,materials):f.material_index=m;f.use_smooth=True
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    obj['rigBound']=False;obj['adoptionAllowed']=False;obj['joinedToSourceBodyTopology']=False
    op=dict(sourceVerticesRetained=len(source.data.vertices),sourceVertexMoveMeters=0,sections=sections,constraintFailures=[],
            spanMeters=SPAN,rayDirectionClearanceRangeMeters=[RAY_CLEARANCE,RAY_CLEARANCE+ADDITIONAL_CLEARANCE],rayDirectionWallMeters=WALL,
            clearanceTransitionSpanMeters=CLEARANCE_TRANSITION_SPAN,
            explicitSkinDiagonalCounts=diagonal_counts,
            maximumNewSourceOffsetMeters=max_offset,newOffsetLimitMeters=MAX_NEW_OFFSET,
            completeShoulderPanel=False,originalCumulativeDisplacementBudgetReset=False,newPanelUVAuthored=False,
            scope='LOCAL_CLOSED_ARM_SECTIONS_ONLY_OPEN_TORSO_PATHS_EXCLUDED')
    if max_offset>MAX_NEW_OFFSET:raise ValueError('NEW_PANEL_OFFSET_BUDGET_REJECTED')
    return obj,op


def audit(obj,body,parts,operation,frame):
    index={(l,r,k):idx(l,r,k) for l in (0,1) for r in range(ROWS+1) for k in range(N)}
    qa=prior.audit(obj,body,parts,operation,index)
    errors=[abs(signed_height(obj.matrix_world@obj.data.vertices[idx(l,r,k)].co,frame)-SPAN*r/ROWS)
            for l in (0,1) for r in range(ROWS+1) for k in range(N)]
    qa['maximumSectionPlaneErrorMeters']=max(errors)
    chart=bpy.data.objects[prior.prior.RESULT_OBJECT];reconstruction_error=0;offsets=[]
    if len(operation['sections'])!=ROWS:raise ValueError('SECTION_REPORT_COUNT_MISMATCH')
    for row,record in enumerate(operation['sections'],1):
        height=SPAN*row/ROWS;points,paths,_=section_paths(chart,frame,height)
        if record['row']!=row or abs(record['heightMeters']-height)>1e-12:raise ValueError('SECTION_REPORT_HEIGHT_MISMATCH')
        if not any(p['closed'] and p['indices']==record['selectedLoop'] for p in paths):raise ValueError('SECTION_REPORT_LOOP_MISMATCH')
        if record['excludedOpenPaths']!=[p['indices'] for p in paths if not p['closed']]:raise ValueError('SECTION_REPORT_OPEN_PATHS_MISMATCH')
        if len(record['samples'])!=N:raise ValueError('SECTION_SAMPLE_COUNT_MISMATCH')
        for k,sample in enumerate(record['samples']):
            hit,a,b,t=angular_hit(points,record['selectedLoop'],frame,k)
            if sample['angleIndex']!=k or sample['sectionEdge']!=[a,b] or abs(sample['edgeT']-t)>1e-8 or (Vector(sample['sourcePoint'])-hit).length>1e-7:
                raise ValueError('SECTION_SAMPLE_PROVENANCE_MISMATCH')
            blend=min(1,height/CLEARANCE_TRANSITION_SPAN);blend=blend*blend*(3-2*blend)
            clearance=RAY_CLEARANCE+ADDITIONAL_CLEARANCE*blend
            _,axis,u=frame;v=axis.cross(u);angle=math.tau*k/N
            direction=(u*math.cos(angle)+v*math.sin(angle)+axis*panel.HEM_SLOPE*math.cos(angle)).normalized()
            for layer in (0,1):
                point=obj.matrix_world@obj.data.vertices[idx(layer,row,k)].co
                reconstruction_error=max(reconstruction_error,(point-(hit+direction*(clearance+WALL*layer))).length)
                offsets.append((point-hit).length)
    qa.update(maximumSourceReconstructionErrorMeters=reconstruction_error,measuredNewSourceOffsetRangeMeters=[min(offsets),max(offsets)],
              sourceSleeveRetainedVertexCount=2*interface.VERTS_PER_LAYER,completeShoulderPanel=False)
    qa['eligible']=qa['eligible'] and max(errors)<1e-6 and reconstruction_error<1e-6 and max(offsets)<MAX_NEW_OFFSET
    return qa


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    metadata=source.parent/'connected-shoulder-report.json'
    if c.base.sha(metadata)!=SOURCE_REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT];old=bpy.data.objects[interface.RESULT_OBJECT]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,op=build(old,bpy.data.objects[prior.prior.RESULT_OBJECT],frame,body)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=audit(obj,body,parts+[bpy.data.objects[interface.prior.prior.prior.RESULT_OBJECT]],op,frame)
    print(json.dumps({k:v for k,v in qa.items() if not k.startswith('diagnostic')},indent=2))
    if not qa['eligible']:raise ValueError('SECTION_TRANSITION_QA_REJECTED')
    output.mkdir(parents=True)
    renders=[] if args.no_render else interface.render(output,old,obj,body,parts,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=signatures[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[old])
    for o in bpy.context.scene.objects:
        if o.type in ('MESH','CURVE'):o.hide_render=o not in [body]+parts+[old]
    obj.hide_set(True);obj['staticQAEligible']=True;obj['completeShoulderPanel']=False
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_SectionGuidedShoulderEntry_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='LOCAL_SECTION_TRANSITION_STATIC_PASS_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=SOURCE_REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                runtime=dict(blenderVersion=bpy.app.version_string,buildHash=bpy.app.build_hash.decode(),device='CPU'),
                operation=op,qa=qa,originalsPreserved=True,adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,
                fullCharacterScore=None,defaultVisibleMeshObjects=visible,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['ONLY_12MM_ARM_ENTRY_NOT_COMPLETE_SHOULDER_OR_TORSO_PATTERN','OPEN_TORSO_PATHS_INTENTIONALLY_EXCLUDED',
                             'UPPER_END_WALL_NOT_SEWN_TO_BODY','NO_UV_BAKE_STRAP_OR_RIG','FINITE_STATIC_SAMPLES_NOT_ANIMATION_CLEARANCE',
                             'NEW_PANEL_HIGH_DENSITY_NOT_RUNTIME_OPTIMIZED','NO_HUMAN_GATE_B'])
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    (output/'section-transition-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 12 mm section-guided shoulder ENTRY — NOT PRODUCTION\nStatic QA passed only for this bounded local arm-entry panel. This is NOT the complete previously rejected shoulder sheet.\nOpen torso section paths are intentionally excluded; no full-scope before/after quality claim.\nOriginal meshes and source sleeve vertices remain unchanged; old assembly stays visible, new study stays hidden.\nNo torso sewing, UV/straps, rig, full-character score, Unity input or human Gate B approval.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
