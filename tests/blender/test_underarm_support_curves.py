"""Broad curve feasibility, upstream provenance and saved artifact guards."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import design_ch101_underarm_support_curves as m
ARGS=None


def curve_snapshot(obj):
    return (list(map(list,obj.matrix_world)),
            [(s.type,s.use_cyclic_u,[list(p.co) for p in s.points]) for s in obj.data.splines])


class SupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report,cls.layout_report,cls.cap_report=m.input_reports(ARGS)
        cls.saved=json.loads((ARGS.artifact.parent/'support-curves-report.json').read_text())

    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.artifact))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]

    def test_all_45_trials_replay_and_source_course_provenance(self):
        qa=m.audit_design(self.source,self.report,self.cap_report,self.layout_report,self.saved['design'])
        self.assertEqual(qa['replayedTrialCount'],45)
        self.assertEqual(qa['boundedCurveCount'],3)
        self.assertTrue(qa['separation']['centerlinesSeparated'])
        self.assertEqual(qa['separation'],self.saved['separationQA'])
        self.assertEqual([r['selectedWeight'] for r in self.saved['design']['courses']],[2.,2.,8.])
        for row in self.saved['design']['courses']:
            self.assertTrue(row['selectedQA']['guideCorridorPassed'])
            self.assertFalse(row['broadTargetQA']['guideCorridorPassed'])
            self.assertGreater(row['broadTargetQA']['maximumOriginalChartDistanceMeters'],.01)
            self.assertGreater(row['sourceStats']['lengthMeters'],.17)

    def test_record_and_nan_tampering_rejected(self):
        # Real deterministic replay is independently tested above. Reuse that
        # expected record here to check rejection without 135 duplicate fits.
        expected=copy.deepcopy(self.saved['design'])
        for key,value in [('selectedWeight',128.),('selectedPoints',[[float('nan'),0,0]])]:
            bad=copy.deepcopy(expected)
            bad['courses'][0][key]=value
            with patch.object(m,'design',return_value=expected):
                with self.assertRaisesRegex(ValueError,'DESIGN_RECORD_CHANGED'):
                    m.audit_design(self.source,self.report,self.cap_report,self.layout_report,bad)

    def test_whole_curve_fit_endpoints_and_objective(self):
        p=[[i/20,.01*np.sin(i*1.3),0] for i in range(21)]
        baseline=m.fit(p,0)
        fitted=m.fit(p,2048)
        np.testing.assert_array_equal(fitted[[0,-1]],np.asarray(p)[[0,-1]])
        self.assertLess(m.curve_stats(fitted)['discreteCurvatureSquaredIntegralPerMeter'],m.curve_stats(baseline)['discreteCurvatureSquaredIntegralPerMeter'])
        for weight in (-1,float('nan'),float('inf')):
            with self.assertRaisesRegex(ValueError,'INVALID_FAIRING_WEIGHT'):
                m.fit(p,weight)
        with self.assertRaisesRegex(ValueError,'DEGENERATE_CURVE'):
            m.fit([[0,0,0],[0,0,0]],1)

    def test_source_surface_guard_is_not_just_curve_proximity(self):
        tree=BVHTree.FromPolygons([Vector((-1,-1,0)),Vector((1,-1,0)),Vector((0,1,0))],[(0,1,2)],all_triangles=True)
        p=[[-.1,0,.003],[0,0,.003],[.1,0,.003]]
        qa=m.feasibility(p,p,tree,tree)
        self.assertAlmostEqual(qa['maximumSourceArcToProposalMeters'],0)
        self.assertGreater(qa['maximumOriginalChartDistanceMeters'],m.LIMIT)
        self.assertFalse(qa['guideCorridorPassed'])

    def test_upstream_map_and_course_position_tampering_rejected(self):
        bad=copy.deepcopy(self.report)
        bad['operation']['keptSourceVertices'][0]=bad['operation']['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'INVALID_UPSTREAM_VERTEX_MAP'):
            m.sectors(self.source,bad,self.cap_report,self.layout_report)
        idx=self.saved['design']['courses'][0]['sourceVertices'][1]
        self.source.data.vertices[idx].co.x+=.001
        with self.assertRaisesRegex(ValueError,'UPSTREAM_COURSE_POSITION_CHANGED'):
            m.sectors(self.source,self.report,self.cap_report,self.layout_report)

    def test_saved_guides_and_mutation_guards(self):
        self.assertEqual(m.audit_guides(self.saved['design'])['guideCount'],9)
        obj=bpy.data.objects[m.PREFIX+'0_bounded']
        obj.data.splines[0].points[3].co.x+=.001
        with self.assertRaisesRegex(ValueError,'SUPPORT_GUIDE_POSITION_CHANGED'):
            m.audit_guides(self.saved['design'])
        obj.data.splines[0].points[3].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'SUPPORT_GUIDE_POSITION_CHANGED'):
            m.audit_guides(self.saved['design'])

    def test_crossing_or_coincident_guides_not_accepted(self):
        bad=copy.deepcopy(self.saved['design'])
        bad['courses'][1]['selectedPoints']=bad['courses'][0]['selectedPoints']
        with self.assertRaisesRegex(ValueError,'SEPARATION_NOT_ESTABLISHED'):
            m.separation(bad)

    def test_nonadjacent_self_crossings_and_parallel_segments(self):
        self.assertEqual(m.self_intersections([[0,0,0],[1,1,0],[0,1,0],[1,0,0]]),1)
        self.assertAlmostEqual(m.segment_distance(*map(np.asarray,[[0,0,0],[1,0,0],[.3,1,0],[.7,1,0]])),1.)
        self.assertAlmostEqual(m.segment_distance(*map(np.asarray,[[0,0,0],[1,0,0],[.3,0,0],[.7,0,0]])),0.)
        bad=copy.deepcopy(self.saved['design'])
        bad['courses'][0]['selectedPoints']=[[0,0,0],[1,1,0],[0,1,0],[1,0,0]]
        with self.assertRaisesRegex(ValueError,'SELF_INTERSECTION'):
            m.separation(bad)

    def test_all_upstream_meshes_guides_and_visibility_preserved(self):
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        digest=m.c.guide.digest(meshes)
        signatures={o.name:m.surface.repair.invariant_signature(o) for o in meshes}
        old_guides={o.name:curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE' and not o.name.startswith(m.PREFIX)}
        visibility={o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.name.startswith(m.PREFIX)}
        for o in bpy.context.scene.objects:
            if o.name.startswith(m.PREFIX):
                self.assertTrue(o.hide_get())
                self.assertTrue(o.hide_render)
                m.surface.require_locked(o)
        bpy.ops.wm.open_mainfile(filepath=str(ARGS.source))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.assertEqual(digest,m.c.guide.digest(meshes))
        self.assertEqual(signatures,{o.name:m.surface.repair.invariant_signature(o) for o in meshes})
        self.assertEqual(old_guides,{o.name:curve_snapshot(o) for o in bpy.context.scene.objects if o.type=='CURVE'})
        self.assertEqual(visibility,{o.name:(o.hide_get(),o.hide_render) for o in bpy.context.scene.objects if o.type in ('MESH','CURVE')})

    def test_artifact_hashes_gates_and_scope(self):
        self.assertEqual(m.c.base.sha(ARGS.artifact),self.saved['blendSha256'])
        self.assertEqual(len(self.saved['renders']),12)
        for row in self.saved['renders']:
            self.assertEqual(m.c.base.sha(ARGS.artifact.parent/row['file']),row['sha256'])
        m.surface.require_locked(bpy.context.scene)
        m.surface.require_locked(self.saved)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound','fullUnderarmRebuilt','majorFoldShapeRedesigned','deformationValidated','garmentStaticQA'):
            self.assertIs(self.saved[key],False)
        self.assertFalse(self.saved['design']['geometryShapeChanged'])
        self.assertIsNone(self.saved['fullCharacterScore'])

    def test_wrong_source_hash_and_existing_output_rejected(self):
        args=SimpleNamespace(**vars(ARGS))
        args.output=ARGS.source.parent
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                m.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            m.run(args)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--layout-report',type=Path,required=True)
    parser.add_argument('--cap-report',type=Path,required=True)
    parser.add_argument('--artifact',type=Path,required=True)
    ARGS=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SupportTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)
