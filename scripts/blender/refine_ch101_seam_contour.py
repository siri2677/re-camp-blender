"""Bounded bridge refinement with all original vertices and shared rims locked."""
import argparse
from collections import defaultdict, Counter
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import join_ch101_body_sleeve as seam

surface,c=seam.surface,seam.c
SOURCE_SHA='66933822dbef7553c47d052e9d517fd5c22a424492486ac40a3c36e2f55ea6e3'
STRATEGY='CH101_LOCKED_RIM_SEAM_CONTOUR_V001'
RESULT_OBJECT='CH101_SourceBody_DistalReplacement_SeamContour_NOT_PRODUCTION'
MAX_OFFSET=.0006


def group_ids(obj,name):
    group=obj.vertex_groups.get(name)
    if group is None:
        raise ValueError('SEAM_GROUP_MISSING:'+name)
    return {v.index for v in obj.data.vertices if any(g.group==group.index and g.weight>.999 for g in v.groups)}


def refine(source,axis,trim_normal,max_offset=MAX_OFFSET,local_safety=True):
    if not 0 < max_offset <= MAX_OFFSET:
        raise ValueError('UNSAFE_CONTOUR_OFFSET')
    axis=Vector(axis); trim_normal=Vector(trim_normal)
    if abs(axis.length-1)>1e-5 or abs(trim_normal.length-1)>1e-5:
        raise ValueError('CONTOUR_FRAME_NOT_UNIT')
    lower,upper=group_ids(source,'SleeveSeam'),group_ids(source,'BodySeam')
    if len(lower)!=32 or len(upper)!=41 or lower&upper:
        raise ValueError('SOURCE_RIM_CONTRACT_CHANGED')
    mesh=source.data
    bridge={p.index for p in mesh.polygons if mesh.materials[p.material_index].name=='BodySleeveSeam_graphite_gold'}
    if len(bridge)!=73 or any(len(mesh.polygons[i].vertices)!=3 for i in bridge):
        raise ValueError('SOURCE_BRIDGE_CONTRACT_CHANGED')
    points=[source.matrix_world@v.co for v in mesh.vertices]
    old_count=len(points)
    edge_faces=defaultdict(list)
    for p in mesh.polygons:
        ids=list(p.vertices)
        for a,b in zip(ids,ids[1:]+ids[:1]):
            edge_faces[tuple(sorted((a,b)))].append(p.index)
    cross_edges=sorted({tuple(sorted((a,b))) for i in bridge for a,b in
                        zip(list(mesh.polygons[i].vertices),list(mesh.polygons[i].vertices)[1:]+list(mesh.polygons[i].vertices)[:1])
                        if (a in lower and b in upper) or (a in upper and b in lower)})
    if len(cross_edges)!=73 or any(len(edge_faces[e])!=2 or not set(edge_faces[e])<=bridge for e in cross_edges):
        raise ValueError('CROSS_EDGE_NOT_INTERNAL_TO_BRIDGE')
    normal_matrix=source.matrix_world.to_3x3().inverted().transposed()
    normals={i:Vector() for i in lower|upper}
    adjacent=set()
    for p in mesh.polygons:
        if p.index in bridge:
            continue
        touched=set(p.vertices)&(lower|upper)
        if touched:
            adjacent.add(p.index)
            for i in touched:
                normals[i]+=(normal_matrix@p.normal).normalized()*p.area
    if any(n.length<1e-10 for n in normals.values()):
        raise ValueError('BOUNDARY_TANGENT_UNDEFINED')
    normals={i:n.normalized() for i,n in normals.items()}
    midpoints={}
    offsets=[]
    # Cubic-Hermite midpoint with endpoint tangents projected onto retained surfaces.
    # Only radial displacement is allowed, then hard-clamped to 0.6 mm.
    for a,b in cross_edges:
        altitudes=[]
        for face_index in edge_faces[(a,b)]:
            triangle=[points[i] for i in mesh.polygons[face_index].vertices]
            area2=(triangle[1]-triangle[0]).cross(triangle[2]-triangle[0]).length
            longest=max((q-p).length for p,q in zip(triangle,triangle[1:]+triangle[:1]))
            altitudes.append(area2/longest)
        # Thin zipper triangles cannot tolerate the same displacement as wide ones.
        # Bound every shared-edge midpoint by 2.5% of BOTH incident triangles' altitude.
        local_limit=min(max_offset,.025*min(altitudes)) if local_safety else max_offset
        d=points[b]-points[a]
        ta=d-normals[a]*d.dot(normals[a])
        tb=d-normals[b]*d.dot(normals[b])
        delta=(ta-tb)/8
        delta-=axis*delta.dot(axis)
        if delta.length>local_limit:
            delta*=local_limit/delta.length
        midpoints[(a,b)]=len(points)
        points.append((points[a]+points[b])/2+delta)
        offsets.append(dict(edge=[a,b],newVertex=len(points)-1,offsetMeters=delta.length,deltaWorld=list(delta),
                            incidentMinimumAltitudeMeters=min(altitudes),localLimitMeters=local_limit))
    faces,slots,shading,uv_rows,source_indices=[],[],[],[],[]
    bridge_output=[]
    unchanged_mapping=[]
    uv_names=[u.name for u in mesh.uv_layers]
    for p in mesh.polygons:
        ids=list(p.vertices)
        rows={name:{v:tuple(mesh.uv_layers[name].data[loop].uv) for v,loop in zip(ids,p.loop_indices)} for name in uv_names}
        if p.index not in bridge:
            new_faces=[ids]
            unchanged_mapping.append((p.index,len(faces)))
        else:
            for rotation in range(3):
                a,b,d=ids[rotation:]+ids[:rotation]
                if (a in lower)==(b in lower):
                    break
            ab=midpoints[tuple(sorted((b,d)))]; ac=midpoints[tuple(sorted((a,d)))]
            for row in rows.values():
                row[ab]=tuple((x+y)/2 for x,y in zip(row[b],row[d]))
                row[ac]=tuple((x+y)/2 for x,y in zip(row[a],row[d]))
            new_faces=[(a,b,ab),(a,ab,ac),(ac,ab,d)]
            bridge_output.extend(range(len(faces),len(faces)+3))
        for face in new_faces:
            faces.append(face); slots.append(p.material_index)
            shading.append(True if p.index in bridge|adjacent else p.use_smooth)
            uv_rows.append({name:[rows[name][i] for i in face] for name in uv_names})
            source_indices.append(p.index)
    data=bpy.data.meshes.new('Locked_rim_refined_seam')
    data.from_pydata(points,[],faces); data.update()
    for m in mesh.materials: data.materials.append(m)
    for name in uv_names:
        layer=data.uv_layers.new(name=name)
        for p,row in zip(data.polygons,uv_rows):
            for loop,co in zip(p.loop_indices,row[name]): layer.data[loop].uv=co
    data.uv_layers.active_index=mesh.uv_layers.active_index
    for layer in data.uv_layers: layer.active_render=layer.name==mesh.uv_layers.active.name
    for p,slot,smooth in zip(data.polygons,slots,shading): p.material_index,p.use_smooth=slot,smooth
    fields=[seam.trim.upper.MASK,seam.trim.DISTANCE]
    for name in fields:
        attr=data.attributes.new(name,'FLOAT','POINT')
        for i in range(old_count): attr.data[i].value=mesh.attributes[name].data[i].value
        for entry in offsets:
            a,b=entry['edge']; value=(attr.data[a].value+attr.data[b].value)/2
            if name==seam.trim.DISTANCE: value+=Vector(entry['deltaWorld']).dot(trim_normal)
            attr.data[entry['newVertex']].value=value
    obj=bpy.data.objects.new(RESULT_OBJECT,data); bpy.context.scene.collection.objects.link(obj)
    for group in source.vertex_groups:
        new=obj.vertex_groups.new(name=group.name)
        for v in mesh.vertices:
            for g in v.groups:
                if g.group==group.index: new.add([v.index],g.weight,'REPLACE')
    obj.vertex_groups.new(name='SeamContourMidpoints').add(list(range(old_count,len(points))),1,'REPLACE')
    c.base.mark(obj)
    obj['bodySleeveSharedBoundary']=True
    obj['attachmentApproved']=False
    # Prove unchanged boundary edges still have two incident faces.
    edge_count=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(list(f),list(f)[1:]+list(f)[:1]))
    boundary_edges=[e for e,fs in edge_faces.items() if len(set(fs)&bridge)==1]
    if len(boundary_edges)!=73 or any(edge_count[e]!=2 for e in boundary_edges):
        raise ValueError('SHARED_BOUNDARY_CHANGED')
    original_positions_exact=all(obj.data.vertices[i].co==p for i,p in enumerate(points[:old_count]))
    min_dot=1.; area_ratios=[]
    for index in bridge_output:
        polygon=data.polygons[index]; original=mesh.polygons[source_indices[index]]
        min_dot=min(min_dot,polygon.normal.dot((normal_matrix@original.normal).normalized()))
        area_ratios.append(polygon.area/original.area)
    if not original_positions_exact or min_dot<.90 or min(area_ratios)<.05 or max(area_ratios)>.85:
        bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.meshes.remove(data)
        raise ValueError('CONTOUR_DISTORTION_REJECTED:'+json.dumps(dict(minDot=min_dot,areaRange=[min(area_ratios),max(area_ratios)])))
    normal_errors=sum(data.polygons[j].normal.dot((normal_matrix@mesh.polygons[i].normal).normalized())<.999 for i,j in unchanged_mapping)
    uv_errors=sum((Vector(data.uv_layers[name].data[loop].uv)-Vector(co)).length>1e-6
                  for name in uv_names for p,row in zip(data.polygons,uv_rows) for loop,co in zip(p.loop_indices,row[name]))
    for entry in offsets:
        a,b=entry['edge']
        actual=data.vertices[entry['newVertex']].co-(points[a]+points[b])/2
        entry['actualStoredOffsetMeters']=actual.length
        entry['actualAxialDriftMeters']=abs(actual.dot(axis))
        if actual.length>entry['localLimitMeters']+1e-7 or abs(actual.dot(axis))>1e-7:
            raise ValueError('STORED_DISPLACEMENT_LIMIT_EXCEEDED')
    return obj,dict(originalVertexCount=old_count,originalPositionsExactlyPreserved=original_positions_exact,
                    localTriangleAltitudeSafetyEnabled=local_safety,localAltitudeFraction=.025,storageToleranceMeters=1e-7,
                    maxActualStoredOffsetMeters=max(r['actualStoredOffsetMeters'] for r in offsets),
                    addedMidpointVertices=len(offsets),offsets=offsets,maxMidpointOffsetMeters=max(r['offsetMeters'] for r in offsets),
                    displacementBoundMeters=max_offset,bridgeTrianglesBefore=len(bridge),bridgeTrianglesAfter=len(bridge_output),
                    sharedBoundaryEdges=len(boundary_edges),sharedRimsLocked=True,unchangedFaceMapping=unchanged_mapping,
                    minimumBridgeNormalDot=min_dot,subtriangleAreaRatioRange=[min(area_ratios),max(area_ratios)],
                    retainedNormalMismatches=normal_errors,copiedUVErrors=uv_errors,
                    smoothedRetainedAdjacentFaces=len(adjacent),bridgeOutputPolygons=bridge_output,
                    bodyAndSleeveSeamGroupMembershipUnchanged=True,rigWeightInterpolationPerformed=False,
                    boundaryGroupsNotAssignedToNewMidpoints=True)


def run(args):
    source,output=args.source.resolve(),args.output.resolve()
    if c.base.sha(source)!=SOURCE_SHA: raise ValueError('SOURCE_SHA256_MISMATCH')
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    bpy.ops.wm.open_mainfile(filepath=str(source))
    surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    before=c.guide.digest(originals)
    invariants={o.name:surface.repair.invariant_signature(o) for o in originals}
    body=bpy.data.objects[seam.RESULT_OBJECT]
    hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
    center=hand.matrix_world@Vector(); axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
    _,normal,_=seam.trim.trim_plane(bpy.data.objects[surface.RESULT_OBJECT],bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
                                   bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'],axis)
    obj,operation=refine(body,axis,normal)
    parts=[o for o in originals if o.name.startswith('PAIR_STUDY_')]
    qa=seam.assess(obj,parts,operation)
    if not qa['eligible']: raise ValueError('REFINED_SEAM_REJECTED:'+json.dumps(qa))
    output.mkdir(parents=True)
    renders=[] if args.no_render else seam.trim.upper.render(output,body,obj,parts,center,axis)
    if c.guide.digest(originals)!=before or any(surface.repair.invariant_signature(o)!=invariants[o.name] for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    visible=seam.replacement.configure_review_viewport([obj]+parts)
    for old in bpy.context.scene.objects:
        if old.type in ('MESH','CURVE'): old.hide_render=old not in [obj]+parts
    surface.require_locked(bpy.context.scene)
    bpy.context.preferences.filepaths.save_version=0
    blend=output/'CH101_SeamContour_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if c.base.sha(source)!=SOURCE_SHA: raise ValueError('SOURCE_FILE_CHANGED')
    report=dict(strategyId=STRATEGY,status='LOCKED_RIM_CONTOUR_STATIC_STUDY_NOT_APPROVED',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,artCommit=c.base.ART_COMMIT,references=refs,operation=operation,qa=qa,
                originalsPreserved=True,attachmentApproved=False,rigBound=False,fullCharacterScore=None,
                defaultVisibleMeshObjects=visible,blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['RIMS_AND_ORIGINAL_COARSE_CONTOUR_LOCKED','SMOOTH_NORMALS_NOT_ANATOMY_RECONSTRUCTION',
                             'INTERNAL_VOID_CAP_REMAINS','STATIC_BVH_NOT_EXHAUSTIVE_OR_DEFORMATION_PROOF',
                             'NO_RIG_FINAL_ATLAS_OR_UNITY_APPROVAL'])
    (output/'seam-contour-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True); p.add_argument('--art-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--no-render',action='store_true')
    result=run(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
    print(json.dumps({k:result[k] for k in ('status','blendSha256','qa')},indent=2))
