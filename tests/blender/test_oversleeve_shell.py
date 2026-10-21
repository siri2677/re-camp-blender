"""Real-scene shell preservation, thickness, reject paths and saved evidence."""
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
import build_ch101_oversleeve_shell as s
SOURCE=ARTIFACT=None


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.band=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_actual_shell_provenance_and_originals(self):
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        digest=s.c.guide.digest(originals)
        inv={o.name:s.surface.repair.invariant_signature(o) for o in originals}
        obj,hits=s.build(self.body,*self.frame)
        self.assertEqual(len(hits),s.ANGULAR*s.ROWS)
        tree,_,triangles=s.c.fit.bvh(self.body)
        for i,hit in enumerate(hits):
            self.assertTrue(0<=hit['sourceTriangle']<len(triangles))
            p=Vector(hit['hit']); ray=Vector(hit['ray'])
            self.assertLess(tree.find_nearest(p)[3],1e-6)
            self.assertLess((obj.data.vertices[i].co-(p+ray*s.CLEARANCE)).length,2e-7)
        self.assertEqual(digest,s.c.guide.digest(originals))
        self.assertEqual(inv,{o.name:s.surface.repair.invariant_signature(o) for o in originals})
        qa=s.audit(obj,self.body,self.parts,self.band)
        self.assertTrue(qa['eligible'],qa)
        self.assertEqual(qa['components'],[4864]); self.assertEqual(qa['triangles'],9728)
        self.assertGreater(qa['sampledOpposingWallRangeMeters'][0],.0002)
        self.assertFalse(obj['attachedOrSewn']); self.assertFalse(obj['rigBound'])
        self.assertEqual(len(obj.data.uv_layers),0)
        with self.assertRaisesRegex(ValueError,'SHELL_ALREADY_EXISTS'):s.build(self.body,*self.frame)

    def test_gate_frame_source_and_destination(self):
        names=set(bpy.data.objects.keys())
        for axis in (Vector(),Vector((float('nan'),0,0)),self.frame[2]):
            with self.assertRaisesRegex(ValueError,'INVALID_SHELL_FRAME'):s.build(self.body,self.frame[0],axis,self.frame[2])
        self.assertEqual(names,set(bpy.data.objects.keys()))
        for gate in ('unityInputAllowed','productionPromotionAllowed'):
            self.body[gate]=True
            with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.body,*self.frame)
            self.body[gate]=False
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                s.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-shell-test')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))

    def test_open_shell_rejected(self):
        obj,_=s.build(self.body,*self.frame)
        bm=s.bmesh.new(); bm.from_mesh(obj.data); bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY'); bm.to_mesh(obj.data); bm.free()
        self.assertFalse(s.audit(obj,self.body,self.parts,self.band)['eligible'])

    def test_intersection_rejected(self):
        obj,_=s.build(self.body,*self.frame)
        obj.location.x+=.005; bpy.context.view_layer.update()
        qa=s.audit(obj,self.body,self.parts,self.band)
        self.assertGreater(qa['intersectionPairsByObject'][self.body.name],0)
        self.assertFalse(qa['eligible'])

    def test_saved_hashes_gates_visibility(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH']; names=[o.name for o in originals]
        digest=s.c.guide.digest(originals)
        r=json.loads((ARTIFACT.parent/'oversleeve-shell-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),r['blendSha256'])
        self.assertEqual(s.c.base.sha(ARTIFACT.parent/'shell-ray-provenance.json'),r['provenanceSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        obj=bpy.data.objects[s.RESULT_OBJECT]
        for subject in (obj,bpy.context.scene,r):s.surface.require_locked(subject)
        self.assertFalse(obj.hide_get());self.assertFalse(bpy.data.objects[s.prior.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),15)
        self.assertIsNone(r['fullCharacterScore']);self.assertFalse(r['rigBound'])
        self.assertEqual(len(r['renders']),8)
        for row in r['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ShellTests))
    if not result.wasSuccessful():raise SystemExit(1)
