"""Reference-guided part authoring, NOT a full-character or production candidate.

One closed lofted saber, a hollow-mouth sheath and one thick swept ribbon.
Dimensions/depth/path are authored estimates, not recovered CAD measurements.
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

STRATEGY = 'CH101_REFERENCE_EQUIPMENT_LOFT_STUDY_V001'
ART_COMMIT = 'b6c9b3128358e061eee6184230929413eba84101'
REFERENCES = {
    'CH101_Rin_CharacterSheet_APPROVED_v001.png': '0ce9c2d94236059966f3159737a6b056716720ff9e3b9f3f75592f4d9b6f561c',
    'CH101_Rin_EquipmentSheet_REVIEW_v001.png': 'b9a01637e70518fe338e686345442579f36f2dc2190ae32ddda53f26cd00325b',
}
GATES = dict(sourceStatus='AI_GENERATED_CANDIDATE_NOT_PRODUCTION',
             gateB='PENDING_HUMAN_REVIEW', unityInputAllowed=False,
             productionPromotionAllowed=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_references(art_root):
    # The sandbox account differs from the checkout owner on Windows. Trust
    # only this explicitly supplied art directory for this read-only command;
    # never change global Git configuration or accept a wildcard safe directory.
    commit = subprocess.check_output(['git', '-c', 'safe.directory='+art_root.resolve().as_posix(),
                                      '-C', str(art_root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != ART_COMMIT:
        raise ValueError('ART_COMMIT_MISMATCH')
    result = []
    for name, expected in REFERENCES.items():
        path = art_root / 'art_refs/characters/rin/concept' / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('REFERENCE_SHA256_MISMATCH:' + name)
        result.append(dict(path=str(path), sha256=expected))
    return result


def mark(data):
    for key, value in GATES.items():
        data[key] = value


def material(name, rgb, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = .34 if metallic else .58
    return mat


def patterned_material(name, mode):
    """UV-only surface pattern; no image projection or texture image editing."""
    mat = material(name, (.005, .55, .62), .25)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tex = nodes.new('ShaderNodeTexCoord')
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex.outputs['UV'], sep.inputs[0])

    def calc(op, a, b):
        n = nodes.new('ShaderNodeMath'); n.operation = op
        for inp, val in zip(n.inputs, (a, b)):
            if isinstance(val, (int, float)):
                inp.default_value = val
            else:
                links.new(val, inp)
        return n.outputs[0]

    u, v = sep.outputs['X'], sep.outputs['Y']
    if mode == 'ribbon':
        a = calc('PINGPONG', calc('ADD', calc('MULTIPLY', v, 18), u), 1)
        b = calc('PINGPONG', calc('SUBTRACT', calc('MULTIPLY', v, 18), u), 1)
        factor = calc('MAXIMUM', calc('LESS_THAN', a, .08), calc('LESS_THAN', b, .08))
        colors = ((.005, .51, .59, 1), (.64, .37, .075, 1))
    else:
        a = calc('FRACT', calc('ADD', calc('MULTIPLY', v, 10), u), 0)
        factor = calc('LESS_THAN', a, .23)
        colors = ((.012, .017, .022, 1), (.005, .64, .73, 1))
    mix = nodes.new('ShaderNodeMixRGB')
    links.new(factor, mix.inputs[0])
    mix.inputs[1].default_value, mix.inputs[2].default_value = colors
    links.new(mix.outputs[0], nodes.get('Principled BSDF').inputs['Base Color'])
    return mat


def loft(name, rings, material_ids, materials, broad_ribbon_uv=False):
    """One connected closed surface, with longitudinal UV coordinates."""
    count = len(rings[0])
    centers = [sum((Vector(v) for v in ring), Vector())/count for ring in rings]
    lengths = [0.0]
    for a,b in zip(centers,centers[1:]):
        lengths.append(lengths[-1]+(b-a).length)
    verts = [v for ring in rings for v in ring]
    faces = [tuple(reversed(range(count)))]
    ids = [material_ids[0]]
    for row in range(len(rings)-1):
        for col in range(count):
            faces.append((row*count+col, row*count+(col+1)%count,
                          (row+1)*count+(col+1)%count, (row+1)*count+col))
            ids.append(material_ids[row])
    faces.append(tuple(range((len(rings)-1)*count, len(rings)*count)))
    ids.append(material_ids[-1])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.data.collections['MODEL_EQUIPMENT'].objects.link(obj)
    for mat in materials:
        mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name='EquipmentUV')
    for poly, matid in zip(mesh.polygons, ids):
        poly.material_index = matid
        cols = [mesh.loops[i].vertex_index % count for i in poly.loop_indices]
        seam = 0 in cols and count-1 in cols
        for i in poly.loop_indices:
            vertex = mesh.loops[i].vertex_index
            col = vertex % count
            u = (0,1,1,0)[col] if broad_ribbon_uv else (count if seam and col == 0 else col)/count
            uv.data[i].uv = (u, lengths[vertex//count]/max(lengths[-1],1e-8))
    mark(obj)
    obj['semanticPart'] = name
    obj['attachmentStatus'] = 'UNATTACHED_PART_STUDY_NOT_APPROVED'
    return obj


def cross_ring(z, width, depth, x=0):
    # Beveled rectangular cross-section, not flat planes or a voxel surface.
    return [(x+u*width, v*depth, z) for u,v in
            [(-.7,-1),(.7,-1),(1,-.7),(1,.7),(.7,1),(-.7,1),(-1,.7),(-1,-.7)]]


def build_geometry():
    collection = bpy.data.collections.new('MODEL_EQUIPMENT')
    bpy.context.scene.collection.children.link(collection)
    mats = [material('Graphite', (.009,.011,.014)),
            material('Gold', (.64,.37,.075), .8),
            material('Steel', (.55,.63,.68), .9),
            patterned_material('Saber_Cyan_Diagonal', 'blade'),
            patterned_material('SignalRibbon_Gold_Lattice', 'ribbon')]
    saber_rings = [cross_ring(*row) for row in [
        (.02,.001,.001,-.014),(.055,.017,.004),(.68,.017,.004),
        (.692,.021,.008),(.699,.048,.016),(.714,.048,.016),
        (.721,.022,.012),(.735,.018,.012),(.915,.018,.012),
        (.924,.022,.014),(.944,.022,.014),(.951,.014,.010)]]
    saber = loft('CH101_Saber', saber_rings, [2,3,2,1,1,1,0,3,1,1,1], mats)
    saber.location.x = -.47
    sheath_rows = [(.02,.017,.008),(.033,.024,.013),(.053,.024,.013),
                   (.66,.024,.013),(.68,.027,.015),(.698,.027,.015),
                   (.698,.020,.009),(.67,.020,.009),(.06,.015,.006)]
    sheath = loft('CH101_Sheath', [cross_ring(*r) for r in sheath_rows], [1,1,0,0,1,1,0,0], mats)
    sheath.location.x = -.29
    rings = []
    for i in range(81):
        t = i/80
        angle = -.40 + t*5.55
        center = Vector((.22+.26*math.cos(angle), .065*math.sin(2*angle), .47+.34*math.sin(angle)))
        width = .025*(1-.8*max(0,(t-.92)/.08))
        side = Vector((math.cos(angle), 0, math.sin(angle)))
        normal = Vector((0, 1, 0))
        rings.append([tuple(center + side*a*width + normal*b*.001)
                      for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    ribbon = loft('CH101_SignalRibbon_SINGLE', rings, [1 if i<2 else 4 for i in range(80)], mats, broad_ribbon_uv=True)

    def socket(name, parent, point):
        obj = bpy.data.objects.new(name, None); collection.objects.link(obj)
        obj.empty_display_type = 'ARROWS'; obj.empty_display_size = .045
        obj.parent = parent; obj.location = point; mark(obj)
        obj['attachmentStatus'] = 'AUTHORED_PART_ENDPOINT_NOT_CHARACTER_FIT'
        return obj

    grip = socket('Socket_Weapon_R', saber, (0,0,.82))
    socket('Socket_BladeTip', saber, (-.014,0,.02))
    # Two contractual endpoint labels on ONE ribbon; neither means a second ribbon.
    socket('Socket_Ribbon_L', ribbon, tuple(sum((Vector(v) for v in rings[0]), Vector())/4))
    socket('Socket_Ribbon_R', ribbon, tuple(sum((Vector(v) for v in rings[-1]), Vector())/4))
    grip['runtimeAlias'] = 'Socket_Equipment_Primary'
    bpy.context.scene['runtimeSocketMap'] = json.dumps({'Socket_Equipment_Primary':'Socket_Weapon_R'})
    mark(bpy.context.scene)
    return [saber, sheath, ribbon]


def audit(objects):
    result = []
    for obj in objects:
        mesh = obj.data; mesh.calc_loop_triangles()
        bm = bmesh.new(); bm.from_mesh(mesh)
        nonmanifold = sum(not e.is_manifold for e in bm.edges)
        remaining = set(bm.verts); components = 0
        while remaining:
            todo = [remaining.pop()]; components += 1
            while todo:
                v = todo.pop()
                for e in v.link_edges:
                    other = e.other_vert(v)
                    if other in remaining:
                        remaining.remove(other); todo.append(other)
        bm.free()
        result.append(dict(object=obj.name, vertices=len(mesh.vertices),
                           triangles=len(mesh.loop_triangles), connectedComponents=components,
                           nonManifoldEdges=nonmanifold, hasUV=bool(mesh.uv_layers)))
    if sum(o['triangles'] for o in result)>2000 or any(o['nonManifoldEdges'] or o['connectedComponents']!=1 or not o['hasUV'] for o in result):
        raise ValueError('EQUIPMENT_GEOMETRY_CHECK_FAILED')
    return result


def render_views(output):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 24
    scene.cycles.device = 'CPU'
    scene.render.resolution_x = 1100; scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new('EquipmentStudio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.13,.16,.21,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .45
    for name, loc, power, size in [('Key',(-2,-3,3),300,3),('Fill',(2,-1,1),120,2),('Rim',(0,2,2),240,2)]:
        data = bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size
        obj = bpy.data.objects.new(name,data); scene.collection.objects.link(obj); obj.location=loc
        obj.rotation_euler=(Vector((0,0,.5))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('ReviewCamera'); cam=bpy.data.objects.new('ReviewCamera',data)
    scene.collection.objects.link(cam); scene.camera=cam; data.type='ORTHO'; data.ortho_scale=1.23
    paths=[]
    for name,loc in [('front',(0,-3,.5)),('back',(0,3,.5)),('three_quarter',(1.5,-3,1.25)),('side',(3,0,.5))]:
        cam.location=loc; cam.rotation_euler=(Vector((0,0,.49))-cam.location).to_track_quat('-Z','Y').to_euler()
        path=output/(name+'.png'); scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(dict(view=name, file=path.name, sha256=sha(path)))
    return paths


def run(art_root, output, render=False):
    refs = verify_references(art_root)
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    output.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = build_geometry(); checks = audit(objects)
    for ref in refs:
        bpy.data.images.load(ref['path']).pack()
    renders = render_views(output) if render else []
    blend = output/'CH101_EquipmentStudy_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend.resolve()))
    report = dict(schemaVersion='ch101-equipment-part-study-v001', strategyId=STRATEGY,
                  status='PART_STUDY_TECHNICAL_PASS_NOT_FULL_CHARACTER', **GATES,
                  artifactScope='EQUIPMENT_ONLY', implementationRevision='PHYSICAL_LENGTH_UV_FIX_V002',
                  artCommit=ART_COMMIT, references=refs,
                  meshAudit=checks, totalTriangles=sum(x['triangles'] for x in checks),
                  uniqueMaterialCount=len({m.name for o in objects for m in o.data.materials}),
                  canonicalSaberCount=1, canonicalRibbonCount=1,
                  runtimeSocketMap={'Socket_Equipment_Primary':'Socket_Weapon_R'},
                  duplicateAliasTransformCreated=False, fullCharacterScore=None,
                  fullCharacterStrictQa='NOT_RUN_INAPPLICABLE_TO_PART_ONLY_STUDY',
                  limitations=['ESTIMATED_SCALE_DEPTH_AND_RIBBON_PATH','NO_CHARACTER_ATTACHMENT_FIT',
                               'CLASP_POMMEL_LOOP_AND_SHEATH_ORNAMENT_DETAIL_INCOMPLETE',
                               'BODY_FACE_HAIR_OUTFIT_UNCHANGED','PROCEDURAL_MATERIAL_NOT_BAKED',
                               'NO_RIG_LOD_OR_PHYSICS_VALIDATION'],
                  blendFile=blend.name, blendSha256=sha(blend), renders=renders)
    (output/'equipment-study-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--art-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(run(args.art_root.resolve(),args.output_dir.resolve(),args.render),indent=2))
