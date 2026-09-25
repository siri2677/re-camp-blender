"""Reversible duplicate-only distal replacement, capped inside an authored sleeve."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit_ch101_upper_sleeve as upper

c = upper.c
STRATEGY = 'CH101_DUPLICATE_DISTAL_REPLACEMENT_STATIC_ASSEMBLY_V001'
SPLIT_HEIGHT = .074


def self_crossing_signatures(obj):
    tree,points,faces=c.fit.bvh(obj)
    def signature(i):
        return tuple(sorted(tuple(round(float(v),7) for v in points[k]) for k in faces[i]))
    return {tuple(sorted((signature(a),signature(b)))) for a,b in tree.overlap(tree)
            if a<b and not set(faces[a])&set(faces[b])}


def clip_triangle(corners, points, center, axis):
    """Sutherland–Hodgman against the retained proximal halfspace; preserve UV seams."""
    result = []
    for a,b in zip(corners,corners[1:]+corners[:1]):
        ia, ua = a
        ib, ub = b
        da, db = (points[ia]-center).dot(axis), (points[ib]-center).dot(axis)
        if abs(da) < 1e-8 or abs(db) < 1e-8:
            raise ValueError('CLIP_PLANE_VERTEX_AMBIGUOUS')
        if da > 0:
            result.append((('v',ia), points[ia], ua))
        if da*db < 0:
            low, high = sorted((ia,ib))
            dl, dh = (points[low]-center).dot(axis), (points[high]-center).dot(axis)
            p = points[low]+(points[high]-points[low])*(dl/(dl-dh))
            t = da/(da-db)
            uv = tuple(x+(y-x)*t for x,y in zip(ua,ub))
            result.append((('e',low,high),p,uv))
    return result


def replacement_copy(source, center, axis, height=SPLIT_HEIGHT):
    center, axis = Vector(center), Vector(axis).normalized()
    if axis.length < .9:
        raise ValueError('INVALID_REPLACEMENT_AXIS')
    section = upper.source_section(source,center+axis*height,axis)
    points, triangles = c.fit.geometry(source)
    region = upper.region_review(points,triangles,center,axis,top=height)
    selected = set(region['selectedConnectedTriangleIndices'])
    collar = set(region['triangleClasses']['UPPER_PLANE_REVIEW_COLLAR'])
    chosen = selected|collar
    uv = source.data.uv_layers.active
    if uv is None:
        raise ValueError('SOURCE_UV_REQUIRED')
    vertices, faces, slots, face_uvs, smooth, lookup = [], [], [], [], [], {}
    untouched, removed, clipped = [], [], []
    for index, triangle in enumerate(source.data.loop_triangles):
        ids = list(triangle.vertices)
        coords = [tuple(uv.data[i].uv) for i in triangle.loops]
        if index in chosen:
            result = clip_triangle(list(zip(ids,coords)),points,center+axis*height,axis)
            if not result:
                removed.append(index)
                continue
            clipped.append(index)
        else:
            result = [(('v',i),points[i],co) for i,co in zip(ids,coords)]
            untouched.append(index)
        face = []
        for identity, position, coordinate in result:
            if identity not in lookup:
                lookup[identity] = len(vertices)
                vertices.append(tuple(position))
            face.append(lookup[identity])
        faces.append(face)
        face_uvs.append([row[2] for row in result])
        original = source.data.polygons[triangle.polygon_index]
        slots.append(original.material_index)
        smooth.append(original.use_smooth)
    mesh = bpy.data.meshes.new('Source_distal_replacement_closed_copy')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    for material in source.data.materials:
        mesh.materials.append(material)
    uv_out = mesh.uv_layers.new(name=uv.name)
    for p,slot,coords,shading in zip(mesh.polygons,slots,face_uvs,smooth):
        p.material_index = slot
        p.use_smooth = shading
        for i,coordinate in zip(p.loop_indices,coords):
            uv_out.data[i].uv = coordinate
    cap_material = c.base.material('INTERNAL_STUDY_CAP_NOT_FINAL_ATLAS',(.012,.015,.021))
    mesh.materials.append(cap_material)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    border = [e for e in bm.edges if e.is_boundary]
    degree = Counter(v for e in border for v in e.verts)
    if len(border) < 3 or any(n != 2 for n in degree.values()):
        bm.free()
        raise ValueError('REPLACEMENT_BOUNDARY_NOT_SIMPLE_CYCLE')
    graph = defaultdict(set)
    for e in border:
        a,b = e.verts
        graph[a].add(b)
        graph[b].add(a)
    visited, stack = set(), [next(iter(graph))]
    while stack:
        v = stack.pop()
        if v not in visited:
            visited.add(v)
            stack.extend(graph[v]-visited)
    if len(visited) != len(degree) or any(abs((v.co-center).dot(axis)-height) > 1e-6 for v in degree):
        bm.free()
        raise ValueError('REPLACEMENT_HAS_UNRELATED_OR_NONPLANAR_HOLE')
    cap = bmesh.ops.holes_fill(bm,edges=border,sides=0)['faces']
    if len(cap) != 1:
        bm.free()
        raise ValueError('CAP_NOT_ONE_FACE')
    cap[0].material_index = len(mesh.materials)-1
    uv_layer = bm.loops.layers.uv.active
    _,u,v = upper.join.frame(axis,(1,0,0) if abs(axis.x)<.9 else (0,1,0))
    for loop in cap[0].loops:
        offset = loop.vert.co-(center+axis*height)
        loop[uv_layer].uv = (.5+offset.dot(u)/.15,.5+offset.dot(v)/.15)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    cap_normal_dot = cap[0].normal.dot(axis)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new('CH101_SourceBody_DistalReplacement_COPY_NOT_PRODUCTION',mesh)
    bpy.context.scene.collection.objects.link(obj)
    c.base.mark(obj)
    obj['originalSourceModified'] = False
    obj['replacementOnWorkingCopy'] = True
    obj['anatomicalSeamVerified'] = False
    obj['weldedToSleeve'] = False
    # Verify UV/material retention after the cap operation rather than trusting
    # that the BMesh conversion kept them. All retained original triangles are
    # emitted in source order before the appended cap.
    retention_errors = 0
    for p,slot,coords in zip(mesh.polygons,slots,face_uvs):
        if p.material_index != slot or len(p.loop_indices) != len(coords):
            retention_errors += 1
            continue
        retention_errors += sum((Vector(mesh.uv_layers.active.data[i].uv)-Vector(co)).length>1e-6
                                for i,co in zip(p.loop_indices,coords))
    if retention_errors:
        raise ValueError('RETAINED_UV_OR_MATERIAL_CHANGED')
    if cap_normal_dot > -.99:
        raise ValueError('CAP_NORMAL_NOT_DISTAL')
    return obj,dict(splitHeightMeters=height,upperSleeveRimMeters=upper.TOP,
                    nominalAxialCoverMeters=upper.TOP-height,
                    splitInterpretation='ARTIFICIAL_CLOTH_INTERIOR_INTERFACE_NOT_SKIN_SEAM',
                    sourceTriangleCount=len(triangles),removedSourceTriangleIndices=removed,
                    clippedSourceTriangleIndices=clipped,untouchedSourceTriangleCount=len(untouched),
                    section=section,boundaryVertexCount=len(border),capFaces=1,
                    capNormalDotAxis=cap_normal_dot,retainedUVMaterialErrors=retention_errors,
                    sourcePositionsUnchangedOutsideClip=True,originalSourceModified=False,
                    sourceReplacementOnCopy=True,weldedToSleeve=False,anatomicalSeamVerified=False)


def render_views(output, original, replacement, sleeve, hand, equipment, center, axis):
    scene = bpy.context.scene
    for o in scene.objects:
        if o.type in ('MESH','CURVE','LIGHT'):
            o.hide_render = True
    data = bpy.data.lights.new('Replacement_review_key','AREA')
    data.energy, data.size = 45, .4
    light = bpy.data.objects.new(data.name,data)
    scene.collection.objects.link(light)
    light.location = center+Vector((-.3,-.4,.5))
    light.rotation_euler = (center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.view_settings.exposure=-.7
    camera=scene.camera;camera.data.type='ORTHO';camera.data.ortho_scale=.40
    renders=[]
    for mode in ('before_source_texture','after_textured_assembly','after_clay_interface'):
        for o in [original,replacement,sleeve,hand]+equipment:
            o.hide_render=True
        if mode=='before_source_texture':
            original.hide_render=False
        else:
            for o in [replacement,sleeve,hand]+equipment:o.hide_render=False
        clay=None
        if mode=='after_clay_interface':
            clay=replacement.copy();clay.data=replacement.data.copy()
            clay.name='REPLACEMENT_CONTEXT_COPY';scene.collection.objects.link(clay)
            clay.data.materials.clear();clay.data.materials.append(c.base.material('Replacement_context_clay',(.18,.20,.23)))
            for p in clay.data.polygons:p.material_index=0
            replacement.hide_render=True
            c.base.mark(clay);clay['diagnosticCopy']=True
        for name,offset in [('front',(-.25,-.7,.15)),('side',(-.7,.05,.1)),('back',(.25,.7,.15))]:
            aim=center+axis*.02;camera.location=aim+Vector(offset)
            camera.rotation_euler=(aim-camera.location).to_track_quat('-Z','Y').to_euler()
            path=output/f'{mode}_{name}.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            renders.append(dict(file=path.name,sha256=c.base.sha(path),mode=mode,originalModified=False))
        if clay is not None:clay.hide_render=True
    replacement.hide_render=False
    return renders


def configure_review_viewport(visible):
    """Open the saved scene on the replacement, with originals still recoverable."""
    visible=set(visible)
    for obj in bpy.context.scene.objects:
        if obj.type in ('MESH','CURVE','ARMATURE'):
            obj.hide_set(obj not in visible)
            obj.select_set(False)
    for obj in visible:
        obj.hide_viewport=False
        obj.hide_set(False)
    body=next(o for o in visible if o.name.startswith('CH101_SourceBody_DistalReplacement'))
    body.select_set(True)
    bpy.context.view_layer.objects.active=body
    return sorted(o.name for o in visible)


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_SHA256_MISMATCH')
    refs=c.base.verify_references(args.art_root.resolve())
    if output.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
    if any(scene.get(k) not in (False,0) for k in ('unityInputAllowed','productionPromotionAllowed')):raise ValueError('SOURCE_GATE_NOT_FALSE')
    originals=[o for o in scene.objects if o.type=='MESH'];before=c.guide.digest(originals)
    body=bpy.data.objects['geometry_0'];sleeve=bpy.data.objects['CH101_UpperSleeveFit_STUDY_NOT_PRODUCTION']
    hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    equipment=[o for o in originals if o.name.startswith('PAIR_STUDY_') and o!=hand]
    center=hand.matrix_world@Vector();axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    obj,operation=replacement_copy(body,center,axis)
    audit=c.author.shape_audit(obj);source_audit=c.author.shape_audit(body)
    source_crossings=self_crossing_signatures(body);new_crossings=self_crossing_signatures(obj)
    self_pairs=len(new_crossings);introduced_crossings=new_crossings-source_crossings
    before_overlaps=c.fit.overlap_report(body,[sleeve,hand]+equipment,center)
    after_overlaps=c.fit.overlap_report(obj,[sleeve,hand]+equipment,center)
    bm=bmesh.new();bm.from_mesh(obj.data)
    winding=sum(not e.is_contiguous for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
    if audit['nonManifoldEdges'] or audit['zeroAreaFaces'] or len(audit['components'])!=len(source_audit['components']) or introduced_crossings or winding or volume<=0:
        raise ValueError('REPLACEMENT_TOPOLOGY_REJECTED:'+json.dumps(dict(audit=audit,sourceAudit=source_audit,selfPairs=self_pairs,sourceSelfPairs=len(source_crossings),introducedSelfPairs=len(introduced_crossings),winding=winding,volume=volume)))
    if any(r['uniqueEquipmentTrianglesCrossing'] for r in after_overlaps):
        raise ValueError('REPLACEMENT_SURFACE_CROSSING_REMAINS:'+json.dumps(after_overlaps))
    output.mkdir(parents=True)
    renders=[] if args.no_render else render_views(output,body,obj,sleeve,hand,equipment,center,axis)
    if c.guide.digest(originals)!=before or c.base.sha(source)!=args.source_sha256:raise ValueError('SOURCE_CHANGED')
    for key,value in c.base.GATES.items():scene[key]=value
    scene['sourceReplacementOnWorkingCopy']=True;scene['originalSourceModified']=False
    scene['sourceHandReplacedInWorkingAssembly']=True
    visible=configure_review_viewport([obj,sleeve,hand]+equipment)
    blend=output/'CH101_DistalReplacementAssembly_NOT_PRODUCTION_v001.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report=dict(strategyId=STRATEGY,status='DUPLICATE_ONLY_STATIC_REPLACEMENT_ASSEMBLY_NOT_APPROVED',**c.base.GATES,
                sourceBlendSha256=args.source_sha256,artCommit=c.base.ART_COMMIT,references=refs,
                operation=operation,topology=audit,sourceTopology=source_audit,selfSurfacePairs=self_pairs,
                sourceSelfSurfacePairs=len(source_crossings),introducedSelfSurfacePairs=len(introduced_crossings),
                inheritedSelfCrossingGeometrySignatures=sorted(new_crossings&source_crossings),inconsistentWindingEdges=winding,
                signedVolumeCubicMeters=volume,bodyPartOverlapBefore=before_overlaps,bodyPartOverlapAfter=after_overlaps,
                originalSourcePreserved=True,sourceReplacementOnWorkingCopy=True,sourceHandReplacedInWorkingAssembly=True,
                defaultVisibleMeshObjects=visible,originalsHiddenInViewportNotDeleted=True,
                weldedToSleeve=False,capIsTemporary=True,rigBound=False,anatomicalSeamVerified=False,
                designApproved=False,attachmentApproved=False,fullCharacterScore=None,renders=renders,
                blendFile=blend.name,blendSha256=c.base.sha(blend),
                limitations=['INTERNAL_CAP_AND_LAYERED_ASSEMBLY_NOT_SHARED_TOPOLOGY','NO_ANIMATION_OR_SOLID_CONTAINMENT_PROOF',
                             'PROJECTED_TEXTURE_AND_FACETED_CLOTH_UNFINISHED','CAP_UV_AND_MATERIAL_NOT_FINAL_ATLAS','NO_UNITY_IMPORT'])
    (output/'distal-replacement-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--art-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--no-render',action='store_true')
    r=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:r[k] for k in ('status','topology','selfSurfacePairs','blendSha256')},indent=2))
