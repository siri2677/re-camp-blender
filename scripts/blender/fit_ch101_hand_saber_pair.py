"""Closed geometric wrist loops and rigid hand/saber pair fit; no body surgery."""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_ch101_equipment_study as base
import review_ch101_equipment_fit as fit
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_CLOSED_WRIST_LOOP_RIGID_PAIR_FIT_V001'


def closed_section(body,center,axis,radius=.06):
    center=Vector(center); axis=Vector(axis).normalized()
    points,triangles=fit.geometry(body); edges=set(); positions={}
    for triangle in triangles:
        tri=[points[i] for i in triangle]; hits=[]
        signed=[(p-center).dot(axis) for p in tri]
        if any(abs(d)<1e-8 for d in signed):
            # Vertex/coplanar events can introduce ambiguous branches: fail
            # locally rather than manufacture a closed loop by bridging gaps.
            if all((p-center).length<radius for p in tri): raise ValueError('AMBIGUOUS_PLANE_VERTEX')
            continue
        for i,j in ((0,1),(1,2),(2,0)):
            a,b=tri[i],tri[j]; da,db=signed[i],signed[j]
            if da*db<0: hits.append(a+(b-a)*(da/(da-db)))
        if len(hits)!=2 or not all((p-center).length<radius for p in hits): continue
        keys=[tuple(round(float(x),6) for x in p) for p in hits]
        if keys[0]==keys[1]: raise ValueError('DEGENERATE_SECTION_SEGMENT')
        for key in keys: positions[key]=Vector(key)
        edges.add(tuple(sorted(keys)))
    graph={key:set() for key in positions}
    for a,b in edges: graph[a].add(b); graph[b].add(a)
    if not graph or any(len(n)!=2 for n in graph.values()): raise ValueError('SECTION_NOT_CLOSED_DEGREE_TWO')
    remaining=set(graph); loops=[]
    while remaining:
        start=min(remaining); current=start; previous=None; ordered=[]
        while True:
            if current in ordered: raise ValueError('SECTION_EARLY_CYCLE')
            ordered.append(current); remaining.discard(current)
            choices=sorted(graph[current]-({previous} if previous is not None else set()))
            next_key=choices[0]
            if next_key==start: break
            previous,current=current,next_key
        if len(ordered)<6: raise ValueError('SECTION_TOO_FEW_VERTICES')
        coords=[positions[k] for k in ordered]
        # Signed planar triangle-fan area centroid (not a sample median).
        total=0.; weighted=Vector()
        for a,b in zip(coords,coords[1:]+coords[:1]):
            area=(a-center).cross(b-center).dot(axis)/2
            total+=area; weighted+=(center+a+b)/3*area
        if abs(total)<1e-8: raise ValueError('SECTION_ZERO_AREA')
        centroid=weighted/total
        loops.append(dict(points=[list(p) for p in coords],pointCount=len(coords),
            areaSquareMeters=abs(total),centroid=list(centroid),closed=True,
            verifiedAnatomicalSeam=False,centerDistanceMeters=(centroid-center).length))
    return sorted(loops,key=lambda r:r['centerDistanceMeters'])


def pair_transform(hand,target,axis):
    wrist=hand.matrix_world@Vector((0,0,0))
    outward=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    rotation=outward.rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    return Matrix.Translation(Vector(target))@rotation@Matrix.Translation(-wrist)


def clone_pair(hand,saber,delta,collection):
    sources=[hand,saber]+list(saber.children_recursive); clones={}
    for source in sources:
        obj=source.copy()
        if source.data is not None: obj.data=source.data.copy()
        obj.name='PAIR_STUDY_'+source.name; collection.objects.link(obj)
        obj.parent=None; obj.matrix_world=delta@source.matrix_world
        obj.hide_render=False; obj.hide_viewport=False; base.mark(obj)
        obj['sourceReplacementAllowed']=False; clones[source]=obj
    # Keep hierarchy and transforms so sockets/details follow the cloned saber.
    world={source:obj.matrix_world.copy() for source,obj in clones.items()}
    for source,obj in clones.items(): obj.parent=clones.get(source.parent)
    bpy.context.view_layer.update()
    for source,obj in clones.items():
        obj.matrix_world=world[source]; bpy.context.view_layer.update()
    return clones[hand],clones[saber],[obj for source,obj in clones.items() if source!=hand]


def collision_regions(body,objects,center,axis):
    tree,points,triangles=fit.bvh(body); center=Vector(center); axis=Vector(axis); result=[]
    for obj in objects:
        other,_,_=fit.bvh(obj); pairs=tree.overlap(other)
        proximal=set(); distal=set(); crossing=set()
        for a,b in pairs:
            distances=[(points[v]-center).dot(axis) for v in triangles[a]]
            if min(distances)>1e-6: proximal.add(b)
            elif max(distances)<-1e-6: distal.add(b)
            else: crossing.add(b)
        result.append(dict(object=obj.name,trianglePairs=len(pairs),
            uniqueStudyTrianglesCrossing=len({b for a,b in pairs}),
            againstProximalSourceTriangles=len(proximal),againstDistalSourceTriangles=len(distal),
            againstPlaneStraddlingSourceTriangles=len(crossing)))
    return result


def render_views(output,body,hand,target,axis,loops):
    scene=bpy.context.scene; camera=scene.camera
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=32
    scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.view_settings.exposure=-1
    for obj in [o for o in scene.objects if o.type=='LIGHT']: obj.hide_render=True
    light_data=bpy.data.lights.new('PairStudy_key','AREA'); light_data.energy=30; light_data.size=.4
    light=bpy.data.objects.new(light_data.name,light_data); scene.collection.objects.link(light)
    light.location=Vector(target)+Vector((-.3,-.4,.4)); light.rotation_euler=(Vector(target)-light.location).to_track_quat('-Z','Y').to_euler()
    line=bpy.data.curves.new('Provisional_section_NOT_CUT','CURVE'); line.dimensions='3D'; line.bevel_depth=.0007; line.bevel_resolution=2
    poly=line.splines.new('POLY'); poly.points.add(len(loops[0]['points'])-1)
    for p,co in zip(poly.points,loops[0]['points']): p.co=(*co,1)
    poly.use_cyclic_u=True
    marker=bpy.data.objects.new(line.name,line); scene.collection.objects.link(marker); base.mark(marker)
    line.materials.append(base.material('Provisional_loop_orange',(.8,.25,.03)))
    slots=list(body.data.materials); indices=[p.material_index for p in body.data.polygons]
    body.data.materials.clear(); body.data.materials.append(base.material('Pair_context_clay',(.19,.22,.25)))
    for p in body.data.polygons: p.material_index=0
    renders=[]
    try:
        for name,offset,visible in [('context_front_UNMERGED',(-.25,-.7,.15),True),
                                    ('context_side_UNMERGED',(-.7,.05,.1),True),
                                    ('isolated_pair',(-.25,-.7,.15),False)]:
            body.hide_render=not visible; marker.hide_render=not visible
            aim=Vector(target)-Vector(axis)*.05
            camera.location=aim+Vector(offset); camera.rotation_euler=(aim-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.type='ORTHO'; camera.data.ortho_scale=.35
            path=output/(name+'.png'); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
            renders.append(dict(file=path.name,sha256=base.sha(path),sourceBodyShown=visible,sourceHandStillPresent=True,merged=False))
    finally:
        body.data.materials.clear()
        for mat in slots: body.data.materials.append(mat)
        for p,index in zip(body.data.polygons,indices): p.material_index=index
        body.hide_render=True; marker.hide_render=True
    return renders


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0): raise ValueError('SOURCE_GATE_NOT_FALSE')
    sources=[o for o in bpy.context.scene.objects if o.type=='MESH']; before=guide.digest(sources)
    body=bpy.data.objects['geometry_0']; hand=bpy.data.objects['CH101_TaperedHand_NOT_PRODUCTION']; saber=bpy.data.objects['CH101_Saber']
    points,_=fit.geometry(body); band=fit.refine_hand(points,guide.estimate(points)); axis=-Vector(band['forearmDirection'])
    center=Vector(band['position'])+axis*.045
    loops=closed_section(body,center,axis); target=loops[0]['centroid']
    delta=pair_transform(hand,target,axis)
    collection=bpy.data.collections.new('PROVISIONAL_WRIST_PAIR_NOT_SOURCE_REPLACEMENT'); bpy.context.scene.collection.children.link(collection)
    fitted,weapon,parts=clone_pair(hand,saber,delta,collection)
    relative_before=hand.matrix_world.inverted()@saber.matrix_world; relative_after=fitted.matrix_world.inverted()@weapon.matrix_world
    relative_error=max(abs(relative_before[i][j]-relative_after[i][j]) for i in range(4) for j in range(4))
    wrist_error=((fitted.matrix_world@Vector())-Vector(target)).length
    outward=(fitted.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    angle_error=math.degrees(outward.angle(axis))
    if relative_error>1e-5 or wrist_error>1e-5 or angle_error>.05: raise ValueError('PAIR_TRANSFORM_INVALID')
    meshes=[o for o in parts if o.type=='MESH']
    equipment=fit.overlap_report(fitted,meshes,weapon.matrix_world@Vector((0,0,.85)))
    body_overlap=collision_regions(body,[fitted]+meshes,center,axis)
    for obj in sources: obj.hide_render=True
    output.mkdir(parents=True); renders=render_views(output,body,fitted,target,axis,loops)
    if guide.digest(sources)!=before: raise ValueError('SOURCE_CHANGED')
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    blend=output/'CH101_WristPairFit_NOT_PRODUCTION_v001.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='PROVISIONAL_PAIR_ALIGNMENT_NOT_INTEGRATION',**base.GATES,
        sourceBlendSha256=args.source_sha256,artCommit=base.ART_COMMIT,references=refs,
        planeCenter=list(center),planeNormal=list(axis),closedLoops=loops,selectedLoopIndex=0,
        transform=[list(row) for row in delta],handSaberRelativeMatrixError=relative_error,
        geometricWristCenterErrorMeters=wrist_error,geometricWristAxisErrorDegrees=angle_error,
        equipmentSurfaceOverlap=equipment,sourceBodyOverlap=body_overlap,sourceGeometryPreserved=True,
        sourceHandReplaced=False,anatomicalSeamVerified=False,wristIntegrationAllowed=False,
        attachmentApproved=False,graspPoseVerified=False,fullCharacterScore=None,
        limitations=['CLOSED_GEOMETRIC_SECTION_NOT_CONFIRMED_CUFF','OLD_HAND_STILL_PRESENT',
            'CAPS_AND_BOUNDARY_VERTEX_COUNTS_NOT_BRIDGED','NO_SKIN_WEIGHTS_OR_ANIMATION',
            'SURFACE_OVERLAP_NOT_SOLID_CONTAINMENT'],renders=renders,blendFile=blend.name,blendSha256=base.sha(blend))
    (output/'wrist-pair-fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
