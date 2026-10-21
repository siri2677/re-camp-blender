"""Patch-only trim shader handoff; existing full-cloth mask, zero geometry edits.

Preserves the packed source atlas. This authored shader study is not a new
texture bake, reconstructed tailoring pattern, rig or production material.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_ch101_sector_profile as prior

c, seam, surface, shared = prior.c, prior.seam, prior.surface, prior.shared
SOURCE_SHA = '12bb1194b7706cf7cc5518586ab62dbaf6488f0bab59fd6a779d11a02ed38fde'
STRATEGY = 'CH101_PATCH_TRIM_HANDOFF_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_TrimHandoff_NOT_PRODUCTION'
HEIGHT = 'PatchTrimHandoffHeight'
MASK_LOW, MASK_HIGH = .98, .995
FADE_LOW, FADE_HIGH = .170, .185


def weight(mask, height):
    # Inherited barycentric attribute peaks at 1.000009179; mirror shader clamp
    # without rewriting that original field. Reject larger/out-of-range values.
    if not all(math.isfinite(v) for v in (mask,height)) or not -1e-5 <= mask <= 1+1e-5:
        raise ValueError('INVALID_HANDOFF_SAMPLE')
    return seam.trim.upper.smoothstep(MASK_LOW,MASK_HIGH,mask)*(1-seam.trim.upper.smoothstep(FADE_LOW,FADE_HIGH,height))


def atlas_hash(obj):
    textures=[n for n in obj.data.materials[-1].node_tree.nodes if n.type=='TEX_IMAGE']
    if len(textures)!=1 or not textures[0].image.packed_file:
        raise ValueError('PACKED_ATLAS_REQUIRED')
    node=textures[0]
    if node.inputs['Vector'].links[0].from_node.uv_map!=shared.bake.ATLAS_UV:
        raise ValueError('EXPLICIT_ATLAS_UV_REQUIRED')
    return hashlib.sha256(bytes(node.image.packed_file.data)).hexdigest()


def verify_preservation(source,obj):
    if surface.structure_signature(source)!=surface.structure_signature(obj):
        raise ValueError('HANDOFF_GEOMETRY_UV_WEIGHTS_CHANGED')
    # structure_signature intentionally ignores SleeveTrimStudy; check ALL UVs.
    if [(u.name,[tuple(v.uv) for v in u.data],u.active_render) for u in source.data.uv_layers] != [(u.name,[tuple(v.uv) for v in u.data],u.active_render) for u in obj.data.uv_layers]:
        raise ValueError('HANDOFF_UV_CHANGED')
    if source.data.uv_layers.active_index!=obj.data.uv_layers.active_index:
        raise ValueError('HANDOFF_ACTIVE_UV_CHANGED')
    if [(p.material_index,p.use_smooth) for p in source.data.polygons]!=[(p.material_index,p.use_smooth) for p in obj.data.polygons]:
        raise ValueError('HANDOFF_FACE_ASSIGNMENTS_CHANGED')
    if list(source.data.materials)[:-1]!=list(obj.data.materials)[:-1] or len(source.data.materials)!=len(obj.data.materials):
        raise ValueError('HANDOFF_OTHER_MATERIAL_CHANGED')
    if shared.fields(source)!=shared.fields(obj):
        raise ValueError('HANDOFF_EXISTING_MASK_OR_TRIM_CHANGED')
    if atlas_hash(source)!=atlas_hash(obj):
        raise ValueError('HANDOFF_ATLAS_CHANGED')
    return dict(retainedNormalMismatches=0,copiedUVErrors=0)


def refine(source,center,axis):
    if HEIGHT in source.data.attributes:raise ValueError('HANDOFF_ALREADY_APPLIED')
    if not all(math.isfinite(v) for v in (*center,*axis)) or abs(axis.length-1)>1e-5:
        raise ValueError('INVALID_HANDOFF_FRAME')
    atlas_hash(source)
    patch_slot=len(source.data.materials)-1
    faces=[p for p in source.data.polygons if p.material_index==patch_slot]
    if len(faces)!=321:raise ValueError('PATCH_FACE_CONTRACT_CHANGED')
    ids={i for p in faces for i in p.vertices}
    points=[source.matrix_world@v.co for v in source.data.vertices]
    if any(not (-.40<points[i].x<-.17 and .90<points[i].z<1.14) for i in ids):
        raise ValueError('PATCH_OUTSIDE_FOREARM')
    heights=[(p-center).dot(axis) for p in points]
    masks=[v.value for v in source.data.attributes[seam.trim.upper.MASK].data]
    # Reuse actual adjacent seam shader width, not a guessed new gold width.
    adjacent=next(m for m in source.data.materials if m.name=='BodySleeveSeam_graphite_gold')
    cutoffs=[n for n in adjacent.node_tree.nodes if n.type=='MATH' and n.operation=='LESS_THAN']
    if len(cutoffs)!=1:raise ValueError('ADJACENT_TRIM_CONTRACT_CHANGED')
    half_width=cutoffs[0].inputs[1].default_value
    if not .0005<half_width<.002:raise ValueError('UNSAFE_TRIM_WIDTH')
    edges={}
    for p in source.data.polygons:
        for key in p.edge_keys:edges.setdefault(tuple(sorted(key)),[]).append(p.material_index)
    adjacent_slot=list(source.data.materials).index(adjacent)
    boundary=[e for e,slots in edges.items() if patch_slot in slots and adjacent_slot in slots]
    if len(boundary)!=41:raise ValueError('SHARED_BOUNDARY_CONTRACT_CHANGED')
    weights=[weight(m,z) for m,z in zip(masks,heights)]
    minimum=min(weights[i] for edge in boundary for i in edge)
    distances=[v.value for v in source.data.attributes[seam.trim.DISTANCE].data]
    trim_edges=[e for e in boundary if min(distances[i] for i in e)<half_width and max(distances[i] for i in e)>-half_width]
    # Only the two gold lanes are promised continuous. Elsewhere the inherited
    # radial mask can be <.98; retain that texture rather than widening support.
    if len(trim_edges)!=4:raise ValueError('TRIM_BOUNDARY_CONTRACT_CHANGED')
    trim_minimum=min(weights[i] for edge in trim_edges for i in edge)
    if trim_minimum<1-1e-6:raise ValueError('HANDOFF_TRIM_BOUNDARY_NOT_FULL_WEIGHT')
    obj=source.copy();obj.data=source.data.copy();obj.name=RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    mat=None
    try:
        field=obj.data.attributes.new(HEIGHT,'FLOAT','POINT')
        for item,z in zip(field.data,heights):item.value=z
        mat=source.data.materials[-1].copy();mat.name='UpperPatch_TrimHandoff_REVIEW_NOT_FINAL'
        obj.data.materials[-1]=mat
        nodes,links=mat.node_tree.nodes,mat.node_tree.links
        bsdf=nodes['Principled BSDF'];old=bsdf.inputs['Base Color'].links[0].from_socket
        def attr(name):
            n=nodes.new('ShaderNodeAttribute');n.attribute_name=name;return n.outputs['Fac']
        def smooth(socket,low,high):
            n=nodes.new('ShaderNodeMapRange');n.interpolation_type='SMOOTHSTEP';n.clamp=True
            n.inputs['From Min'].default_value=low;n.inputs['From Max'].default_value=high
            links.new(socket,n.inputs['Value']);return n.outputs['Result']
        mask=smooth(attr(seam.trim.upper.MASK),MASK_LOW,MASK_HIGH)
        fade=smooth(attr(HEIGHT),FADE_LOW,FADE_HIGH)
        inverse=nodes.new('ShaderNodeMath');inverse.operation='SUBTRACT';inverse.inputs[0].default_value=1
        links.new(fade,inverse.inputs[1])
        factor=nodes.new('ShaderNodeMath');factor.name='HandoffBoundedFactor';factor.operation='MULTIPLY'
        links.new(mask,factor.inputs[0]);links.new(inverse.outputs[0],factor.inputs[1])
        absolute=nodes.new('ShaderNodeMath');absolute.operation='ABSOLUTE';links.new(attr(seam.trim.DISTANCE),absolute.inputs[0])
        cutoff=nodes.new('ShaderNodeMath');cutoff.name='HandoffSameSeamHalfWidth';cutoff.operation='LESS_THAN';cutoff.inputs[1].default_value=half_width
        links.new(absolute.outputs[0],cutoff.inputs[0])
        palette=nodes.new('ShaderNodeMixRGB');palette.name='HandoffGraphiteGold'
        palette.inputs[1].default_value=(*surface.linear_color('151518'),1)
        palette.inputs[2].default_value=(*surface.linear_color('D2A445'),1)
        links.new(cutoff.outputs[0],palette.inputs[0])
        mix=nodes.new('ShaderNodeMixRGB');mix.name='HandoffAtlasBlend'
        links.new(factor.outputs[0],mix.inputs[0]);links.new(old,mix.inputs[1]);links.new(palette.outputs[0],mix.inputs[2])
        links.new(mix.outputs[0],bsdf.inputs['Base Color'])
        verify_preservation(source,obj)
        c.base.mark(obj);obj['trimHandoffStudy']=True
        return obj,dict(patchMaterialFaces=321,sharedBoundaryEdges=len(boundary),minimumBoundaryWeight=minimum,
                        trimCrossingBoundaryEdges=len(trim_edges),minimumTrimBoundaryWeight=trim_minimum,
                        changedMaterialSlot=patch_slot,maskThresholds=[MASK_LOW,MASK_HIGH],axialFadeMeters=[FADE_LOW,FADE_HIGH],
                        planarHalfWidthMeters=half_width,geometryMovedVertices=0,packedAtlasSha256=atlas_hash(obj),
                        patchVerticesWithPositiveWeight=sum(weights[i]>0 for i in ids),
                        formulaTrimBoundaryContinuity=True,wholeBoundaryContinuity=False,visualContinuityApproved=False,
                        originalMaskUnchanged=True,inheritedMaskRange=[min(masks),max(masks)],
                        retainedNormalMismatches=0,copiedUVErrors=0)
    except Exception:
        mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
        if mat is not None:bpy.data.materials.remove(mat)
        raise


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals)
    invariants={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[prior.RESULT_OBJECT]
    center,axis,_=shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=refine(body,center,axis)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=seam.assess(obj,parts,operation)
    if not qa['eligible']:raise ValueError('HANDOFF_STATIC_QA_REJECTED')
    output.mkdir(parents=True)
    renders=[] if args.no_render else seam.trim.upper.render(output,body,obj,parts,center,axis)
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=invariants[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    verify_preservation(body,obj)
    visible=seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'):old.hide_render=old not in [obj]+parts
    surface.require_locked(bpy.context.scene);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_PatchTrimHandoff_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='PATCH_TRIM_HANDOFF_STUDY_NOT_APPROVED',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['PROCEDURAL_BLENDER_SHADER_NOT_NEW_BAKED_ATLAS','UPPER_FADE_AND_INHERITED_TEXTURE_REMAIN',
                             'PLANAR_TRIM_NOT_REFERENCE_EXACT_TAILORING','GEOMETRY_NOT_IMPROVED_IN_THIS_STAGE',
                             'STATIC_BVH_EXCLUDES_SHARED_VERTICES','NO_RIG_OR_HUMAN_GATE_B'])
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    (output/'patch-trim-handoff-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 patch trim shader handoff — NOT PRODUCTION\nGeometry, old UVs, packed atlas, masks, weights and other material slots unchanged.\nOnly the patch material inside existing near-full cloth support is authored. Upper source transition remains.\nThis is a Blender procedural shader study, not a new baked/export-ready atlas or whole-character pass.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps({k:r[k] for k in ('status','blendSha256','operation')},indent=2))
