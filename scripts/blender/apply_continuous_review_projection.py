"""Continuous world-space reference projection for a review-only mesh.

Blend reference colors by smooth surface normal and foreground confidence.
No polygon-level material switches and no inferred semantic geometry labels.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_review_multiview_textures import _foreground_texture, _base_color, sha256_file

STRATEGY = 'CH101_CONTINUOUS_WORLD_PROJECTION_V001'


def geometry_digest(objects):
    digest = hashlib.sha256()
    for obj in sorted(objects, key=lambda o: o.name):
        digest.update(obj.name.encode())
        for vertex in obj.data.vertices:
            digest.update(repr(tuple(obj.matrix_world @ vertex.co)).encode())
        for polygon in obj.data.polygons:
            digest.update(repr(tuple(polygon.vertices)).encode())
    return digest.hexdigest()


def create_material(references, minimum, maximum, base_color):
    material = bpy.data.materials.new('CH101_CONTINUOUS_REFERENCE_NOT_PRODUCTION')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()

    def math_node(operation, a, b=None):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        for i, value in enumerate((a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[i].default_value = value
            else:
                links.new(value, node.inputs[i])
        return node.outputs[0]

    def scaled_coordinate(value, low, high, first, last, pixels):
        fraction = math_node('DIVIDE', math_node('SUBTRACT', value, low), max(high-low, 1e-6))
        return math_node('ADD', math_node('MULTIPLY', fraction, (last-first)/pixels), (first+.5)/pixels)

    geometry = nodes.new('ShaderNodeNewGeometry')
    position = nodes.new('ShaderNodeSeparateXYZ')
    normal = nodes.new('ShaderNodeSeparateXYZ')
    links.new(geometry.outputs['Position'], position.inputs[0])
    links.new(geometry.outputs['Normal'], normal.inputs[0])
    ny = normal.outputs['Y']
    directions = {
        'front': math_node('MAXIMUM', math_node('MULTIPLY', ny, -1), 0),
        'back': math_node('MAXIMUM', ny, 0),
        'right': math_node('ABSOLUTE', normal.outputs['X']),
    }
    colors, weights, mask_reports = [], [], {}
    for role in ('front', 'back', 'right'):
        image, audit = _foreground_texture('CH101_CONTINUOUS_'+role.upper(), references[role], .08)
        mask_reports[role] = audit
        left, bottom, right, top = audit['foregroundBoundsInclusive']
        width, height = audit['size']
        lateral = 1 if role == 'right' else 0
        first, last = (right, left) if role == 'back' else (left, right)
        uv = nodes.new('ShaderNodeCombineXYZ')
        links.new(scaled_coordinate(position.outputs[lateral], minimum[lateral], maximum[lateral], first, last, width), uv.inputs['X'])
        links.new(scaled_coordinate(position.outputs['Z'], minimum.z, maximum.z, bottom, top, height), uv.inputs['Y'])
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = image
        texture.interpolation = 'Linear'
        texture.extension = 'CLIP'
        texture.label = role
        links.new(uv.outputs[0], texture.inputs['Vector'])
        weight = math_node('MULTIPLY', math_node('POWER', directions[role], 4), texture.outputs['Alpha'])
        colors.append(texture.outputs['Color'])
        weights.append(weight)
    total = math_node('ADD', math_node('ADD', weights[0], weights[1]), weights[2])
    safe_total = math_node('MAXIMUM', total, 1e-6)
    weighted = []
    for color, weight in zip(colors, weights):
        scale = nodes.new('ShaderNodeVectorMath')
        scale.operation = 'SCALE'
        links.new(color, scale.inputs[0])
        links.new(math_node('DIVIDE', weight, safe_total), scale.inputs['Scale'])
        weighted.append(scale.outputs['Vector'])
    summed = weighted[0]
    for value in weighted[1:]:
        add = nodes.new('ShaderNodeVectorMath')
        add.operation = 'ADD'
        links.new(summed, add.inputs[0])
        links.new(value, add.inputs[1])
        summed = add.outputs['Vector']
    mix = nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MIX'
    mix.inputs[1].default_value = base_color
    links.new(math_node('MINIMUM', math_node('MULTIPLY', total, 1000), 1), mix.inputs[0])
    links.new(summed, mix.inputs[2])
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Roughness'].default_value = .72
    links.new(mix.outputs[0], shader.inputs['Base Color'])
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(shader.outputs[0], output.inputs['Surface'])
    material['source_status'] = 'AI_GENERATED_CANDIDATE_NOT_PRODUCTION'
    return material, mask_reports


def apply(args):
    if args.output_blend.resolve() == args.input_blend.resolve() or args.output_blend.exists():
        raise ValueError('OUTPUT_EXISTS_OR_OVERWRITES_SOURCE')
    if sha256_file(args.input_blend) != args.input_sha256:
        raise ValueError('INPUT_BLEND_SHA256_MISMATCH')
    refs = {role: getattr(args, role+'_image').resolve() for role in ('front','back','right')}
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and len(o.data.vertices)
               and not o.name.startswith('ReviewFloor_')]
    if not objects:
        raise ValueError('NO_REVIEW_MESH')
    points = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    minimum = Vector(tuple(min(p[a] for p in points) for a in range(3)))
    maximum = Vector(tuple(max(p[a] for p in points) for a in range(3)))
    before = geometry_digest(objects)
    base = _base_color(next((o.data.materials[0] for o in objects if o.data.materials), None))
    material, mask_reports = create_material(refs, minimum, maximum, base)
    for obj in objects:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        obj.data.materials.clear()
        obj.data.materials.append(material)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True
    after = geometry_digest(objects)
    if before != after:
        raise RuntimeError('UNEXPECTED_GEOMETRY_CHANGE')
    for key, value in {'source_status':'AI_GENERATED_CANDIDATE_NOT_PRODUCTION',
                       'gate_b':'PENDING_HUMAN_REVIEW','unity_input_allowed':False,
                       'production_promotion_allowed':False}.items():
        bpy.context.scene[key] = value
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report = {
        'strategyId': STRATEGY, 'status':'CONTINUOUS_PROJECTION_APPLIED_NOT_APPROVED',
        'sourceStatus':'AI_GENERATED_CANDIDATE_NOT_PRODUCTION', 'gateB':'PENDING_HUMAN_REVIEW',
        'unityInputAllowed':False, 'productionPromotionAllowed':False,
        'inputBlendSha256':args.input_sha256, 'outputBlendSha256':sha256_file(args.output_blend),
        'geometryDigestBefore':before,'geometryDigestAfter':after,
        'meshCount':len(objects),'materialCount':1,'baseColor':list(base),
        'maskReports':mask_reports,
        'referenceSha256':{role:sha256_file(path) for role,path in refs.items()},
        'limitations':['SEMANTIC_GEOMETRY_NOT_CREATED','LEFT_VIEW_USES_RIGHT_REFERENCE_INFERRED',
                       'SHADER_ONLY_REVIEW_BLEND_NOT_EXPORT_BAKED_ATLAS'],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('input-blend','front-image','back-image','right-image','output-blend','report'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--input-sha256', required=True)
    apply(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
