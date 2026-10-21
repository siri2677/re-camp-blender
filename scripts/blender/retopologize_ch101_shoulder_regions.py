"""Shared quad cage preserving the pinned source edges and panel regions.

Open, unoffset retopology study only: no thickness, garment clearance or sewing.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import design_ch101_shoulder_branches as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='341074e648341a27c51290e0a29650b1297604506eb2defeec9f5010bf04577e'
REPORT_SHA='487c101ee45d6884d9d959e431fcbf02334191fba65ceccb3bb3bc357110698f'
RESULT_OBJECT='CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION'
STRATEGY='CH101_FEATURE_PRESERVING_SHARED_QUAD_CAGE_V001'
U,V=24,40
MAX_SURFACE_ERROR=.0015


def region_sides(source, faces, design, lower):
    counts=defaultdict(int)
    for fi in faces:
        ids=list(source.data.polygons[fi].vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):counts[tuple(sorted((a,b)))]+=1
    boundary={edge for edge,count in counts.items() if count==1}
    names=[name for name,path in design['paths'].items()
           if all(tuple(sorted(e)) in boundary for e in zip(path,path[1:]))]
    if len(names)!=2:raise ValueError('REGION_MUST_HAVE_TWO_BRANCHES')
    a,b=names;pa,pb=design['paths'][a],design['paths'][b]
    adjacency=defaultdict(list)
    for i,j in boundary:adjacency[i].append(j);adjacency[j].append(i)
    if any(len(ns)!=2 for ns in adjacency.values()):raise ValueError('REGION_BOUNDARY_NOT_SIMPLE')
    order=[pa[0]];previous=pa[1];current=pa[0]
    while True:
        nxt=next(i for i in adjacency[current] if i!=previous)
        if nxt==order[0]:break
        if nxt in order:raise ValueError('REPEATED_BOUNDARY_VERTEX')
        order.append(nxt);previous,current=current,nxt
    if set(order)!=set(adjacency):raise ValueError('REGION_HAS_MULTIPLE_LOOPS')
    corners=[pa[0],pb[0],pb[-1],pa[-1]]
    positions=[order.index(i) for i in corners]
    if positions!=sorted(positions):raise ValueError('WRONG_REGION_CORNER_ORDER')
    bottom=order[:positions[1]+1]
    right=order[positions[1]:positions[2]+1]
    top=list(reversed(order[positions[2]:positions[3]+1]))
    left=[pa[0]]+list(reversed(order[positions[3]:]))
    if not set(bottom)<=set(lower) or left!=pa or right!=pb:raise ValueError('BRANCH_SIDE_MISMATCH')
    return (bottom,right,top,left),(a,b)


def fractions(points, path):
    lengths=[(points[b]-points[a]).length for a,b in zip(path,path[1:])]
    if not lengths or min(lengths)<1e-10:raise ValueError('DEGENERATE_BOUNDARY_EDGE')
    result=[0]
    for length in lengths:result.append(result[-1]+length)
    return [value/result[-1] for value in result]


def interpolate(values, path, ts, t):
    j=min(len(path)-2,max(0,int(np.searchsorted(ts,t,side='right'))-1))
    f=(t-ts[j])/(ts[j+1]-ts[j])
    return values[path[j]]*(1-f)+values[path[j+1]]*f


def parameterize(source, faces, sides):
    points=[source.matrix_world@p.co for p in source.data.vertices]
    ids=sorted({i for f in faces for i in source.data.polygons[f].vertices})
    coords={};side_fractions=[fractions(points,path) for path in sides]
    # Each side gets a quarter circle. Convex arcs avoid collapsing bent source
    # boundary triangles onto a straight square edge in the parameter domain.
    for side,(path,ts) in enumerate(zip(sides,side_fractions)):
        for i,t in zip(path,ts):
            angle=[-3*math.pi/4+math.pi/2*t,-math.pi/4+math.pi/2*t,
                   3*math.pi/4-math.pi/2*t,-3*math.pi/4-math.pi/2*t][side]
            coords[i]=np.array([math.cos(angle),math.sin(angle)])
    adjacency=defaultdict(set)
    triangles=[tuple(source.data.polygons[f].vertices) for f in faces]
    for tri in triangles:
        if len(tri)!=3:raise ValueError('SOURCE_NOT_TRIANGULATED')
        for a,b in zip(tri,tri[1:]+tri[:1]):adjacency[a].add(b);adjacency[b].add(a)
    unknown=[i for i in ids if i not in coords];lookup={i:j for j,i in enumerate(unknown)}
    matrix=np.zeros((len(unknown),len(unknown)));rhs=np.zeros((len(unknown),2))
    for i in unknown:
        row=lookup[i];matrix[row,row]=len(adjacency[i])
        for j in adjacency[i]:
            if j in lookup:matrix[row,lookup[j]]-=1
            else:rhs[row]+=coords[j]
    solution=np.linalg.solve(matrix,rhs)
    coords.update({i:solution[j] for i,j in lookup.items()})
    areas=[float(np.linalg.det(np.array([coords[b]-coords[a],coords[d]-coords[a]]))) for a,b,d in triangles]
    if min(abs(a) for a in areas)<1e-12 or not(all(a>0 for a in areas) or all(a<0 for a in areas)):
        raise ValueError('REGION_PARAMETER_FOLD')
    return points,coords,triangles,side_fractions,min(abs(a) for a in areas)


def build_structured_trial(source, report):
    surface.require_locked(source)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('STRUCTURED_PATCHES_ALREADY_EXIST')
    allpoints=[];allfaces=[];materials=[];lookup={};records=[];patches=[]
    for region,source_faces in enumerate(report['design']['faceRegions']):
        sides,names=region_sides(source,source_faces,report['design'],report['operation']['lowerLoop'])
        points,coords,triangles,ts,minarea=parameterize(source,source_faces,sides)
        inverses=np.array([np.linalg.inv(np.column_stack((coords[b]-coords[a],coords[d]-coords[a]))) for a,b,d in triangles])
        origins=np.array([coords[t[0]] for t in triangles])
        corners=[coords[sides[0][0]],coords[sides[0][-1]],coords[sides[2][-1]],coords[sides[2][0]]]
        grid=[];parameter_grid=[]
        for j in range(V+1):
            row=[];parameter_row=[]
            for i in range(U+1):
                u,v=i/U,j/V
                bottom=interpolate(coords,sides[0],ts[0],u);top=interpolate(coords,sides[2],ts[2],u)
                left=interpolate(coords,sides[3],ts[3],v);right=interpolate(coords,sides[1],ts[1],v)
                uv=(1-v)*bottom+v*top+(1-u)*left+u*right-((1-u)*(1-v)*corners[0]+u*(1-v)*corners[1]+u*v*corners[2]+(1-u)*v*corners[3])
                bary2=np.einsum('ijk,ik->ij',inverses,uv-origins)
                weights=np.column_stack((1-bary2.sum(axis=1),bary2))
                candidates=np.flatnonzero(weights.min(axis=1)>=-1e-7)
                if not len(candidates):raise ValueError('GRID_OUTSIDE_SOURCE_REGION')
                tri_index=int(candidates[0]);w=weights[tri_index];tri=triangles[tri_index]
                point=sum((points[k]*float(t) for k,t in zip(tri,w)),Vector())
                if i in (0,U) and j in (0,V):key=('corner',sides[0 if j==0 else 2][0 if i==0 else -1])
                elif i==0:key=('branch',names[0],j)
                elif i==U:key=('branch',names[1],j)
                else:key=('region',region,i,j)
                if key in lookup:
                    index=lookup[key]
                    if (allpoints[index]-point).length>1e-6:raise ValueError('SHARED_BRANCH_POSITION_MISMATCH')
                else:
                    index=len(allpoints);lookup[key]=index;allpoints.append(point)
                    records.append(dict(sourceVertices=list(tri),weights=[float(t) for t in w],sourceFace=source_faces[tri_index]))
                row.append(index)
                parameter_row.append(uv)
            grid.append(row)
            parameter_grid.append(parameter_row)
        parameter_areas=[]
        for j in range(V):
            for i in range(U):
                p=[parameter_grid[y][x] for x,y in ((i,j),(i+1,j),(i+1,j+1),(i,j+1))]
                for a,b,d in ((p[0],p[1],p[2]),(p[0],p[2],p[3])):
                    parameter_areas.append(float(np.linalg.det(np.array([b-a,d-a]))))
        print('PATCH_PARAMETER',region,min(parameter_areas),sum(a<=0 for a in parameter_areas),flush=True)
        if min(parameter_areas)<=0:raise ValueError('PATCH_GRID_PARAMETER_FOLD')
        for j in range(V):
            for i in range(U):
                face=(grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i])
                # Orient all patches consistently with their source, independently
                # of which branch was first in the region boundary traversal.
                if (coords[triangles[0][1]]-coords[triangles[0][0]])[0]*(coords[triangles[0][2]]-coords[triangles[0][0]])[1]-(coords[triangles[0][1]]-coords[triangles[0][0]])[1]*(coords[triangles[0][2]]-coords[triangles[0][0]])[0]<0:face=tuple(reversed(face))
                allfaces.append(face);materials.append(region)
        patches.append(dict(region=region,branches=list(names),grid=grid,minimumParameterTriangleArea=minarea))
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(allpoints,[],allfaces);mesh.update()
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    for mat in source.data.materials:mesh.materials.append(mat)
    for f,r in zip(mesh.polygons,materials):f.material_index=r;f.use_smooth=False
    obj['adoptionAllowed']=False;obj['rigBound']=False;obj['openUnsewnSurface']=True
    return obj,dict(method='STRUCTURED_GRID_REJECTED_TRIAL',patches=patches,vertexProvenance=records,gridU=U,gridV=V,
                    surfaceErrorLimitMeters=MAX_SURFACE_ERROR,sourceVerticesMoved=0,garmentStaticQA=False)


def build(source, report):
    """Each source triangle becomes three coplanar quads; edge IDs stay shared."""
    surface.require_locked(source)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('QUAD_CAGE_ALREADY_EXISTS')
    groups=report['design']['faceRegions']
    if len(groups)!=4 or sorted(i for group in groups for i in group)!=list(range(len(source.data.polygons))):
        raise ValueError('INVALID_SOURCE_REGION_PARTITION')
    points=[source.matrix_world@v.co for v in source.data.vertices]
    vertices=[];records=[];lookup={};faces=[];regions=[];face_sources=[]
    def vertex(key, tri, weights, fi):
        point=sum((points[i]*w for i,w in zip(tri,weights)),Vector())
        if key not in lookup:
            lookup[key]=len(vertices);vertices.append(point)
            records.append(dict(sourceVertices=list(tri),weights=list(weights),sourceFace=fi))
        elif (vertices[lookup[key]]-point).length>1e-7:raise ValueError('SHARED_FEATURE_POSITION_MISMATCH')
        return lookup[key]
    for region,group in enumerate(groups):
        for fi in group:
            tri=tuple(source.data.polygons[fi].vertices)
            if len(tri)!=3:raise ValueError('SOURCE_NOT_TRIANGULATED')
            corners=[vertex(('v',i),tri,tuple(float(j==k) for j in range(3)),fi) for k,i in enumerate(tri)]
            mids=[]
            for k in range(3):
                ids=tuple(sorted((tri[k],tri[(k+1)%3])))
                mids.append(vertex(('e',*ids),tri,tuple(.5 if j in (k,(k+1)%3) else 0 for j in range(3)),fi))
            center=vertex(('f',fi),tri,(1/3,1/3,1/3),fi)
            for k in range(3):
                faces.append((corners[k],mids[k],center,mids[(k-1)%3]))
                regions.append(region);face_sources.append(fi)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    for mat in source.data.materials:mesh.materials.append(mat)
    for f,region in zip(mesh.polygons,regions):f.material_index=region;f.use_smooth=False
    obj['adoptionAllowed']=False;obj['rigBound']=False;obj['openUnsewnSurface']=True
    paths={}
    for name,path in report['design']['paths'].items():
        ordered=[]
        for a,b in zip(path,path[1:]):
            ordered.extend((lookup[('v',a)],lookup[('e',*sorted((a,b)))]))
        ordered.append(lookup[('v',path[-1])]);paths[name]=ordered
    return obj,dict(method='SOURCE_FEATURE_CONFORMING_QUADS',vertexProvenance=records,
                    faceSourceTriangles=face_sources,sourceRegionFaces=groups,sharedBranchPaths=paths,
                    originalCornerVertexMap={str(i):lookup[('v',i)] for i in range(len(points))},
                    sourceEdgeMidpointMap=[dict(sourceEdge=list(e.vertices),newVertex=lookup[('e',*sorted(e.vertices))]) for e in source.data.edges],
                    surfaceErrorLimitMeters=MAX_SURFACE_ERROR,sourceVerticesMoved=0,garmentStaticQA=False)


def audit(obj, source, operation):
    surface.require_locked(obj);surface.require_locked(source)
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    source_points=[source.matrix_world@v.co for v in source.data.vertices]
    if len(operation['vertexProvenance'])!=len(points):raise ValueError('PROVENANCE_COUNT_MISMATCH')
    errors=[]
    for point,r in zip(points,operation['vertexProvenance']):
        if min(r['weights'])< -1e-7 or abs(sum(r['weights'])-1)>1e-6:raise ValueError('INVALID_BARYCENTRIC')
        expected=sum((source_points[i]*w for i,w in zip(r['sourceVertices'],r['weights'])),Vector())
        errors.append((point-expected).length)
    topology=prior.s.prior.prior.boundaries(obj)
    bm=bmesh.new();bm.from_mesh(obj.data)
    orientation_errors=sum(e.is_manifold and not e.is_contiguous for e in bm.edges)
    valence_counts=defaultdict(int)
    for vertex in bm.verts:valence_counts[len(vertex.link_edges)]+=1
    bm.free()
    tree,_,triangles=c.fit.bvh(obj);source_tree,_,source_tris=c.fit.bvh(source)
    crossings=len({(a,b) for a,b in tree.overlap(tree) if a<b and not set(triangles[a])&set(triangles[b])})
    samples=points+[sum((points[i] for i in t),Vector())/3 for t in triangles]
    samples +=[(points[e.vertices[0]]+points[e.vertices[1]])/2 for e in obj.data.edges]
    forward=[source_tree.find_nearest(p)[3] for p in samples]
    reverse_samples=source_points+[sum((source_points[i] for i in t),Vector())/3 for t in source_tris]
    reverse=[tree.find_nearest(p)[3] for p in reverse_samples]
    edge_faces=defaultdict(list)
    for face in obj.data.polygons:
        ids=list(face.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):edge_faces[tuple(sorted((a,b)))].append(face.material_index)
    seam=[(e,fs) for e,fs in edge_faces.items() if len(set(fs))>1]
    regions=[sum(f.material_index==r for f in obj.data.polygons) for r in range(4)]
    if operation['method']=='SOURCE_FEATURE_CONFORMING_QUADS':
        expected_regions=[3*len(g) for g in operation['sourceRegionFaces']]
        expected_seam=sum(len(path)-1 for path in operation['sharedBranchPaths'].values())
        face_map=operation['faceSourceTriangles']
        if len(face_map)!=len(obj.data.polygons):raise ValueError('FACE_PROVENANCE_COUNT_MISMATCH')
        source_counts=defaultdict(int)
        for face,fi in zip(obj.data.polygons,face_map):
            source_counts[fi]+=1
            if fi not in operation['sourceRegionFaces'][face.material_index]:raise ValueError('REGION_FACE_PROVENANCE_MISMATCH')
            tri=source.data.polygons[fi]
            for i in face.vertices:
                point=points[i];p=[source_points[k] for k in tri.vertices]
                normal=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
                if abs((point-p[0]).dot(normal))>1e-6:raise ValueError('QUAD_CROSSES_SOURCE_CREASE')
        if set(source_counts)!=set(range(len(source.data.polygons))) or any(n!=3 for n in source_counts.values()):
            raise ValueError('SOURCE_TRIANGLE_COVERAGE_MISMATCH')
        for path in operation['sharedBranchPaths'].values():
            for a,b in zip(path,path[1:]):
                if len(set(edge_faces.get(tuple(sorted((a,b))),[])))!=2:raise ValueError('BRANCH_NOT_SHARED_BY_TWO_REGIONS')
    else:
        expected_regions=[U*V]*4;expected_seam=4*V
    qa=dict(vertices=len(points),quads=len(obj.data.polygons),triangles=len(triangles),
            allFacesQuads=all(len(f.vertices)==4 for f in obj.data.polygons),
            regionQuadCounts=regions,sharedBranchEdges=len(seam),
            maximumProvenanceErrorMeters=max(errors),maximumForwardSampleErrorMeters=max(forward),
            maximumReverseSampleErrorMeters=max(reverse),forwardSampleCount=len(samples),reverseSampleCount=len(reverse_samples),
            nonAdjacentSelfIntersectionPairs=crossings,nonContiguousInteriorEdges=orientation_errors,
            vertexValenceCounts=dict(sorted(valence_counts.items())),topology=topology,garmentStaticQA=False,originalBodyMovedVertices=0)
    qa['eligible']=qa['allFacesQuads'] and len(topology['components'])==1 and len(topology['boundaryLoops'])==2 and topology['euler']==0 and topology['zeroAreaFaces']==0 and crossings==0 and orientation_errors==0 and max(errors)<1e-6 and max(forward+reverse)<=MAX_SURFACE_ERROR and len(seam)==expected_seam and regions==expected_regions
    if not qa['eligible']:raise ValueError('STRUCTURED_SURFACE_QA_REJECTED:'+json.dumps({k:v for k,v in qa.items() if k!='topology'}))
    return qa


def run(args):
    source_path,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source_path)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    metadata=source_path.parent/'branch-boundary-report.json'
    if c.base.sha(metadata)!=REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source_path));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    visible=[o for o in originals if not o.hide_get()]
    source=bpy.data.objects[prior.RESULT_OBJECT];metadata=json.loads(metadata.read_text())
    obj,operation=(build_structured_trial if args.structured_trial else build)(source,metadata);qa=audit(obj,source,operation)
    if args.structured_trial:raise ValueError('STRUCTURED_TRIAL_NOT_PUBLISHABLE_AS_FEATURE_CAGE')
    output.mkdir(parents=True);renders=[]
    if not args.no_render:
        for label,item in [('before',source),('after',obj)]:
            folder=output/label;folder.mkdir();rows=prior.render(folder,item,[])
            renders.extend(dict(file=label+'/'+r['file'],sha256=r['sha256']) for r in rows)
        data=bpy.data.curves.new('QuadTopologyReview','CURVE');data.dimensions='3D'
        data.bevel_depth=.000075;data.bevel_resolution=1
        for edge in obj.data.edges:
            spline=data.splines.new('POLY');spline.points.add(1)
            for point,i in zip(spline.points,edge.vertices):point.co=(*obj.data.vertices[i].co,1)
        wire=bpy.data.objects.new('QuadTopologyReview',data);bpy.context.scene.collection.objects.link(wire)
        data.materials.append(c.base.material('QuadCageWire',surface.linear_color('183142')))
        folder=output/'wire';folder.mkdir()
        rows=prior.render(folder,wire,[])
        renders.extend(dict(file='wire/'+r['file'],sha256=r['sha256']) for r in rows)
        bpy.data.objects.remove(wire,do_unlink=True);bpy.data.curves.remove(data)
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):raise ValueError('ORIGINAL_CHANGED')
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in visible
    obj.hide_set(True);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='OPEN_QUAD_CAGE_TOPOLOGY_PASS_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                runtime=dict(blenderVersion=bpy.app.version_string,device='CPU'),operation=operation,qa=qa,
                originalsPreserved=True,adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['OPEN_UNOFFSET_SURFACE_NOT_THICKNESS_OR_BODY_CLEARANCE_PASS','COARSE_SOURCE_FOLDS_REMAIN',
                             'TRIANGLE_TO_THREE_QUAD_REFINEMENT_NOT_FINAL_ANIMATION_EDGE_FLOW',
                             'OUTER_CLIP_BOUNDARY_NOT_FINAL_TORSO_ATTACHMENT','SHARED_PATCH_BRANCHES_NOT_WELDED_TO_SLEEVE',
                             'NO_UV_BAKE_RIG_OR_HUMAN_GATE_B','FINITE_SURFACE_ERROR_SAMPLES_NOT_CONTINUOUS_BOUND'])
    (output/'quad-cage-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 feature-preserving shoulder quad cage — NOT PRODUCTION\nEach source triangle is rebuilt as three coplanar quads. Shared source edges and four region boundaries are preserved. Surface shape and coarse folds remain.\nNo thickness or sleeve/torso sewing. Prior assembly stays visible; CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION stays hidden.\nNo visual baseline adoption, whole-character score, rig, Gate B or Unity promotion.\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in qa.items() if k!='topology'},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true');p.add_argument('--structured-trial',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
