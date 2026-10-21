"""Author a coarse enclosing garment cage and one shared white/graphite shell."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_oversleeve_shell as prior
c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA=prior.SOURCE_SHA
RESULT_OBJECT='CH101_SharedHemPanelCage_NOT_PRODUCTION'
STRATEGY='CH101_ENCLOSING_PANEL_CAGE_SHARED_HEM_V001'
N=64
HEIGHTS=(-.0015,.0015,.004,.008,.012,.016,.020,.024,.028)
M=len(HEIGHTS)
WALL=.0008
MAX_EXPANSION=.015
KNOTS=16


def basis(angle):
    """Positive periodic cubic B-spline weights; only 16 controls per section."""
    t=(angle%math.tau)*KNOTS/math.tau;j=math.floor(t);t-=j
    row=np.zeros(KNOTS)
    for i,w in zip((j-1,j,j+1,j+2),((1-t)**3/6,(3*t**3-6*t*t+4)/6,(-3*t**3+3*t*t+3*t+1)/6,t**3/6)):
        row[i%KNOTS]=w
    return row


def idx(layer,row,angle):
    return (layer*M+row)*N+angle%N


def gather(body,center,axis,u):
    """Collision samples are constraints, never copied vertices in this cage."""
    tree,_,_=c.fit.bvh(body);v=axis.cross(u);result=[]
    # Denser than the new topology, including midway through every row span.
    heights=sorted(set(HEIGHTS+tuple((a+b)/2 for a,b in zip(HEIGHTS,HEIGHTS[1:]))))
    for q in heights:
        ring=[]
        for i in range(128):
            a=math.tau*i/128
            direction=(u*math.cos(a)+v*math.sin(a)+axis*panel.HEM_SLOPE*math.cos(a)).normalized()
            hit,normal,triangle,_=tree.ray_cast(center+axis*(panel.HEM_HEIGHT+q)+direction*.1,-direction,.1)
            if hit is None:raise ValueError('CAGE_RAY_MISSED_BODY')
            d=hit-center;x,y=d.dot(u),d.dot(v)
            if not (.02<math.hypot(x,y)<.07 and -.36<hit.x<-.12 and -.105<hit.y<.09 and .95<hit.z<1.22 and normal.dot(direction)>.25):
                raise ValueError('CAGE_HIT_OUTSIDE_ARM_OR_GRAZING')
            ring.append(dict(q=q,x=x,y=y,triangle=triangle,hit=list(hit)))
        result.append(ring)
    return result


def fit_controls(rings):
    controls=[]
    for ring in (rings[0],rings[len(rings)//2],rings[-1]):
        xs=[h['x'] for h in ring];ys=[h['y'] for h in ring]
        cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2
        if min(max(xs)-min(xs),max(ys)-min(ys))<.02:raise ValueError('COLLAPSED_CAGE_CONTROL')
        matrix=np.array([basis(math.atan2(h['y']-cy,h['x']-cx)) for h in ring])
        targets=np.array([math.hypot(h['x']-cx,h['y']-cy)+.002 for h in ring])
        curvature=np.zeros((KNOTS,KNOTS))
        for i in range(KNOTS):curvature[i,i]=-2;curvature[i,(i-1)%KNOTS]=1;curvature[i,(i+1)%KNOTS]=1
        radii=np.linalg.lstsq(np.vstack((matrix,.5*curvature)),np.concatenate((targets,np.zeros(KNOTS))),rcond=None)[0]
        if min(radii)<.01 or max(radii)>.08:raise ValueError('INVALID_CAGE_RADII')
        controls.append(dict(q=ring[0]['q'],cx=cx,cy=cy,radii=radii.tolist()))
    return controls


def profile(controls,q):
    a,b=(controls[0],controls[1]) if q<=controls[1]['q'] else (controls[1],controls[2])
    t=(q-a['q'])/(b['q']-a['q'])
    # Fixed smooth interpolation of three authored controls. No per-ray patch.
    t=t*t*(3-2*t)
    return dict(cx=a['cx']*(1-t)+b['cx']*t,cy=a['cy']*(1-t)+b['cy']*t,
                radii=np.array(a['radii'])*(1-t)+np.array(b['radii'])*t)


def build(body,center,axis,u):
    surface.require_locked(body)
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('CAGE_ALREADY_EXISTS')
    if not all(math.isfinite(x) for x in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_CAGE_FRAME')
    rings=gather(body,center,axis,u);controls=fit_controls(rings)
    # One uniform outward allowance keeps the coarse surface outside constraints.
    # It is measured and bounded, never a per-vertex copy of the source facets.
    allowance=0.
    for ring in rings:
        for h in ring:
            p=profile(controls,h['q'])
            x,y=h['x']-p['cx'],h['y']-p['cy']
            allowance=max(allowance,math.hypot(x,y)+.002-float(basis(math.atan2(y,x))@p['radii']))
    for p in controls:
        p['radii']=[r+allowance for r in p['radii']]
    expansions=[]
    for ring in rings:
        p=profile(controls,ring[0]['q'])
        for h in ring:
            x,y=h['x']-p['cx'],h['y']-p['cy']
            r=math.hypot(x,y)
            expansions.append(float(basis(math.atan2(y,x))@p['radii'])-r)
    if max(expansions)>MAX_EXPANSION or min(expansions)<0:raise ValueError('CAGE_EXPANSION_BUDGET_REJECTED')
    v=axis.cross(u);vertices=[]
    for layer in range(2):
        for q in HEIGHTS:
            p=profile(controls,q)
            for i in range(N):
                a=math.tau*i/N
                # Radial paired wall; measured opposing surfaces decide eligibility.
                radius=float(basis(a)@p['radii'])+layer*WALL
                x=p['cx']+radius*math.cos(a)
                y=p['cy']+radius*math.sin(a)
                vertices.append(center+axis*(panel.HEM_HEIGHT+q+panel.HEM_SLOPE*x)+u*x+v*y)
    faces=[];materials=[]
    for layer in range(2):
        for row in range(M-1):
            for i in range(N):
                faces.append((idx(layer,row,i),idx(layer,row,i+1),idx(layer,row+1,i+1),idx(layer,row+1,i)))
                materials.append(1 if row==0 else 0)
    for row in (0,M-1):
        for i in range(N):
            faces.append((idx(0,row,i),idx(0,row,i+1),idx(1,row,i+1),idx(1,row,i)))
            materials.append(1 if row==0 else 0)
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for color,name in [('F5F4EF','CageWhite'),('151518','CageGraphite')]:
        mat=c.base.material(name,surface.linear_color(color));mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.72
        mesh.materials.append(mat)
    for face,material in zip(mesh.polygons,materials):face.material_index=material;face.use_smooth=True
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj);obj['rigBound']=False;obj['integratedHemTopology']=True;obj['attachedOrSewn']=False
    # Cardinal rails are explicit authoring coordinates, not anatomical claims.
    rails={name:[idx(1,row,i) for row in range(M)] for name,i in [('u_positive',0),('v_positive',N//4),('u_negative',N//2),('v_negative',3*N//4)]}
    return obj,dict(controls=controls,uniformOutwardAllowanceMeters=allowance,angularControlKnots=KNOTS,collisionSamples=rings,
                    innerRadialExpansionRangeMeters=[min(expansions),max(expansions)],
                    expansionBudgetMeters=MAX_EXPANSION,cardinalRails=rails,
                    lowerBindingRows=[0,1],upperUnattachedRow=M-1)


def audit(obj,body,parts,oldband):
    qa=prior.prior.prior.audit(obj,body,parts+[oldband],expected_vertices=2*N*M)
    points=[obj.matrix_world@v.co for v in obj.data.vertices];count=N*M
    # Use the actual opposing faces, excluding the two end caps.
    from mathutils.bvhtree import BVHTree
    obj.data.calc_loop_triangles();distances=[]
    sides=[[tuple(t.vertices) for t in obj.data.loop_triangles if all((i<count)==(layer==0) for i in t.vertices)] for layer in range(2)]
    for layer in range(2):
        target=BVHTree.FromPolygons(points,sides[1-layer],all_triangles=True)
        samples=points[layer*count:(layer+1)*count]+[sum((points[i] for i in f),Vector())/3 for f in sides[layer]]
        distances.extend(target.find_nearest(p)[3] for p in samples)
    shared=[e for e in obj.data.edges if all(count+N<=i<count+2*N for i in e.vertices)]
    # Both white and graphite polygons use these very same edges.
    polygon_edges={}
    for f in obj.data.polygons:
        for a,b in f.edge_keys:polygon_edges.setdefault(tuple(sorted((a,b))),set()).add(f.material_index)
    seam_ok=len(shared)==N and all(polygon_edges[tuple(sorted(e.vertices))]=={0,1} for e in shared)
    qa.update(sampledWallRangeMeters=[min(distances),max(distances)],thicknessSampleCount=len(distances),
              sharedOuterHemEdges=len(shared),sharedHemMaterialBoundaryValid=seam_ok,
              continuousThicknessProven=False,bodyMovedVertices=0,rigBound=False)
    qa['eligible']=qa['eligible'] and seam_ok and min(distances)>.0002 and max(distances)<.0012
    return qa


def render(output,obj,body,parts,oldband,center,axis):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=center+axis*(panel.HEM_HEIGHT+.012)
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('CageReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO';rows=[]
    views=[('front',Vector((0,-.7,.08)),.22),('side',Vector((-.7,0,.08)),.22),('back',Vector((0,.7,.08)),.22)]
    for state in ('before','after','isolated'):
        for part in [body]+parts:part.hide_render=state=='isolated'
        oldband.hide_render=state!='before';obj.hide_render=state=='before'
        selected=views if state!='isolated' else [('oblique',-axis*.6+Vector((0,-.25,0)),.13),('side',Vector((-.7,0,.08)),.13)]
        for name,delta,scale in selected:
            scene.camera.location=target+delta;scene.camera.data.ortho_scale=scale
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/(state+'_'+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            rows.append(dict(file=path.name,sha256=c.base.sha(path)))
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
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT];oldband=bpy.data.objects[prior.prior.RESULT_OBJECT]
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=build(body,*frame);qa=audit(obj,body,parts,oldband)
    if not qa['eligible']:raise ValueError('CAGE_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,obj,body,parts,oldband,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[obj])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [body]+parts+[obj]
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_SharedHemPanelCage_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='PANEL_CAGE_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['THREE_SECTION_PERIODIC_SPLINE_SHAPE_IS_AUTHORING_HYPOTHESIS','ORIGINAL_OLD_BAND_HIDDEN_AND_PRESERVED',
                             'UPPER_BOUNDARY_UNATTACHED','NO_RECOVERED_FOLDS_PATTERN_OR_ANIMATION_PROOF',
                             'NO_UV_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'panel-cage-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))['qa'],indent=2))
