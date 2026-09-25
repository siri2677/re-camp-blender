"""Geometry-anchored narrow trim within the existing local clothing mask only."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refine_ch101_upper_sleeve_material as upper

surface, c = upper.surface, upper.c
SOURCE_SHA = 'e4f8e156052ec2c6dec32bba19ef2a118144f2f1f0e47852a504f38a1c7d9c98'
STRATEGY = 'CH101_UPPER_TRIM_ANCHORED_PLANE_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_UpperTrim_NOT_PRODUCTION'
DISTANCE = 'UpperTrimSignedPlaneDistance'


def trim_plane(sleeve, joined, cloth, axis):
    axis = Vector(axis)
    if abs(axis.length-1) > 1e-5:
        raise ValueError('TRIM_AXIS_MUST_BE_UNIT')
    if [list(p.vertices) for p in sleeve.data.polygons] != [list(p.vertices) for p in joined.data.polygons]:
        raise ValueError('TRIM_SOURCE_TOPOLOGY_CHANGED')
    mapping = surface.fit.sleeve_vertex_map(joined, cloth)
    anchors, widths = [], []
    for lane in (3, 19):
        a, b = [sleeve.matrix_world@sleeve.data.vertices[mapping[7*32+j]].co for j in (lane, lane+1)]
        anchors.append((a+b)/2)
        widths.append((a-b).length*surface.TRIM_FRACTION)
    normal = axis.cross(anchors[1]-anchors[0])
    if normal.length < .01:
        raise ValueError('DEGENERATE_TRIM_ANCHORS')
    normal.normalize()
    half_width = sum(widths)/4
    if not .0005 < half_width < .002:
        raise ValueError('TRIM_WIDTH_OUT_OF_BOUND')
    return anchors, normal, half_width


def trim_copy(source, anchors, normal, half_width):
    if DISTANCE in source.data.attributes:
        raise ValueError('TRIM_ALREADY_APPLIED')
    if upper.MASK not in source.data.attributes:
        raise ValueError('EXISTING_MASK_REQUIRED')
    if abs(normal.length-1) > 1e-5 or not .0005 < half_width < .002:
        raise ValueError('INVALID_TRIM_PLANE_OR_WIDTH')
    # Verify all shader entry points before allocating the copy.
    for m in source.data.materials:
        if not m.name.startswith('INTERNAL_STUDY_CAP') and 'LocalGraphiteCloth' not in m.node_tree.nodes:
            raise ValueError('LOCAL_CLOTH_SHADER_REQUIRED')
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = RESULT_OBJECT
    bpy.context.scene.collection.objects.link(obj)
    attr = obj.data.attributes.new(DISTANCE, 'FLOAT', 'POINT')
    for item, vertex in zip(attr.data, obj.data.vertices):
        item.value = (obj.matrix_world@vertex.co-anchors[0]).dot(normal)
    for i, original in enumerate(source.data.materials):
        if original.name.startswith('INTERNAL_STUDY_CAP'):
            continue
        mat = original.copy()
        mat.name = 'UpperTrim_'+original.name
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        attribute = nodes.new('ShaderNodeAttribute')
        attribute.attribute_name = DISTANCE
        absolute = nodes.new('ShaderNodeMath')
        absolute.operation = 'ABSOLUTE'
        links.new(attribute.outputs['Fac'], absolute.inputs[0])
        mask = nodes.new('ShaderNodeMath')
        mask.name = 'AnchoredTrimHalfWidth'
        mask.operation = 'LESS_THAN'
        mask.inputs[1].default_value = half_width
        links.new(absolute.outputs[0], mask.inputs[0])
        color = nodes.new('ShaderNodeMixRGB')
        color.inputs[1].default_value = (*surface.linear_color('151518'), 1)
        color.inputs[2].default_value = (*surface.linear_color('D2A445'), 1)
        links.new(mask.outputs[0], color.inputs[0])
        links.new(color.outputs[0], nodes['LocalGraphiteCloth'].inputs['Base Color'])
        obj.data.materials[i] = mat
    c.base.mark(obj)
    obj['trimRestored'] = False
    obj['anchoredTrimStudy'] = True
    obj['exactReferenceTrimReconstruction'] = False
    if surface.structure_signature(obj) != surface.structure_signature(source):
        raise ValueError('GEOMETRY_UV_OR_WEIGHTS_CHANGED')
    if [x.value for x in obj.data.attributes[upper.MASK].data] != [x.value for x in source.data.attributes[upper.MASK].data]:
        raise ValueError('CLOTHING_MASK_CHANGED')
    return obj


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs = c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    surface.require_locked(scene)
    originals = [o for o in scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    invariants = {o.name: surface.repair.invariant_signature(o) for o in originals}
    body = bpy.data.objects[upper.RESULT_OBJECT]
    sleeve = bpy.data.objects[surface.RESULT_OBJECT]
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center = hand.matrix_world@Vector()
    axis = (hand.matrix_world.to_3x3()@Vector((0, 0, -1))).normalized()
    anchors, normal, half_width = trim_plane(sleeve, bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
                                            bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], axis)
    obj = trim_copy(body, anchors, normal, half_width)
    parts = [sleeve]+[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    pairs = surface.repair.crossing_pairs(obj)[2]
    overlaps = c.fit.overlap_report(obj, parts, center)
    if pairs or any(r['uniqueEquipmentTrianglesCrossing'] for r in overlaps):
        raise ValueError('STATIC_ASSEMBLY_CROSSING')
    body_tree, _, _ = c.fit.bvh(body)
    anchor_gaps = [body_tree.find_nearest(p)[3] for p in anchors]
    output.mkdir(parents=True)
    renders = [] if args.no_render else upper.render(output, body, obj, parts, center, axis)
    if c.guide.digest(originals) != digest or any(surface.repair.invariant_signature(o) != invariants[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible = surface.repair.replacement.configure_review_viewport([obj]+parts)
    for old in scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = old not in [obj]+parts
    surface.require_locked(scene)
    bpy.context.preferences.filepaths.save_version = 0
    blend = output/'CH101_UpperTrimContinuity_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='ANCHORED_TRIM_DESIGN_STUDY_NOT_APPROVED', **c.base.GATES,
                  sourceBlendSha256=SOURCE_SHA, artCommit=c.base.ART_COMMIT, references=refs,
                  anchorsWorld=[list(p) for p in anchors], planeNormalWorld=list(normal),
                  planeStripWidthMeters=2*half_width, widthIsPlanarNotGeodesic=True,
                  anchorPlaneResidualMeters=[abs((p-anchors[0]).dot(normal)) for p in anchors],
                  anchorToBodySurfaceDistanceMeters=anchor_gaps,
                  anchorDistanceIsNotGlobalMinimumGap=True, actualGeometricSeamConnected=False,
                  existingClothingMaskUnchanged=True, sourceGeometryUVAndWeightsUnchanged=True,
                  originalsPreserved=True, nonAdjacentSelfSurfacePairs=len(pairs), bodyPartOverlap=overlaps,
                  selfCheckExcludesSharedVertexPairs=True, defaultVisibleMeshObjects=visible,
                  fullCharacterScore=None, designApproved=False, exactReferenceTrimReconstruction=False,
                  blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['STRAIGHT_PLANE_HYPOTHESIS_NOT_RECOVERED_TAILORING_PATTERN',
                               'EXISTING_MASK_FADE_AND_PROJECTED_UPPER_TRIM_REMAIN',
                               'BODY_SLEEVE_GAP_NOT_WELDED_OR_BRIDGED', 'NO_RIG_OR_DEFORMATION_PROOF',
                               'PROCEDURAL_SHADER_NEEDS_BAKING_FOR_UNITY'])
    (output/'upper-trim-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
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
    print(json.dumps({k: r[k] for k in ('status', 'planeStripWidthMeters', 'anchorToBodySurfaceDistanceMeters', 'blendSha256')}, indent=2))
