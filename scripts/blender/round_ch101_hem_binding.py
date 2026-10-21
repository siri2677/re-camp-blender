"""Round only the separate binding's cross-section, within its old envelope."""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_hem_binding as prior

c,surface,panel=prior.c,prior.surface,prior.panel
SOURCE_SHA='c39909027aa7c85459dc081450f2ba7f327f248474f10ff21de585ee202ed42e'
RESULT_OBJECT='CH101_RoundedHemBinding_NOT_PRODUCTION'
STRATEGY='CH101_ROUNDED_HEM_BINDING_STUDY_V001'
RADIUS=.00015
CORNER_SEGMENTS=3
SECTION_POINTS=4*(CORNER_SEGMENTS+1)


def section(points,radius=RADIUS):
    if len(points)!=4 or not math.isfinite(radius) or not 0<radius<=RADIUS:
        raise ValueError('INVALID_ROUNDING_PARAMETERS')
    if not all(math.isfinite(x) for p in points for x in p):raise ValueError('NONFINITE_SECTION')
    thickness=min((points[1]-points[0]).length,(points[2]-points[3]).length)
    width=min((points[3]-points[0]).length,(points[2]-points[1]).length)
    if thickness<radius*4 or width<radius*4:raise ValueError('SECTION_TOO_SMALL')
    rx,ry=radius/thickness,radius/width
    result=[]
    # Convex bilinear interpolation never extends beyond the original section.
    for x,y,start in ((rx,ry,math.pi),(1-rx,ry,1.5*math.pi),
                      (1-rx,1-ry,0),(rx,1-ry,.5*math.pi)):
        for j in range(CORNER_SEGMENTS+1):
            a=start+j*math.pi/(2*CORNER_SEGMENTS)
            r,t=x+rx*math.cos(a),y+ry*math.sin(a)
            if not (-1e-9<=r<=1+1e-9 and -1e-9<=t<=1+1e-9):raise ValueError('OUTSIDE_SECTION_ENVELOPE')
            result.append(points[0]*(1-r)*(1-t)+points[1]*r*(1-t)+points[2]*r*t+points[3]*(1-r)*t)
    return result


def build(source):
    if bpy.data.objects.get(RESULT_OBJECT):raise ValueError('ROUNDING_ALREADY_EXISTS')
    if len(source.data.vertices)!=512 or len(source.data.polygons)!=512:raise ValueError('UNEXPECTED_SOURCE_TOPOLOGY')
    points=[source.matrix_world@v.co for v in source.data.vertices]
    vertices=[p for i in range(prior.SAMPLES) for p in section(points[4*i:4*i+4])]
    n=SECTION_POINTS
    faces=[(i*n+j,((i+1)%prior.SAMPLES)*n+j,((i+1)%prior.SAMPLES)*n+(j+1)%n,i*n+(j+1)%n)
           for i in range(prior.SAMPLES) for j in range(n)]
    mesh=bpy.data.meshes.new(RESULT_OBJECT);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for face in mesh.polygons:face.use_smooth=True
    for mat in source.data.materials:mesh.materials.append(mat)
    obj=bpy.data.objects.new(RESULT_OBJECT,mesh);bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj);obj['rigBound']=False;obj['separateFloatingBindingStudy']=True
    return obj


def audit(obj,source,body,parts):
    qa=prior.audit(obj,body,parts,expected_vertices=prior.SAMPLES*SECTION_POINTS)
    tree,points,faces=c.fit.bvh(obj);old,oldpoints,oldfaces=c.fit.bvh(source)
    # Both directions catch unsupported widening as well as excessive removal.
    samples=points+[sum((points[i] for i in f),Vector())/3 for f in faces]
    oldsamples=oldpoints+[sum((oldpoints[i] for i in f),Vector())/3 for f in oldfaces]
    new_to_old=max(old.find_nearest(p)[3] for p in samples)
    old_to_new=max(tree.find_nearest(p)[3] for p in oldsamples)
    qa.update(maximumSampledNewToOldDistanceMeters=new_to_old,
              maximumSampledOldToNewDistanceMeters=old_to_new,
              symmetricSampledEnvelopeLimitMeters=.0002,continuousEnvelopeProven=False)
    qa['eligible']=qa['eligible'] and max(new_to_old,old_to_new)<=.0002
    return qa


def render(output,source,obj,body,parts,center,axis):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=center+axis*panel.HEM_HEIGHT
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('RoundedHemReviewLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    rows=[];scene.camera.data.type='ORTHO'
    views=[('front',Vector((0,-.7,.08)),.22,False),('side',Vector((-.7,0,.08)),.22,False),
           ('back',Vector((0,.7,.08)),.22,False),('isolated',axis*.6+Vector((0,-.25,0)),.12,True)]
    for label,band in [('before',source),('after',obj)]:
        source.hide_render=band!=source;obj.hide_render=band!=obj
        for name,direction,scale,isolated in views:
            for part in [body]+parts:part.hide_render=isolated
            scene.camera.location=target+direction;scene.camera.data.ortho_scale=scale
            scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/(label+'_'+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            rows.append(dict(file=path.name,sha256=c.base.sha(path)))
    return rows


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals);inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    band=bpy.data.objects[prior.RESULT_OBJECT];body=bpy.data.objects[panel.RESULT_OBJECT]
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    obj=build(band);qa=audit(obj,band,body,parts)
    if not qa['eligible']:raise ValueError('ROUNDED_HEM_QA_REJECTED:'+json.dumps(qa))
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,band,obj,body,parts,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[obj])
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [body]+parts+[obj]
    surface.require_locked(bpy.context.scene);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_RoundedHemBinding_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='ROUNDED_BINDING_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                operation=dict(crossSectionCornerRadiusMeters=RADIUS,cornerSegments=CORNER_SEGMENTS,
                               angularSamplesUnchanged=128,crossSectionPoints=SECTION_POINTS,
                               bodyMovedVertices=0,originalBindingPreserved=True,smoothShading=True,
                               circumferentialPathSmoothed=False,attachedOrSewn=False),
                qa=qa,originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['CROSS_SECTION_ROUNDING_NOT_FULL_CONTOUR_REAUTHORING','ANGULAR_PATH_KINKS_REMAIN',
                             'SEPARATE_FLOATING_BINDING_NOT_SEWN','SAMPLED_STATIC_CLEARANCE_ONLY',
                             'NO_COMPLETE_OVERSLEEVE_SHELL_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'rounded-hem-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 rounded hem binding — NOT PRODUCTION\nOnly the separate binding cross-section corners are rounded, with smooth shading.\nOriginal body and prior binding preserved; angular-path kinks and floating attachment remain.\nNo complete sleeve shell, bake, rig, animation proof or full-character score.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    report=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps(report['qa'],indent=2))
