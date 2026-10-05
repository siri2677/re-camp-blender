"""Upper sleeve fit and explicit geometric replacement-region REVIEW, no cutting."""
import argparse
from collections import defaultdict, Counter
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import join_ch101_sleeve_cuff_study as join
import review_ch101_wrist_boundary as boundary

c = join.c
STRATEGY = 'CH101_UPPER_SLEEVE_FIT_REGION_REVIEW_V001'
TOP = .098
LOCKED_HEIGHT = .030
EASE = .0035
MAX_DISPLACEMENT = .025
FOLD_AMPLITUDE = .0012


def key(point):
    return tuple(round(float(x), 7) for x in point)


def source_section(body, center, axis, radius=.085):
    """Join section segments by source edge IDs, never rounded coordinates."""
    center = Vector(center)
    axis = Vector(axis).normalized()
    if axis.length < .9 or radius <= 0:
        raise ValueError('INVALID_SECTION_FRAME')
    points, triangles = c.fit.geometry(body)
    graph, positions = defaultdict(set), {}
    for face in triangles:
        signed = [(points[i]-center).dot(axis) for i in face]
        if any(abs(x) < 1e-8 for x in signed):
            if all((points[i]-center).length < radius for i in face):
                raise ValueError('SECTION_PLANE_VERTEX_AMBIGUOUS')
            continue
        hits = []
        for a, b in ((0,1),(1,2),(2,0)):
            if signed[a]*signed[b] < 0:
                edge = tuple(sorted((face[a], face[b])))
                ia, ib = edge
                da, db = (points[ia]-center).dot(axis), (points[ib]-center).dot(axis)
                p = points[ia]+(points[ib]-points[ia])*(da/(da-db))
                hits.append((edge, p))
        if len(hits) != 2 or not all((p-center).length < radius for _,p in hits):
            continue
        (a, pa), (b, pb) = hits
        graph[a].add(b)
        graph[b].add(a)
        positions[a], positions[b] = pa, pb
    if not graph or any(len(n) != 2 for n in graph.values()):
        raise ValueError('SECTION_NOT_CLOSED_DEGREE_TWO')
    start = min(graph)
    order = [start]
    previous, current = start, min(graph[start])
    while current != start:
        if current in order:
            raise ValueError('SECTION_EARLY_CYCLE')
        order.append(current)
        previous, current = current, next(i for i in graph[current] if i != previous)
    if len(order) != len(graph):
        raise ValueError('MULTIPLE_LOCAL_SECTION_LOOPS')
    coords = [positions[i] for i in order]
    area, weighted = 0., Vector()
    for a,b in zip(coords, coords[1:]+coords[:1]):
        weight = (a-center).cross(b-center).dot(axis)/2
        area += weight
        weighted += (center+a+b)/3*weight
    if abs(area) < 1e-8:
        raise ValueError('SECTION_ZERO_AREA')
    return dict(points=[list(p) for p in coords], pointCount=len(coords),
                centroid=list(weighted/area), areaSquareMeters=abs(area), closed=True,
                method='SOURCE_EDGE_ID_CONNECTIVITY_NO_COORDINATE_ROUNDING',
                verifiedAnatomicalSeam=False)


def sleeve_vertex_map(joined, original):
    lookup = defaultdict(list)
    for vertex in joined.data.vertices:
        lookup[key(joined.matrix_world @ vertex.co)].append(vertex.index)
    result = []
    for vertex in original.data.vertices:
        matches = lookup.get(key(original.matrix_world @ vertex.co), [])
        if len(matches) != 1:
            raise ValueError('SOURCE_SLEEVE_VERTEX_CORRESPONDENCE_AMBIGUOUS')
        result.append(matches[0])
    if len(set(result)) != len(result):
        raise ValueError('SOURCE_SLEEVE_MAPPING_NOT_INJECTIVE')
    return result


def fitted_copy(joined, cloth, center, axis, u, sections):
    axis, u, v = join.frame(axis, u)
    center = Vector(center)
    mapping = sleeve_vertex_map(joined, cloth)
    profiles = join.sleeve.PROFILES
    if len(mapping) != len(profiles)*64:
        raise ValueError('UNEXPECTED_SLEEVE_PROFILE_TOPOLOGY')
    points = [joined.matrix_world @ vertex.co for vertex in joined.data.vertices]
    targets = {}
    for z, loop in sections.items():
        centroid = Vector(loop['centroid'])
        if abs((centroid-center).dot(axis)-z) > 1e-5:
            raise ValueError('TARGET_SECTION_HEIGHT_MISMATCH')
        if not loop.get('closed'):
            raise ValueError('TARGET_SECTION_NOT_CLOSED')
        sampled = c.resample(loop['points'], axis, u, count=32, center=centroid)
        targets[z] = c.radial_offset(sampled, centroid, axis, EASE+join.sleeve.WALL)
    corrections = []
    # The source has a bulge between .065 and .083 m. Use its measured midpoint
    # profile to correct only outward chord deficits, keeping topology unchanged.
    for j in range(32):
        angle = 2*math.pi*j/32
        radial = u*math.cos(angle)+v*math.sin(angle)
        chord = (targets[.065][j]+targets[.083][j])/2
        deficit = max(0., (targets[.074][j]-chord).dot(radial))
        correction = deficit+.0004 if deficit > 0 else 0.
        if correction > .006:
            raise ValueError('MIDSECTION_CORRECTION_EXCEEDS_6MM_BOUND')
        for z in (.065, .083):
            targets[z][j] += radial*correction
        corrections.append(correction)
    updates = {}
    # The structured sleeve retains its original vertex correspondence inside
    # the joined mesh. Inner and outer pairs receive exactly the same offset.
    for k, (z, rx, ry) in enumerate(profiles):
        if z > LOCKED_HEIGHT:
            target_outer = targets[z]
        for j in range(32):
            outer_id = mapping[k*32+j]
            inner_id = mapping[(2*len(profiles)-1-k)*32+j]
            if abs((points[outer_id]-center).dot(axis)-z) > 1e-6:
                raise ValueError('SOURCE_PROFILE_HEIGHT_MISMATCH')
            if z <= LOCKED_HEIGHT:
                continue
            t = (z-LOCKED_HEIGHT)/(TOP-LOCKED_HEIGHT)
            blend = min(1., (z-LOCKED_HEIGHT)/(.065-LOCKED_HEIGHT))
            weight = blend*blend*(3-2*blend)
            angle = 2*math.pi*j/32
            radial = u*math.cos(angle)+v*math.sin(angle)
            delta = (target_outer[j]-points[outer_id])*weight
            # A bounded diagonal fold dies out at both the locked area and rim.
            delta += radial*(FOLD_AMPLITUDE*math.sin(math.pi*t)**2*math.cos(3*angle-3*t))
            if delta.length > MAX_DISPLACEMENT:
                raise ValueError('UPPER_FIT_EXCEEDS_25MM_BOUND')
            updates[outer_id] = points[outer_id]+delta
            updates[inner_id] = points[inner_id]+delta
    obj = joined.copy()
    obj.data = joined.data.copy()
    obj.name = 'CH101_UpperSleeveFit_STUDY_NOT_PRODUCTION'
    bpy.context.scene.collection.objects.link(obj)
    inverse = obj.matrix_world.inverted()
    for index, point in updates.items():
        obj.data.vertices[index].co = inverse @ point
    obj.data.update()
    obj['sourceReplacementAllowed'] = False
    obj['attachedToBody'] = False
    obj['authoredSleeveCuffJoined'] = True
    c.base.mark(obj)
    upper_outer = [mapping[(len(profiles)-1)*32+j] for j in range(32)]
    upper_inner = [mapping[len(profiles)*32+j] for j in range(32)]
    for name, indices in [('UpperOpening_outer', upper_outer), ('UpperOpening_inner', upper_inner)]:
        obj.vertex_groups.new(name=name).add(indices, 1, 'REPLACE')
    preserved = [i for i in range(len(points)) if i not in updates]
    if any((obj.matrix_world@obj.data.vertices[i].co-points[i]).length > 1e-7 for i in preserved):
        raise ValueError('LOCKED_VERTICES_CHANGED')
    thickness_change = max(abs((obj.data.vertices[mapping[k*32+j]].co-
                               obj.data.vertices[mapping[(2*len(profiles)-1-k)*32+j]].co).length-
                              (points[mapping[k*32+j]]-points[mapping[(2*len(profiles)-1-k)*32+j]]).length)
                           for k in range(len(profiles)) for j in range(32))
    return obj, dict(changedVertices=len(updates), unchangedVertices=len(preserved),
                     maxDisplacementMeters=max((p-points[i]).length for i, p in updates.items()),
                     displacementBoundMeters=MAX_DISPLACEMENT, lockedAtOrBelowMeters=LOCKED_HEIGHT,
                     maxPairedWallDistanceChangeMeters=thickness_change,
                     targetRadialEaseMeters=EASE, addedFoldAmplitudeMeters=FOLD_AMPLITUDE,
                     midpointProfileMeters=.074, outwardChordCorrectionsMeters=corrections,
                     maxMidpointCorrectionMeters=max(corrections),
                     upperOuterVertices=upper_outer, upperInnerVertices=upper_inner,
                     fitMethod='FOUR_GEOMETRIC_PROFILES_WITH_LOCKED_DISTAL_BLEND_AND_PAIRED_WALL_OFFSETS',
                     anatomyVerified=False, exactArtReconstruction=False)


def region_review(points, faces, center, axis, top=TOP, radius=.075, distal=-.18):
    """Connected local source patch with a plane-straddling review collar.

    Centroid ROI is solely a geometric working hypothesis. No deletion list is
    authorized; all original triangles stay in the diagnostic mesh.
    """
    center = Vector(center)
    axis = Vector(axis).normalized()
    if axis.length < .9 or top <= distal or radius <= 0:
        raise ValueError('INVALID_REGION_FRAME_OR_BOUNDS')
    candidates, straddling = set(), set()
    centroids = []
    for i, face in enumerate(faces):
        vertices = [points[j] for j in face]
        centroid = sum(vertices, Vector())/len(vertices)
        centroids.append(centroid)
        delta = centroid-center
        z = delta.dot(axis)
        signed = [(p-center).dot(axis) for p in vertices]
        radial = (delta-axis*z).length
        if distal < z < top and radial < radius:
            candidates.add(i)
        if min(signed) <= top <= max(signed) and radial < radius:
            straddling.add(i)
    if not candidates:
        raise ValueError('EMPTY_REVIEW_REGION')
    edge_faces = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face, face[1:]+face[:1]):
            edge_faces[tuple(sorted((a, b)))].append(i)
    adjacency = defaultdict(set)
    for entries in edge_faces.values():
        for i in entries:
            adjacency[i].update(j for j in entries if j != i)
    seed = min(candidates, key=lambda i: (centroids[i]-(center-axis*.04)).length)
    selected, stack = set(), [seed]
    while stack:
        i = stack.pop()
        if i not in selected:
            selected.add(i)
            stack.extend((adjacency[i]&candidates)-selected)
    frontier = [list(edge) for edge, entries in edge_faces.items()
                if any(i in selected for i in entries) and any(i not in selected for i in entries)]
    colors = {label: [] for label in ('OUTSIDE_REVIEW', 'LOCAL_REPLACEMENT_HYPOTHESIS', 'UPPER_PLANE_REVIEW_COLLAR')}
    for i in range(len(faces)):
        label = 'UPPER_PLANE_REVIEW_COLLAR' if i in straddling else 'LOCAL_REPLACEMENT_HYPOTHESIS' if i in selected else 'OUTSIDE_REVIEW'
        colors[label].append(i)
    degree = Counter(v for edge in frontier for v in edge)
    return dict(triangleClasses=colors, selectedConnectedTriangleIndices=sorted(selected),
                frontierEdges=frontier, frontierVertices=len(degree),
                frontierDegreeTwo=bool(degree) and all(n == 2 for n in degree.values()),
                discardedDisconnectedCandidateTriangles=len(candidates-selected),
                counts={k: len(v) for k, v in colors.items()}, seedTriangle=seed,
                sourceTriangleCount=len(faces), topMeters=top, distalMeters=distal, radiusMeters=radius,
                method='CENTROID_CYLINDER_AND_EDGE_CONNECTED_PATCH_WITH_UPPER_PLANE_COLLAR',
                semanticLabels=False, anatomicalBoundaryVerified=False, cutAllowed=False)


def band_overlap(body, obj, center, axis):
    tree, _, _ = c.fit.bvh(body)
    other, points, faces = c.fit.bvh(obj)
    crossed = {b for _, b in tree.overlap(other)}
    upper = {i for i, face in enumerate(faces) if min((points[j]-center).dot(axis) for j in face) > .0649}
    return dict(allCrossingTriangles=len(crossed), upperBandTriangles=len(upper),
                upperBandCrossingTriangles=len(upper&crossed), upperBandStartsMeters=.065)


def render_region(output, body, region, center, axis, section):
    points, faces = c.fit.geometry(body)
    mesh = bpy.data.meshes.new('Source_region_review_all_triangles')
    mesh.from_pydata(points, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('SOURCE_REPLACEMENT_REGION_REVIEW_NOT_CUT_MASK', mesh)
    bpy.context.scene.collection.objects.link(obj)
    for label, color in zip(region['triangleClasses'], ((.18,.20,.23),(.55,.08,.10),(.85,.38,.02))):
        mesh.materials.append(c.base.material(label, color))
    for slot, indices in enumerate(region['triangleClasses'].values()):
        for i in indices:
            mesh.polygons[i].material_index = slot
    c.base.mark(obj)
    obj['cutAllowed'] = False
    scene = bpy.context.scene
    for old in scene.objects:
        if old.type in ('MESH', 'CURVE'):
            old.hide_render = True
    obj.hide_render = False
    marker = boundary.marker(section)
    camera = scene.camera
    camera.data.ortho_scale = .46
    renders = []
    for name, offset in [('front',(-.25,-.7,.15)),('side',(-.7,.05,.1)),('back',(.25,.7,.15))]:
        aim = center+axis*.015
        camera.location = aim+Vector(offset)
        camera.rotation_euler = (aim-camera.location).to_track_quat('-Z','Y').to_euler()
        path = output/f'region_{name}_NOT_CUT.png'
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append(dict(file=path.name, sha256=c.base.sha(path), cutPerformed=False, geometricClassesOnly=True))
    obj.hide_render = marker.hide_render = True
    return renders


def run(args):
    source, output = args.source.resolve(), args.output.resolve()
    if c.base.sha(source) != args.source_sha256:
        raise ValueError('SOURCE_SHA256_MISMATCH')
    refs = c.base.verify_references(args.art_root.resolve())
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    if any(scene.get(k) not in (False, 0) for k in ('unityInputAllowed','productionPromotionAllowed')):
        raise ValueError('SOURCE_GATE_NOT_FALSE')
    originals = [o for o in scene.objects if o.type == 'MESH']
    digest = c.guide.digest(originals)
    joined = bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION']
    cloth = bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION']
    hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    body = bpy.data.objects['geometry_0']
    center = hand.matrix_world @ Vector()
    axis, u, _ = join.frame(hand.matrix_world.to_3x3()@Vector((0,0,-1)), hand.matrix_world.to_3x3()@Vector((1,0,0)))
    sections = {z: source_section(body, center+axis*z, axis)
                for z, _, _ in join.sleeve.PROFILES if z > LOCKED_HEIGHT}
    sections[.074] = source_section(body, center+axis*.074, axis)
    obj, fit = fitted_copy(joined, cloth, center, axis, u, sections)
    equipment = [o for o in originals if o.name.startswith('PAIR_STUDY_') and o != hand]
    # The bridge and cuff are locked. assess() independently checks whole-mesh
    # winding, topology, self-intersection, and hand/equipment surface crossings.
    qa = join.assess(obj, dict(retainedNormalMismatches=0, reversedTransitionFaces={}), hand, equipment)
    if not qa['eligible']:
        raise ValueError('UPPER_FIT_REJECTED:'+json.dumps(qa))
    before_overlap = band_overlap(body, joined, center, axis)
    after_overlap = band_overlap(body, obj, center, axis)
    if after_overlap['upperBandCrossingTriangles'] != 0:
        raise ValueError('UPPER_BAND_SURFACE_INTERSECTION_REMAINS')
    points, faces = c.fit.geometry(body)
    region = region_review(points, faces, center, axis)
    if len(obj.data.uv_layers.active.data) != len(joined.data.uv_layers.active.data) or any(
            a.uv != b.uv for a,b in zip(obj.data.uv_layers.active.data, joined.data.uv_layers.active.data)):
        raise ValueError('STUDY_UV_VALUES_CHANGED')
    output.mkdir(parents=True)
    renders = []
    if not args.no_render:
        renders = join.render(output, body, obj, center, axis)
        renders += render_region(output, body, region, center, axis, sections[TOP])
        obj.hide_render = False
        for o in equipment+[hand]:
            o.hide_render = False
    if c.guide.digest(originals) != digest or c.base.sha(source) != args.source_sha256:
        raise ValueError('SOURCE_CHANGED')
    for k, value in c.base.GATES.items():
        scene[k] = value
    blend = output/'CH101_UpperSleeveFit_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = dict(strategyId=STRATEGY, status='UPPER_SLEEVE_FIT_WITH_GEOMETRIC_REGION_REVIEW',
                  **c.base.GATES, sourceBlendSha256=args.source_sha256, artCommit=c.base.ART_COMMIT,
                  references=refs, fit=fit, sourceSections=sections, qa=qa,
                  bodyOverlapBefore=before_overlap, bodyOverlapAfter=after_overlap,
                  replacementRegionReview=region, sourceGeometryPreserved=True,
                  sourceHandReplaced=False, sourceBodyJoined=False, authoredSleeveCuffJoined=True,
                  anatomicalSeamVerified=False, cutPerformed=False, cutAllowed=False,
                  attachmentApproved=False, designApproved=False, wristIntegrationAllowed=False,
                  fullCharacterScore=None, blendFile=blend.name, blendSha256=c.base.sha(blend), renders=renders,
                  limitations=['FIT_TO_APPROXIMATE_SOURCE_GEOMETRY_NOT_EXACT_ART',
                               'REGION_IS_GEOMETRIC_HYPOTHESIS_NOT_AUTHORIZED_CUT_MASK',
                               'ORIGINAL_BODY_INTERSECTIONS_REMAIN','UPPER_OPENING_NOT_WELDED',
                               'NO_CONTAINMENT_OR_ANIMATION_PROOF','NO_FINAL_ATLAS_OR_SKINNING'])
    (output/'upper-sleeve-fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-render',action='store_true')
    report = run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:report[k] for k in ('status','fit','bodyOverlapBefore','bodyOverlapAfter','blendSha256')},indent=2))
