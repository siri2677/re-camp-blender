"""Duplicate-only body/sleeve seam with shared boundaries and retained originals."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_ch101_upper_sleeve_trim as trim

surface, c = trim.surface, trim.c
replacement = surface.repair.replacement
join = surface.fit.join
SOURCE_SHA = 'ac0ecd79c2f2f65ab9db3efa639f350e8ee5a0a6bae55f5a3ef0451919d25309'
STRATEGY = 'CH101_SHARED_BODY_SLEEVE_SEAM_V001'
RESULT_OBJECT = 'CH101_SourceBody_DistalReplacement_JoinedSleeve_NOT_PRODUCTION'
CUT_HEIGHT = .110


def ring(points, indices, center, axis, u):
    axis, u, v = join.frame(axis, u)
    indices = list(indices)
    area = sum((points[a]-center).cross(points[b]-center).dot(axis)
               for a, b in zip(indices, indices[1:]+indices[:1]))/2
    if abs(area) < 1e-8:
        raise ValueError('DEGENERATE_BODY_RING')
    if area < 0:
        indices.reverse()
    def angle(i):
        d = points[i]-center
        return math.atan2(d.dot(v), d.dot(u)) % (2*math.pi)
    start = min(range(len(indices)), key=lambda k: min(angle(indices[k]), 2*math.pi-angle(indices[k])))
    indices = indices[start:]+indices[:start]
    lengths = [(points[b]-points[a]).length for a,b in zip(indices, indices[1:]+indices[:1])]
    if min(lengths) < 1e-8:
        raise ValueError('ZERO_BOUNDARY_EDGE')
    total = sum(lengths)
    params = [0.]
    for length in lengths[:-1]:
        params.append(params[-1]+length/total)
    return dict(vertices=indices, parameters=params)


def transfer_fields(source, points, names):
    """Exact retained-vertex values; barycentric interpolation only on new cuts."""
    tree, old, triangles = c.fit.bvh(source)
    kd = KDTree(len(old))
    for i, p in enumerate(old):
        kd.insert(p, i)
    kd.balance()
    values = {name: [] for name in names}
    exact = interpolated = 0
    max_distance = 0.
    for point in points:
        _, index, distance = kd.find(point)
        if distance < 1e-8:
            exact += 1
            for name in names:
                values[name].append(source.data.attributes[name].data[index].value)
        else:
            nearest, _, triangle, distance = tree.find_nearest(point)
            if nearest is None or distance > 2e-6:
                raise ValueError('CUT_VERTEX_NOT_ON_SOURCE_SURFACE')
            max_distance = max(max_distance, distance)
            interpolated += 1
            a,b,d = triangles[triangle]
            weights = barycentric_transform(nearest, old[a], old[b], old[d],
                                             Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1)))
            for name in names:
                attr = source.data.attributes[name]
                values[name].append(sum(w*attr.data[i].value for w,i in zip(weights, (a,b,d))))
    return values, dict(exactRetainedVertices=exact, interpolatedCutVertices=interpolated,
                        maxCutProjectionErrorMeters=max_distance)


def seam_material():
    mat = c.base.material('BodySleeveSeam_graphite_gold', surface.linear_color('151518'))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    attr = nodes.new('ShaderNodeAttribute')
    attr.attribute_name = trim.DISTANCE
    absolute = nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    links.new(attr.outputs['Fac'], absolute.inputs[0])
    cutoff = nodes.new('ShaderNodeMath')
    cutoff.operation = 'LESS_THAN'
    links.new(absolute.outputs[0], cutoff.inputs[0])
    color = nodes.new('ShaderNodeMixRGB')
    color.inputs[1].default_value = (*surface.linear_color('151518'),1)
    color.inputs[2].default_value = (*surface.linear_color('D2A445'),1)
    links.new(cutoff.outputs[0], color.inputs[0])
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = .72
    links.new(color.outputs[0], bsdf.inputs['Base Color'])
    return mat, cutoff


def build(body, sleeve, hand):
    center = hand.matrix_world@Vector()
    axis = (hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    u = hand.matrix_world.to_3x3()@Vector((1,0,0))
    cropped, cut_report = replacement.replacement_copy(body, center, axis, CUT_HEIGHT)
    cropped.name = 'PRESERVED_INTERMEDIATE_BODY_CUT_NOT_PRODUCTION'
    body_points = [cropped.matrix_world@v.co for v in cropped.data.vertices]
    cap = [p for p in cropped.data.polygons if all(abs((body_points[i]-center).dot(axis)-CUT_HEIGHT)<1e-6 for i in p.vertices)]
    if len(cap) != 1:
        raise ValueError('BODY_CUT_NOT_ONE_PLANAR_CAP')
    body_ring = ring(body_points, cap[0].vertices, center, axis, u)
    spec, sleeve_points = join.open_rim(sleeve, center, axis, u, surface.fit.TOP)
    fields, field_report = transfer_fields(body, body_points, [trim.upper.MASK, trim.DISTANCE])
    anchors, normal, width = trim.trim_plane(sleeve, bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
                                            bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], axis)
    offset = len(body_points)
    points = body_points+sleeve_points
    fields[trim.upper.MASK] += [0.]*len(sleeve_points)
    fields[trim.DISTANCE] += [(p-anchors[0]).dot(normal) for p in sleeve_points]
    materials = list(cropped.data.materials)+list(sleeve.data.materials)
    faces, slots, smooth, uv_rows, expected_normals = [], [], [], [], []
    uv_names = ['UVMap', 'StudyUV', surface.UV_NAME]
    retained_ranges = []
    for source, vertex_offset, slot_offset, excluded in (
            (cropped, 0, 0, {cap[0].index}),
            (sleeve, offset, len(cropped.data.materials), set(spec['removedCapFaces']))):
        start = len(faces)
        normal_matrix = source.matrix_world.to_3x3().inverted().transposed()
        for p in source.data.polygons:
            if p.index in excluded:
                continue
            faces.append([vertex_offset+i for i in p.vertices])
            slots.append(slot_offset+p.material_index)
            smooth.append(p.use_smooth)
            row = {}
            for name in uv_names:
                layer = source.data.uv_layers.get(name)
                if layer is None and name in ('UVMap','StudyUV'):
                    layer = source.data.uv_layers.active
                row[name] = [tuple(layer.data[i].uv) if layer else (0.,0.) for i in p.loop_indices]
            uv_rows.append(row)
            expected_normals.append((normal_matrix@p.normal).normalized())
        retained_ranges.append([start,len(faces)])
    retained = len(faces)
    lower = dict(vertices=[offset+i for i in spec['outer']['vertices']], parameters=spec['outer']['parameters'])
    bridge = join.zipper(lower, body_ring)
    seam, cutoff = seam_material()
    cutoff.inputs[1].default_value = width
    seam_slot = len(materials)
    materials.append(seam)
    cap_slot = len(materials)
    materials.append(c.base.material('BodySleeve_INTERNAL_VOID_CAP_NOT_FINAL', surface.linear_color('151518')))
    for face in bridge+[list(reversed([offset+i for i in spec['inner']['vertices']]))]:
        faces.append(face)
        is_cap = len(face) > 3
        slots.append(cap_slot if is_cap else seam_slot)
        smooth.append(False)
        _, frame_u, frame_v = join.frame(axis,u)
        coords = [(.5+(points[i]-center).dot(frame_u)/.2,.5+(points[i]-center).dot(frame_v)/.2) for i in face]
        uv_rows.append({name:coords for name in uv_names})
    mesh = bpy.data.meshes.new('Body_sleeve_shared_seam_mesh')
    mesh.from_pydata(points, [], faces)
    mesh.update()
    for m in materials:
        mesh.materials.append(m)
    for name in uv_names:
        layer = mesh.uv_layers.new(name=name)
        for p,row in zip(mesh.polygons,uv_rows):
            for loop,coordinate in zip(p.loop_indices,row[name]):
                layer.data[loop].uv = coordinate
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True
    for p,slot,shading in zip(mesh.polygons,slots,smooth):
        p.material_index,p.use_smooth = slot,shading
    for name,values in fields.items():
        attr = mesh.attributes.new(name,'FLOAT','POINT')
        for item,value in zip(attr.data,values):
            item.value = value
    obj = bpy.data.objects.new(RESULT_OBJECT,mesh)
    bpy.context.scene.collection.objects.link(obj)
    # Preserve sleeve semantic groups, remapped by concatenation offset.
    for group in sleeve.vertex_groups:
        target = obj.vertex_groups.new(name=group.name)
        for vertex in sleeve.data.vertices:
            for entry in vertex.groups:
                if entry.group == group.index:
                    target.add([offset+vertex.index], entry.weight, 'REPLACE')
    for name, ids in [('BodySeam',body_ring['vertices']),('SleeveSeam',lower['vertices'])]:
        obj.vertex_groups.new(name=name).add(ids,1,'REPLACE')
    c.base.mark(obj)
    obj['bodySleeveSharedBoundary'] = True
    obj['attachmentApproved'] = False
    # No global normal recalculation: retained source winding must be identical.
    normal_mismatches = sum(p.normal.dot(n)<.999 for p,n in zip(mesh.polygons[:retained],expected_normals))
    uv_errors = sum((Vector(mesh.uv_layers[name].data[i].uv)-Vector(co)).length>1e-6
                    for name in uv_names for p,row in zip(mesh.polygons,uv_rows)
                    for i,co in zip(p.loop_indices,row[name]))
    edge_counts = Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face,face[1:]+face[:1]))
    seam_edges = [tuple(sorted((a,b))) for r in (body_ring,lower)
                  for a,b in zip(r['vertices'],r['vertices'][1:]+r['vertices'][:1])]
    bridge_counts = Counter(tuple(sorted((a,b))) for face in bridge for a,b in zip(face,face[1:]+face[:1]))
    if any(edge_counts[e] != 2 or bridge_counts[e] != 1 for e in seam_edges):
        raise ValueError('SEAM_BOUNDARY_NOT_SHARED_WITH_RETAINED_FACES')
    return obj, dict(cut=cut_report, fieldTransfer=field_report, bodyBoundaryVertices=len(body_ring['vertices']),
                     sharedBoundaryEdgeCount=len(seam_edges), eachSeamEdgeHasOneBridgeAndOneRetainedFace=True,
                     sleeveOuterBoundaryVertices=len(lower['vertices']), bridgeTriangles=len(bridge),
                     bridgePolygonRange=[retained,retained+len(bridge)], internalVoidCapPolygon=len(faces)-1,
                     retainedFaceRanges=retained_ranges, retainedNormalMismatches=normal_mismatches,
                     copiedUVErrors=uv_errors, sourceSleeveVertexOffset=offset,
                     sourceSleevePositionsCopiedExactly=True, sourceGeometryPreservedOutsideBodyCut=True,
                     physicalSeamTopology='SHARED_BODY_RING_TO_SLEEVE_OUTER_RING_PLUS_INTERNAL_VOID_CAP',
                     attachmentApproved=False, rigBound=False)


def assess(obj, parts, operation):
    audit = c.author.shape_audit(obj)
    audit['selfIntersectionTestPerformed'] = True
    audit['selfIntersectionTestScope'] = 'NON_ADJACENT_BVH_SHARED_VERTEX_PAIRS_EXCLUDED'
    pairs = surface.repair.crossing_pairs(obj)[2]
    overlaps = [dict(target=p.name, **c.fit.overlap_report(p,[obj],Vector())[0]) for p in parts]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    winding = sum(not e.is_contiguous for e in bm.edges)
    volume = bm.calc_volume(signed=True)
    bm.free()
    reasons = []
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or winding or volume <= 0:
        reasons.append('INVALID_CLOSED_TOPOLOGY_OR_WINDING')
    if len(audit['components']) != 2 or min(audit['components']) != 48:
        reasons.append('UNEXPECTED_COMPONENTS')
    if pairs:
        reasons.append('SELF_SURFACE_CROSSING')
    if any(r['uniqueEquipmentTrianglesCrossing'] for r in overlaps):
        reasons.append('HAND_EQUIPMENT_CROSSING')
    if operation['retainedNormalMismatches'] or operation['copiedUVErrors']:
        reasons.append('RETAINED_FACE_DATA_CHANGED')
    return dict(eligible=not reasons, rejectionReasons=reasons, topology=audit,
                nonAdjacentSelfSurfacePairs=pairs, selfCheckExcludesSharedVertexPairs=True,
                inconsistentWindingEdges=winding, signedVolumeMeters3=volume, partOverlaps=overlaps)


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    before=c.guide.digest(originals)
    body=bpy.data.objects[trim.RESULT_OBJECT]
    sleeve=bpy.data.objects[surface.RESULT_OBJECT]
    hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    obj,operation=build(body,sleeve,hand)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=assess(obj,parts,operation)
    if not qa['eligible']:
        raise ValueError('SEAM_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[]
    if not args.no_render:
        center=hand.matrix_world@Vector()
        axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
        renders=trim.upper.render(output,body,obj,parts,center,axis,before_extras=[sleeve])
    if c.guide.digest(originals)!=before or c.base.sha(source)!=SOURCE_SHA:
        raise ValueError('ORIGINAL_CHANGED')
    visible=replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'): old.hide_render=old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_BodySleeveSeam_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='SHARED_BODY_SLEEVE_SEAM_STATIC_STUDY_NOT_APPROVED',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalSourcesPreserved=True,defaultVisibleMeshObjects=visible,attachmentApproved=False,
                rigBound=False,fullCharacterScore=None,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['ARTIFICIAL_CLOTHING_INTERFACE_NOT_ANATOMICAL_SEAM','INTERNAL_VOID_CAP_REMAINS',
                             'COARSE_SOURCE_GEOMETRY_AND_PATTERN_REMAIN','NOT_EXHAUSTIVE_SOLID_OR_DEFORMATION_PROOF',
                             'NO_FINAL_ATLAS_MATERIAL_BUDGET_OR_UNITY_APPROVAL'])
    (output/'body-sleeve-seam-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    result=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:result[k] for k in ('status','blendSha256','qa')},indent=2))
