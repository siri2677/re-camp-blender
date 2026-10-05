"""Separate raised hem binding: static geometry hypothesis, never production."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_ch101_garment_panel as panel

c, surface = panel.c, panel.surface
SOURCE_SHA = '3d8c83891d89fe6f7bd3d2fbe10655a51ff93efa14ffea1620adaf4974017bcc'
RESULT_OBJECT = 'CH101_RaisedHemBinding_NOT_PRODUCTION'
STRATEGY = 'CH101_RAISED_HEM_BINDING_STUDY_V001'
SAMPLES = 128
HALF_WIDTH = .0015
CLEARANCE = .001
THICKNESS = .0008


def build(body, center, axis, u):
    if bpy.data.objects.get(RESULT_OBJECT):
        raise ValueError('BINDING_ALREADY_EXISTS')
    if not all(math.isfinite(x) for x in (*center, *axis, *u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_BINDING_FRAME')
    tree, _, _ = c.fit.bvh(body)
    v = axis.cross(u)
    vertices, hits = [], []
    # Rays lie in the SAME slanted plane as the existing authored hem.
    # Offsets are ray-direction distances, not normal thickness guarantees.
    for i in range(SAMPLES):
        a = math.tau*i/SAMPLES
        direction = (u*math.cos(a)+v*math.sin(a)+axis*panel.HEM_SLOPE*math.cos(a)).normalized()
        for q, offset in ((-HALF_WIDTH,CLEARANCE),(-HALF_WIDTH,CLEARANCE+THICKNESS),
                          (HALF_WIDTH,CLEARANCE+THICKNESS),(HALF_WIDTH,CLEARANCE)):
            origin = center+axis*(panel.HEM_HEIGHT+q)+direction*.10
            hit, normal, _, _ = tree.ray_cast(origin, -direction, .10)
            if hit is None:
                raise ValueError('HEM_RAY_MISSED_BODY')
            d = hit-center
            radius = (d-axis*d.dot(axis)).length
            if not (.02 < radius < .07 and -.36 < hit.x < -.12 and -.105 < hit.y < .09 and .95 < hit.z < 1.22 and normal.dot(direction) > .25):
                raise ValueError('HEM_HIT_OUTSIDE_LOCAL_ARM_OR_GRAZING')
            if abs(d.dot(axis)-panel.HEM_HEIGHT-panel.HEM_SLOPE*d.dot(u)-q)>1e-6:
                raise ValueError('HEM_PLANE_MISMATCH')
            vertices.append(hit+direction*offset)
            hits.append(radius)
    faces = [(4*i+j,4*((i+1)%SAMPLES)+j,4*((i+1)%SAMPLES)+(j+1)%4,4*i+(j+1)%4)
             for i in range(SAMPLES) for j in range(4)]
    mesh = bpy.data.meshes.new(RESULT_OBJECT)
    mesh.from_pydata(vertices, [], faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(RESULT_OBJECT, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(c.base.material('RaisedHemGraphite',surface.linear_color('151518')))
    c.base.mark(obj); obj['rigBound']=False; obj['separateFloatingBindingStudy']=True
    return obj, dict(angularSamples=SAMPLES, signedHemWidthMeters=2*HALF_WIDTH,
                     rayDirectionClearanceMeters=CLEARANCE, rayDirectionWallThicknessMeters=THICKNESS,
                     rayHitRadiusRangeMeters=[min(hits),max(hits)], bodyMovedVertices=0,
                     normalThicknessGuaranteed=False, attachedOrSewn=False,
                     originalCumulativeDisplacementBudgetReset=False)


def audit(obj, body, parts, expected_vertices=SAMPLES*4):
    if not isinstance(expected_vertices,int) or expected_vertices<=0:
        raise ValueError('INVALID_EXPECTED_VERTEX_COUNT')
    mesh=obj.data; mesh.calc_loop_triangles()
    bm=bmesh.new(); bm.from_mesh(mesh)
    remaining=set(bm.verts); components=[]
    while remaining:
        stack=[remaining.pop()]; size=0
        while stack:
            vertex=stack.pop(); size+=1
            for edge in vertex.link_edges:
                other=edge.other_vert(vertex)
                if other in remaining:remaining.remove(other); stack.append(other)
        components.append(size)
    result=dict(vertices=len(mesh.vertices),faces=len(mesh.polygons),triangles=len(mesh.loop_triangles),
                components=components,nonManifoldEdges=sum(not e.is_manifold for e in bm.edges),
                nonContiguousEdges=sum(not e.is_contiguous for e in bm.edges),
                zeroAreaFaces=sum(f.calc_area()<1e-12 for f in bm.faces),
                euler=len(bm.verts)-len(bm.edges)+len(bm.faces),signedVolumeM3=bm.calc_volume(signed=True))
    bm.free()
    tree,points,faces=c.fit.bvh(obj)
    result['nonAdjacentSelfIntersectionPairs']=len({(a,b) for a,b in tree.overlap(tree) if a<b and not set(faces[a]) & set(faces[b])})
    result['intersectionPairsByObject']={other.name:len(tree.overlap(c.fit.bvh(other)[0])) for other in [body]+parts}
    # Explicit finite sampling: vertices, mesh-edge midpoints, triangle centroids.
    samples=points+[(points[e.vertices[0]]+points[e.vertices[1]])*.5 for e in mesh.edges]
    samples += [sum((points[i] for i in f),Vector())/3 for f in faces]
    target=c.fit.bvh(body)[0]
    distances=[target.find_nearest(p)[3] for p in samples]
    result.update(clearanceSampleCount=len(samples),minimumSampledBodyGapMeters=min(distances),
                  maximumSampledBodyGapMeters=max(distances),continuousClearanceProven=False,
                  sharedVertexSelfPairsExcluded=True,animationTested=False)
    result['eligible']=(components==[expected_vertices] and result['euler']==0 and result['signedVolumeM3']>0
        and not any(result[k] for k in ('nonManifoldEdges','nonContiguousEdges','zeroAreaFaces','nonAdjacentSelfIntersectionPairs'))
        and not any(result['intersectionPairsByObject'].values()) and min(distances)>.0002)
    return result


def render(output, body, parts, band, center, axis):
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24
    scene.render.resolution_x=900; scene.render.resolution_y=900; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='AgX'; scene.view_settings.exposure=-1
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    target=center+axis*panel.HEM_HEIGHT
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('HemReviewLight','AREA'); data.energy=energy; data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    views=[(name,Vector(delta)) for name,delta in [('front',(0,-.7,.08)),('side',(-.7,0,.08)),('back',(0,.7,.08))]]
    rows=[];scene.camera.data.type='ORTHO'
    for state in ('before','after','isolated'):
        for obj in [body]+parts:obj.hide_render=state=='isolated'
        band.hide_render=state=='before'
        isolated_direction=axis*.6+Vector((0,-.25,0))
        for name,delta in views if state!='isolated' else [('oblique',isolated_direction)]:
            scene.camera.location=target+delta;scene.camera.data.ortho_scale=.22 if state!='isolated' else .12
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
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals);inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[panel.RESULT_OBJECT];parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    frame=panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    band,operation=build(body,*frame);qa=audit(band,body,parts)
    if not qa['eligible']:raise ValueError('HEM_STATIC_QA_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render(output,body,parts,band,*frame[:2])
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    visible=panel.seam.replacement.configure_review_viewport([body]+parts+[band])
    for obj in bpy.context.scene.objects:
        if obj.type in ('MESH','CURVE'):obj.hide_render=obj not in [body]+parts+[band]
    surface.require_locked(bpy.context.scene);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_RaisedHemBinding_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='STATIC_BINDING_STUDY_PENDING_VISUAL_REVIEW',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['SEPARATE_FLOATING_BINDING_NOT_SEWN_OR_WELDED','NOT_A_COMPLETE_LAYERED_OVERSLEEVE',
                             'RAY_DIRECTION_DIMENSIONS_NOT_NORMAL_THICKNESS','SAMPLED_STATIC_GAP_NOT_ANIMATION_CLEARANCE',
                             'BODY_FACETS_AND_UPPER_CROSSFADE_UNCHANGED','NO_UV_BAKE_RIG_OR_HUMAN_GATE_B'])
    (output/'hem-binding-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 raised hem binding — NOT PRODUCTION\nSeparate floating narrow binding only; NOT a complete layered jacket or sewn edge.\nOriginal meshes, UVs, materials and prior displacement are unchanged.\nDimensions are authored hypotheses, not recovered measurements. Static sampled clearance is not animation clearance.\nNo full-character score, rig, Unity approval or human Gate B.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    report=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps(report['qa'],indent=2))
