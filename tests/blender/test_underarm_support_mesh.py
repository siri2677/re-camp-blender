"""Actual latest-source regression for forward-only original-chart violations."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_underarm_support_mesh as m
ARGS=None


class SupportMeshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports=m.input_reports(ARGS)
        cls.record=json.loads((ARGS.artifact.parent/'support-mesh-report.json').read_text()) if ARGS.artifact else None

    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.source.resolve()))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.ctx=m.context(self.source,self.reports)

    def test_forward_only_violation_creates_a_real_interior_support(self):
        rows,_=m.prior.candidates(self.source,self.ctx)
        row=next(r for r in rows if (r['seedVertex'],r['domain'],r['faceRings'])==(887,6,1))
        recipe=m.prior.triangulate(self.source,self.ctx,row)
        qa=m.measure_row(self.source,self.ctx,recipe)
        self.assertGreater(qa['maximumForwardOriginalChartSampleErrorMeters'],m.LIMIT)
        self.assertLessEqual(qa['maximumReverseOriginalChartSampleErrorMeters'],m.LIMIT)
        repaired=m.insert_knot(self.ctx,recipe,qa,.0012)
        self.assertEqual(len(repaired['supportPoints']),1)
        self.assertEqual(repaired['supportSteps'][0]['direction'],'FORWARD_PATCH_TO_CHART')

    def test_dense_error_does_not_disappear_behind_coarse_pass(self):
        rows,_=m.prior.candidates(self.source,self.ctx)
        row=next(r for r in rows if (r['seedVertex'],r['domain'],r['faceRings'])==(887,6,1))
        recipe=m.prior.triangulate(self.source,self.ctx,row)
        for _ in range(3):recipe=m.insert_knot(self.ctx,recipe,m.measure_row(self.source,self.ctx,recipe),.0012)
        qa=m.measure_row(self.source,self.ctx,recipe)
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),m.LIMIT)
        self.assertFalse(qa['eligible']);self.assertFalse(qa['densePatchQA']['eligible'])
        repaired=m.insert_knot(self.ctx,recipe,qa,.0012)
        self.assertEqual(len(repaired['supportPoints']),4)
        self.assertEqual(repaired['supportSteps'][-1]['witness']['sampleKind'],'DENSE_BARYCENTRIC')
        with self.assertRaisesRegex(ValueError,'BUDGET_OR_TARGET_INVALID'):m.insert_knot(self.ctx,repaired,qa,.0012)

    def artifact(self):
        if ARGS.artifact is None:self.skipTest('Saved artifact required')
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.artifact));self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        return bpy.data.objects[m.RESULT_OBJECT]

    def test_actual_geometry_and_preservation(self):
        obj=self.artifact();qa=m.audit(obj,self.source,self.reports,self.record['operation'])
        self.assertEqual(qa,self.record['qa']);self.assertTrue(qa['eligible'])
        self.assertEqual((qa['vertices'],qa['triangles']),(2693,5028))
        self.assertEqual((qa['preservedLayoutEdges'],qa['preservedPreviousPatchFaces']),(907,67))
        self.assertEqual((qa['removedInteriorVertices'],qa['addedSupportVertices']),(5,1))
        self.assertEqual(qa['maximumRetainedVertexMoveMeters'],0)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertTrue(qa['densePatchQA']['eligible'])
        self.assertLess(qa['patches'][0]['after']['maximumDegrees'],55)
        self.assertAlmostEqual(qa['afterBending']['maximumDegrees'],134.755862,places=5)

    def test_entire_finite_search_selects_the_same_recipe(self):
        if self.record is None:self.skipTest('Saved record required')
        obj,op,selection=m.build(self.source,self.reports)
        self.assertEqual(selection,self.record['selection'])
        self.assertEqual(op,self.record['operation'])
        self.assertTrue(m.audit(obj,self.source,self.reports,op)['eligible'])
        self.assertEqual((selection['partitionCount'],selection['seedCount'],len(selection['trials']),selection['actualGeometryMeasurements']),(61,39,52,42))
        self.assertEqual(len(selection['passing']),3)

    def test_recipe_witness_and_support_point_tampering_rejected(self):
        obj=self.artifact()
        for key in ('point','witness','direction'):
            op=copy.deepcopy(self.record['operation'])
            if key=='point':op['panels'][0]['supportPoints'][0][0]+=.001
            elif key=='witness':op['panels'][0]['supportSteps'][0]['witness']['point'][0]+=.001
            else:op['panels'][0]['supportSteps'][0]['direction']='REVERSE_CHART_TO_PATCH'
            with self.assertRaisesRegex(ValueError,'PROVENANCE_CHANGED'):m.audit(obj,self.source,self.reports,op)

    def test_maps_topology_materials_and_nonfinite_edits_rejected(self):
        obj=self.artifact();op=copy.deepcopy(self.record['operation'])
        op['keptSourceVertices'][0]=op['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'MAP_CHANGED'):m.audit(obj,self.source,self.reports,op)
        obj.data.polygons[0].material_index=(obj.data.polygons[0].material_index+1)%16
        with self.assertRaisesRegex(ValueError,'TOPOLOGY_OR_REGION_CHANGED'):m.audit(obj,self.source,self.reports,self.record['operation'])
        obj=self.artifact();obj.data.vertices[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'POSITION_CHANGED'):m.audit(obj,self.source,self.reports,self.record['operation'])
        obj.data.vertices[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'NONFINITE_SUPPORT_VERTEX'):m.audit(obj,self.source,self.reports,self.record['operation'])

    def test_preservation_and_gate_tampering_rejected(self):
        bad=copy.deepcopy(self.reports);bad[-1]['operation']['keptSourceVertices'][0]=bad[-1]['operation']['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'VERTEX_MAP_CHANGED'):m.context(self.source,bad)
        bad=copy.deepcopy(self.reports);bad[-1]['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.context(self.source,bad)
        obj=self.artifact();obj['productionPromotionAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.audit(obj,self.source,self.reports,self.record['operation'])

    def test_guide_mutation_rejected(self):
        self.artifact();row=self.record['operation']['panels'][0]
        self.assertEqual(m.audit_guide(self.source,row)['guideCount'],1)
        line=bpy.data.objects[m.GUIDE_PREFIX+'0'];line.data.splines[0].points[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'GUIDE_POSITION_CHANGED'):m.audit_guide(self.source,row)

    def test_saved_scene_originals_visibility_and_all_hashes(self):
        if self.record is None:self.skipTest('Saved record required')
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];names=[o.name for o in meshes]
        digest=m.c.guide.digest(meshes);signatures={o.name:m.surface.repair.invariant_signature(o) for o in meshes}
        curves={o.name:m.prior.curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE'}
        visibility={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')}
        obj=self.artifact()
        self.assertEqual(digest,m.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(signatures,{n:m.surface.repair.invariant_signature(bpy.data.objects[n]) for n in names})
        self.assertEqual(curves,{n:m.prior.curve_snapshot(bpy.data.objects[n]) for n in curves})
        self.assertEqual(visibility,{n:(bpy.data.objects[n].hide_get(),bpy.data.objects[n].hide_render) for n in visibility})
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        for subject in (obj,self.record,bpy.context.scene):m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound','fullUnderarmRebuilt','majorFoldShapeRedesigned','garmentStaticQA','deformationValidated','courseBoundaryRelocationApplied'):self.assertFalse(self.record[key])
        self.assertIsNone(self.record['fullCharacterScore'])
        self.assertEqual(m.c.base.sha(ARGS.artifact),self.record['blendSha256'])
        self.assertEqual(len(self.record['renders']),17)
        for row in self.record['renders']:self.assertEqual(m.c.base.sha(ARGS.artifact.parent/row['file']),row['sha256'])

    def test_input_and_output_guards(self):
        args=SimpleNamespace(**vars(ARGS));args.output=ARGS.source.parent
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):m.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):m.run(args)
        self.artifact()
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):m.build(self.source,self.reports)

    def test_remaining_fold_classification_is_read_only_and_not_an_impossibility_claim(self):
        obj=self.artifact();before=m.c.guide.digest([obj])
        actual=m.crease_constraints(obj,self.source,self.reports,self.record['operation'])
        saved=json.loads((ARGS.artifact.parent/'remaining-crease-report.json').read_text())
        self.assertEqual(actual,saved)
        self.assertEqual((actual['majorEdgeCount'],actual['protectedMajorEdgeCount'],actual['unprotectedMajorEdgeCount']),(63,8,55))
        self.assertFalse(actual['edges'][0]['protectedDesignEdge'])
        self.assertEqual(actual['edges'][0]['domains'],[6,6])
        self.assertFalse(actual['boundaryRelocationApplied']);self.assertFalse(actual['impossibilityProved'])
        self.assertEqual(before,m.c.guide.digest([obj]))


if __name__=='__main__':
    p=m.parser();p.add_argument('--artifact',type=Path)
    p.add_argument('--test-name')
    ARGS=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    suite=unittest.TestSuite([SupportMeshTests(ARGS.test_name)]) if ARGS.test_name else unittest.defaultTestLoader.loadTestsFromTestCase(SupportMeshTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
