"""Rounded section bounds, strict static guards, preservation and saved artifact."""
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
import round_ch101_hem_binding as s
SOURCE=ARTIFACT=None


class RoundedTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.band=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]

    def test_section_bounds_and_bad_input(self):
        points=[Vector(p) for p in [(0,0,0),(.0008,0,0),(.0008,.003,0),(0,.003,0)]]
        result=s.section(points)
        self.assertEqual(len(result),16)
        for p in result:
            self.assertGreaterEqual(p.x,-1e-10);self.assertLessEqual(p.x,.000800001)
            self.assertGreaterEqual(p.y,-1e-10);self.assertLessEqual(p.y,.003000001)
            self.assertEqual(p.z,0)
        for radius in (0,-1,float('nan'),.000151):
            with self.assertRaisesRegex(ValueError,'INVALID_ROUNDING'):s.section(points,radius)
        with self.assertRaisesRegex(ValueError,'SECTION_TOO_SMALL'):s.section([p*.01 for p in points])

    def test_rounding_and_preservation(self):
        originals=[self.band,self.body]+self.parts;digest=s.c.guide.digest(originals)
        signatures=[s.surface.repair.invariant_signature(o) for o in originals]
        obj=s.build(self.band);qa=s.audit(obj,self.band,self.body,self.parts)
        self.assertTrue(qa['eligible'],qa);self.assertEqual(qa['vertices'],2048)
        self.assertEqual(qa['components'],[2048]);self.assertEqual(qa['euler'],0)
        self.assertEqual(digest,s.c.guide.digest(originals))
        self.assertEqual(signatures,[s.surface.repair.invariant_signature(o) for o in originals])
        self.assertTrue(all(p.use_smooth for p in obj.data.polygons))
        self.assertEqual(list(obj.data.materials),list(self.band.data.materials))
        s.surface.require_locked(obj)
        with self.assertRaisesRegex(ValueError,'ROUNDING_ALREADY_EXISTS'):s.build(self.band)

    def test_bad_source_path_and_gate(self):
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_SOURCE_TOPOLOGY'):s.build(self.body)
        bpy.context.scene['productionPromotionAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.surface.require_locked(bpy.context.scene)

    def test_envelope_and_collision_rejections(self):
        obj=s.build(self.band)
        obj.location.x+=.003;bpy.context.view_layer.update()
        self.assertFalse(s.audit(obj,self.band,self.body,self.parts)['eligible'])
        obj.location.x=0;bpy.context.view_layer.update()
        duplicate=obj.copy();duplicate.data=obj.data.copy();bpy.context.scene.collection.objects.link(duplicate)
        duplicate.location.x=.0002;bpy.context.view_layer.update()
        qa=s.audit(obj,self.band,self.body,self.parts+[duplicate])
        self.assertGreater(qa['intersectionPairsByObject'][duplicate.name],0)
        self.assertFalse(qa['eligible'])

    def test_open_mesh_rejection(self):
        obj=s.build(self.band);bm=s.bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        qa=s.audit(obj,self.band,self.body,self.parts)
        self.assertGreater(qa['nonManifoldEdges'],0);self.assertFalse(qa['eligible'])

    def test_saved_artifact(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'rounded-hem-report.json').read_text(encoding='utf-8'))
        digest=s.c.guide.digest([self.band,self.body]+self.parts)
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        band=bpy.data.objects[s.prior.RESULT_OBJECT];obj=bpy.data.objects[s.RESULT_OBJECT]
        body=bpy.data.objects[s.panel.RESULT_OBJECT]
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertEqual(digest,s.c.guide.digest([band,body]+parts))
        self.assertTrue(s.audit(obj,band,body,parts)['eligible']);self.assertTrue(band.hide_get())
        self.assertFalse(obj.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        for subject in (bpy.context.scene,obj,report):s.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore']);self.assertFalse(report['rigBound'])
        self.assertEqual(len(report['renders']),8)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RoundedTests))
    if not result.wasSuccessful():raise SystemExit(1)
