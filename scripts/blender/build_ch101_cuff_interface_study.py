"""Hollow cuff hypothesis bridging size difference without cutting the source."""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit_ch101_hand_saber_pair as pair
import build_ch101_equipment_study as base
import build_ch101_hand_authoring_study as author
import refine_ch101_hand_wrist_study as wrist
import review_ch101_equipment_fit as fit
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_HOLLOW_CUFF_INTERFACE_HYPOTHESIS_V001'


def resample(points,axis,u,count=32,center=None):
    """Match radial directions, not arc fractions of differently shaped loops.

    Only star-shaped loops with one positive intersection per ray are accepted.
    Ambiguous concavities are rejected, never bridged by choosing the outer hit.
    """
    points=[Vector(p) for p in points]
    center=Vector(center) if center is not None else sum(points,Vector())/len(points)
    axis=Vector(axis).normalized(); u=Vector(u); u=(u-axis*u.dot(axis)).normalized(); v=axis.cross(u)
    if u.length<.9: raise ValueError('DEGENERATE_CUFF_FRAME')
    poly=[((p-center).dot(u),(p-center).dot(v)) for p in points]
    def cross(a,b): return a[0]*b[1]-a[1]*b[0]
    result=[]
    for i in range(count):
        angle=2*math.pi*i/count; d=(math.cos(angle),math.sin(angle)); hits=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            e=(b[0]-a[0],b[1]-a[1]); denominator=cross(d,e)
            if abs(denominator)<1e-12: continue
            radius=cross(a,e)/denominator; fraction=cross(a,d)/denominator
            if radius>1e-6 and -1e-8<=fraction<=1+1e-8 and not any(abs(radius-r)<1e-7 for r in hits): hits.append(radius)
        if len(hits)!=1: raise ValueError('CUFF_LOOP_NOT_SINGLE_RADIAL_INTERSECTION')
        result.append(center+(u*d[0]+v*d[1])*hits[0])
    return result


def radial_offset(points,center,axis,amount):
    result=[]
    for p in points:
        r=Vector(p)-Vector(center); r-=axis*r.dot(axis)
        if r.length<=abs(amount): raise ValueError('CUFF_OFFSET_COLLAPSES_LOOP')
        result.append(Vector(p)+r.normalized()*amount)
    return result


def shell(collection,source_loop,hand_loop,axis,u):
    proximal=resample(source_loop['points'],axis,u,center=source_loop['centroid'])
    distal=resample(hand_loop['points'],axis,u,center=hand_loop['centroid'])
    # 1.5mm estimated radial clearance, plus 2mm wall at the distal aperture.
    distal_outer=radial_offset(distal,hand_loop['centroid'],axis,.0035)
    distal_inner=radial_offset(distal,hand_loop['centroid'],axis,.0015)
    proximal_inner=radial_offset(proximal,source_loop['centroid'],axis,-.002)
    rings=[proximal,distal_outer,distal_inner,proximal_inner]; n=32
    verts=[tuple(p) for ring in rings for p in ring]; faces=[]
    for k in range(4):
        for j in range(n):
            a,b,c,d=k*n+j,k*n+(j+1)%n,((k+1)%4)*n+(j+1)%n,((k+1)%4)*n+j
            # Inner wall runs distal -> proximal: reverse its diagonal so both
            # walls use proximal[j] -> distal[j+1]. Independent quad tessellation
            # can make thin non-planar walls intersect despite separated rings.
            faces.extend(((a,b,d),(b,c,d)) if k==2 else ((a,b,c),(a,c,d)))
    mesh=bpy.data.meshes.new('Cuff_hollow_shell'); mesh.from_pydata(verts,[],faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    obj=bpy.data.objects.new('CH101_HollowCuff_HYPOTHESIS_NOT_PRODUCTION',mesh); collection.objects.link(obj)
    base.mark(obj); obj['sourceReplacementAllowed']=False; obj['designApproved']=False
    obj.data.materials.append(base.material('CuffStudy_Graphite',(.018,.022,.026)))
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(island_margin=.03); bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def run(args):
    source=args.source.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    for key in ('unityInputAllowed','productionPromotionAllowed'):
        if bpy.context.scene.get(key) not in (False,0): raise ValueError('SOURCE_GATE_NOT_FALSE')
    sources=[o for o in bpy.context.scene.objects if o.type=='MESH']; before=guide.digest(sources)
    body=bpy.data.objects['geometry_0']; hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center=hand.matrix_world@Vector(); axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    u=hand.matrix_world.to_3x3()@Vector((1,0,0))
    source_loops=pair.closed_section(body,center,axis)
    hand_loops=pair.closed_section(hand,center-axis*.015,axis)
    collection=bpy.data.collections.new('CUFF_INTERFACE_HYPOTHESIS_UNMERGED'); bpy.context.scene.collection.children.link(collection)
    cuff=shell(collection,source_loops[0],hand_loops[0],axis,u)
    audit=author.shape_audit(cuff); self_pairs=wrist.self_surface_pairs(cuff)
    euler=len(cuff.data.vertices)-len(cuff.data.edges)+len(cuff.data.polygons)
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or len(audit['components'])!=1 or euler!=0 or self_pairs: raise ValueError('CUFF_SHELL_INVALID')
    hand_overlap=fit.overlap_report(hand,[cuff],center)
    body_overlap=fit.overlap_report(body,[cuff],center)
    for old in sources: old.hide_render=not old.name.startswith('PAIR_STUDY_')
    output.mkdir(parents=True); renders=pair.render_views(output,body,hand,center,axis,source_loops)
    if guide.digest(sources)!=before: raise ValueError('SOURCE_CHANGED')
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    blend=output/'CH101_HollowCuffInterface_NOT_PRODUCTION_v001.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='HOLLOW_CUFF_HYPOTHESIS_NOT_APPROVED',**base.GATES,
        sourceBlendSha256=args.source_sha256,artCommit=base.ART_COMMIT,references=refs,
        sourceSection=source_loops[0],handSection=hand_loops[0],distalSectionOffsetMeters=.015,
        resampledRingVertices=32,correspondence='SHARED_ANGULAR_RAYS_SINGLE_HIT_REQUIRED',distalRadialClearanceMeters=.0015,radialWallOffsetMeters=.002,
        topology=audit,eulerCharacteristic=euler,nonAdjacentSelfSurfaceOverlapPairs=self_pairs,
        cuffVsHand=hand_overlap,cuffVsSourceBody=body_overlap,
        sourceGeometryPreserved=True,sourceHandReplaced=False,cuffWeldedToSource=False,
        designApproved=False,anatomicalSeamVerified=False,wristIntegrationAllowed=False,
        attachmentApproved=False,fullCharacterScore=None,
        limitations=['CUFF_INTERPRETATION_IS_A_DESIGN_HYPOTHESIS','RADIAL_OFFSETS_NOT_EXACT_NORMAL_THICKNESS',
            'RESAMPLING_IS_NOT_SOURCE_BOUNDARY_WELD','OLD_HAND_REMAINS','NO_ANIMATION_OR_FINAL_ATLAS'],
        renders=renders,blendFile=blend.name,blendSha256=base.sha(blend))
    (output/'cuff-interface-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
