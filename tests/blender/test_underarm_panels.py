"""Real multi-interior panel replacement, cumulative bounds and prior preservation."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import rebuild_ch101_underarm_panels as m
ARGS=None


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports=m.input_reports(ARGS)
        cls.record=json.loads((ARGS.artifact.parent/'underarm-panels-report.json').read_text())

    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.artifact))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.obj=bpy.data.objects[m.RESULT_OBJECT]
        self.ctx=m.context(self.source,*self.reports)

    def test_actual_replacement_and_full_surface_audit(self):
        qa=m.audit(self.obj,self.source,self.reports,self.record['operation'])
        self.assertEqual(qa,self.record['qa'])
        self.assertTrue(qa['eligible'])
        self.assertEqual((qa['vertices'],qa['triangles']),(2697,5036))
        self.assertEqual((qa['removedInteriorVertices'],qa['addedSupportVertices']),(3,1))
        self.assertEqual((qa['patches'][0]['removedTriangles'],qa['patches'][0]['replacementTriangles']),(21,17))
        self.assertEqual((qa['preservedLayoutEdges'],qa['preservedPreviousPatchFaces']),(907,50))
        self.assertEqual(qa['maximumRetainedVertexMoveMeters'],0)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertAlmostEqual(qa['patches'][0]['after']['maximumDegrees'],37.23212956,places=5)
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),.0015)
        self.assertTrue(qa['densePatchQA']['eligible'])
        self.assertEqual((qa['densePatchQA']['forwardSamples'],qa['densePatchQA']['reverseLocalOriginalSamples']),(1547,221))
        self.assertFalse(qa['fullUnderarmRebuilt'])

    def test_entire_declared_search_replays_and_selects_same_panel(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.source))
        source=bpy.data.objects[m.prior.RESULT_OBJECT]
        obj,op,selection=m.build(source,self.reports)
        self.assertEqual(selection,self.record['selection'])
        self.assertEqual(op,self.record['operation'])
        self.assertEqual(selection['partitionCandidateCount'],68)
        self.assertEqual(len(selection['candidates']),16)
        self.assertEqual(sum(r['singlePanelQA']['eligible'] for r in selection['candidates']),2)
        self.assertEqual(selection['selectedIdentity'],dict(seedVertex=910,domain=7,faceRings=2,supportTargetMeters=.00145))
        self.assertTrue(m.audit(obj,source,self.reports,op)['eligible'])

    def trial(self,seed,target):
        row=next(r for r in self.record['selection']['candidates'] if r['seedVertex']==seed and r.get('supportInsertion',{}).get('targetMeters')==target)
        clean={k:v for k,v in row.items() if k!='singlePanelQA'}
        return m.compose(self.source,self.ctx,[clean],m.RESULT_OBJECT+'_TEST')

    def test_low_bending_is_not_original_surface_approval(self):
        obj,op=self.trial(910,None)
        qa=m.measure(obj,self.source,self.ctx,op)
        self.assertTrue(qa['patches'][0]['eligible'])
        self.assertGreater(qa['maximumReverseOriginalChartSampleErrorMeters'],m.LIMIT)
        self.assertFalse(qa['eligible'])

    def test_low_error_is_not_crease_approval(self):
        obj,op=self.trial(1071,.00145)
        qa=m.measure(obj,self.source,self.ctx,op)
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),m.LIMIT)
        self.assertGreater(qa['patches'][0]['after']['maximumDegrees'],55)
        self.assertFalse(qa['eligible'])

    def test_low_error_is_not_bending_gain_approval(self):
        obj,op=self.trial(1101,.00145)
        qa=m.measure(obj,self.source,self.ctx,op)
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),m.LIMIT)
        self.assertGreater(qa['afterBending']['weightedRadiansSquaredMeters'],qa['beforeBending']['weightedRadiansSquaredMeters'])
        self.assertFalse(qa['eligible'])

    def test_single_vertex_star_is_not_a_multi_interior_panel(self):
        found=False
        for seed in self.ctx['seeds']:
            try:
                m.boundary(self.source,self.ctx,self.ctx['vertexFaces'][seed])
            except ValueError as error:
                found=found or str(error)=='NOT_MULTI_INTERIOR_PANEL'
        self.assertTrue(found)
        with self.assertRaisesRegex(ValueError,'PREVIOUS_PATCH_TOUCHED'):
            m.boundary(self.source,self.ctx,self.ctx['preservedFaces'])

    def test_support_point_and_witness_recipe_tampering_rejected(self):
        for change in ('supportPoints','supportInsertion'):
            op=copy.deepcopy(self.record['operation'])
            if change=='supportPoints':
                op['panels'][0]['supportPoints'][0][0]+=.001
            else:
                op['panels'][0]['supportInsertion']['originalWitness']['point'][0]+=.001
            with self.assertRaisesRegex(ValueError,'PROVENANCE_CHANGED'):
                m.audit(self.obj,self.source,self.reports,op)

    def test_vertex_face_maps_and_region_tampering_rejected(self):
        op=copy.deepcopy(self.record['operation'])
        op['keptSourceVertices'][0]=op['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'MAP_CHANGED'):
            m.audit(self.obj,self.source,self.reports,op)
        self.obj.data.polygons[0].material_index=(self.obj.data.polygons[0].material_index+1)%16
        with self.assertRaisesRegex(ValueError,'TOPOLOGY_OR_REGION_CHANGED'):
            m.audit(self.obj,self.source,self.reports,self.record['operation'])

    def test_retained_and_nonfinite_vertex_edits_rejected(self):
        self.obj.data.vertices[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'POSITION_CHANGED'):
            m.audit(self.obj,self.source,self.reports,self.record['operation'])
        self.obj.data.vertices[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'NONFINITE_PANEL_VERTEX'):
            m.audit(self.obj,self.source,self.reports,self.record['operation'])

    def test_upstream_map_and_preservation_set_guards(self):
        bad=copy.deepcopy(self.reports)
        bad[0]['operation']['keptSourceVertices'][0]=bad[0]['operation']['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'INVALID_UPSTREAM_VERTEX_MAP'):
            m.context(self.source,*bad)
        bad=copy.deepcopy(self.reports)
        bad[0]['operation']['patchFaceIndices'][0].append(0)
        with self.assertRaisesRegex(ValueError,'PRESERVATION_SET_CHANGED'):
            m.context(self.source,*bad)

    def test_boundary_guide_and_nan_guards(self):
        self.assertEqual(m.audit_guides(self.source,self.record['operation'])['guideCount'],1)
        obj=bpy.data.objects[m.GUIDE_PREFIX+'0']
        obj.data.splines[0].points[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'GUIDE_POSITION_CHANGED'):
            m.audit_guides(self.source,self.record['operation'])
        obj.data.splines[0].points[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'GUIDE_POSITION_CHANGED'):
            m.audit_guides(self.source,self.record['operation'])

    def test_all_original_meshes_guides_uv_weights_and_visibility_preserved(self):
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=self.obj]
        digest=m.c.guide.digest(meshes)
        signatures={o.name:m.surface.repair.invariant_signature(o) for o in meshes}
        curves={o.name:m.curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE' and not o.name.startswith(m.GUIDE_PREFIX)}
        visibility={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and o!=self.obj and not o.name.startswith(m.GUIDE_PREFIX)}
        self.assertTrue(self.obj.hide_get())
        self.assertTrue(self.obj.hide_render)
        self.assertFalse(any(o.name.startswith(('PanelCompare','PanelWire','PanelLabel',m.RESULT_OBJECT+'_REPLAY',m.RESULT_OBJECT+'_EXPECTED')) for o in bpy.context.scene.objects))
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.source))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.assertEqual(digest,m.c.guide.digest(meshes))
        self.assertEqual(signatures,{o.name:m.surface.repair.invariant_signature(o) for o in meshes})
        self.assertEqual(curves,{o.name:m.curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE'})
        self.assertEqual(visibility,{o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')})

    def test_saved_files_gates_and_scope(self):
        self.assertEqual(m.c.base.sha(ARGS.artifact),self.record['blendSha256'])
        self.assertEqual(len(self.record['renders']),17)
        for row in self.record['renders']:
            self.assertEqual(m.c.base.sha(ARGS.artifact.parent/row['file']),row['sha256'])
        for subject in (bpy.context.scene,self.obj,self.record):
            m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound','fullUnderarmRebuilt','majorFoldShapeRedesigned','deformationValidated','garmentStaticQA','courseBoundaryRelocationApplied'):
            self.assertIs(self.record[key],False)
        self.assertIsNone(self.record['fullCharacterScore'])

    def test_input_hash_existing_output_and_output_object_guards(self):
        args=SimpleNamespace(**vars(ARGS))
        args.output=ARGS.source.parent
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                m.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            m.run(args)
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):
            m.compose(self.source,self.ctx,self.record['operation']['panels'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--disk-report',type=Path,required=True)
    p.add_argument('--cap-report',type=Path,required=True)
    p.add_argument('--layout-report',type=Path,required=True)
    p.add_argument('--artifact',type=Path,required=True)
    ARGS=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PanelTests)).wasSuccessful():
        raise SystemExit(1)
