"""Closed lower oversleeve shell study; preserve body, binding and locked gates."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import round_ch101_hem_binding as prior
c, surface, panel = prior.c, prior.surface, prior.panel
SOURCE_SHA = '39f5e07de24a433a7d74ff51a607219ace089162c916a0c1040c96c9b7b31a20'
RESULT_OBJECT = 'CH101_LowerOversleeveShell_NOT_PRODUCTION'
STRATEGY = 'CH101_LOWER_OVERSLEEVE_SHELL_V001'
ANGULAR, ROWS = 128, 19
LOW, HIGH = .003, .021
CLEARANCE, WALL = .002, .0008


def index(layer, row, angle):
    return (layer*ROWS+row)*ANGULAR+angle % ANGULAR


def build(body, center, axis, u):
    surface.require_locked(body)
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('SHELL_ALREADY_EXISTS')
    if not all(math.isfinite(x) for x in (*center, *axis, *u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_SHELL_FRAME')
    tree, _, _ = c.fit.bvh(body)
    v = axis.cross(u)
    hits, directions, provenance = [], [], []
    for row in range(ROWS):
        q = LOW+(HIGH-LOW)*row/(ROWS-1)
        for i in range(ANGULAR):
            a = math.tau*i/ANGULAR
            direction = (u*math.cos(a)+v*math.sin(a)+axis*panel.HEM_SLOPE*math.cos(a)).normalized()
            origin = center+axis*(panel.HEM_HEIGHT+q)+direction*.10
            hit, normal, triangle, _ = tree.ray_cast(origin, -direction, .10)
            if hit is None:
                raise ValueError('SHELL_RAY_MISSED_BODY')
            d = hit-center
            radius = (d-axis*d.dot(axis)).length
            if not (.02<radius<.07 and -.36<hit.x<-.12 and -.105<hit.y<.09 and .95<hit.z<1.22 and normal.dot(direction)>.25):
                raise ValueError('SHELL_HIT_OUTSIDE_ARM_OR_GRAZING')
            if abs(d.dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*d.dot(u)-q)>1e-6:
                raise ValueError('SHELL_PLANE_MISMATCH')
            hits.append(hit); directions.append(direction)
            provenance.append(dict(row=row, angle=i, sourceTriangle=triangle, hit=list(hit), ray=list(direction)))
    vertices = [hit+direction*offset for offset in (CLEARANCE,CLEARANCE+WALL) for hit,direction in zip(hits,directions)]
    faces = []
    for layer in range(2):
        for row in range(ROWS-1):
            for i in range(ANGULAR):
                faces.append((index(layer,row,i),index(layer,row,i+1),index(layer,row+1,i+1),index(layer,row+1,i)))
    for row in (0, ROWS-1):
        for i in range(ANGULAR):
            faces.append((index(0,row,i),index(0,row,i+1),index(1,row,i+1),index(1,row,i)))
    mesh = bpy.data.meshes.new(RESULT_OBJECT); mesh.from_pydata(vertices,[],faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0: bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    # Keep true face normals: smoothing must not disguise the inherited faceting.
    mat = c.base.material('LowerOversleeveWhiteStudy',surface.linear_color('F5F4EF'))
    mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.72
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(RESULT_OBJECT,mesh); bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj); obj['rigBound']=False; obj['attachedOrSewn']=False; obj['lowerOversleeveShellStudy']=True
    return obj, provenance


def audit(obj, body, parts, band):
    qa = prior.prior.audit(obj,body,parts+[band],expected_vertices=2*ROWS*ANGULAR)
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    count = ROWS*ANGULAR
    if len(points)!=2*count:
        qa['eligible']=False; qa['thicknessError']='UNEXPECTED_VERTEX_COUNT'; return qa
    paired = [(points[i+count]-points[i]).length for i in range(count)]
    obj.data.calc_loop_triangles()
    # Opposing-surface nearest distances, excluding end caps. Finite vertex and
    # triangle-centroid samples; not a continuous wall-thickness proof.
    from mathutils.bvhtree import BVHTree
    side_faces = [[tuple(t.vertices) for t in obj.data.loop_triangles if all((i<count)==(layer==0) for i in t.vertices)] for layer in range(2)]
    distances = []
    for layer in range(2):
        other = BVHTree.FromPolygons(points,side_faces[1-layer],all_triangles=True)
        samples = points[layer*count:(layer+1)*count]+[sum((points[i] for i in face),Vector())/3 for face in side_faces[layer]]
        distances.extend(other.find_nearest(p)[3] for p in samples)
    band_tree = c.fit.bvh(band)[0]
    qa.update(pairedRayWallRangeMeters=[min(paired),max(paired)],
              sampledOpposingWallRangeMeters=[min(distances),max(distances)],
              minimumVertexBindingGapMeters=min(band_tree.find_nearest(p)[3] for p in points),
              thicknessSampleCount=len(distances),continuousThicknessProven=False,
              attachedOrSewn=False,bodyMovedVertices=0)
    qa['eligible'] = qa['eligible'] and min(distances)>.0002 and max(distances)<.0012 and max(abs(x-WALL) for x in paired)<2e-7
    return qa


def render(output, obj, body, parts, band, center, axis):
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24
    scene.render.resolution_x=900; scene.render.resolution_y=900; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='AgX'; scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'): old.hide_render=True
    target=center+axis*(panel.HEM_HEIGHT+(LOW+HIGH)/2)
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('ShellReviewLight','AREA'); data.energy=energy; data.size=.4
        light=bpy.data.objects.new(data.name,data); scene.collection.objects.link(light); light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO'; rows=[]
    views=[('front',Vector((0,-.7,.08)),.22),('side',Vector((-.7,0,.08)),.22),('back',Vector((0,.7,.08)),.22)]
    for state in ('before','after','isolated'):
        for part in [body]+parts+[band]: part.hide_render=state=='isolated'
        obj.hide_render=state=='before'
        selected=views if state!='isolated' else [('oblique',-axis*.6+Vector((0,-.25,0)),.13),('longitudinal',Vector((-.7,0,.08)),.13)]
        for name,delta,scale in selected:
            scene.camera.location=target+delta; scene.camera.data.ortho_scale=scale
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/(state+'_'+name+'.png'); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
            rows.append(dict(file=path.name,sha256=c.base.sha(path)))
    return rows


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA: raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=panel.TURNAROUND_SHA: raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source)); surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals); inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT]; band=bpy.data.objects[prior.RESULT_OBJECT]
    surface.require_locked(band)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,provenance=build(body,*frame); qa=audit(obj,body,parts,band)
    if not qa['eligible']: raise ValueError('SHELL_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,obj,body,parts,band,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals): raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[band,obj])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'): old.hide_render=old not in [body]+parts+[band,obj]
    surface.require_locked(bpy.context.scene); bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_LowerOversleeveShell_NOT_PRODUCTION_v001.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='LOWER_SHELL_STUDY_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                operation=dict(angularSamples=ANGULAR,axialRows=ROWS,signedHemRangeMeters=[LOW,HIGH],
                               rayClearanceMeters=CLEARANCE,rayWallMeters=WALL,attachedOrSewn=False,
                               originalCumulativeDisplacementBudgetReset=False),qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['LOWER_18MM_ONLY_NOT_COMPLETE_OVERSLEEVE','UNATTACHED_UPPER_AND_LOWER_INTERFACE',
                             'RAY_OFFSET_NOT_CONSTANT_NORMAL_THICKNESS','INHERITS_SOURCE_FACETS',
                             'STATIC_SAMPLES_NOT_ANIMATION_OR_CONTINUOUS_PROOF','NO_UV_BAKE_RIG_OR_GATE_B'])
    (output/'shell-ray-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    report['provenanceSha256']=c.base.sha(output/'shell-ray-provenance.json')
    (output/'oversleeve-shell-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('Lower 18mm white oversleeve shell study — NOT PRODUCTION\nSeparate inner/outer surfaces and closed end walls; neither upper nor lower interface is sewn.\nOriginal body and rounded binding preserved. Dimensions are authoring hypotheses, not reference measurements.\nNo UV, rig, animation, full-character score, Gate B or Unity approval.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--no-render',action='store_true')
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))['qa'],indent=2))
