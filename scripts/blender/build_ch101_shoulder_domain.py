"""Extract a UV-preserving, face-graph shoulder shell; never a production asset."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_upper_interface as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='a4a9c424fc74005594321fa1d72135ecaa0fbd379452aa25e5b04b8dd9f27e24'
RESULT_OBJECT='CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION'
STRATEGY='CH101_SHOULDER_FACE_GRAPH_DOMAIN_V001'
CLEARANCE=.001
WALL=.0008
MAX_OFFSET=.006
SHORT_EDGE=.002


def face_domain(body,frame):
    """World envelope is only a seed filter. Actual adjacency defines the patch."""
    surface.require_locked(body)
    center,axis,u=frame
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_SHOULDER_FRAME')
    points=[body.matrix_world@v.co for v in body.data.vertices]
    selected=set()
    for f in body.data.polygons:
        p=sum((points[i] for i in f.vertices),Vector())/len(f.vertices)
        d=p-center;q=d.dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*d.dot(u)
        if -.265<p.x<-.085 and 1.11<p.z<1.31 and abs(p.y)<.115 and q>.042:
            selected.add(f.index)
    bm=bmesh.new();bm.from_mesh(body.data)
    bm.faces.ensure_lookup_table();bm.edges.ensure_lookup_table();bm.verts.ensure_lookup_table()
    left=set(selected);components=[]
    while left:
        stack=[left.pop()];group=[]
        while stack:
            i=stack.pop();group.append(i)
            for e in bm.faces[i].edges:
                for f in e.link_faces:
                    if f.index in left:left.remove(f.index);stack.append(f.index)
        components.append(group)
    if len(components)!=1:bm.free();raise ValueError('SHOULDER_DOMAIN_DISCONNECTED')
    selected=set(components[0]);edges=defaultdict(list)
    for i in sorted(selected):
        for e in bm.faces[i].edges:edges[e.index].append(i)
    if any(len(fs)>2 for fs in edges.values()):bm.free();raise ValueError('SHOULDER_SOURCE_NON_MANIFOLD')
    boundary=[e for e,fs in edges.items() if len(fs)==1];neighbors=defaultdict(list)
    for e in boundary:
        a,b=[v.index for v in bm.edges[e].verts];neighbors[a].append(b);neighbors[b].append(a)
    if any(len(ns)!=2 for ns in neighbors.values()):bm.free();raise ValueError('SHOULDER_BOUNDARY_BRANCH_INVALID')
    loops=[];left=set(neighbors)
    while left:
        start=min(left);loop=[start];left.remove(start);previous=None;current=start
        while True:
            following=next(x for x in sorted(neighbors[current]) if x!=previous)
            if following==start:break
            if following not in left:bm.free();raise ValueError('SHOULDER_BOUNDARY_NOT_SIMPLE')
            loop.append(following);left.remove(following);previous,current=current,following
        loops.append(loop)
    verts=sorted(set(i for f in selected for i in body.data.polygons[f].vertices))
    euler=len(verts)-len(edges)+len(selected)
    bm.free()
    if len(loops)!=2 or euler!=0:raise ValueError('SHOULDER_DOMAIN_NOT_ANNULUS')
    if len(selected)!=506 or len(verts)!=297:raise ValueError('SHOULDER_SOURCE_DOMAIN_CHANGED')
    loops.sort(key=lambda loop:sum((points[i]-center).dot(axis) for i in loop)/len(loop))
    return dict(faces=sorted(selected),vertices=verts,boundaryLoops=loops,euler=euler,
                selection='CONNECTED_SOURCE_FACE_GRAPH_NOT_RADIAL_RAYS',
                boundaryRoles=['LOWER_SLEEVE_CORRESPONDENCE','SHOULDER_FRONT_BACK_UNDERARM_PERIMETER'],
                decorativeStraps='BAKED_SOURCE_TEXTURE_NOT_SEPARATE_GEOMETRY')


def offset_directions(body,domain):
    """Share one miter for a short-edge cluster to avoid reversing tiny faces."""
    points=[body.matrix_world@v.co for v in body.data.vertices]
    parents={i:i for i in domain['vertices']}
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for e in body.data.edges:
        a,b=e.vertices
        if a in parents and b in parents and (points[a]-points[b]).length<SHORT_EDGE:
            parents[root(b)]=root(a)
    groups=defaultdict(list)
    for i in parents:groups[root(i)].append(i)
    if any(max((points[a]-points[b]).length for a in ids for b in ids)>.004 for ids in groups.values()):
        raise ValueError('SHOULDER_SHORT_EDGE_CLUSTER_TOO_LARGE')
    normals=defaultdict(list)
    normal_matrix=body.matrix_world.to_3x3().inverted().transposed()
    for i in domain['faces']:
        f=body.data.polygons[i];n=(normal_matrix@f.normal).normalized()
        for group in set(root(j) for j in f.vertices):normals[group].append(n)
    result={}
    for i,ns in normals.items():
        matrix=Matrix(((.001,0,0),(0,.001,0),(0,0,.001)));rhs=Vector()
        for n in ns:
            rhs+=n
            for a in range(3):
                for b in range(3):matrix[a][b]+=n[a]*n[b]
        direction=matrix.inverted()@rhs
        if not all(math.isfinite(x) for x in direction) or direction.length* (CLEARANCE+WALL)>MAX_OFFSET:
            raise ValueError('SHOULDER_MITER_OFFSET_OUTSIDE_LIMIT')
        result[i]=direction
    # Paired direction thickness stays 0.8 mm even at a sharp source fold.
    # This is NOT a guaranteed plane-normal or continuous shell thickness.
    return {i:result[root(i)].normalized() for i in domain['vertices']}


def build(body,interface,frame):
    for o in (body,interface):surface.require_locked(o)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('SHOULDER_DOMAIN_ALREADY_EXISTS')
    domain=face_domain(body,frame);directions=offset_directions(body,domain)
    ids=domain['vertices'];lookup={old:new for new,old in enumerate(ids)};count=len(ids)
    source=[body.matrix_world@body.data.vertices[i].co for i in ids]
    vertices=[source[j]+directions[i]*offset for offset in (CLEARANCE,CLEARANCE+WALL) for j,i in enumerate(ids)]
    faces=[];source_faces=[]
    for layer in (0,1):
        for i in domain['faces']:
            indices=[lookup[j]+layer*count for j in body.data.polygons[i].vertices]
            if layer==0:indices.reverse()
            faces.append(indices);source_faces.append(i)
    for loop in domain['boundaryLoops']:
        for i,a in enumerate(loop):
            b=loop[(i+1)%len(loop)];a,b=lookup[a],lookup[b]
            faces.append((a,b,b+count,a+count));source_faces.append(None)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for material in body.data.materials:mesh.materials.append(material)
    for uv in body.data.uv_layers:mesh.uv_layers.new(name=uv.name)
    for attr in body.data.attributes:
        if attr.is_internal or attr.name=='position' or attr.domain!='POINT' or attr.data_type not in ('FLOAT','FLOAT_VECTOR','INT','BOOLEAN'):continue
        target=mesh.attributes.new(attr.name,attr.data_type,'POINT')
        key='vector' if attr.data_type=='FLOAT_VECTOR' else 'value'
        for j,i in enumerate(ids):
            for layer in (0,1):setattr(target.data[j+layer*count],key,getattr(attr.data[i],key))
    uv_error=0
    for f,source_i in zip(mesh.polygons,source_faces):
        f.use_smooth=True
        if source_i is None:f.material_index=0;continue
        old=body.data.polygons[source_i];f.material_index=old.material_index
        original_loops={v:l for v,l in zip(old.vertices,old.loop_indices)}
        for uv in body.data.uv_layers:
            target=mesh.uv_layers[uv.name]
            for j in f.loop_indices:
                old_vertex=ids[mesh.loops[j].vertex_index%count]
                original=uv.data[original_loops[old_vertex]].uv;target.data[j].uv=original
                uv_error=max(uv_error,(target.data[j].uv-original).length)
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj);obj['rigBound']=False;obj['attachedOrSewn']=False;obj['joinedToSleeveTopology']=False
    distances=[(vertices[j]-source[j%count]).length for j in range(len(vertices))]
    # Record correspondence to the ACTUAL preserved upper loop; do not weld or
    # pretend a nearest-edge association is a finished seam pattern.
    end=[prior.idx(1,prior.M-1,i) for i in range(prior.EXT_N)]
    edge_points=[interface.matrix_world@interface.data.vertices[i].co for i in end]
    matches=[]
    for i in domain['boundaryLoops'][0]:
        p=vertices[lookup[i]+count];best=None
        for k,a in enumerate(edge_points):
            b=edge_points[(k+1)%len(end)];d=b-a;t=max(0,min(1,(p-a).dot(d)/d.length_squared))
            gap=(p-a-d*t).length
            if best is None or gap<best[0]:best=(gap,k,t)
        gap,k,t=best;matches.append(dict(sourceVertex=i,interfaceEdge=[end[k],end[(k+1)%len(end)]],t=t,gapMeters=gap))
    return obj,dict(domain=domain,sourceVertexCount=count,sourceFaceCount=len(domain['faces']),
                    pairedDirectionClearanceMeters=CLEARANCE,pairedDirectionWallMeters=WALL,
                    offsetRangeMeters=[min(distances),max(distances)],offsetLimitMeters=MAX_OFFSET,
                    transferredUVLayers=[uv.name for uv in mesh.uv_layers],maximumUVCornerError=uv_error,
                    bodyMovedVertices=0,sourceMaterialsCopiedUnchanged=True,
                    decorativeStrapsPreservedAsTexture=True,joinedToSleeveTopology=False,
                    boundaryPatternRecovered=False,wallUVsAuthored=False,
                    shortEdgeSharedMiterThresholdMeters=SHORT_EDGE,seamCorrespondence=matches,
                    lowerBoundaryToInterfaceGapRangeMeters=[min(m['gapMeters'] for m in matches),max(m['gapMeters'] for m in matches)],
                    correspondenceIsNotOneToOneSewingMap=True)


def audit(obj,body,interface,parts):
    # Annulus doubled into a closed shell has Euler 0, not an assumed disk/sphere.
    qa=prior.prior.prior.prior.prior.audit(obj,body,parts+[interface],expected_vertices=594)
    from mathutils.bvhtree import BVHTree
    points=[obj.matrix_world@v.co for v in obj.data.vertices];count=297;obj.data.calc_loop_triangles()
    skins=[[tuple(t.vertices) for t in obj.data.loop_triangles if all((i<count)==(layer==0) for i in t.vertices)] for layer in (0,1)]
    distances=[]
    for layer in (0,1):
        tree=BVHTree.FromPolygons(points,skins[1-layer],all_triangles=True)
        samples=points[layer*count:(layer+1)*count]+[sum((points[i] for i in f),Vector())/3 for f in skins[layer]]
        distances.extend(tree.find_nearest(p)[3] for p in samples)
    qa.update(sampledWallRangeMeters=[min(distances),max(distances)],wallSampleCount=len(distances),continuousThicknessProven=False)
    qa['eligible']=qa['eligible'] and min(distances)>.0002 and max(distances)<.0012
    qa.update(bodyMovedVertices=0,joinedToSleeveTopology=False,animationTested=False)
    return qa


def render(output,obj,body,interface,parts,domain):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=Vector((-.18,0,1.2))
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('ShoulderDomainReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';records=[]
    def capture(name,at,delta,scale):
        scene.camera.location=at+Vector(delta);scene.camera.data.ortho_scale=scale
        scene.camera.rotation_euler=(at-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        path=output/(name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        records.append(dict(file=path.name,sha256=c.base.sha(path)))
    for state in ('before','after'):
        for part in [body,interface]+parts:part.hide_render=False
        obj.hide_render=state=='before'
        for name,delta in [('front',(0,-.7,.08)),('side',(-.7,0,.08)),('back',(0,.7,.08))]:capture(state+'_'+name,target,delta,.35)
        capture(state+'_full',Vector((0,0,.8)),(0,-3,0),1.85)
    for part in [body,interface]+parts:part.hide_render=True
    obj.hide_render=False;capture('after_isolated',target,(-.7,-.3,.08),.35)
    boundaries=[];lookup={old:new for new,old in enumerate(domain['vertices'])};count=len(lookup)
    for loop,color,name in zip(domain['boundaryLoops'],('DDAA36','34C8DB'),('LowerSeamCorrespondence','ShoulderBranchPerimeter')):
        data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=.0006;data.resolution_u=1;data.bevel_resolution=2
        spline=data.splines.new('POLY');spline.points.add(len(loop)-1);spline.use_cyclic_u=True
        for point,i in zip(spline.points,loop):point.co=(*obj.data.vertices[lookup[i]+count].co,1)
        curve=bpy.data.objects.new(name,data);scene.collection.objects.link(curve)
        data.materials.append(c.base.material(name,surface.linear_color(color)));c.base.mark(curve);boundaries.append(curve)
    capture('after_boundary_diagnostic',target,(-.7,-.3,.08),.35)
    for curve in boundaries:curve.hide_render=True;curve.hide_set(True)
    return records


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT];interface=bpy.data.objects[prior.RESULT_OBJECT]
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=build(body,interface,frame);qa=audit(obj,body,interface,parts)
    print(json.dumps(qa,indent=2))
    if not qa['eligible']:raise ValueError('SHOULDER_DOMAIN_QA_REJECTED')
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,obj,body,interface,parts,operation['domain'])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    # Visual inspection rejects the raw zigzag extraction as a new visible
    # jacket. Keep it as optional evidence, not the default authoring baseline.
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[interface])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [body]+parts+[interface]
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='SHOULDER_DOMAIN_DIAGNOSTIC_NOT_ADOPTED',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                adoptionAllowed=False,defaultTrialShellVisible=False,
                runtime=dict(blenderVersion=bpy.app.version_string,buildHash=bpy.app.build_hash.decode(),device='CPU'),
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['SOURCE_FACE_GRAPH_EXTRACT_NOT_AUTHORED_FINAL_SEWING_PATTERN',
                             'BAKED_STRAPS_NOT_SEPARATE_SEMANTIC_GEOMETRY','SOURCE_COARSE_FOLDS_RETAINED',
                             'ZIGZAG_BOUNDARY_NOT_A_FINAL_PANEL_PATTERN','LOWER_BOUNDARY_CORRESPONDENCE_NOT_WELDED_TO_SLEEVE','END_WALL_UVS_NOT_AUTHORED',
                             'SAMPLED_STATIC_QA_NOT_CONTINUOUS_OR_ANIMATION_PROOF','NO_RIG_OR_HUMAN_GATE_B'])
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    (output/'shoulder-domain-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
