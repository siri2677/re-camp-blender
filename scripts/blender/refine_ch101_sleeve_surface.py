"""Reversible sleeve-only surface study. No coordinate edits or source repaint."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_ch101_local_crossing as repair
import fit_ch101_upper_sleeve as fit

c = repair.c
SOURCE_SHA = 'e89357579ef64eda53bf8c37eda9942d898e23171f0f0bcb39f2fd833b7456b0'
SOURCE_OBJECT = 'CH101_UpperSleeveFit_STUDY_NOT_PRODUCTION'
BODY_OBJECT = 'CH101_SourceBody_DistalReplacement_TopologyRepair_NOT_PRODUCTION'
RESULT_OBJECT = 'CH101_SleeveSurface_STUDY_NOT_PRODUCTION'
STRATEGY = 'CH101_SLEEVE_SURFACE_TRIM_V001'
UV_NAME = 'SleeveTrimStudy'
TRIM_FRACTION = .24


def linear_color(hex_rgb):
    values = [int(hex_rgb[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values)


def structure_signature(obj):
    """Geometry, original UVs and weights; intentionally excludes new shading."""
    mesh = obj.data
    value = dict(vertices=[list(v.co) for v in mesh.vertices],
                 edges=[list(e.vertices) for e in mesh.edges],
                 polygons=[list(p.vertices) for p in mesh.polygons],
                 uv=[(u.name, [list(x.uv) for x in u.data]) for u in mesh.uv_layers if u.name != UV_NAME],
                 weights=[[(g.group, g.weight) for g in v.groups] for v in mesh.vertices],
                 groups=[g.name for g in obj.vertex_groups], transform=[list(r) for r in obj.matrix_world])
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def require_locked(scene):
    if any(scene.get(k) != v for k, v in c.base.GATES.items()):
        raise ValueError('SOURCE_GATE_NOT_LOCKED')


def trim_material(fraction):
    if not 0 < fraction <= .5:
        raise ValueError('TRIM_WIDTH_OUT_OF_REVIEW_RANGE')
    graphite, gold = linear_color('151518'), linear_color('D2A445')
    mat = c.base.material('SleeveSurface_narrow_gold_on_graphite', graphite)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    uv = nodes.new('ShaderNodeUVMap')
    uv.uv_map = UV_NAME
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(uv.outputs['UV'], separate.inputs[0])
    subtract = nodes.new('ShaderNodeMath')
    subtract.operation = 'SUBTRACT'
    subtract.inputs[1].default_value = .5
    links.new(separate.outputs['X'], subtract.inputs[0])
    absolute = nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    links.new(subtract.outputs[0], absolute.inputs[0])
    mask = nodes.new('ShaderNodeMath')
    mask.name = 'TrimHalfWidth'
    mask.operation = 'LESS_THAN'
    mask.inputs[1].default_value = fraction/2
    links.new(absolute.outputs[0], mask.inputs[0])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (*graphite, 1)
    mix.inputs[2].default_value = (*gold, 1)
    links.new(mask.outputs[0], mix.inputs[0])
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = .72
    links.new(mix.outputs[0], bsdf.inputs['Base Color'])
    return mat


def surface_copy(source, joined, cloth, fraction=TRIM_FRACTION):
    if not 0 < fraction <= .5:
        raise ValueError('TRIM_WIDTH_OUT_OF_REVIEW_RANGE')
    if [list(p.vertices) for p in source.data.polygons] != [list(p.vertices) for p in joined.data.polygons]:
        raise ValueError('JOINED_TOPOLOGY_CORRESPONDENCE_CHANGED')
    mapping = fit.sleeve_vertex_map(joined, cloth)
    inverse = {v: i for i, v in enumerate(mapping)}
    if len(mapping) != 512 or UV_NAME in source.data.uv_layers:
        raise ValueError('UNEXPECTED_SLEEVE_SOURCE_OR_ALREADY_APPLIED')
    # Locate original outer gold lanes by vertex correspondence, not face order.
    selected, smooth = [], []
    widths = []
    for p in source.data.polygons:
        if not all(v in inverse for v in p.vertices):
            continue
        ids = [inverse[v] for v in p.vertices]
        rings = {i//32 for i in ids}
        angles = {i % 32 for i in ids}
        if len(rings) == 2 and max(rings)-min(rings) == 1 and min(rings) != 7:
            smooth.append(p.index)
        if max(rings) >= 8:
            continue
        lane = next((j for j in (3, 19) if angles == {j, j+1}), None)
        if lane is not None and len(rings) == 2:
            selected.append((p.index, lane))
    if len(selected) != 28 or len(smooth) != 896:
        raise ValueError('SLEEVE_FACE_CORRESPONDENCE_CHANGED')
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    mesh = obj.data
    # Never edit shared material datablocks. Only replace two slots on the copy.
    cloth_slot = next(i for i, m in enumerate(mesh.materials) if m.name == 'SleeveStudy_graphite_fabric')
    trim_slot = next(i for i, m in enumerate(mesh.materials) if m.name == 'SleeveStudy_gold_woven_trim')
    fabric = c.base.material('SleeveSurface_graphite_151518', linear_color('151518'))
    fabric.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .72
    mesh.materials[cloth_slot] = fabric
    mesh.materials[trim_slot] = trim_material(fraction)
    uv = mesh.uv_layers.new(name=UV_NAME)
    for index, lane in selected:
        p = mesh.polygons[index]
        if p.material_index != trim_slot:
            raise ValueError('SOURCE_GOLD_LANE_MATERIAL_CHANGED')
        for loop_index in p.loop_indices:
            old_id = inverse[mesh.loops[loop_index].vertex_index]
            uv.data[loop_index].uv = (old_id % 32-lane, (old_id//32)/7)
    for k in range(8):
        for lane in (3, 19):
            a, b = [obj.matrix_world @ mesh.vertices[mapping[k*32+j]].co for j in (lane, lane+1)]
            widths.append((a-b).length*fraction)
    for index in smooth:
        mesh.polygons[index].use_smooth = True
    # Existing image-based materials must continue to use the original UV map.
    mesh.uv_layers.active_index = source.data.uv_layers.active_index
    for layer in mesh.uv_layers:
        layer.active_render = layer.name == source.data.uv_layers.active.name
    c.base.mark(obj)
    obj['designApproved'] = False
    obj['surfaceStudyOnly'] = True
    if structure_signature(source) != structure_signature(obj):
        raise ValueError('GEOMETRY_OR_EXISTING_UV_CHANGED')
    return obj, dict(trimTriangleCount=len(selected), smoothSideTriangleCount=len(smooth),
                     goldLaneCoverageFraction=fraction, goldWidthSampleRangeMeters=[min(widths), max(widths)],
                     widthIsCrossRingSampleNotExactSurfaceWidth=True,
                     graphiteSRGB='151518', goldSRGB='D2A445', sRGBConvertedToSceneLinear=True,
                     newUVLayer=UV_NAME, existingUVUnchanged=True, coordinatesUnchanged=True,
                     cuffAndBridgeShadingUnchanged=True, upperSourceTrimAlignmentVerified=False)


def render(output, before, after, body, parts, center, axis):
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type in ('MESH', 'CURVE', 'LIGHT'):
            obj.hide_render = True
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.view_settings.exposure = -.5
    camera = scene.camera
    camera.data.type = 'ORTHO'
    lights = []
    for name, delta, energy in [('key', (-.4, -.5, .6), 65), ('fill', (.3, .4, .3), 40)]:
        data = bpy.data.lights.new('SleeveSurface_'+name, 'AREA')
        data.energy, data.size = energy, .4
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        lights.append((obj, Vector(delta)))
    rows = []
    def shot(name, target, offset, scale, active):
        for obj in [body, before, after]+parts:
            obj.hide_render = obj not in active
        for light, delta in lights:
            light.location = target+delta
            light.rotation_euler = (target-light.location).to_track_quat('-Z', 'Y').to_euler()
        camera.location = target+Vector(offset)
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = scale
        path = output/(name+'.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        rows.append(dict(file=path.name, sha256=c.base.sha(path)))
    for label, obj in [('before', before), ('after', after)]:
        for view, offset in [('front', (-.25, -.7, .15)), ('back', (.25, .7, .15)), ('side', (-.7, .05, .1))]:
            shot(label+'_'+view, center+axis*.055, offset, .29, [body, obj]+parts)
    shot('assembly_front', Vector((0, 0, .84)), (0, -3, .1), 1.95, [body, after]+parts)
    return rows


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    require_locked(scene)
    originals = [o for o in scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    invariants = {o.name: repair.invariant_signature(o) for o in originals}
    before = bpy.data.objects[SOURCE_OBJECT]
    body = bpy.data.objects[BODY_OBJECT]
    obj, operation = surface_copy(before, bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
                                  bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'])
    parts = [o for o in originals if o.name.startswith('PAIR_STUDY_')]
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center = hand.matrix_world @ Vector()
    axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    qa = fit.join.assess(obj, dict(retainedNormalMismatches=0, reversedTransitionFaces={}), hand, [o for o in parts if o != hand])
    qa['topology']['selfIntersectionTestPerformed'] = True
    qa['topology']['selfIntersectionTestScope'] = 'NON_ADJACENT_BVH_SHARED_VERTEX_PAIRS_EXCLUDED'
    overlap = c.fit.overlap_report(body, [obj]+parts, center)
    if not qa['eligible'] or any(r['uniqueEquipmentTrianglesCrossing'] for r in overlap):
        raise ValueError('STATIC_ASSEMBLY_VALIDATION_FAILED')
    output.mkdir(parents=True)
    renders = [] if args.no_render else render(output, before, obj, body, parts, center, axis)
    if c.guide.digest(originals) != digest or any(repair.invariant_signature(o) != invariants[o.name] for o in originals):
        raise ValueError('PRESERVED_ORIGINAL_CHANGED')
    visible = repair.replacement.configure_review_viewport([body, obj]+parts)
    for old in scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [body, obj]+parts
    require_locked(scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_SleeveSurface_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='SLEEVE_SURFACE_STUDY_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  operation=operation, qa=qa, bodyPartOverlap=overlap, originalsPreserved=True,
                  defaultVisibleMeshObjects=visible, fullCharacterScore=None, designApproved=False,
                  rigBound=False, weldedToBody=False, blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['MATERIAL_AND_SHADING_ONLY_NO_CONTOUR_CHANGE', 'UPPER_SOURCE_TEXTURE_ARTIFACTS_REMAIN',
                               'TRIM_WIDTH_AND_PLACEMENT_ARE_AUTHORED_HYPOTHESIS', 'PROCEDURAL_SHADER_NOT_UNITY_READY',
                               'UNWELDED_BODY_TEMPORARY_CAP_NO_RIG', 'NO_FULL_CHARACTER_QUALITY_OR_GATE_B_APPROVAL'])
    (output/'sleeve-surface-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--art-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--no-render', action='store_true')
    result = run(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: result[k] for k in ('status', 'operation', 'blendSha256')}, indent=2))
