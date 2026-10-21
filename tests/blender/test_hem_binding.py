"""Pinned source, physical ring topology, collision guard and saved review."""
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
import build_ch101_hem_binding as s
SOURCE=ARTIFACT=None


class HemTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_closed_ring_and_preservation(self):
        digest=s.c.guide.digest([self.body]+self.parts)
        signature=s.surface.repair.invariant_signature(self.body)
        band,op=s.build(self.body,*self.frame);qa=s.audit(band,self.body,self.parts)
        self.assertTrue(qa['eligible'],qa)
        self.assertEqual(qa['vertices'],512);self.assertEqual(qa['triangles'],1024)
        self.assertEqual(qa['components'],[512]);self.assertEqual(qa['euler'],0)
        self.assertEqual(digest,s.c.guide.digest([self.body]+self.parts))
        self.assertEqual(signature,s.surface.repair.invariant_signature(self.body))
        self.assertEqual(op['bodyMovedVertices'],0);self.assertFalse(op['attachedOrSewn'])
        s.surface.require_locked(band)
        center,axis,u=self.frame
        for vertex in band.data.vertices:
            d=vertex.co-center
            self.assertAlmostEqual(abs(d.dot(axis)-s.panel.HEM_HEIGHT-s.panel.HEM_SLOPE*d.dot(u)),s.HALF_WIDTH,places=6)
        with self.assertRaisesRegex(ValueError,'BINDING_ALREADY_EXISTS'):s.build(self.body,*self.frame)

    def test_bad_frames_and_source_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'INVALID_BINDING_FRAME'):s.build(self.body,self.frame[0],Vector(),self.frame[2])
        with self.assertRaisesRegex(ValueError,'HEM_RAY_MISSED_BODY'):s.build(self.body,self.frame[0]+Vector((0,0,5)),*self.frame[1:])
        self.assertIsNone(bpy.data.objects.get(s.RESULT_OBJECT))
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.surface.require_locked(bpy.context.scene)

    def test_intersecting_duplicate_rejected(self):
        band,_=s.build(self.body,*self.frame)
        duplicate=band.copy();duplicate.data=band.data.copy();bpy.context.scene.collection.objects.link(duplicate)
        duplicate.location.x+=.0002;bpy.context.view_layer.update()
        qa=s.audit(band,self.body,self.parts+[duplicate])
        self.assertGreater(qa['intersectionPairsByObject'][duplicate.name],0)
        self.assertFalse(qa['eligible'])

    def test_open_ring_rejected(self):
        band,_=s.build(self.body,*self.frame)
        bm=s.bmesh.new();bm.from_mesh(band.data);bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(band.data);bm.free()
        qa=s.audit(band,self.body,self.parts)
        self.assertGreater(qa['nonManifoldEdges'],0);self.assertFalse(qa['eligible'])

    def test_saved_reopen(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'hem-binding-report.json').read_text(encoding='utf-8'))
        original=s.c.guide.digest([self.body]+self.parts)
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        body=bpy.data.objects[s.panel.RESULT_OBJECT];band=bpy.data.objects[s.RESULT_OBJECT]
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertEqual(original,s.c.guide.digest([body]+parts))
        self.assertTrue(s.audit(band,body,parts)['eligible'])
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        for subject in (bpy.context.scene,band,report):s.surface.require_locked(subject)
        self.assertFalse(report['rigBound']);self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),7)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HemTests))
    if not result.wasSuccessful():raise SystemExit(1)
