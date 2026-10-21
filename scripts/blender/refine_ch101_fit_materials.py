"""Conservative material consolidation and fixed-anchor sheath clearance study."""
import argparse
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_ch101_equipment_fit as fit
import build_ch101_equipment_study as base
import prepare_ch101_landmark_rig_review as guide

STRATEGY='CH101_SOLID_MATERIAL_AND_SHEATH_AXIS_STUDY_V001'
SOLID_NAMES={'Graphite','Gold','Steel','Cyan_Hardware_Inset'}


def consolidate(objects):
    materials={m.name:m for o in objects for m in o.data.materials if m}
    solid={name:materials[name] for name in SOLID_NAMES if name in materials}
    if len(solid)!=4: raise ValueError('EXPECTED_FOUR_KNOWN_SOLID_MATERIALS')
    values={}
    for name,mat in solid.items():
        node=mat.node_tree.nodes.get('Principled BSDF')
        if node is None or any(node.inputs[k].is_linked for k in ['Base Color','Metallic','Roughness','Normal']):
            raise ValueError('UNSUPPORTED_SOLID_SHADER:'+name)
        values[name]={'color':list(node.inputs['Base Color'].default_value),
                      'metallic':node.inputs['Metallic'].default_value,
                      'roughness':node.inputs['Roughness'].default_value}
    merged=base.material('Equipment_SolidSurface_Attributes',(.1,.1,.1))
    nodes,links=merged.node_tree.nodes,merged.node_tree.links
    shader=nodes.get('Principled BSDF')
    for attr,socket,output in [('Equipment_BaseColor','Base Color','Color'),
                               ('Equipment_Metallic','Metallic','Fac'),('Equipment_Roughness','Roughness','Fac')]:
        node=nodes.new('ShaderNodeAttribute'); node.attribute_name=attr
        links.new(node.outputs[output],shader.inputs[socket])
    changed=[]
    for obj in objects:
        mesh=obj.data; original=list(mesh.materials)
        polygon_materials=[original[p.material_index] for p in mesh.polygons]
        if not any(m.name in solid for m in original): continue
        for name in ['Equipment_BaseColor','Equipment_Metallic','Equipment_Roughness']:
            if name in mesh.attributes: raise ValueError('EXISTING_ATTRIBUTE:'+name)
        color=mesh.attributes.new('Equipment_BaseColor','FLOAT_COLOR','CORNER')
        metal=mesh.attributes.new('Equipment_Metallic','FLOAT','FACE')
        rough=mesh.attributes.new('Equipment_Roughness','FLOAT','FACE')
        # Attribute creation can invalidate RNA collection references; reacquire.
        color=mesh.attributes['Equipment_BaseColor']; metal=mesh.attributes['Equipment_Metallic']; rough=mesh.attributes['Equipment_Roughness']
        new_materials=[]
        for mat in original:
            replacement=merged if mat.name in solid else mat
            if replacement not in new_materials: new_materials.append(replacement)
        assigned=[]
        for p,mat in zip(mesh.polygons,polygon_materials):
            replacement=merged if mat.name in solid else mat
            assigned.append(new_materials.index(replacement))
            if mat.name in values:
                data=values[mat.name]
                for i in p.loop_indices: color.data[i].color=data['color']
                metal.data[p.index].value=data['metallic']; rough.data[p.index].value=data['roughness']
        mesh.materials.clear()
        for mat in new_materials: mesh.materials.append(mat)
        for p,index in zip(mesh.polygons,assigned): p.material_index=index
        changed.append(obj.name)
    return dict(status='SOLID_SHADER_INPUTS_PRESERVED_IN_ATTRIBUTES',sourceValues=values,
                changedObjects=changed,unityShaderExportReady=False,textureBaked=False)


def topology(objects):
    return [(o.name,[list(o.matrix_world@v.co) for v in o.data.vertices],
             [list(p.vertices) for p in o.data.polygons]) for o in objects]


def run(args):
    source=args.source.resolve(); report_path=args.report.resolve(); output=args.output.resolve()
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_SHA256_MISMATCH')
    if base.sha(report_path)!=args.report_sha256: raise ValueError('REPORT_SHA256_MISMATCH')
    source_report=json.loads(report_path.read_text(encoding='utf-8'))
    if source_report['blendSha256']!=args.source_sha256: raise ValueError('REPORT_SOURCE_MISMATCH')
    if source_report.get('unityInputAllowed') is not False or source_report.get('productionPromotionAllowed') is not False:
        raise ValueError('GATE_MUST_REMAIN_FALSE')
    refs=base.verify_references(args.art_root.resolve())
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    character=bpy.data.objects['geometry_0']; before=guide.digest([character])
    objects=[o for o in bpy.data.collections['MODEL_EQUIPMENT'].all_objects if o.type=='MESH']
    original_equipment_geometry=topology(objects)
    output.mkdir(parents=True)
    # Identical camera/light baseline lets the shader rewrite be judged separately.
    before_dir=output/'material-before'; before_dir.mkdir()
    before_renders=fit.render(before_dir,source_report['hand']['position'],source_report['waist']['position'])
    material_report=consolidate(objects)
    if topology(objects)!=original_equipment_geometry: raise ValueError('MATERIAL_REWRITE_CHANGED_GEOMETRY')
    after_dir=output/'material-after'; after_dir.mkdir()
    after_renders=fit.render(after_dir,source_report['hand']['position'],source_report['waist']['position'])
    sheath=bpy.data.objects['CH101_Sheath']
    anchor=sheath.matrix_world@Vector((0,0,.698))
    sheath_parts=[o for o in objects if o==sheath or o.get('equipmentOwner')==sheath.name]
    trials=[]
    for name,axis in [('original',Vector((-.1,0,1))),('vertical',Vector((0,0,1))),('rear_tip',Vector((0,-.18,1)))]:
        matrix=fit.pose_at_anchor(sheath,(0,0,.698),anchor,axis)
        bpy.context.view_layer.update()
        audit=fit.overlap_report(character,sheath_parts,source_report['hand']['position'])
        trials.append(dict(name=name,axis=list(axis),matrix=[list(r) for r in matrix],
            surfaceCrossingTriangles=sum(x['uniqueEquipmentTrianglesCrossing'] for x in audit)))
    selected=min(trials,key=lambda x:x['surfaceCrossingTriangles'])
    fit.pose_at_anchor(sheath,(0,0,.698),anchor,selected['axis']); bpy.context.view_layer.update()
    anchor_error=((sheath.matrix_world@Vector((0,0,.698)))-anchor).length
    if anchor_error>1e-5: raise ValueError('SHEATH_ANCHOR_MOVED')
    visible=[o for o in objects if not o.hide_render]
    final_audit=fit.overlap_report(character,visible,source_report['hand']['position'])
    final_dir=output/'final'; final_dir.mkdir()
    final_renders=fit.render(final_dir,source_report['hand']['position'],source_report['waist']['position'])
    if guide.digest([character])!=before: raise ValueError('CHARACTER_CHANGED')
    for key,value in base.GATES.items(): bpy.context.scene[key]=value
    blend=output/'CH101_MaterialClearance_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if base.sha(source)!=args.source_sha256: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='STATIC_REFINEMENT_NOT_APPROVED',**base.GATES,
        artifactScope='MATERIAL_CLEARANCE_DIAGNOSTIC_NOT_PRODUCTION',artCommit=base.ART_COMMIT,references=refs,
        sourceBlendSha256=args.source_sha256,sourceReportSha256=args.report_sha256,
        materialRewrite=material_report,
        combinedMaterialSlotKinds=len({m.name for o in [character]+objects for m in o.data.materials if m}),
        sheathTrials=trials,selectedSheathPose=selected['name'],sheathAnchorErrorMeters=anchor_error,
        surfaceOverlapAudit=final_audit,characterGeometryWeightsMaterialsUnchanged=True,
        handPoseModified=False,graspPoseVerified=False,attachmentApproved=False,
        fullCharacterScore=None,
        limitations=['OPEN_HAND_AND_HANDLE_STILL_INTERSECT','NO_SOLID_OR_ANIMATED_COLLISION_TEST',
                     'BODY_FACE_HAIR_OUTFIT_QUALITY_UNCHANGED','ATTRIBUTE_SHADER_REQUIRES_UNITY_ADAPTATION'],
        materialBeforeRenders=before_renders,materialAfterRenders=after_renders,finalRenders=final_renders,
        blendFile=blend.name,blendSha256=base.sha(blend))
    (output/'material-clearance-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--source-sha256',required=True)
    p.add_argument('--report',type=Path,required=True); p.add_argument('--report-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args(sys.argv[sys.argv.index('--')+1:])),indent=2))
