"""Review-only selected-source patch albedo bake with independent hit coverage."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_ch101_patch_uv as uv

patch, seam, surface, c = uv.patch, uv.seam, uv.surface, uv.c
SOURCE_SHA = uv.SOURCE_SHA
STRATEGY = 'CH101_BOUNDED_PATCH_ALBEDO_BAKE_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_PatchBake_NOT_PRODUCTION'
ATLAS_UV = 'UpperPatchBakeUV'
SIZE = 1024


def verify_preservation(target, obj, first):
    """Fail before QA if anything beyond patch shader/added atlas changed."""
    def geometry(o):
        return ([tuple(v.co) for v in o.data.vertices],
                [tuple(p.vertices) for p in o.data.polygons],
                [p.use_smooth for p in o.data.polygons],
                [tuple(row) for row in o.matrix_world],
                [g.name for g in o.vertex_groups],
                [[(g.group, g.weight) for g in v.groups] for v in o.data.vertices])
    if geometry(target) != geometry(obj):
        raise ValueError('BAKE_CHANGED_GEOMETRY_OR_WEIGHTS')
    for name in (seam.trim.upper.MASK, seam.trim.DISTANCE):
        if ([v.value for v in target.data.attributes[name].data] !=
                [v.value for v in obj.data.attributes[name].data]):
            raise ValueError('BAKE_CHANGED_MASK')
    for layer in target.data.uv_layers:
        if ([tuple(v.uv) for v in layer.data] !=
                [tuple(v.uv) for v in obj.data.uv_layers[layer.name].data]):
            raise ValueError('BAKE_CHANGED_ORIGINAL_UV')
    if (list(obj.data.materials)[:-1] != list(target.data.materials) or
            [p.material_index for p in obj.data.polygons[:first]] !=
            [p.material_index for p in target.data.polygons[:first]]):
        raise ValueError('BAKE_CHANGED_RETAINED_MATERIALS')
    return dict(retainedNormalMismatches=0, copiedUVErrors=0)


def subset(source, faces, name):
    mesh = bpy.data.meshes.new(name)
    selected = [source.data.polygons[i] for i in faces]
    mesh.from_pydata([source.matrix_world @ v.co for v in source.data.vertices], [], [list(p.vertices) for p in selected])
    mesh.update()
    for material in source.data.materials:
        mesh.materials.append(material)
    for new, old in zip(mesh.polygons, selected):
        new.material_index, new.use_smooth = old.material_index, old.use_smooth
    for original in source.data.uv_layers:
        layer = mesh.uv_layers.new(name=original.name)
        for new, old in zip(mesh.polygons, selected):
            for a, b in zip(new.loop_indices, old.loop_indices):
                layer.data[a].uv = original.data[b].uv
        layer.active_render = original.active_render
    mesh.uv_layers.active_index = source.data.uv_layers.active_index
    for name in (seam.trim.upper.MASK, seam.trim.DISTANCE):
        field = mesh.attributes.new(name, 'FLOAT', 'POINT')
        for a, b in zip(field.data, source.data.attributes[name].data):
            a.value = b.value
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def atlas_layout(target):
    if len(target.data.polygons) != 321:
        raise ValueError('PATCH_FACE_COUNT_CHANGED')
    layer = target.data.uv_layers.new(name=ATLAS_UV)
    target.data.uv_layers.active_index = len(target.data.uv_layers)-1
    layer.active_render = True
    grid = math.ceil(math.sqrt(len(target.data.polygons)))
    cell = SIZE/grid
    rows = []
    for p in target.data.polygons:
        if len(p.vertices) != 3:
            raise ValueError('PATCH_NOT_TRIANGLES')
        x, y = p.index % grid*cell, p.index//grid*cell
        values = [((x+5)/SIZE, (y+5)/SIZE), ((x+cell-5)/SIZE, (y+5)/SIZE), ((x+5)/SIZE, (y+cell-5)/SIZE)]
        for loop, value in zip(p.loop_indices, values):
            layer.data[loop].uv = value
        rows.append(values)
    return rows


def bake_select(source, target):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (source, target):
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = target


def bake(source, target, operation, output):
    removed = set(operation['removedSourcePolygons'])
    source_faces = set(removed)
    for faces in uv.edge_faces(source).values():
        if set(faces) & removed:
            source_faces.update(faces)
    support = {i for face in source_faces for i in source.data.polygons[face].vertices}
    if any(not (-.40 < (source.matrix_world @ source.data.vertices[i].co).x < -.17
                and .91 < (source.matrix_world @ source.data.vertices[i].co).z < 1.14) for i in support):
        raise ValueError('BAKE_COLLAR_OUTSIDE_INSPECTED_FOREARM')
    source_part = subset(source, sorted(source_faces), 'BAKE_SOURCE_PRESERVED_PATCH_COPY')
    first = operation['retainedPolygonCount']
    target_part = subset(target, range(first, len(target.data.polygons)), 'BAKE_TARGET_PATCH_COPY')
    atlas = atlas_layout(target_part)
    mat = c.base.material('UpperPatch_BakeTarget_NOT_FINAL', (.2, .2, .2))
    target_part.data.materials.clear()
    target_part.data.materials.append(mat)
    for face in target_part.data.polygons:
        face.material_index = 0
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    mat.node_tree.nodes.active = node
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.use_cage = False
    scene.render.bake.cage_extrusion = .020
    scene.render.bake.max_ray_distance = .060
    scene.render.bake.margin = 3
    scene.render.bake.use_clear = True
    coverage = bpy.data.images.new('UpperPatch_BakeCoverage', width=SIZE, height=SIZE, alpha=True, float_buffer=True)
    coverage.colorspace_settings.name = 'Non-Color'
    node.image = coverage
    coverage_source = source_part.copy()
    coverage_source.data = source_part.data.copy()
    bpy.context.scene.collection.objects.link(coverage_source)
    white = bpy.data.materials.new('UpperPatch_CoverageWhite')
    white.use_nodes = True
    white.node_tree.nodes.clear()
    emission = white.node_tree.nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (1, 1, 1, 1)
    out = white.node_tree.nodes.new('ShaderNodeOutputMaterial')
    white.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
    coverage_source.data.materials.clear()
    coverage_source.data.materials.append(white)
    for face in coverage_source.data.polygons:
        face.material_index = 0
    bake_select(coverage_source, target_part)
    bpy.ops.object.bake(type='EMIT')
    pixels = np.empty(SIZE*SIZE*4, dtype=np.float32)
    coverage.pixels.foreach_get(pixels)
    pixels = pixels.reshape(SIZE, SIZE, 4)
    misses, checked = [], 0
    for index, triangle in enumerate(atlas):
        for a, b in ((.6, .2), (.2, .6), (.2, .2), (.4, .4), (.4, .2), (.2, .4)):
            q = np.array(triangle[0])*a+np.array(triangle[1])*b+np.array(triangle[2])*(1-a-b)
            x, y = [min(SIZE-1, int(v*SIZE)) for v in q]
            checked += 1
            if float(pixels[y, x, :3].min()) < .95:
                misses.append(dict(face=index, pixel=[x, y], value=float(pixels[y, x, :3].min())))
    print(json.dumps(dict(bakeCoverageSamples=checked, misses=len(misses), examples=misses[:5])))
    if misses:
        raise ValueError('BAKE_SOURCE_COVERAGE_INCOMPLETE:'+str(len(misses)))
    image = bpy.data.images.new('CH101_UpperPatch_Albedo_NOT_PRODUCTION', width=SIZE, height=SIZE, alpha=False)
    image.colorspace_settings.name = 'sRGB'
    node.image = image
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bake_select(source_part, target_part)
    bpy.ops.object.bake(type='DIFFUSE')
    output.mkdir(parents=True)
    image.filepath_raw = str(output/'upper-patch-albedo.png')
    image.file_format = 'PNG'
    image.save()
    image.pack()
    coverage.filepath_raw = str(output/'upper-patch-coverage.png')
    coverage.file_format = 'PNG'
    coverage.save()
    obj = target.copy()
    obj.data = target.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    layer = obj.data.uv_layers.new(name=ATLAS_UV)
    for p, row in zip(obj.data.polygons[first:], atlas):
        for loop, value in zip(p.loop_indices, row):
            layer.data[loop].uv = value
    # Explicit shader UV leaves every retained material's original active UV intact.
    obj.data.uv_layers.active_index = target.data.uv_layers.active_index
    for l in obj.data.uv_layers:
        l.active_render = l.name == target.data.uv_layers.active.name
    baked = c.base.material('UpperPatch_BakedAlbedo_REVIEW_NOT_FINAL', (.2, .2, .2))
    uv_node = baked.node_tree.nodes.new('ShaderNodeUVMap')
    uv_node.uv_map = ATLAS_UV
    texture = baked.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    baked.node_tree.links.new(uv_node.outputs[0], texture.inputs['Vector'])
    baked.node_tree.links.new(texture.outputs['Color'], baked.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    baked.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .72
    slot = len(obj.data.materials)
    obj.data.materials.append(baked)
    for face in obj.data.polygons[first:]:
        face.material_index = slot
    c.base.mark(obj)
    for helper in (source_part, coverage_source, target_part):
        mesh = helper.data
        bpy.data.objects.remove(helper, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    return obj, dict(bakeCoverageSamples=checked, missedCoverageSamples=0, atlasSize=SIZE,
                     atlasUV=ATLAS_UV, bakedPatchFaces=321, sourceFaces=len(source_faces),
                     sourceFaceIndices=sorted(source_faces), addedSourceCollarFaces=len(source_faces-removed),
                     sourceScope='REMOVED_FOREARM_PATCH_PLUS_ONE_EDGE_RING_WITH_FOREARM_BOUNDS', useSelectedToActive=True,
                     cageExtrusionMeters=.020, maxRayDistanceMeters=.060, geometryAndMasksUnchanged=True,
                     originalUVLayersPreserved=True, newShaderUsesExplicitAtlasUV=True,
                     albedoFile='upper-patch-albedo.png', albedoSha256=c.base.sha(output/'upper-patch-albedo.png'),
                     coverageFile='upper-patch-coverage.png', coverageSha256=c.base.sha(output/'upper-patch-coverage.png'))


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    operation = json.loads((source.parent/'upper-patch-report.json').read_text(encoding='utf-8'))['operation']
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    signatures = {o.name: surface.repair.invariant_signature(o) for o in originals}
    original, target = bpy.data.objects[patch.contour.RESULT_OBJECT], bpy.data.objects[patch.RESULT_OBJECT]
    diagnosis = uv.audit(original, target, operation)
    obj, bake_report = bake(original, target, operation, output)
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center = hand.matrix_world @ Vector()
    axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    preservation = verify_preservation(target, obj, operation['retainedPolygonCount'])
    qa = seam.assess(obj, parts, preservation)
    if not qa['eligible']:
        raise ValueError('BAKED_PATCH_STATIC_QA_REJECTED')
    renders = [] if args.no_render else seam.trim.upper.render(output, target, obj, parts, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != signatures[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_PatchAlbedoBake_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    report = dict(strategyId=STRATEGY, status='PATCH_ALBEDO_BAKE_REVIEW_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  diagnosis=diagnosis, bake=bake_report, qa=qa, originalsPreserved=True,
                  defaultVisibleMeshObjects=visible, fullCharacterScore=None, rigBound=False,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['ALBEDO_ONLY_NOT_COMPLETE_PBR_BAKE', 'SOURCE_ARTIFACTS_MAY_BE_INHERITED',
                               'SAMPLED_COVERAGE_NOT_EVERY_TEXEL_PROOF', 'NO_HUMAN_GATE_B_OR_UNITY_APPROVAL'])
    (output/'patch-albedo-bake-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--art-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--no-render', action='store_true')
    r = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: r[k] for k in ('status', 'blendSha256', 'bake')}, indent=2))
