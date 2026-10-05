"""Add actual low-poly hardware to the equipment study; never fit by guesswork."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ch101_equipment_study as base

STRATEGY = 'CH101_REFERENCE_EQUIPMENT_HARDWARE_STUDY_V002'


def attach(obj, parent):
    obj.parent = parent
    obj['equipmentOwner'] = parent.name
    obj['detailOnly'] = True
    return obj


def closed_loop(name, path, radius, mats, parent):
    """Swept closed four-sided metal stock with a real aperture, not a decal."""
    count = len(path); verts = []
    for i, point in enumerate(path):
        tangent = (Vector(path[(i+1)%count])-Vector(path[(i-1)%count])).normalized()
        normal = Vector((0,1,0)); side = tangent.cross(normal).normalized()
        verts.extend(tuple(Vector(point)+side*a*radius+normal*b*radius)
                     for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)])
    faces = [(i*4+j,i*4+(j+1)%4,((i+1)%count)*4+(j+1)%4,((i+1)%count)*4+j)
             for i in range(count) for j in range(4)]
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name,mesh); bpy.data.collections['MODEL_EQUIPMENT'].objects.link(obj)
    for mat in mats: mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name='HardwareUV')
    for poly in mesh.polygons:
        poly.material_index = 1
        for loop in poly.loop_indices:
            # Per-quad island avoids the closing segment interpolating across the full seam.
            j = list(poly.loop_indices).index(loop)
            uv.data[loop].uv = [(0,0),(1,0),(1,1),(0,1)][j]
    base.mark(obj)
    obj['semanticPart'] = name; obj['attachmentStatus']='AUTHORED_HARDWARE_NOT_CHARACTER_FIT'
    return attach(obj,parent)


def plaque(name, points, front_y, depth, mats, mat_id, parent):
    rings = [[(x,y,z) for x,z in points] for y in [front_y,front_y+depth]]
    return attach(base.loft(name,rings,[mat_id],mats),parent)


def rect_points(x,z,w,h):
    return [(x+u*w,z+v*h) for u,v in [(-.7,-1),(.7,-1),(1,-.7),(1,.7),(.7,1),(-.7,1),(-1,.7),(-1,-.7)]]


def build_details():
    saber,sheath,ribbon = base.build_geometry()
    mats = list(saber.data.materials)+[base.material('Cyan_Hardware_Inset',(.002,.53,.63),.35)]
    for obj in [saber,sheath,ribbon]: obj.data.materials.append(mats[-1])
    # Distinguish the wrapped graphite grip from the striped blade surface.
    for poly in saber.data.polygons:
        if .736 < poly.center.z < .914:
            poly.material_index = 0
    details=[]
    for i in range(7):
        z=.751+i*.023
        points=[(0,z-.0075),(.0065,z),(0,z+.0075),(-.0065,z)]
        details.append(plaque('Grip_CyanDiamond_%02d'%i,points,-.013,.026,mats,5,saber))
    for side in [-1,1]:
        y=side*.017
        details.append(plaque('Guard_CyanInset_'+str(side),rect_points(0,.7065,.032,.005),y,.0015*side,mats,5,saber))
    # Pommel ring and guard perimeter are closed apertures with real thickness.
    details.append(closed_loop('Saber_PommelRing',[(.014*math.cos(i*math.tau/12),0,.956+.017*math.sin(i*math.tau/12)) for i in range(12)],.003,mats,saber))
    details.append(closed_loop('Sheath_EndRing',[(.014*math.cos(i*math.tau/12),0,.017+.017*math.sin(i*math.tau/12)) for i in range(12)],.003,mats,sheath))
    details.append(plaque('Sheath_CyanBadge',[(0,.572),(.012,.584),(.012,.621),(0,.633),(-.012,.621),(-.012,.584)],-.014,.002,mats,5,sheath))
    details.append(closed_loop('Sheath_BadgeBezel',[(x,-.015,z) for x,z in [(0,.570),(.015,.583),(.015,.623),(0,.636),(-.015,.623),(-.015,.583)]],.002,mats,sheath))

    # One clasp on the single ribbon's leading endpoint. Its pose follows the
    # local ribbon tangent, rather than being a floating world-space ornament.
    end=bpy.data.objects['Socket_Ribbon_L'].location.copy()
    angle=-.4
    tangent=Vector((-.26*math.sin(angle),.13*math.cos(2*angle),.34*math.cos(angle))).normalized()
    xaxis=Vector((math.cos(angle),0,math.sin(angle)))
    xaxis=(xaxis-tangent*xaxis.dot(tangent)).normalized()
    zaxis=-tangent; yaxis=zaxis.cross(xaxis).normalized()
    frame=Matrix((xaxis,yaxis,zaxis)).transposed().to_4x4(); frame.translation=end
    clasp=closed_loop('Ribbon_SingleClasp',[(x,0,z) for x,z in [(-.019,0),(.019,0),(.019,.036),(.009,.049),(-.009,.049),(-.019,.036)]],.003,mats,ribbon)
    clasp.matrix_basis=frame
    details.append(clasp)
    pin=plaque('Ribbon_ClaspPin',rect_points(0,.011,.021,.003),-.003,.006,mats,1,ribbon)
    pin.matrix_basis=frame; details.append(pin)
    for obj in [saber,sheath,ribbon]+details:
        obj['strategyId']=STRATEGY
    bpy.context.view_layer.update()
    return [saber,sheath,ribbon]+details


def inspect_character(path, expected_sha):
    if base.sha(path)!=expected_sha: raise ValueError('CHARACTER_SHA256_MISMATCH')
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    armatures=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    sockets=[o.name for o in bpy.context.scene.objects if o.name.startswith('Socket_')]
    meshes=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('ReviewFloor_')]
    report=dict(sourceBlendSha256=expected_sha,armatures=[o.name for o in armatures],
                boneNames={o.name:[b.name for b in o.data.bones] for o in armatures},
                sockets=sockets,meshObjects=meshes,
                status='BLOCKED_UNVERIFIED_CHARACTER_ATTACHMENT',attachmentPerformed=False,
                reasons=['NO_REVIEWED_HAND_WAIST_ATTACHMENT_EVIDENCE'],**base.GATES)
    if not armatures: report['reasons'].append('NO_ARMATURE_IN_SOURCE')
    if 'Socket_Weapon_R' not in sockets: report['reasons'].append('NO_WEAPON_SOCKET_IN_SOURCE')
    if base.sha(path)!=expected_sha: raise ValueError('SOURCE_CHANGED_DURING_READ')
    return report


def extra_renders(output,objects):
    scene=bpy.context.scene; cam=scene.camera
    initial={o.name:o.hide_render for o in objects}
    paths=[]
    # Isolated views eliminate the previous side-view overlap.
    specs=[('saber_side','CH101_Saber',(-.47,0,.49),(3,0,.49),1.05),
           ('sheath_side','CH101_Sheath',(-.29,0,.35),(3,0,.35),.80),
           ('grip_guard_close','CH101_Saber',(-.47,0,.824),(-.32,-1,.86),.35),
           ('sheath_badge_close','CH101_Sheath',(-.29,0,.605),(-.15,-1,.67),.18)]
    clasp=bpy.data.objects['Ribbon_SingleClasp']; center=clasp.matrix_world@Vector((0,0,.023))
    specs.append(('ribbon_clasp_close','CH101_SignalRibbon_SINGLE',tuple(center),tuple(center+Vector((.08,-1,.12))),.16))
    try:
        for name,owner,center,position,scale in specs:
            for o in objects: o.hide_render=o.name!=owner and o.get('equipmentOwner')!=owner
            cam.data.ortho_scale=scale; cam.location=position
            cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler()
            file=output/(name+'.png'); scene.render.filepath=str(file)
            bpy.ops.render.render(write_still=True)
            paths.append(dict(view=name,file=file.name,sha256=base.sha(file),scope=owner))
    finally:
        for o in objects: o.hide_render=initial[o.name]
        cam.data.ortho_scale=1.23; cam.location=(1.5,-3,1.25)
        cam.rotation_euler=(Vector((0,0,.49))-cam.location).to_track_quat('-Z','Y').to_euler()
    return paths


def run(args):
    # Freeze CLI paths before loading/resetting any Blender scene. Blender's
    # renderer must not reinterpret a relative path against its own file base.
    args.art_root=args.art_root.resolve()
    args.output_dir=args.output_dir.resolve()
    args.character_blend=args.character_blend.resolve()
    refs=base.verify_references(args.art_root.resolve())
    if args.output_dir.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    attachment=inspect_character(args.character_blend,args.character_sha256)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects=build_details(); audit=base.audit(objects)
    materials={m.name for o in objects for m in o.data.materials}
    if len(materials)>6: raise ValueError('MATERIAL_BUDGET_EXCEEDED')
    args.output_dir.mkdir(parents=True)
    for ref in refs: bpy.data.images.load(ref['path']).pack()
    renders=base.render_views(args.output_dir)+extra_renders(args.output_dir,objects)
    blend=args.output_dir/'CH101_EquipmentHardware_NOT_PRODUCTION_v002.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend.resolve()))
    report=dict(schemaVersion='ch101-equipment-hardware-study-v002',strategyId=STRATEGY,
                status='PART_DETAIL_TECHNICAL_PASS_VISUAL_REVIEW_PENDING',artifactScope='EQUIPMENT_ONLY',
                **base.GATES,artCommit=base.ART_COMMIT,references=refs,
                meshAudit=audit,totalTriangles=sum(x['triangles'] for x in audit),
                uniqueMaterialCount=len(materials),canonicalSaberCount=1,canonicalRibbonCount=1,
                detailMeshCount=len(objects)-3,attachmentAudit=attachment,
                runtimeSocketMap=json.loads(bpy.context.scene['runtimeSocketMap']),
                duplicateAliasTransformCreated=False,fullCharacterScore=None,
                limitations=['ESTIMATED_DIMENSIONS_AND_DETAIL_PROPORTIONS','NO_CHARACTER_ATTACHMENT',
                             'NO_MECHANICAL_CLASP_OR_COLLISION_TEST','PROCEDURAL_TEXTURE_NOT_BAKED',
                             'GRIP_WRAP_RELIEF_AND_BLADE_EDGE_DETAIL_UNFINISHED',
                             'BODY_FACE_HAIR_OUTFIT_UNCHANGED','NO_RIG_LOD_PHYSICS_VALIDATION'],
                blendFile=blend.name,blendSha256=base.sha(blend),renders=renders)
    (args.output_dir/'equipment-hardware-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--art-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--character-blend',type=Path,required=True)
    parser.add_argument('--character-sha256',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(run(args),indent=2))
