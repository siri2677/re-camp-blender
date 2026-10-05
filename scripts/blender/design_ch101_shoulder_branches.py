"""Source-surface panel boundary hypothesis, NOT a sewn or offset garment."""
import argparse
from collections import defaultdict
import heapq
import itertools
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ch101_section_transition as s
c, surface, panel = s.c, s.surface, s.panel
SOURCE_SHA = '0d89a0bf4f842c2debb15f896f4fb6a641c0ac7e35befe43cd1b2db5b8aced84'
REPORT_SHA = '98540d2638a5579542ebbbdd1056eacfe7bb2825cff38bb55680a10815ca44fc'
RESULT_OBJECT = 'CH101_ShoulderBranchChart_NOT_PRODUCTION'
STRATEGY = 'CH101_SOURCE_SURFACE_BRANCH_BOUNDARIES_V001'
TARGETS = {
    'front': (-.085, -.075, 1.23),
    'underarm': (-.085, 0, 1.10),
    'back': (-.11, .115, 1.25),
    'shoulder': (-.15, 0, 1.31),
}
COLORS = {'front': 'E9AD46', 'underarm': 'D863B5', 'back': '42C7DA', 'shoulder': '85D05B'}


def crop(chart, frame):
    """Clip triangles by signed +12 mm plane with shared source-edge keys."""
    surface.require_locked(chart)
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('BRANCH_CHART_ALREADY_EXISTS')
    chart.data.calc_loop_triangles()
    points = [chart.matrix_world @ v.co for v in chart.data.vertices]
    distances = [s.signed_height(p, frame)-s.SPAN for p in points]
    vertices, provenance, lookup, faces, face_sources = [], [], {}, [], []
    def put(key, point, source):
        if key not in lookup:
            lookup[key] = len(vertices); vertices.append(point); provenance.append(source)
        return lookup[key]
    for tri in chart.data.loop_triangles:
        poly = []
        ids = list(tri.vertices)
        for a, b in zip(ids, ids[1:]+ids[:1]):
            da, db = distances[a], distances[b]
            if da >= 0:
                poly.append(put(('v', a), points[a], dict(sourceEdge=[a, a], edgeT=0)))
            if (da >= 0) != (db >= 0):
                a, b = sorted((a,b)); da, db = distances[a], distances[b]
                t = da/(da-db)
                poly.append(put(('e', a, b), points[a].lerp(points[b],t), dict(sourceEdge=[a,b],edgeT=t)))
        for j in range(1,len(poly)-1):
            face = (poly[0],poly[j],poly[j+1])
            if (vertices[face[1]]-vertices[face[0]]).cross(vertices[face[2]]-vertices[face[0]]).length < 1e-12:
                raise ValueError('DEGENERATE_CUT_TRIANGLE')
            faces.append(face); face_sources.append(tri.index)
    mesh = bpy.data.meshes.new(RESULT_OBJECT); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj = bpy.data.objects.new(RESULT_OBJECT,mesh); bpy.context.scene.collection.objects.link(obj); c.base.mark(obj)
    obj['referenceChartOnly']=True; obj['adoptionAllowed']=False
    topology = s.prior.prior.boundaries(obj)
    loops = topology['boundaryLoops']
    seam = [loop for loop in loops if max(abs(s.signed_height(vertices[i],frame)-s.SPAN) for i in loop)<1e-6]
    if len(topology['components'])!=1 or len(loops)!=2 or len(seam)!=1:
        raise ValueError('BRANCH_DOMAIN_NOT_ANNULUS')
    return obj, dict(vertexProvenance=provenance,sourceTriangles=face_sources,lowerLoop=seam[0],
                     outerLoop=next(loop for loop in loops if loop!=seam[0]),topology=topology)


def shortest_path(points, adjacency, start, end, forbidden):
    queue=[(0,start)]; costs={start:0}; parents={}
    a,b=points[start],points[end]; direction=b-a
    while queue:
        cost,i=heapq.heappop(queue)
        if cost!=costs[i]:continue
        if i==end:
            path=[i]
            while i!=start:i=parents[i];path.append(i)
            return list(reversed(path))
        for j in sorted(adjacency[i]):
            if j in forbidden and j!=end:continue
            t=max(0,min(1,(points[j]-a).dot(direction)/direction.length_squared))
            deviation=(points[j]-(a+direction*t)).length
            new=cost+(points[j]-points[i]).length*(1+deviation/.02)
            if new<costs.get(j,float('inf')):
                costs[j]=new;parents[j]=i;heapq.heappush(queue,(new,j))
    raise ValueError('NO_DISJOINT_BRANCH_PATH')


def regions(obj, paths):
    blocked={tuple(sorted((a,b))) for path in paths.values() for a,b in zip(path,path[1:])}
    edges=defaultdict(list)
    for face in obj.data.polygons:
        ids=list(face.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):edges[tuple(sorted((a,b)))].append(face.index)
    neighbors=defaultdict(set)
    for edge,fs in edges.items():
        if edge not in blocked and len(fs)==2:
            a,b=fs;neighbors[a].add(b);neighbors[b].add(a)
    unseen=set(range(len(obj.data.polygons))); groups=[]
    while unseen:
        stack=[min(unseen)];group=[]
        while stack:
            i=stack.pop()
            if i not in unseen:continue
            unseen.remove(i);group.append(i);stack.extend(neighbors[i]&unseen)
        groups.append(sorted(group))
    return groups


def design(obj, operation):
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    lower,outer=operation['lowerLoop'],operation['outerLoop']
    keys={'front':lambda p:p.y,'back':lambda p:-p.y,'shoulder':lambda p:p.x,'underarm':lambda p:-p.x}
    starts={name:min(lower,key=lambda i:(key(points[i]),i)) for name,key in keys.items()}
    ends={name:min(outer,key=lambda i:((points[i]-Vector(target)).length,i)) for name,target in TARGETS.items()}
    if len(set(starts.values()))!=4 or len(set(ends.values()))!=4:raise ValueError('DUPLICATED_BRANCH_ANCHOR')
    adjacency=defaultdict(set)
    for edge in obj.data.edges:
        a,b=edge.vertices;adjacency[a].add(b);adjacency[b].add(a)
    for order in itertools.permutations(TARGETS):
        forbidden=set(lower+outer);paths={}
        try:
            for name in order:
                paths[name]=shortest_path(points,adjacency,starts[name],ends[name],forbidden)
                forbidden.update(paths[name])
        except ValueError:continue
        groups=regions(obj,paths)
        if len(groups)==4:break
    else:raise ValueError('CANNOT_PARTITION_FOUR_PANELS')
    for i,color in enumerate(COLORS.values()):
        obj.data.materials.append(c.base.material('BranchRegion_'+str(i),surface.linear_color(color)))
    for region,faces in enumerate(groups):
        for i in faces:obj.data.polygons[i].material_index=region
    return dict(paths=paths,starts=starts,ends=ends,authoredTargetHints={k:list(v) for k,v in TARGETS.items()},
                routingOrder=list(order),faceRegions=groups,patternHypothesisOnly=True)


def audit(obj, chart, op, design_record, frame):
    surface.require_locked(obj);surface.require_locked(chart)
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    source=[chart.matrix_world@v.co for v in chart.data.vertices]
    if len(op['vertexProvenance'])!=len(points):raise ValueError('PROVENANCE_COUNT_MISMATCH')
    errors=[]
    for point,r in zip(points,op['vertexProvenance']):
        a,b=r['sourceEdge'];t=r['edgeT']
        if not 0<=t<=1:raise ValueError('INVALID_SOURCE_INTERPOLATION')
        errors.append((point-source[a].lerp(source[b],t)).length)
    edge_set={tuple(sorted(e.vertices)) for e in obj.data.edges}
    paths=design_record['paths'];used=set()
    if set(paths)!=set(TARGETS):raise ValueError('BRANCH_NAMES_MISMATCH')
    for name,path in paths.items():
        if len(path)<2 or len(path)!=len(set(path)) or used.intersection(path):raise ValueError('BRANCH_PATH_OVERLAP')
        if path[0]!=design_record['starts'][name] or path[-1]!=design_record['ends'][name]:raise ValueError('ANCHOR_MISMATCH')
        if path[0] not in op['lowerLoop'] or path[-1] not in op['outerLoop']:raise ValueError('ANCHOR_NOT_ON_BOUNDARY')
        if set(path[1:-1]).intersection(op['lowerLoop']+op['outerLoop']):raise ValueError('PATH_TOUCHES_OTHER_BOUNDARY')
        if any(tuple(sorted(e)) not in edge_set for e in zip(path,path[1:])):raise ValueError('PATH_LEAVES_SOURCE_EDGES')
        used.update(path)
    groups=regions(obj,paths)
    if groups!=design_record['faceRegions'] or len(groups)!=4:raise ValueError('REGION_PARTITION_MISMATCH')
    tree,_,triangles=c.fit.bvh(obj)
    intersections=len({(a,b) for a,b in tree.overlap(tree) if a<b and not set(triangles[a])&set(triangles[b])})
    qa=dict(vertices=len(points),faces=len(obj.data.polygons),branchCount=4,regionFaceCounts=[len(g) for g in groups],
            maximumSourcePositionErrorMeters=max(errors),minimumSignedSectionHeightMeters=min(s.signed_height(p,frame) for p in points),
            nonAdjacentChartSelfIntersectionPairs=intersections,originalBodyMovedVertices=0,garmentStaticQA=False,
            sourceSurfaceCoincidenceIntentional=True,openReferenceChart=True)
    qa['eligible']=max(errors)<1e-6 and qa['minimumSignedSectionHeightMeters']>=s.SPAN-1e-6 and intersections==0
    if not qa['eligible']:raise ValueError('BRANCH_CHART_QA_REJECTED')
    return qa


def curve(name, points, color, cyclic=False):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=.0005;data.bevel_resolution=2
    spline=data.splines.new('POLY');spline.points.add(len(points)-1);spline.use_cyclic_u=cyclic
    for p,co in zip(spline.points,points):p.co=(*co,1)
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
    data.materials.append(c.base.material(name,surface.linear_color(color)));c.base.mark(obj);obj['guideOnly']=True
    return obj


def render(output, obj, guides):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=Vector((-.17,0,1.2))
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('BranchReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';records=[]
    obj.hide_render=False
    for guide in guides:guide.hide_render=False
    for name,delta in [('front',(0,-.7,.08)),('side',(-.7,0,.08)),('back',(0,.7,.08)),('oblique',(-.7,-.3,.15))]:
        scene.camera.location=target+Vector(delta);scene.camera.data.ortho_scale=.34
        scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path=output/('branch_'+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        records.append(dict(file=path.name,sha256=c.base.sha(path)))
    return records


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if c.base.sha(source.parent/'section-transition-report.json')!=REPORT_SHA:raise ValueError('SOURCE_REPORT_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals};digest=c.guide.digest(originals)
    visible=[o for o in originals if not o.hide_get()]
    chart=bpy.data.objects[s.prior.prior.RESULT_OBJECT];entry=bpy.data.objects[s.RESULT_OBJECT]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,op=crop(chart,frame);design_record=design(obj,op);qa=audit(obj,chart,op,design_record,frame)
    guides=[];mapping=[]
    for name,path in design_record['paths'].items():
        points=[obj.matrix_world@obj.data.vertices[i].co for i in path]
        guides.append(curve('BRANCH_GUIDE_'+name,points,COLORS[name]))
    ring=[entry.matrix_world@entry.data.vertices[s.idx(1,s.ROWS,k)].co for k in range(s.N)]
    guides.append(curve('BRANCH_GUIDE_entry_outer_ring',ring,'FFFFFF',True))
    for name,i in design_record['starts'].items():
        point=obj.matrix_world@obj.data.vertices[i].co
        k=min(range(s.N),key=lambda k:(ring[k]-point).length)
        mapping.append(dict(name=name,chartVertex=i,entryAngleIndex=k,entryVertex=s.idx(1,s.ROWS,k),
                            sourcePoint=list(point),entryPoint=list(ring[k]),gapMeters=(point-ring[k]).length,sewn=False))
        guides.append(curve('BRANCH_GUIDE_gap_'+name,[point,ring[k]],'FFFFFF'))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,obj,guides)
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in visible
    obj.hide_set(True)
    for guide in guides:guide.hide_set(True)
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_ShoulderBranchBoundaries_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='BOUNDARY_HYPOTHESIS_NOT_GARMENT',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                operation=op,design=design_record,qa=qa,entryMapping=mapping,originalsPreserved=True,
                adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['SOURCE_SURFACE_PARTITION_NOT_NEW_CLOTHING','OUTER_BORDER_IS_CLIP_ENVELOPE_NOT_APPROVED_SEWING_LINE',
                             'ROUTES_FOLLOW_COARSE_SOURCE_EDGES_NOT_SMOOTH_FINAL_CREASES','ENTRY_GAP_NOT_WELDED',
                             'NO_THICKNESS_OFFSET_UV_RIG_OR_FULL_CHARACTER_SCORE'])
    (output/'branch-boundary-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 source-surface branching boundary study — NOT PRODUCTION\nFour disjoint paths partition an open reference chart. This is NOT a new garment shell or torso attachment.\nPrior assembly stays visible; chart and guide curves are hidden by default. Unhide CH101_ShoulderBranchChart_NOT_PRODUCTION and BRANCH_GUIDE objects together to inspect.\nGate B pending; no Unity, rig, whole-character score or visual baseline adoption.\n',encoding='utf-8')
    print(json.dumps(qa,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
