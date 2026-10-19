"""Broad underarm course proposals and bounded feasibility, NOT new cloth faces.

Fit three whole sector arcs, never isolated vertex stars. The strongest sampled
fairing that stays inside a conservative 1.5 mm guide corridor is retained.
Rejected stronger fits remain explicit hypotheses, not relaxed-limit results.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_ch101_underarm_disks as prior

c, surface, branch, layout = prior.c, prior.surface, prior.branch, prior.layout
SOURCE_SHA = '153bdb0528548ca587c0276d5a99eb49b823d36ed823145a2173eb0c7016a8bb'
REPORT_SHA = '74a762ba537fb6f1b2ee7d22cffd130ea36d427b8c689cfff431f9d8a712fa6a'
LAYOUT_SHA = prior.LAYOUT_SHA
CAP_REPORT_SHA = prior.REPORT_SHA
STRATEGY = 'CH101_BROAD_UNDERARM_SUPPORT_CURVE_FEASIBILITY_V001'
PREFIX = 'UNDERARM_SUPPORT_'
LIMIT = .0015
SAMPLE_STEP = .00025
FIT_POINTS = 129
WEIGHTS = (0., .03125, .125, .5, 2., 8., 32., 128., 512., 2048.,
           8192., 32768., 131072., 524288., 2097152.)


def arrays(points):
    result = np.asarray(points, dtype=float)
    if result.ndim != 2 or result.shape[1] != 3 or not np.isfinite(result).all():
        raise ValueError('NONFINITE_OR_INVALID_CURVE')
    if len(result) < 2 or np.any(np.linalg.norm(np.diff(result, axis=0), axis=1) < 1e-9):
        raise ValueError('DEGENERATE_CURVE_SEGMENT')
    return result


def sample(points, step=SAMPLE_STEP):
    p = arrays(points)
    result = []
    for a, b in zip(p, p[1:]):
        n = max(1, math.ceil(float(np.linalg.norm(b-a))/step))
        result.extend(a + (b-a)*t/n for t in range(n))
    return np.asarray(result + [p[-1]])


def distances(points, polyline):
    """Exact point-to-segment distance; finite query points, not Hausdorff proof."""
    p = arrays(polyline)
    a, d = p[:-1], np.diff(p, axis=0)
    lengths = np.sum(d*d, axis=1)
    result = []
    for point in points:
        t = np.clip(np.sum((point-a)*d, axis=1)/lengths, 0, 1)
        result.append(float(np.min(np.linalg.norm(point-a-t[:, None]*d, axis=1))))
    return result


def resample(points):
    p = arrays(points)
    s = np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    u = np.linspace(0, s[-1], FIT_POINTS)
    return np.column_stack([np.interp(u, s, p[:, i]) for i in range(3)])


def fit(points, weight):
    """Endpoint-fixed quadratic fairing; weight is grid-dependent, not metres."""
    if not math.isfinite(weight) or weight < 0:
        raise ValueError('INVALID_FAIRING_WEIGHT')
    p = resample(points)
    d = np.diff(np.eye(len(p)), n=2, axis=0)
    matrix = np.eye(len(p)) + weight*(d.T@d)
    q = p.copy()
    q[1:-1] = np.linalg.solve(matrix[1:-1, 1:-1], p[1:-1] - matrix[1:-1, [0]]*p[0] - matrix[1:-1, [-1]]*p[-1])
    return arrays(q)


def curve_stats(points):
    p = arrays(points)
    d = np.diff(p, axis=0)
    lengths = np.linalg.norm(d, axis=1)
    angles = np.arccos(np.clip(np.sum(d[:-1]*d[1:], axis=1)/(lengths[:-1]*lengths[1:]), -1, 1))
    return dict(lengthMeters=float(sum(lengths)), maximumTurnDegrees=float(np.degrees(max(angles,default=0.))),
                discreteCurvatureSquaredIntegralPerMeter=float(sum(angles**2/((lengths[:-1]+lengths[1:])/2))))


def sectors(source, report, cap_report, layout_report):
    surface.require_locked(source)
    under_to_cap = report['operation']['keptSourceVertices']
    cap_to_layout = cap_report['operation']['keptSourceVertices']
    if len(under_to_cap) != len(source.data.vertices) or len(set(under_to_cap)) != len(under_to_cap):
        raise ValueError('INVALID_UPSTREAM_VERTEX_MAP')
    mapped = [cap_to_layout[i] for i in under_to_cap]
    if len(set(mapped)) != len(mapped):
        raise ValueError('INVALID_UPSTREAM_VERTEX_MAP')
    inverse = {j:i for i,j in enumerate(mapped)}
    chart = bpy.data.objects[layout.RESULT_OBJECT]
    edges = prior.edgeflow.edge_faces([tuple(f.vertices) for f in chart.data.polygons])
    current_edges = prior.edgeflow.edge_faces([tuple(f.vertices) for f in source.data.polygons])
    rows = []
    fold = next(g for g in layout_report['design']['majorFoldGroups'] if g['id'] == 193)
    fold_edges = {tuple(sorted(e)) for e in fold['sourceEdges']}
    provenance = layout_report['operation']['vertexProvenance']
    for course in layout_report['design']['transverseCourses']:
        selected = [tuple(e) for e in course['sharedEdges'] if any(chart.data.polygons[fi].material_index//4 == 1 for fi in edges[tuple(e)])]
        path = layout.ordered_path(selected)
        ids = [inverse[i] for i in path]
        if any(tuple(sorted(e)) not in current_edges for e in zip(ids, ids[1:])):
            raise ValueError('SOURCE_COURSE_EDGE_MISSING')
        p = [list(source.matrix_world@source.data.vertices[i].co) for i in ids]
        if max((Vector(a)-(chart.matrix_world@chart.data.vertices[i].co)).length for a,i in zip(p,path)) > 1e-8:
            raise ValueError('UPSTREAM_COURSE_POSITION_CHANGED')
        crosses = [dict(layoutVertex=i, sourceEdge=provenance[i]['sourceEdge']) for i in path
                   if tuple(provenance[i]['sourceEdge']) in fold_edges]
        domains = [4+course['index'], 5+course['index']]
        rows.append(dict(courseIndex=course['index'], harmonicLevel=course['level'],
                         layoutVertices=path, sourceVertices=ids, sourcePoints=p,
                         adjacentDomains=domains, foldNetworkCrossings=crosses,
                         endpointPolicy='FIXED_EXISTING_LONGITUDINAL_SEAM_INTERSECTIONS'))
    if len(rows) != 3:
        raise ValueError('EXPECTED_THREE_UNDERARM_COURSES')
    return rows


def feasibility(points, source_points, reference, domain):
    q = arrays(points)
    probes = sample(q)
    old_probes = sample(source_points)
    forward = max(reference.find_nearest(Vector(p))[3] for p in probes)
    same_domain = max(domain.find_nearest(Vector(p))[3] for p in probes)
    old_to_new = max(distances(old_probes, q))
    new_to_old = max(distances(probes, source_points))
    endpoint = max(float(np.linalg.norm(q[i]-source_points[i])) for i in (0,-1))
    stats = curve_stats(q)
    return dict(**stats, maximumOriginalChartDistanceMeters=forward,
                maximumAdjacentDomainDistanceMeters=same_domain,
                maximumSourceArcToProposalMeters=old_to_new,
                maximumProposalToSourceArcMeters=new_to_old,
                maximumEndpointMoveMeters=endpoint, proposalSamples=len(probes), sourceArcSamples=len(old_probes),
                guideCorridorPassed=max(forward,same_domain,old_to_new,new_to_old)<=LIMIT and endpoint<1e-8)


def design(source, report, cap_report, layout_report):
    rows = sectors(source, report, cap_report, layout_report)
    reference = c.fit.bvh(bpy.data.objects[branch.RESULT_OBJECT])[0]
    points = [source.matrix_world@v.co for v in source.data.vertices]
    for row in rows:
        domain = BVHTree.FromPolygons(points, [tuple(f.vertices) for f in source.data.polygons if f.material_index in row['adjacentDomains']], all_triangles=True)
        trials = []
        for weight in WEIGHTS:
            q = fit(row['sourcePoints'], weight)
            qa = feasibility(q, row['sourcePoints'], reference, domain)
            trials.append(dict(weight=weight, **qa))
        accepted = [r for r in trials if r['guideCorridorPassed']]
        if not accepted:
            raise ValueError('NO_FEASIBLE_BROAD_SUPPORT_CURVE')
        selected = min(accepted, key=lambda r:r['discreteCurvatureSquaredIntegralPerMeter'])
        row.update(sourceStats=curve_stats(row['sourcePoints']), resampledBaselineStats=curve_stats(resample(row['sourcePoints'])), trials=trials,
                   selectedWeight=selected['weight'], selectedQA=selected,
                   selectedPoints=fit(row['sourcePoints'], selected['weight']).tolist(),
                   broadTargetWeight=WEIGHTS[-1], broadTargetQA=trials[-1],
                   broadTargetPoints=fit(row['sourcePoints'], WEIGHTS[-1]).tolist())
        print('SUPPORT_CURVE', json.dumps(dict(course=row['courseIndex'], selected=selected, target=trials[-1])), flush=True)
    return dict(courses=rows, fitPoints=FIT_POINTS, weights=list(WEIGHTS), maximumSampleStepMeters=SAMPLE_STEP,
                originalChartLimitMeters=LIMIT, geometryShapeChanged=False,
                courseBoundaryRelocationApplied=False, designHypothesisOnly=True,
                selectionRule='MINIMUM_DISCRETE_CURVATURE_AMONG_DECLARED_CORRIDOR_PASSING_TRIALS',
                mathematicalInfeasibilityProved=False, continuousSurfaceBoundProved=False)


def guides(design_record):
    result = []
    for row in design_record['courses']:
        for role, key, color in [('source','sourcePoints','E9AD46'), ('bounded','selectedPoints','42C7DA'), ('target','broadTargetPoints','F06464')]:
            obj = branch.curve(PREFIX+str(row['courseIndex'])+'_'+role, [Vector(p) for p in row[key]], color)
            obj['adoptionAllowed'] = False
            obj['rigBound'] = False
            obj['proposalOnly'] = True
            obj['role'] = role
            obj['courseIndex'] = row['courseIndex']
            result.append(obj)
    return result


def segment_distance(a,b,c,d):
    u,v,w=b-a,d-c,a-c
    aa,bb,cc,dd,ee=float(u@u),float(u@v),float(v@v),float(u@w),float(v@w)
    denominator=aa*cc-bb*bb
    s=float(np.clip((bb*ee-cc*dd)/denominator,0,1)) if denominator>1e-15*aa*cc else 0.
    t=(bb*s+ee)/cc
    if t<0:
        t,s=0.,float(np.clip(-dd/aa,0,1))
    elif t>1:
        t,s=1.,float(np.clip((bb-dd)/aa,0,1))
    return float(np.linalg.norm(w+s*u-t*v))


def self_intersections(points):
    p=arrays(points)
    return sum(segment_distance(p[i],p[i+1],p[j],p[j+1])<=1e-8
               for i in range(len(p)-1) for j in range(i+2,len(p)-1))


def separation(design_record):
    rows=[]
    counts=[self_intersections(r['selectedPoints']) for r in design_record['courses']]
    if any(counts):
        raise ValueError('SUPPORT_CURVE_SELF_INTERSECTION')
    for i,a in enumerate(design_record['courses']):
        for b in design_record['courses'][i+1:]:
            minimum=min(distances(sample(a['selectedPoints']),b['selectedPoints']))
            # Distance to a set is 1-Lipschitz; each point is within step/2
            # of a probe. This lower bound applies only to these POLY lines.
            lower=max(0.,minimum-SAMPLE_STEP/2)
            rows.append(dict(coursePair=[a['courseIndex'],b['courseIndex']],
                             minimumSampleToOtherPolylineMeters=minimum,
                             centerlineSeparationLowerBoundMeters=lower))
    if min(r['centerlineSeparationLowerBoundMeters'] for r in rows)<=0:
        raise ValueError('SUPPORT_CURVE_SEPARATION_NOT_ESTABLISHED')
    return dict(pairs=rows,nonAdjacentSelfIntersectingSegmentPairs=counts,
                centerlineContactToleranceMeters=1e-8,centerlinesSeparated=True,garmentClearanceValidated=False)


def audit_design(source, report, cap_report, layout_report, record):
    expected=design(source,report,cap_report,layout_report)
    if record!=expected:
        raise ValueError('SUPPORT_DESIGN_RECORD_CHANGED')
    return dict(replayedTrialCount=sum(len(r['trials']) for r in expected['courses']),
                boundedCurveCount=len(expected['courses']),separation=separation(expected))


def audit_guides(design_record):
    expected = {PREFIX+str(r['courseIndex'])+'_'+role:(r,key) for r in design_record['courses']
                for role,key in [('source','sourcePoints'),('bounded','selectedPoints'),('target','broadTargetPoints')]}
    actual = {o.name:o for o in bpy.context.scene.objects if o.name.startswith(PREFIX)}
    if set(actual) != set(expected):
        raise ValueError('SUPPORT_GUIDE_SET_CHANGED')
    maximum = 0.
    for name,(row,key) in expected.items():
        obj = actual[name]
        surface.require_locked(obj)
        if obj.type != 'CURVE' or not obj.get('guideOnly') or not obj.get('proposalOnly') or obj.get('adoptionAllowed') is not False or obj.get('rigBound') is not False or len(obj.data.splines)!=1:
            raise ValueError('SUPPORT_GUIDE_STRUCTURE_CHANGED')
        spline = obj.data.splines[0]
        if spline.type!='POLY' or spline.use_cyclic_u or len(spline.points)!=len(row[key]):
            raise ValueError('SUPPORT_GUIDE_STRUCTURE_CHANGED')
        for p,target in zip(spline.points,row[key]):
            error = (obj.matrix_world@Vector(p.co[:3])-Vector(target)).length
            if not math.isfinite(error) or error>1e-6:
                raise ValueError('SUPPORT_GUIDE_POSITION_CHANGED')
            maximum=max(maximum,error)
    return dict(guideCount=len(actual), maximumStoredPointErrorMeters=maximum)


def input_reports(args):
    source=args.source.resolve()
    checks=[(source,SOURCE_SHA,'SOURCE'), (source.parent/'underarm-disks-report.json',REPORT_SHA,'SOURCE_REPORT'),
            (args.layout_report,LAYOUT_SHA,'LAYOUT_REPORT'),(args.cap_report,CAP_REPORT_SHA,'CAP_REPORT')]
    for path,sha,label in checks:
        if c.base.sha(path)!=sha:
            raise ValueError(label+'_SHA256_MISMATCH')
    return [json.loads(path.read_text()) for path,_,_ in checks[1:]]


def run(args):
    report,layout_report,cap_report=input_reports(args)
    output=args.output.resolve()
    if output.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    refs=c.base.verify_references(args.art_root.resolve())
    turnaround=args.art_root/'art_refs/characters/rin/concept/CH101_Rin_Turnaround_REVIEW_v001.png'
    if c.base.sha(turnaround)!=layout.panel.TURNAROUND_SHA:
        raise ValueError('TURNAROUND_REFERENCE_CHANGED')
    refs.append(dict(path=str(turnaround.resolve()),sha256=layout.panel.TURNAROUND_SHA))
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    surface.require_locked(bpy.context.scene)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
    digest=c.guide.digest(originals)
    signatures={o.name:surface.repair.invariant_signature(o) for o in originals}
    visible={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')}
    source=bpy.data.objects[prior.RESULT_OBJECT]
    design_record=design(source,report,cap_report,layout_report)
    separation_qa=separation(design_record)
    lines=guides(design_record)
    guide_qa=audit_guides(design_record)
    output.mkdir(parents=True)
    renders=[]
    if not args.no_render:
        ghost,material=layout.fold_review_ghost(source)
        for role in ('source','bounded','target'):
            folder=output/role
            folder.mkdir()
            for row in branch.render(folder,ghost,[o for o in lines if o['role']==role]):
                renders.append(dict(file=role+'/'+row['file'],sha256=row['sha256']))
        mesh=ghost.data
        bpy.data.objects.remove(ghost,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.materials.remove(material)
    if digest!=c.guide.digest(originals) or any(signatures[o.name]!=surface.repair.invariant_signature(o) for o in originals):
        raise ValueError('ORIGINAL_CHANGED')
    for name,(hidden,render_hidden) in visible.items():
        bpy.data.objects[name].hide_set(hidden)
        bpy.data.objects[name].hide_render=render_hidden
    for line in lines:
        line.hide_set(True)
        line.hide_render=True
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.preferences.filepaths.file_preview_type='NONE'
    blend=output/'CH101_BroadUnderarmSupportCurves_NOT_PRODUCTION_v001.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    result=dict(strategyId=STRATEGY,status='BROAD_CURVE_FEASIBILITY_ONLY_NOT_SURFACE_REBUILD',**c.base.GATES,
                sourceBlendSha256=SOURCE_SHA,sourceReportSha256=REPORT_SHA,layoutReportSha256=LAYOUT_SHA,
                capReportSha256=CAP_REPORT_SHA,artCommit=c.base.ART_COMMIT,references=refs,
                design=design_record,guideQA=guide_qa,separationQA=separation_qa,originalsPreserved=True,
                inheritedSurfaceQA=dict(recomputedHere=False,sourceReportSha256=REPORT_SHA,qa=report['qa']),
                adoptionAllowed=False,completeShoulderPanel=False,rigBound=False,fullCharacterScore=None,
                fullUnderarmRebuilt=False,majorFoldShapeRedesigned=False,deformationValidated=False,garmentStaticQA=False,
                originalBodyMovedVertices=0,originalBodyCumulativeMaximumMoveMeters=.002999919,
                blendFile=blend.name,blendSha256=c.base.sha(blend),renders=renders,
                limitations=['GUIDES_ONLY_NO_NEW_FACES_OR_COURSE_RELOCATION',
                             'FINITE_GUIDE_SAMPLES_NOT_BIDIRECTIONAL_MESH_QA_OR_CONTINUOUS_PROOF',
                             'DECLARED_WEIGHT_FAMILY_NOT_PROOF_ALL_BROAD_REDESIGNS_IMPOSSIBLE',
                             'PROVISIONAL_TORSO_CLIP_AND_18_DEFERRED_CREASE_EDGES_UNCHANGED',
                             'NO_THICKNESS_UV_RIG_CLEARANCE_DEFORMATION_OR_GARMENT_APPROVAL'])
    (output/'support-curves-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('CH101 broad underarm support curve feasibility — NOT PRODUCTION\nNine editable hidden POLY curves: amber source arcs, cyan bounded proposals, red stronger targets (not approved).\nNo mesh vertex, topology, UV, material or weight was changed; the previous assembly remains visible. Original branch-chart 1.5 mm limit and body cumulative 2.999919 mm / 3 mm remain.\nThe guide corridor is finite-sampled, not bidirectional surface QA or a proof that other broad designs are impossible. Stronger target failures do not authorize raising the limit.\nDo not adopt, sew, rig or import to Unity. Gate B pending.\n',encoding='utf-8')
    print('SAVED_SUPPORT_CURVES',result['blendSha256'],flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--layout-report',type=Path,required=True)
    parser.add_argument('--cap-report',type=Path,required=True)
    parser.add_argument('--art-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--no-render',action='store_true')
    run(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
