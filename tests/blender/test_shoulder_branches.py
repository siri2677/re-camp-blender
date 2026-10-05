"""Boundary graph regressions; passing does NOT approve a garment."""
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
import design_ch101_shoulder_branches as m
SOURCE=ARTIFACT=None

class BranchTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.chart=bpy.data.objects[m.s.prior.prior.RESULT_OBJECT]
        self.frame=m.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def build(self):
        obj,op=m.crop(self.chart,self.frame)
        return obj,op,m.design(obj,op)

    def test_disjoint_partition_and_original_preservation(self):
        digest=m.c.guide.digest(self.originals)
        inv={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op,design=self.build();qa=m.audit(obj,self.chart,op,design,self.frame)
        self.assertTrue(qa['eligible']);self.assertFalse(qa['garmentStaticQA'])
        self.assertEqual(len(design['paths']),4)
        self.assertEqual(sorted(i for group in design['faceRegions'] for i in group),list(range(len(obj.data.polygons))))
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):m.crop(self.chart,self.frame)

    def test_geometry_and_provenance_tampering_rejected(self):
        obj,op,design=self.build()
        changed=copy.deepcopy(op);changed['vertexProvenance'][0]['edgeT']=2
        with self.assertRaisesRegex(ValueError,'INVALID_SOURCE_INTERPOLATION'):m.audit(obj,self.chart,changed,design,self.frame)
        obj.data.vertices[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'QA_REJECTED'):m.audit(obj,self.chart,op,design,self.frame)

    def test_path_and_partition_tampering_rejected(self):
        obj,op,design=self.build()
        changed=copy.deepcopy(design);changed['paths']['front']=changed['paths']['back']
        with self.assertRaises(ValueError):m.audit(obj,self.chart,op,changed,self.frame)
        changed=copy.deepcopy(design);changed['faceRegions'][0].pop()
        with self.assertRaisesRegex(ValueError,'REGION_PARTITION'):m.audit(obj,self.chart,op,changed,self.frame)

    def test_missing_route_or_duplicated_target_fails_closed(self):
        obj,op,_=self.build()
        with patch.object(m,'TARGETS',{k:(-.085,0,1.1) for k in m.TARGETS}):
            with self.assertRaisesRegex(ValueError,'DUPLICATED_BRANCH_ANCHOR'):m.design(obj,op)
        with self.assertRaisesRegex(ValueError,'NO_DISJOINT_BRANCH_PATH'):
            m.shortest_path([v.co for v in obj.data.vertices],{0:set()},0,1,set())

    def test_hash_and_gate_validation(self):
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                m.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-branch-test'))
        self.chart['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.crop(self.chart,self.frame)

    def test_reopened_artifact_preserves_visibility_and_locks(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        names=[o.name for o in self.originals];digest=m.c.guide.digest(self.originals)
        visible={o.name for o in self.originals if not o.hide_get()}
        report=json.loads((ARTIFACT.parent/'branch-boundary-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,m.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        obj=bpy.data.objects[m.RESULT_OBJECT];chart=bpy.data.objects[m.s.prior.prior.RESULT_OBJECT]
        self.assertTrue(m.audit(obj,chart,report['operation'],report['design'],self.frame)['eligible'])
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        guides=[o for o in bpy.context.scene.objects if o.name.startswith('BRANCH_GUIDE_')]
        self.assertEqual(len(guides),9)
        for subject in [obj,bpy.context.scene,report]+guides:m.surface.require_locked(subject)
        self.assertTrue(all(o.hide_get() and o.hide_render for o in guides))
        self.assertFalse(report['adoptionAllowed']);self.assertFalse(report['completeShoulderPanel'])
        self.assertFalse(report['rigBound']);self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),4)
        for row in report['renders']:self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BranchTests))
    if not result.wasSuccessful():raise SystemExit(1)
