"""Local clothing-material hypothesis on a preserved body copy, not segmentation."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refine_ch101_sleeve_surface as surface

c = surface.c
SOURCE_SHA = 'f627a89f822bc7d48269bb34b99415aec6e16be62279e0ad92108df2ce444f66'
STRATEGY = 'CH101_UPPER_SLEEVE_LOCAL_MATERIAL_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_UpperMaterial_NOT_PRODUCTION'
MASK = 'UpperSleeveReviewMask'


def smoothstep(a, b, x):
    t = max(0., min(1., (x-a)/(b-a)))
    return t*t*(3-2*t)


def point_weight(point, center, axis):
    delta = point-center
    z = delta.dot(axis)
    radial = (delta-axis*z).length
    return (smoothstep(.084, .098, z) * (1-smoothstep(.185, .225, z))
            * (1-smoothstep(.060, .075, radial)))


def region_weights(body, center, axis):
    center, axis = Vector(center), Vector(axis)
    if abs(axis.length-1) > 1e-5:
        raise ValueError('MASK_AXIS_MUST_BE_UNIT')
    points = [body.matrix_world@v.co for v in body.data.vertices]
    weights = [point_weight(p, center, axis) for p in points]
    selected = {i for i, w in enumerate(weights) if w > 0}
    if not 50 <= len(selected) <= 350:
        raise ValueError('UNEXPECTED_LOCAL_MASK_VERTEX_COUNT')
    graph = {i: set() for i in selected}
    for e in body.data.edges:
        a, b = e.vertices
        if a in selected and b in selected:
            graph[a].add(b)
            graph[b].add(a)
    visited, stack = set(), [min(selected)]
    while stack:
        i = stack.pop()
        if i not in visited:
            visited.add(i)
            stack.extend(graph[i]-visited)
    if visited != selected:
        raise ValueError('MASK_REACHES_DISCONNECTED_REGION')
    affected = [p.index for p in body.data.polygons if any(i in selected for i in p.vertices)]
    support = {i for p in affected for i in body.data.polygons[p].vertices}
    # Guard the full interpolated support, not only vertices with positive masks.
    if any(not (-.40 < points[i].x < -.17 and .91 < points[i].z < 1.14) for i in support):
        raise ValueError('MASK_SUPPORT_OUTSIDE_INSPECTED_FOREARM')
    return weights, dict(weightedVertexCount=len(selected), affectedPolygonCount=len(affected),
                         affectedPolygonIndices=affected, vertexIndices=sorted(selected),
                         fullWeightVertexCount=sum(w > .999999 for w in weights),
                         axialWindowMeters=[.084, .098, .185, .225], radialFadeMeters=[.060, .075],
                         supportBoundsWorld=[[min(points[i][k] for i in support), max(points[i][k] for i in support)] for k in range(3)],
                         connectedMask=True, anatomicalOrSemanticSegmentationApproved=False,
                         maskInterpolation='POINT_ATTRIBUTE_LINEAR_OVER_SOURCE_TRIANGLES')


def material_copy(source, weights):
    if MASK in source.data.attributes:
        raise ValueError('MASK_ALREADY_PRESENT')
    if len(weights) != len(source.data.vertices) or any(not 0 <= w <= 1 for w in weights):
        raise ValueError('INVALID_MASK_WEIGHTS')
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    attr = obj.data.attributes.new(MASK, 'FLOAT', 'POINT')
    for item, value in zip(attr.data, weights):
        item.value = value
    for i, original in enumerate(source.data.materials):
        if original.name.startswith('INTERNAL_STUDY_CAP'):
            continue
        mat = original.copy()
        mat.name = 'UpperSleeveLocal_'+original.name
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
        old_socket = output.inputs['Surface'].links[0].from_socket
        attribute = nodes.new('ShaderNodeAttribute')
        attribute.attribute_name = MASK
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.name = 'LocalGraphiteCloth'
        bsdf.inputs['Base Color'].default_value = (*surface.linear_color('151518'), 1)
        bsdf.inputs['Roughness'].default_value = .72
        mix = nodes.new('ShaderNodeMixShader')
        mix.name = 'BoundedClothingMask'
        links.new(attribute.outputs['Fac'], mix.inputs[0])
        links.new(old_socket, mix.inputs[1])
        links.new(bsdf.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs['Surface'])
        obj.data.materials[i] = mat
    c.base.mark(obj)
    obj['localMaterialHypothesisOnly'] = True
    obj['trimRestored'] = False
    if surface.structure_signature(obj) != surface.structure_signature(source):
        raise ValueError('GEOMETRY_UV_OR_WEIGHTS_CHANGED')
    return obj


def diagnostic_copy(source):
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = 'DIAGNOSTIC_UpperSleeveMask_NOT_CLOTHING'
    bpy.context.scene.collection.objects.link(obj)
    mat = c.base.material('UpperSleeveMask_gray_orange', (.16, .19, .22))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    attr = nodes.new('ShaderNodeAttribute')
    attr.attribute_name = MASK
    mix = nodes.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (.16, .19, .22, 1)
    mix.inputs[2].default_value = (.95, .15, .015, 1)
    links.new(attr.outputs['Fac'], mix.inputs[0])
    links.new(mix.outputs[0], nodes.get('Principled BSDF').inputs['Base Color'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    c.base.mark(obj)
    return obj


def render(output, before, after, parts, center, axis):
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type in ('MESH', 'CURVE', 'LIGHT'):
            obj.hide_render = True
    diagnostic = diagnostic_copy(after)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.view_settings.exposure = -.5
    camera = scene.camera
    camera.data.type = 'ORTHO'
    lights = []
    for name, delta, energy in [('key', (-.4, -.5, .6), 65), ('fill', (.3, .4, .3), 40)]:
        data = bpy.data.lights.new('UpperMaterial_'+name, 'AREA')
        data.energy, data.size = energy, .4
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        lights.append((obj, Vector(delta)))
    rows = []
    def shot(name, target, offset, scale, objects):
        for obj in [before, after, diagnostic]+parts:
            obj.hide_render = obj not in objects
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
        for view, offset in [('front', (-.25, -.7, .15)), ('side', (-.7, .05, .1)), ('back', (.25, .7, .15))]:
            shot(label+'_'+view, center+axis*.14, offset, .43, [obj]+parts)
    shot('mask_context', center+axis*.14, (-.25, -.7, .15), .70, [diagnostic]+parts)
    shot('assembly_front', Vector((0, 0, .84)), (0, -3, .1), 1.95, [after]+parts)
    diagnostic.hide_render = True
    return rows


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    invariants = {o.name: surface.repair.invariant_signature(o) for o in originals}
    body = bpy.data.objects[surface.BODY_OBJECT]
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center = hand.matrix_world@Vector()
    axis = (hand.matrix_world.to_3x3()@Vector((0, 0, -1))).normalized()
    weights, region = region_weights(body, center, axis)
    obj = material_copy(body, weights)
    parts = [bpy.data.objects[surface.RESULT_OBJECT]]+[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    pairs = surface.repair.crossing_pairs(obj)[2]
    overlaps = c.fit.overlap_report(obj, parts, center)
    if pairs or any(r['uniqueEquipmentTrianglesCrossing'] for r in overlaps):
        raise ValueError('STATIC_ASSEMBLY_CROSSING')
    output.mkdir(parents=True)
    renders = [] if args.no_render else render(output, body, obj, parts, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != invariants[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = surface.repair.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_UpperSleeveMaterial_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='LOCAL_CLOTHING_MATERIAL_HYPOTHESIS_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  region=region, sourceGeometryExistingUVAndWeightsUnchanged=True, originalsPreserved=True,
                  materialSlotsBefore=len(body.data.materials), materialSlotsAfter=len(obj.data.materials),
                  fullCharacterScore=None, trimRestored=False, designApproved=False, rigBound=False,
                  defaultVisibleMeshObjects=visible, nonAdjacentSelfSurfacePairs=len(pairs),
                  selfCheckExcludesSharedVertexPairs=True, bodyPartOverlap=overlaps,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['MATERIAL_MASK_NOT_ANATOMICAL_SEGMENTATION', 'SOURCE_TRIM_SUPPRESSED_IN_MASK_NOT_RECONSTRUCTED',
                               'PROXIMAL_FADE_NOT_A_REAL_TAILORING_SEAM', 'SOURCE_FACETED_GEOMETRY_AND_OTHER_PROJECTION_DEFECTS_REMAIN',
                               'LAYERED_UNWELDED_TEMPORARY_CAP_NO_RIG', 'BLENDER_PROCEDURAL_SHADER_NOT_UNITY_READY'])
    (output/'upper-sleeve-material-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_FILE_CHANGED')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--art-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--no-render', action='store_true')
    r = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k: r[k] for k in ('status', 'blendSha256', 'region')}, indent=2))
