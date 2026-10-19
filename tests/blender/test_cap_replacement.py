"""Actual cap-disk replacement, not whole-shoulder or garment approval."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import rebuild_ch101_cap_patch as m
SOURCE = ARTIFACT = None


class CapReplacementTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        self.source_report = json.loads((SOURCE.parent/'deformation-layout-report.json').read_text())
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[m.prior.RESULT_OBJECT]
        self.originals = [o for o in bpy.context.scene.objects if o.type=='MESH']

    def restored(self):
        if ARTIFACT is None:
            self.skipTest('Saved artifact required')
        report = json.loads((ARTIFACT.parent/'cap-replacement-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        return bpy.data.objects[m.RESULT_OBJECT],bpy.data.objects[m.prior.RESULT_OBJECT],report

    def test_actual_replacement_removes_crease_and_preserves_originals(self):
        digest = m.c.guide.digest(self.originals)
        inv = {o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op = m.build(self.source,self.source_report)
        qa = m.audit(obj,self.source,self.source_report,op)
        self.assertTrue(qa['eligible'])
        self.assertEqual((qa['vertices'],qa['triangles']),(2704,5050))
        self.assertEqual((qa['removedTriangles'],qa['replacementTriangles'],qa['removedInteriorVertices']),(20,14,3))
        self.assertEqual(qa['preservedPatchBoundaryVertices'],16)
        self.assertEqual(qa['preservedLayoutEdges'],907)
        self.assertEqual(qa['maximumRetainedVertexMoveMeters'],0)
        self.assertEqual((qa['capBefore']['edgesAbove55Degrees'],qa['capAfter']['edgesAbove55Degrees']),(2,0))
        self.assertLess(qa['capAfter']['weightedRadiansSquaredMeters'],qa['capBefore']['weightedRadiansSquaredMeters'])
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),.0015)
        self.assertFalse(qa['fullUnderarmRebuilt'])
        self.assertFalse(qa['garmentStaticQA'])
        self.assertFalse(qa['deformationValidated'])
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):
            m.build(self.source,self.source_report)

    def test_polygon_dp_handles_concavity_and_rejects_incompatible_boundary(self):
        points = [Vector(p) for p in [(0,0,0),(2,0,0),(2,1,0),(1,.3,0),(0,1,0)]]
        border = list(range(5))
        neighbors = {tuple(sorted((a,b))):Vector((0,0,1)) for a,b in zip(border,border[1:]+border[:1])}
        faces,_ = m.triangulate_boundary(points,border,neighbors)
        self.assertEqual(len(faces),3)
        edges = m.prior.prior.edge_faces(faces)
        self.assertEqual({e for e,fs in edges.items() if len(fs)==1},set(neighbors))
        self.assertTrue(all((points[b]-points[a]).cross(points[d]-points[a]).z>0 for a,b,d in faces))
        with self.assertRaisesRegex(ValueError,'NO_SAFE_CAP_BOUNDARY_TRIANGULATION'):
            m.triangulate_boundary(points,border,{e:-n for e,n in neighbors.items()})

    def test_naive_underarm_fill_is_rejected_without_changing_geometry(self):
        digest = m.c.guide.digest([self.source])
        probe = m.probe_underarm_disk(self.source,self.source_report)
        self.assertEqual(probe['selectedFaces'],318)
        self.assertEqual(probe['boundaryComponentEdgeCounts'],[203,3])
        self.assertEqual(probe['branchingBoundaryVertices'],1)
        self.assertEqual(probe['courseVerticesTouched'],75)
        self.assertEqual(probe['sourceRegions'],[0,1])
        self.assertFalse(probe['simpleBoundary'])
        self.assertFalse(probe['canAutoFillAsOneDisk'])
        self.assertEqual(digest,m.c.guide.digest([self.source]))

    def test_policy_and_disk_identity_tampering_rejected(self):
        bad = copy.deepcopy(self.source_report)
        next(g for g in bad['design']['majorFoldGroups'] if g['id']==1874)['policy']='KEEP'
        with self.assertRaisesRegex(ValueError,'CAP_POLICY_CHANGED'):
            m.extract(self.source,bad)
        bad = copy.deepcopy(self.source_report)
        next(g for g in bad['design']['majorFoldGroups'] if g['id']==1874)['sourceEdges'][0][0]=0
        with self.assertRaisesRegex(ValueError,'CAP_DISK_IDENTITY_CHANGED|PATCH_'):
            m.extract(self.source,bad)

    def test_provenance_and_recipe_tampering_rejected(self):
        obj,source,report = self.restored()
        for key in ('keptSourceVertices','removedFaces','replacementFaceIndices'):
            bad = copy.deepcopy(report['operation'])
            bad[key].pop()
            with self.assertRaisesRegex(ValueError,'CAP_'):
                m.audit(obj,source,self.source_report,bad)
        bad = copy.deepcopy(report['operation'])
        bad['replacementSourceTriangles'][0][0]=0
        with self.assertRaisesRegex(ValueError,'CAP_TRIANGULATION_RECORD_CHANGED'):
            m.audit(obj,source,self.source_report,bad)

    def test_changed_retained_point_is_not_eligible(self):
        obj,source,report = self.restored()
        obj.data.vertices[0].co.x+=.004
        obj.data.update()
        self.assertFalse(m.audit(obj,source,self.source_report,report['operation'])['eligible'])

    def test_outside_face_and_material_changes_rejected(self):
        obj,source,report = self.restored()
        obj.data.polygons[0].material_index=(obj.data.polygons[0].material_index+1)%16
        with self.assertRaisesRegex(ValueError,'CAP_OUTSIDE_TOPOLOGY_OR_REGION_CHANGED'):
            m.audit(obj,source,self.source_report,report['operation'])

    def test_good_triangle_shape_alone_is_not_a_surface_pass(self):
        obj,op = m.build(self.source,self.source_report,shape_only=True)
        qa = m.audit(obj,self.source,self.source_report,op)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),m.MAX_ERROR)
        self.assertGreater(qa['capAfter']['weightedRadiansSquaredMeters'],qa['capBefore']['weightedRadiansSquaredMeters'])
        self.assertGreater(qa['capAfter']['edgesAbove55Degrees'],0)
        self.assertFalse(qa['eligible'])

    def test_source_hash_gates_and_output_guards(self):
        args = SimpleNamespace(source=SOURCE,output=SOURCE.parent)
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                m.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            m.run(args)
        self.source['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            m.extract(self.source,self.source_report)

    def test_saved_artifact_reopens_with_originals_visibility_and_locks(self):
        names = [o.name for o in self.originals]
        digest = m.c.guide.digest(self.originals)
        inv = {o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        visible = {o.name for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()}
        obj,source,report = self.restored()
        restored = [bpy.data.objects[n] for n in names]
        self.assertEqual(digest,m.c.guide.digest(restored))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in restored})
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()})
        self.assertTrue(obj.hide_get() and obj.hide_render)
        self.assertIsNone(bpy.data.objects.get('CapPatchWire_RENDER_ONLY'))
        self.assertEqual(m.audit(obj,source,self.source_report,report['operation']),report['qa'])
        for subject in (obj,bpy.context.scene,report):
            m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound'):
            self.assertFalse(report[key])
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),12)
        for row in report['renders']:
            self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE=args.source.resolve()
    ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CapReplacementTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
