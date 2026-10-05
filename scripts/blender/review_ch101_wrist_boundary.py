"""Non-destructive geometric boundary review. Colored sides are NOT cut masks."""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_cuff_interface_study as c

LABELS=('OUTSIDE_REVIEW_ROI','PROXIMAL_GEOMETRIC','DISTAL_GEOMETRIC','PLANE_STRADDLING')
def classify(points,faces,center,axis):
    center=Vector(center);axis=Vector(axis).normalized();result={k:[] for k in LABELS}
    if axis.length<.9:raise ValueError('INVALID_BOUNDARY_AXIS')
    for i,face in enumerate(faces):
        vertices=[points[j] for j in face];offsets=[v-center for v in vertices]
        signed=[v.dot(axis) for v in offsets]
        local=all(abs(d)<.1 and (v-axis*d).length<.06 for v,d in zip(offsets,signed))
        label='OUTSIDE_REVIEW_ROI' if not local else ('PROXIMAL_GEOMETRIC' if min(signed)>1e-6 else 'DISTAL_GEOMETRIC' if max(signed)<-1e-6 else 'PLANE_STRADDLING')
        result[label].append(i)
    return result

def overlay(body,center,axis):
    points,faces=c.fit.geometry(body);groups=classify(points,faces,center,axis)
    mesh=bpy.data.meshes.new('Boundary_diagnostic_triangles');mesh.from_pydata(points,[],faces);mesh.update()
    obj=bpy.data.objects.new('BOUNDARY_DIAGNOSTIC_NOT_CUT_MASK',mesh);bpy.context.scene.collection.objects.link(obj)
    colors=[(.18,.20,.23),(.015,.35,.42),(.65,.035,.07),(.85,.34,.015)]
    for label,color in zip(LABELS,colors):mesh.materials.append(c.base.material(label,color))
    for slot,label in enumerate(LABELS):
        for i in groups[label]:mesh.polygons[i].material_index=slot
    c.base.mark(obj);obj['cutAllowed']=False;obj['anatomicalSeamVerified']=False
    return obj,groups

def marker(loop):
    curve=bpy.data.curves.new('Provisional_boundary_NOT_CUT','CURVE');curve.dimensions='3D';curve.bevel_depth=.0006
    poly=curve.splines.new('POLY');poly.points.add(len(loop['points'])-1)
    for p,co in zip(poly.points,loop['points']):p.co=(*co,1)
    poly.use_cyclic_u=True;curve.materials.append(c.base.material('Boundary_marker_orange',(.9,.3,.02)))
    obj=bpy.data.objects.new(curve.name,curve);bpy.context.scene.collection.objects.link(obj);c.base.mark(obj)
    return obj

def run(args):
    source=args.source.resolve();output=args.output.resolve()
    if c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=c.base.verify_references(args.art_root.resolve())
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if scene.get(key) not in (False,0):raise ValueError('SOURCE_GATE_NOT_FALSE')
    sources=[o for o in scene.objects if o.type=='MESH'];before=c.guide.digest(sources)
    body=bpy.data.objects['geometry_0'];hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    cuff=bpy.data.objects['CUFF_REDUCTION_0.5_NOT_PRODUCTION'];saber=bpy.data.objects['PAIR_STUDY_CH101_Saber']
    center=hand.matrix_world@Vector();axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    sections=[]
    for offset in (-.005,0,.005):
        try:sections.append(dict(offsetMeters=offset,status='GEOMETRIC_LOOPS_ONLY',loops=c.pair.closed_section(body,center+axis*offset,axis)))
        except ValueError as error:sections.append(dict(offsetMeters=offset,status='SECTION_REJECTED',reason=str(error)))
    central=next(s for s in sections if s['offsetMeters']==0)
    if central['status']!='GEOMETRIC_LOOPS_ONLY':raise ValueError('CENTRAL_BOUNDARY_UNAVAILABLE')
    diagnostic,groups=overlay(body,center,axis)
    for obj in scene.objects:
        if obj.type in ('MESH','CURVE','LIGHT'):obj.hide_render=True
    line=marker(central['loops'][0])
    light_data=bpy.data.lights.new('Boundary_review_key','AREA');light_data.energy=30;light_data.size=.4
    light=bpy.data.objects.new(light_data.name,light_data);scene.collection.objects.link(light)
    light.location=center+Vector((-.3,-.4,.4));light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.view_settings.exposure=-1;camera=scene.camera;camera.data.type='ORTHO';camera.data.ortho_scale=.26
    renders=[];output.mkdir(parents=True)
    for mode in ('source_texture','geometric_sides'):
        body.hide_render=mode!='source_texture';diagnostic.hide_render=mode!='geometric_sides'
        for name,offset in [('front',(-.25,-.7,.15)),('side',(-.7,.05,.1))]:
            aim=center-axis*.02;camera.location=aim+Vector(offset);camera.rotation_euler=(aim-camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/f'{mode}_{name}_NOT_CUT.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            renders.append(dict(file=path.name,sha256=c.base.sha(path),sourceBodyShown=True,newHandAndCuffShown=False,cutPerformed=False))
    if c.guide.digest(sources)!=before:raise ValueError('SOURCE_GEOMETRY_CHANGED')
    blend=output/'CH101_WristBoundaryReview_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId='CH101_NONDESTRUCTIVE_WRIST_BOUNDARY_REVIEW_V001',status='GEOMETRIC_BOUNDARY_ONLY_SEMANTIC_REVIEW_REQUIRED',
        **c.base.GATES,sourceBlendSha256=args.source_sha256,artCommit=c.base.ART_COMMIT,references=refs,
        planeCenter=list(center),planeAxis=list(axis),sections=sections,
        classification=dict(method='ALL_TRIANGLE_VERTICES_IN_LOCAL_CYLINDER_THEN_SIGNED_PLANE_SIDE',radialRoiMeters=.06,axialHalfExtentMeters=.1,
            triangleIndices=groups,counts={k:len(v) for k,v in groups.items()},semanticLabels=False,cutMaskApproved=False),
        sourceOverlap=c.pair.collision_regions(body,[hand,cuff,saber],center,axis),
        sourceGeometryPreserved=True,sourceHandReplaced=False,anatomicalSeamVerified=False,cutPerformed=False,
        cutAllowed=False,wristIntegrationAllowed=False,attachmentApproved=False,fullCharacterScore=None,
        limitations=['GEOMETRIC_SIDE_IS_NOT_SKIN_OR_CLOTH','TEXTURE_PROJECTION_IS_NOT_SEMANTIC_BOUNDARY',
            'NO_SOURCE_CUT_OR_REPLACEMENT','NO_FULL_CHARACTER_QUALITY_PASS'],
        renders=renders,blendFile=blend.name,blendSha256=c.base.sha(blend))
    (output/'wrist-boundary-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    report=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:report[k] for k in ('status','blendFile','blendSha256','cutAllowed','sourceGeometryPreserved')},indent=2))
