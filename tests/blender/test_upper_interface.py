"""Real-scene upper-interface collision, retained cage and saved-state evidence."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_upper_interface as s
SOURCE=ARTIFACT=None


class UpperInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[s.prior.RESULT_OBJECT];self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.oldband=bpy.data.objects[s.prior.prior.prior.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_real_interface_clears_body_and_reduces_upper_gap(self):
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=s.c.guide.digest(originals)
        obj,operation=s.build(self.source,self.body,*self.frame)
        qa=s.audit(obj,self.source,self.body,self.parts,self.oldband)
        self.assertEqual(qa['intersectionPairsByObject'][self.body.name],0)
        self.assertGreater(qa['minimumSampledBodyGapMeters'],.0002)
        self.assertLess(qa['newUpperEdgeBodyGap']['maxMeters'],.003)
        self.assertLess(qa['newUpperEdgeBodyGap']['meanMeters'],qa['oldUpperEdgeBodyGap']['meanMeters'])
        self.assertTrue(qa['eligible'],qa)
        self.assertEqual(digest,s.c.guide.digest(originals))
        for old,new in operation['sourceVertexToNewIndex'].items():
            self.assertLess((self.source.matrix_world@self.source.data.vertices[int(old)].co-obj.matrix_world@obj.data.vertices[new].co).length,1e-7)
        self.assertFalse(obj['joinedToSourceBodyTopology']);self.assertFalse(obj['rigBound'])

    def test_gate_hash_destination_and_duplicate(self):
        self.source['productionPromotionAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.source,self.body,*self.frame)
        self.source['productionPromotionAllowed']=False
        s.build(self.source,self.body,*self.frame)
        with self.assertRaisesRegex(ValueError,'UPPER_INTERFACE_ALREADY_EXISTS'):s.build(self.source,self.body,*self.frame)
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                s.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-upper-test')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))

    def test_open_interface_rejected(self):
        obj,_=s.build(self.source,self.body,*self.frame)
        bm=s.bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        self.assertFalse(s.audit(obj,self.source,self.body,self.parts,self.oldband)['eligible'])

    def test_torso_extension_and_collision_rejected(self):
        tree=s.c.fit.bvh(self.body)[0]
        for q in (.044,.052,float('nan')):
            with self.assertRaisesRegex(ValueError,'UPPER_INTERFACE_HEIGHT_OUTSIDE_SCOPE'):
                s.ray_hit(tree,*self.frame,q,0)
        obj,_=s.build(self.source,self.body,*self.frame)
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        nearest=[tree.find_nearest(p) for p in points];i=min(range(len(points)),key=lambda j:nearest[j][3])
        obj.location=(nearest[i][0]-points[i])*2;bpy.context.view_layer.update()
        qa=s.audit(obj,self.source,self.body,self.parts,self.oldband)
        self.assertGreater(qa['intersectionPairsByObject'][self.body.name],0)
        self.assertFalse(qa['eligible'])

    def test_saved_originals_hashes_visibility_and_gates(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];names=[o.name for o in originals];digest=s.c.guide.digest(originals)
        r=json.loads((ARTIFACT.parent/'upper-interface-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),r['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertTrue(bpy.data.objects[s.prior.RESULT_OBJECT].hide_get())
        self.assertFalse(bpy.data.objects[s.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        for subject in (r,bpy.context.scene,bpy.data.objects[s.RESULT_OBJECT]):s.surface.require_locked(subject)
        self.assertIsNone(r['fullCharacterScore']);self.assertFalse(r['rigBound'])
        self.assertEqual(len(r['renders']),9)
        for row in r['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path);p.add_argument('--collision-only',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    suite=unittest.TestSuite([UpperInterfaceTests('test_real_interface_clears_body_and_reduces_upper_gap')]) if a.collision_only else unittest.defaultTestLoader.loadTestsFromTestCase(UpperInterfaceTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
