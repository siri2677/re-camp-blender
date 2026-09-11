"""Read-only geometry/clay evidence; never infer grip or anatomy from topology."""
import argparse
import json
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_ch101_equipment_fit as fit
import build_ch101_equipment_study as base
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_ATTACHMENT_SURFACE_DIAGNOSIS_V001'


def inspect_region(obj,center,radius):
    """Geometric sphere ROI; induced components are not semantic fingers."""
    points,_=fit.geometry(obj)
    chosen={i for i,p in enumerate(points) if (p-Vector(center)).length<=radius}
    if not chosen: raise ValueError('EMPTY_SURFACE_REGION')
    bm=bmesh.new()
    try:
        bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
        neighbors={i:set() for i in chosen}
        for edge in bm.edges:
            a,b=[v.index for v in edge.verts]
            if a in chosen and b in chosen:
                neighbors[a].add(b); neighbors[b].add(a)
        remaining=set(chosen); sizes=[]
        while remaining:
            stack=[remaining.pop()]; size=0
            while stack:
                node=stack.pop(); size+=1
                for other in neighbors[node]&remaining:
                    remaining.remove(other); stack.append(other)
            sizes.append(size)
        edges=[e for e in bm.edges if all(v.index in chosen for v in e.verts)]
        coords=[tuple(points[i]) for i in chosen]
        nearest=fit.bvh(obj)[0].find_nearest(Vector(center))
        return dict(center=list(center),radiusMeters=radius,vertexCount=len(chosen),
            inducedComponentSizes=sorted(sizes,reverse=True),
            exactDuplicateVertexCount=len(coords)-len(set(coords)),
            originalBoundaryEdges=sum(e.is_boundary for e in edges),
            originalNonManifoldEdges=sum(not e.is_manifold for e in edges),
            nearestSurfaceDistanceMeters=nearest[3],
            axisAlignedExtentMeters=[max(p[i] for p in coords)-min(p[i] for p in coords) for i in range(3)],
            anatomicalRegionVerified=False,
            limitation='SPHERE_ROI_MAY_INCLUDE_CUFF_OR_CLOTHING; COMPONENTS_ARE_NOT_FINGERS; NO_SELF_INTERSECTION_TEST')
    finally: bm.free()


def clay_views(output,hand,waist):
    scene=bpy.context.scene; layer=bpy.context.view_layer
    saved_override=layer.material_override
    objects=[o for o in bpy.data.collections['MODEL_EQUIPMENT'].all_objects]
    visibility=[(o,o.hide_render) for o in objects]
    scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.device='CPU'
    scene.render.resolution_x=900; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    mat=base.material('Diagnostic_Clay_NOT_SOURCE_MATERIAL',(.32,.32,.32))
    camera=scene.camera; camera.data.type='ORTHO'
    specs=[('clay_body',(2,-4,1.1),(0,0,.84),2.15,True),
           ('clay_hand_with_saber',tuple(Vector(hand)+Vector((-.15,-1,.10))),hand,.32,True),
           ('clay_hand_front',tuple(Vector(hand)+Vector((-.15,-1,.10))),hand,.32,False),
           ('clay_hand_back',tuple(Vector(hand)+Vector((-.15,1,.10))),hand,.32,False),
           ('clay_waist',tuple(Vector(waist)+Vector((1,-.7,.13))),waist,.48,False)]
    renders=[]
    try:
        layer.material_override=mat
        for name,position,target,scale,equipment_visible in specs:
            for obj,hidden in visibility: obj.hide_render=hidden or not equipment_visible
            camera.location=position; camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=scale; path=output/(name+'.png'); scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            renders.append(dict(file=path.name,sha256=base.sha(path),equipmentShown=equipment_visible,materialOverrideOnly=True))
    finally:
        layer.material_override=saved_override
        for obj,hidden in visibility: obj.hide_render=hidden
    return renders


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0): raise ValueError('SOURCE_GATE_NOT_FALSE')
    body=bpy.data.objects['geometry_0']; saber=bpy.data.objects['CH101_Saber']
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']; before=guide.digest(meshes)
    tree,points,faces=fit.bvh(body)
    hand=bpy.data.objects['Socket_Weapon_R'].matrix_world.translation.copy()
    waist=fit.waist_surface(tree,points,faces)['position']
    hand_region=inspect_region(body,hand,.10); waist_region=inspect_region(body,waist,.12)
    overlap=fit.overlap_report(body,[saber],hand)[0]
    output.mkdir(parents=True)
    renders=clay_views(output,hand,waist)
    if before!=guide.digest(meshes) or base.sha(source)!=args.source_sha256:
        raise ValueError('SOURCE_CHANGED')
    result=dict(strategyId=STRATEGY,status='DIAGNOSIS_ONLY_NOT_REPAIR',**base.GATES,
        artCommit=base.ART_COMMIT,references=refs,sourceBlendSha256=args.source_sha256,
        hand=hand_region,waist=waist_region,minimalSaberOverlap=overlap,
        sourceUnchanged=True,graspPoseVerified=False,attachmentApproved=False,
        fullCharacterScore=None,modelModified=False,renders=renders)
    (output/'attachment-surface-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True); parser.add_argument('--art-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(parser.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
