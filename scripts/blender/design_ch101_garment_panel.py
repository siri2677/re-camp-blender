"""Reference-informed, explicit white oversleeve hem layout on a review copy.

Authored 3D hypothesis, not a recovered sewing pattern. No geometry movement,
old mask expansion, atlas repaint, rig approval or export-ready bake.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_ch101_patch_trim_handoff as prior

c,seam,surface,shared=prior.c,prior.seam,prior.surface,prior.shared
SOURCE_SHA='510e183538be551e4c5c08aaddab137a789a9748f5a5e48cfa9f4c998ba9fbb0'
TURNAROUND_SHA='87d7583cd28081b5bd109ea24e9b00a81e43f2decd621e48225ca3f151ad4b35'
STRATEGY='CH101_EXPLICIT_OVERSLEEVE_PANEL_LAYOUT_V001'
RESULT_OBJECT='CH101_SourceBody_DistalReplacement_PanelLayout_NOT_PRODUCTION'
Z='GarmentPanelHandHeight';R='GarmentPanelHandRadius';HEM='GarmentPanelSignedHem'
HEM_HEIGHT=.245;HEM_SLOPE=.15
LOW,START,END,HIGH=.140,.160,.270,.290
RADIAL_FULL,RADIAL_STOP=.060,.070


def influence(z,r):
    if not all(math.isfinite(v) for v in (z,r)) or r<0:raise ValueError('INVALID_PANEL_SAMPLE')
    smooth=seam.trim.upper.smoothstep
    return smooth(LOW,START,z)*(1-smooth(END,HIGH,z))*(1-smooth(RADIAL_FULL,RADIAL_STOP,r))


def classify(hem,trim):
    if not all(math.isfinite(v) for v in (hem,trim)):raise ValueError('INVALID_PANEL_SAMPLE')
    if hem>.0015:return 'WHITE_OVERSLEEVE'
    if hem>-.0015:return 'GRAPHITE_HEM_BINDING'
    if abs(trim)<.0009596364689059556:return 'GOLD_UNDERSLEEVE_TRIM'
    return 'GRAPHITE_UNDERSLEEVE'


def values(source,center,axis,u):
    if not all(math.isfinite(v) for v in (*center,*axis,*u)) or abs(axis.length-1)>1e-5 or abs(u.length-1)>1e-5 or abs(axis.dot(u))>1e-5:
        raise ValueError('INVALID_PANEL_FRAME')
    points=[source.matrix_world@v.co for v in source.data.vertices]
    dz=[(p-center).dot(axis) for p in points]
    rr=[((p-center)-axis*z).length for p,z in zip(points,dz)]
    hem=[z-HEM_HEIGHT-HEM_SLOPE*(p-center).dot(u) for p,z in zip(points,dz)]
    # Include every face whose interpolated attributes can enter the support.
    faces=[p.index for p in source.data.polygons if max(dz[i] for i in p.vertices)>LOW and min(dz[i] for i in p.vertices)<HIGH and min(rr[i] for i in p.vertices)<RADIAL_STOP]
    support={i for f in faces for i in source.data.polygons[f].vertices}
    if not faces or any(not (-.36<points[i].x<-.12 and -.105<points[i].y<.09 and .95<points[i].z<1.22) for i in support):
        raise ValueError('PANEL_SUPPORT_OUTSIDE_INSPECTED_ARM')
    slots=sorted({source.data.polygons[i].material_index for i in faces})
    if not set(slots)<=set((0,1,2,10)):raise ValueError('PANEL_TOUCHES_CUFF_OR_SEAM_MATERIAL')
    # A single connected face region, not accidentally selected other body parts.
    graph={f:set() for f in faces};edges={}
    for f in faces:
        for edge in source.data.polygons[f].edge_keys:edges.setdefault(tuple(sorted(edge)),[]).append(f)
    for fs in edges.values():
        for f in fs:graph[f].update(set(fs)-{f})
    visited=set();stack=[faces[0]]
    while stack:
        f=stack.pop()
        if f not in visited:visited.add(f);stack.extend(graph[f]-visited)
    if len(visited)!=len(faces):raise ValueError('PANEL_SUPPORT_DISCONNECTED')
    return points,dz,rr,hem,faces,slots


def verify(source,obj,faces,mapping):
    if surface.structure_signature(source)!=surface.structure_signature(obj):raise ValueError('PANEL_GEOMETRY_UV_WEIGHTS_CHANGED')
    if [(u.name,[tuple(x.uv) for x in u.data],u.active_render) for u in source.data.uv_layers]!=[(u.name,[tuple(x.uv) for x in u.data],u.active_render) for u in obj.data.uv_layers]:raise ValueError('PANEL_UV_CHANGED')
    if source.data.uv_layers.active_index!=obj.data.uv_layers.active_index:raise ValueError('PANEL_ACTIVE_UV_CHANGED')
    count=len(source.data.materials)
    if list(obj.data.materials)[:count]!=list(source.data.materials) or len(obj.data.materials)!=count+len(mapping):raise ValueError('PANEL_ORIGINAL_MATERIAL_CHANGED')
    selected=set(faces)
    for a,b in zip(source.data.polygons,obj.data.polygons):
        if a.use_smooth!=b.use_smooth or b.material_index!=(mapping[a.material_index] if a.index in selected else a.material_index):raise ValueError('PANEL_FACE_ASSIGNMENT_CHANGED')
    if shared.fields(source)!=shared.fields(obj):raise ValueError('PANEL_OLD_FIELDS_CHANGED')
    # The original packed patch shader remains at its original slot, untouched.
    if obj.data.materials[10]!=source.data.materials[10]:raise ValueError('PANEL_ORIGINAL_ATLAS_MATERIAL_CHANGED')
    return dict(retainedNormalMismatches=0,copiedUVErrors=0)


def shader(original):
    mat=original.copy();mat.name='PanelLayout_'+original.name
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
    old=output.inputs['Surface'].links[0].from_socket
    def attr(name):
        n=nodes.new('ShaderNodeAttribute');n.attribute_name=name;return n.outputs['Fac']
    def calc(op,a,b=None,name=None):
        n=nodes.new('ShaderNodeMath');n.operation=op
        if name:n.name=name
        for i,v in enumerate((a,b)):
            if v is None:continue
            if isinstance(v,(int,float)):n.inputs[i].default_value=v
            else:links.new(v,n.inputs[i])
        return n.outputs[0]
    def smooth(a,low,high):
        n=nodes.new('ShaderNodeMapRange');n.interpolation_type='SMOOTHSTEP';n.clamp=True
        n.inputs['From Min'].default_value=low;n.inputs['From Max'].default_value=high
        links.new(a,n.inputs['Value']);return n.outputs['Result']
    def mix(f,a,b,name):
        n=nodes.new('ShaderNodeMixRGB');n.name=name;links.new(f,n.inputs[0])
        for i,v in ((1,a),(2,b)):
            if isinstance(v,tuple):n.inputs[i].default_value=v
            else:links.new(v,n.inputs[i])
        return n.outputs[0]
    graphite=(*surface.linear_color('151518'),1);gold=(*surface.linear_color('D2A445'),1);white=(*surface.linear_color('F5F4EF'),1)
    z,r,hem=attr(Z),attr(R),attr(HEM)
    axial=calc('MULTIPLY',smooth(z,LOW,START),calc('SUBTRACT',1,smooth(z,END,HIGH)))
    factor=calc('MULTIPLY',axial,calc('SUBTRACT',1,smooth(r,RADIAL_FULL,RADIAL_STOP)),'PanelSupportFactor')
    trim=calc('LESS_THAN',calc('ABSOLUTE',attr(seam.trim.DISTANCE)),.0009596364689059556)
    cloth=mix(trim,graphite,gold,'PanelUndersleeve')
    # Stop longitudinal gold before a 3 mm graphite binding; white above.
    bind=calc('GREATER_THAN',hem,-.0015)
    cloth=mix(bind,cloth,graphite,'PanelHemBinding')
    color=mix(calc('GREATER_THAN',hem,.0015),cloth,white,'PanelWhiteOversleeve')
    bsdf=nodes.new('ShaderNodeBsdfPrincipled');bsdf.name='PanelAuthoredCloth';bsdf.inputs['Roughness'].default_value=.72
    links.new(color,bsdf.inputs['Base Color'])
    m=nodes.new('ShaderNodeMixShader');m.name='PanelBoundedShader'
    links.new(factor,m.inputs[0]);links.new(old,m.inputs[1]);links.new(bsdf.outputs[0],m.inputs[2]);links.new(m.outputs[0],output.inputs['Surface'])
    return mat


def design(source,center,axis,u):
    if any(name in source.data.attributes for name in (Z,R,HEM)):raise ValueError('PANEL_ALREADY_APPLIED')
    points,dz,rr,hem,faces,slots=values(source,center,axis,u)
    obj=source.copy();obj.data=source.data.copy();obj.name=RESULT_OBJECT;bpy.context.scene.collection.objects.link(obj)
    mats=[]
    try:
        for name,items in ((Z,dz),(R,rr),(HEM,hem)):
            field=obj.data.attributes.new(name,'FLOAT','POINT')
            for dest,val in zip(field.data,items):dest.value=val
        mapping={}
        for slot in slots:
            mat=shader(source.data.materials[slot]);mats.append(mat);mapping[slot]=len(obj.data.materials);obj.data.materials.append(mat)
        for f in faces:obj.data.polygons[f].material_index=mapping[source.data.polygons[f].material_index]
        verify(source,obj,faces,mapping);c.base.mark(obj);obj['explicitPanelLayoutStudy']=True
        support={i for f in faces for i in source.data.polygons[f].vertices}
        return obj,dict(method='EXPLICIT_SLANTED_OVERSLEEVE_HEM_AND_GRAPHITE_BINDING',faceIndices=faces,materialMapping=mapping,
                        selectedFaceCount=len(faces),supportVertexCount=len(support),geometryMovedVertices=0,
                        hemHandHeightMeters=HEM_HEIGHT,hemSlopeAlongHandU=HEM_SLOPE,bindingWidthMeters=.003,
                        axialSupportMeters=[LOW,START,END,HIGH],radialSupportMeters=[RADIAL_FULL,RADIAL_STOP],
                        supportWorldBounds=[[min(points[i][k] for i in support),max(points[i][k] for i in support)] for k in range(3)],
                        connectedFaceRegion=True,originalClothMaskUnchanged=True,newMaterialDomainExplicit=True,
                        exactReferenceBoundaryRecovered=False,panelDesignApproved=False,newAtlasBaked=False,
                        retainedNormalMismatches=0,copiedUVErrors=0)
    except Exception:
        mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
        for mat in mats:bpy.data.materials.remove(mat)
        raise


def render_support(output,obj,parts,operation,center,axis):
    """Render the actual per-shading-point support, not the inherited old mask."""
    scene=bpy.context.scene
    for old in scene.objects:
        if old.type in ('MESH','CURVE','LIGHT'):old.hide_render=True
    diagnostic=obj.copy();diagnostic.data=obj.data.copy();diagnostic.name='DIAGNOSTIC_PanelDomain_NOT_CLOTHING'
    scene.collection.objects.link(diagnostic)
    gray=c.base.material('PanelDiagnosticOutside',(.16,.19,.22))
    gray_slot=len(diagnostic.data.materials);diagnostic.data.materials.append(gray)
    authored=set(operation['materialMapping'].values())
    for slot in authored:
        mat=obj.data.materials[slot].copy();mat.name='DIAGNOSTIC_PanelWeight'
        nodes,links=mat.node_tree.nodes,mat.node_tree.links
        mix=nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.16,.19,.22,1);mix.inputs[2].default_value=(.95,.15,.015,1)
        links.new(nodes['PanelSupportFactor'].outputs[0],mix.inputs[0])
        bsdf=nodes.new('ShaderNodeBsdfPrincipled');links.new(mix.outputs[0],bsdf.inputs['Base Color'])
        out=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
        links.new(bsdf.outputs[0],out.inputs['Surface']);diagnostic.data.materials[slot]=mat
    for face in diagnostic.data.polygons:
        if face.material_index not in authored:face.material_index=gray_slot
    diagnostic.hide_render=False
    for part in parts:part.hide_render=False
    target=center+axis*.20
    for delta,energy in [((-.4,-.5,.6),65),((.3,.4,.3),40)]:
        data=bpy.data.lights.new('PanelDomainLight','AREA');data.energy=energy;data.size=.4
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=target+Vector(delta)
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.location=target+Vector((-.25,-.7,.15));scene.camera.data.ortho_scale=.65
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    path=output/'panel_support.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    diagnostic.hide_render=True
    return dict(file=path.name,sha256=c.base.sha(path),meaning='ACTUAL_PANEL_SHADER_INFLUENCE_NOT_INHERITED_MASK')


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=TURNAROUND_SHA:raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(source));surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=c.guide.digest(originals)
    inv={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[prior.RESULT_OBJECT];center,axis,u=shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
    obj,operation=design(body,center,axis,u);parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=seam.assess(obj,parts,operation)
    if not qa['eligible']:raise ValueError('PANEL_STATIC_QA_REJECTED')
    output.mkdir(parents=True)
    renders=[] if args.no_render else seam.trim.upper.render(output,body,obj,parts,center,axis)
    if not args.no_render:renders.append(render_support(output,obj,parts,operation,center,axis))
    if digest!=c.guide.digest(originals) or any(surface.repair.invariant_signature(o)!=inv[o.name] for o in originals):raise ValueError('ORIGINAL_CHANGED')
    verify(body,obj,operation['faceIndices'],operation['materialMapping'])
    visible=seam.replacement.configure_review_viewport([obj]+parts)
    for o in bpy.context.scene.objects:
        if o.type in ('MESH','CURVE'):o.hide_render=o not in [obj]+parts
    surface.require_locked(bpy.context.scene);bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_GarmentPanelLayout_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA:raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='PANEL_LAYOUT_HYPOTHESIS_PENDING_VISUAL_REVIEW',**c.base.GATES,sourceBlendSha256=SOURCE_SHA,
                artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,originalsPreserved=True,
                rigBound=False,fullCharacterScore=None,defaultVisibleMeshObjects=visible,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['AUTHORED_HEM_NOT_EXACT_REFERENCE_REGISTRATION','COLOR_BOUNDARY_NOT_LAYERED_CLOTH_GEOMETRY',
                             'SOURCE_DETAILS_REPLACED_WITHIN_EXPLICIT_PANEL_DOMAIN','PROCEDURAL_SHADER_NOT_BAKED_OR_UNITY_READY',
                             'UPPER_CROSSFADE_AND_GEOMETRIC_FOLDS_REMAIN','NO_HUMAN_GATE_B'])
    (output/'garment-panel-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 garment panel layout hypothesis — NOT PRODUCTION\nWhite short oversleeve / graphite undersleeve with explicit slanted hem and 3 mm binding.\nNew authored appearance domain; source texture details are intentionally replaced inside it.\nGeometry, old UVs, old masks, original shaders and atlas remain preserved in this Blend.\nNo actual cloth overlap geometry, new bake, rig or final reference fidelity is claimed.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]));print(json.dumps({k:r[k] for k in ('status','blendSha256')},indent=2))
