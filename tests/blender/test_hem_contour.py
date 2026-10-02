"""Bounded section translations, cumulative envelope, negative gates and reopen."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_hem_contour as s
SOURCE=ARTIFACT=None


class ContourTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.band=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.anchor=bpy.data.objects[s.prior.prior.RESULT_OBJECT]
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]

    def test_actual_contour_improvement_and_preservation(self):
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        digest=s.c.guide.digest(originals)
        obj,r=s.build(self.band)
        self.assertLess(r['after']['maximumTurnDegrees'],r['before']['maximumTurnDegrees'])
        self.assertLess(r['after']['rmsTurnDegrees'],r['before']['rmsTurnDegrees'])
        self.assertLessEqual(r['maxMoveMeters'],.0001001)
        self.assertEqual(s.surface.repair.invariant_signature(obj),s.surface.repair.invariant_signature(self.band))
        for i in range(128):
            first=obj.data.vertices[16*i].co-self.band.data.vertices[16*i].co
            for j in range(16):
                delta=obj.data.vertices[16*i+j].co-self.band.data.vertices[16*i+j].co
                self.assertLessEqual((delta-first).length,1e-7)
        self.assertEqual(digest,s.c.guide.digest(originals))
        self.assertEqual(len(obj.data.vertices),2048)
        with self.assertRaisesRegex(ValueError,'CONTOUR_ALREADY_EXISTS'):s.build(self.band)

    def test_cumulative_anchor_and_clearance(self):
        obj,_=s.build(self.band)
        qa=s.prior.audit(obj,self.anchor,self.body,self.parts)
        self.assertTrue(qa['eligible'],qa)
        self.assertLessEqual(max(qa['maximumSampledNewToOldDistanceMeters'],qa['maximumSampledOldToNewDistanceMeters']),.0002)
        self.assertGreater(qa['minimumSampledBodyGapMeters'],.0002)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertFalse(any(qa['intersectionPairsByObject'].values()))
        obj.location.x+=.003;bpy.context.view_layer.update()
        self.assertFalse(s.prior.audit(obj,self.anchor,self.body,self.parts)['eligible'])

    def test_parameters_hash_gate(self):
        names=set(bpy.data.objects.keys())
        for bound in (0,-1,.000101,float('nan')):
            with self.assertRaisesRegex(ValueError,'UNSAFE_CONTOUR_MOVE'):s.build(self.band,bound)
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_ROUNDED_HEM_TOPOLOGY'):s.build(self.body)
        self.assertEqual(names,set(bpy.data.objects.keys()))
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                s.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-contour-test')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        self.band['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.band)

    def test_bad_contour_and_open_mesh(self):
        with self.assertRaisesRegex(ValueError,'INVALID_CONTOUR'):s.contour_metrics([Vector()])
        with self.assertRaisesRegex(ValueError,'COLLAPSED_CONTOUR_SEGMENT'):s.contour_metrics([Vector() for _ in range(128)])
        obj,_=s.build(self.band)
        bm=s.prior.bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        s.prior.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        self.assertFalse(s.prior.audit(obj,self.anchor,self.body,self.parts)['eligible'])

    def test_saved_reopen_hashes_gates(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        names=[o.name for o in originals];digest=s.c.guide.digest(originals)
        r=json.loads((ARTIFACT.parent/'hem-contour-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),r['blendSha256'])
        self.assertEqual(r['envelopeReferenceObject'],s.prior.prior.RESULT_OBJECT)
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        obj=bpy.data.objects[s.RESULT_OBJECT]
        self.assertFalse(obj.hide_get());self.assertTrue(bpy.data.objects[s.prior.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        for subject in (obj,bpy.context.scene,r):s.surface.require_locked(subject)
        self.assertIsNone(r['fullCharacterScore']);self.assertFalse(r['rigBound'])
        self.assertEqual(len(r['renders']),10)
        for row in r['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContourTests))
    if not result.wasSuccessful():raise SystemExit(1)
