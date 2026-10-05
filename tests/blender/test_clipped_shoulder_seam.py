"""Source interpolation, closed seam correspondence and preservation checks."""
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
import clip_ch101_shoulder_seam as s
SOURCE=ARTIFACT=None


class ClipTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.interface=bpy.data.objects[s.prior.prior.RESULT_OBJECT]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_plane_intersection_and_barycentric_interpolation(self):
        poly=[(Vector(p),Vector(w)) for p,w in [((-1,0,0),(1,0,0)),((1,0,0),(0,1,0)),((1,1,0),(0,0,1))]]
        clipped=s.clip_polygon(poly,Vector((1,0,0)),0)
        self.assertEqual(len(clipped),4)
        for p,w in clipped:
            self.assertGreaterEqual(p.x,0);self.assertAlmostEqual(sum(w),1)
        cuts=[(p,w) for p,w in clipped if p.x==0]
        self.assertEqual(len(cuts),2)
        self.assertTrue(any((w-Vector((.5,.5,0))).length<1e-7 for p,w in cuts))
        self.assertEqual(s.clip_polygon(poly,Vector((1,0,0)),2),[])

    def test_chart_seam_and_originals(self):
        digest=s.c.guide.digest(self.originals)
        inv={o.name:s.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=s.build(self.body,self.frame);qa=s.verify_chart(self.body,obj,op,self.frame)
        self.assertTrue(qa['eligible']);self.assertEqual(len(op['seamLoop']),34)
        mapping=s.seam_map(obj,self.interface,self.frame,op['seamLoop'])
        self.assertEqual(len(mapping['samples']),128)
        self.assertEqual([r['angleIndex'] for r in mapping['samples']],list(range(128)))
        self.assertEqual(len({r['interfaceVertex'] for r in mapping['samples']}),128)
        for row in mapping['samples']:self.assertAlmostEqual(row['gapMeters'],.0028,places=6)
        self.assertFalse(mapping['automaticWeldAllowed'])
        self.assertEqual(digest,s.c.guide.digest(self.originals))
        self.assertEqual(inv,{o.name:s.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):s.build(self.body,self.frame)

    def test_provenance_uv_and_parameter_mutations_rejected(self):
        obj,op=s.build(self.body,self.frame)
        old=obj.data.uv_layers[0].data[0].uv.copy();obj.data.uv_layers[0].data[0].uv.x+=.1
        with self.assertRaisesRegex(ValueError,'PROVENANCE_QA'):s.verify_chart(self.body,obj,op,self.frame)
        obj.data.uv_layers[0].data[0].uv=old
        vertex=obj.data.vertices[op['seamLoop'][0]];old=vertex.co.copy();vertex.co.x+=.001
        with self.assertRaisesRegex(ValueError,'PROVENANCE_QA'):s.verify_chart(self.body,obj,op,self.frame)
        vertex.co=old
        index=s.prior.prior.idx(1,s.prior.prior.M-1,0)
        self.interface.data.vertices[index].co.x+=.001
        with self.assertRaisesRegex(ValueError,'INTERFACE_DOES_NOT_MATCH'):s.seam_map(obj,self.interface,self.frame,op['seamLoop'])

    def test_invalid_inputs_fail_closed(self):
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        with self.assertRaisesRegex(ValueError,'INVALID_CLIP_FRAME'):s.build(self.body,(self.frame[0],Vector(),self.frame[2]))
        self.body['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.body,self.frame)

    def test_saved_artifact(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'clipped-shoulder-report.json').read_text(encoding='utf-8'))
        digest=s.c.guide.digest(self.originals);names=[o.name for o in self.originals]
        visible={o.name for o in self.originals if not o.hide_get()}
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        obj=bpy.data.objects[s.RESULT_OBJECT];body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        self.assertTrue(s.verify_chart(body,obj,report['operation'],self.frame)['eligible'])
        self.assertFalse(report['adoptionAllowed']);self.assertIsNone(report['fullCharacterScore'])
        for subject in (bpy.context.scene,obj,report):s.surface.require_locked(subject)
        self.assertEqual(len(report['renders']),8)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClipTests))
    if not result.wasSuccessful():raise SystemExit(1)
