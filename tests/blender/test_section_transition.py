"""Provenance, scope, source preservation and static section-bridge regression."""
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
import build_ch101_section_transition as s
SOURCE=ARTIFACT=None


class SectionTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT];self.source=bpy.data.objects[s.interface.RESULT_OBJECT]
        self.chart=bpy.data.objects[s.prior.prior.RESULT_OBJECT]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
        self.parts=[o for o in self.originals if o.name.startswith('PAIR_STUDY_')]+[bpy.data.objects[s.interface.prior.prior.prior.RESULT_OBJECT]]

    def build(self):return s.build(self.source,self.chart,self.frame,self.body)

    def test_closed_arm_open_torso_and_edge_provenance(self):
        for height in (.0005,.002,.006,.012):
            points,paths,records=s.section_paths(self.chart,self.frame,height)
            self.assertEqual(sum(p['closed'] for p in paths),1)
            self.assertGreater(sum(not p['closed'] for p in paths),0)
            loop=next(p['indices'] for p in paths if p['closed'])
            for point,rec in zip(points,records):
                a,b=rec['sourceEdge'];t=rec['edgeT']
                self.assertGreaterEqual(t,0);self.assertLessEqual(t,1)
                expected=self.chart.data.vertices[a].co.lerp(self.chart.data.vertices[b].co,t)
                self.assertLess((point-expected).length,1e-7)
                self.assertLess(abs(s.signed_height(point,self.frame)-height),1e-6)
            for k in range(s.N):
                point,a,b,t=s.angular_hit(points,loop,self.frame,k)
                self.assertIn(a,loop);self.assertIn(b,loop)
                self.assertLess((point-points[a].lerp(points[b],t)).length,1e-7)

    def test_static_bridge_preserves_every_original_and_shared_seam(self):
        digest=s.c.guide.digest(self.originals)
        signatures={o.name:s.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=self.build();qa=s.audit(obj,self.body,self.parts,op,self.frame)
        self.assertTrue(qa['eligible']);self.assertEqual(qa['vertices'],10368)
        self.assertEqual(qa['faces'],18752);self.assertEqual(qa['triangles'],20736)
        self.assertEqual(qa['sharedSeamEdgeCountsInnerOuter'],[128,128])
        self.assertEqual(qa['sourceVertexMoveMeters'],0)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertTrue(all(v==0 for v in qa['intersectionPairsByObject'].values()))
        self.assertGreater(qa['minimumSampledBodyGapMeters'],.0002)
        self.assertGreater(qa['newPanelWallRangeMeters'][0],.0002)
        self.assertLess(qa['newPanelWallRangeMeters'][1],.0012)
        self.assertLess(qa['measuredNewSourceOffsetRangeMeters'][1],.006)
        self.assertEqual(op['spanMeters'],.012);self.assertFalse(op['completeShoulderPanel'])
        self.assertEqual(digest,s.c.guide.digest(self.originals))
        self.assertEqual(signatures,{o.name:s.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):self.build()
        altered=copy.deepcopy(op);altered['sections'][0]['samples'][0]['sourcePoint'][0]+=.001
        with self.assertRaisesRegex(ValueError,'PROVENANCE_MISMATCH'):s.audit(obj,self.body,self.parts,altered,self.frame)
        obj.data.vertices[s.idx(0,1,0)].co.x+=.001
        self.assertFalse(s.audit(obj,self.body,self.parts,op,self.frame)['eligible'])

    def test_insufficient_transition_gap_is_rejected(self):
        # Same scope and hard QA threshold: the slow initial bulge leaves a
        # triangle closer than 0.2 mm despite zero exact intersections.
        with patch.object(s,'CLEARANCE_TRANSITION_SPAN',.006):
            obj,op=self.build();qa=s.audit(obj,self.body,self.parts,op,self.frame)
            self.assertFalse(qa['eligible'])
            self.assertLess(qa['minimumSampledBodyGapMeters'],.0002)

    def test_ambiguous_higher_section_is_not_blindly_extended(self):
        with patch.object(s,'SPAN',.016):
            with self.assertRaisesRegex(ValueError,'NO_UNIQUE_CLOSED_ARM_SECTION'):self.build()
        self.assertIsNone(bpy.data.objects.get(s.RESULT_OBJECT))

    def test_invalid_input_and_unlocked_gates_fail_closed(self):
        args=SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-section-test')
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        real_sha=s.c.base.sha
        with patch.object(s.c.base,'sha',side_effect=lambda p:'0'*64 if p.name=='connected-shoulder-report.json' else real_sha(p)):
            with self.assertRaisesRegex(ValueError,'SOURCE_REPORT_SHA256_MISMATCH'):s.run(args)
        for value in (0,-1,float('nan'),.013):
            with self.assertRaisesRegex(ValueError,'HEIGHT_OUTSIDE_SCOPE'):s.section_paths(self.chart,self.frame,value)
        with self.assertRaisesRegex(ValueError,'INVALID_SECTION_FRAME'):
            s.build(self.source,self.chart,(self.frame[0],Vector(),self.frame[2]),self.body)
        self.body['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):self.build()

    def test_saved_artifact_reopens_without_promotion(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'section-transition-report.json').read_text())
        digest=s.c.guide.digest(self.originals);names=[o.name for o in self.originals]
        visible={o.name for o in self.originals if not o.hide_get()}
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        obj=bpy.data.objects[s.RESULT_OBJECT];body=bpy.data.objects[s.panel.RESULT_OBJECT]
        parts=[bpy.data.objects[name] for name in report['qa']['intersectionPairsByObject'] if name!=body.name]
        qa=s.audit(obj,body,parts,report['operation'],self.frame)
        self.assertTrue(qa['eligible']);self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        self.assertFalse(report['adoptionAllowed']);self.assertFalse(report['completeShoulderPanel'])
        self.assertIsNone(report['fullCharacterScore']);self.assertFalse(report['rigBound'])
        for subject in (obj,bpy.context.scene,report):s.surface.require_locked(subject)
        self.assertEqual(len(report['renders']),9)
        for rec in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/rec['file']),rec['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SectionTests))
    if not result.wasSuccessful():raise SystemExit(1)
