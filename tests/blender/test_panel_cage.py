"""Actual source cage budget, shared interface, topology and saved scene gates."""
import argparse
import json
from pathlib import Path
import sys
import unittest
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import author_ch101_panel_cage as s
SOURCE=ARTIFACT=None


class CageTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.band=bpy.data.objects[s.prior.prior.RESULT_OBJECT]
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_real_source_budget_and_shared_hem(self):
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=s.c.guide.digest(originals)
        obj,operation=s.build(self.body,*self.frame)
        self.assertLessEqual(operation['innerRadialExpansionRangeMeters'][1],.015)
        qa=s.audit(obj,self.body,self.parts,self.band)
        self.assertTrue(qa['eligible'],qa)
        self.assertEqual(qa['sharedOuterHemEdges'],s.N)
        self.assertTrue(qa['sharedHemMaterialBoundaryValid'])
        self.assertEqual(digest,s.c.guide.digest(originals))

    def test_locked_gate_and_duplicate(self):
        self.body['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.body,*self.frame)
        self.body['unityInputAllowed']=False
        s.build(self.body,*self.frame)
        with self.assertRaisesRegex(ValueError,'CAGE_ALREADY_EXISTS'):s.build(self.body,*self.frame)

    def test_open_cage_rejected(self):
        obj,_=s.build(self.body,*self.frame)
        bm=s.bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        self.assertFalse(s.audit(obj,self.body,self.parts,self.band)['eligible'])

    def test_colliding_cage_rejected(self):
        obj,_=s.build(self.body,*self.frame)
        tree=s.c.fit.bvh(self.body)[0]
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        nearest=[tree.find_nearest(p) for p in points]
        i=min(range(len(points)),key=lambda j:nearest[j][3])
        # Construct penetration from the measured nearest point, not an arbitrary
        # world-axis translation that can leave this oblique sleeve collision-free.
        obj.location=(nearest[i][0]-points[i])*2;bpy.context.view_layer.update()
        qa=s.audit(obj,self.body,self.parts,self.band)
        self.assertGreater(qa['intersectionPairsByObject'][self.body.name],0)
        self.assertFalse(qa['eligible'])

    def test_saved_evidence(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];names=[o.name for o in originals];digest=s.c.guide.digest(originals)
        r=json.loads((ARTIFACT.parent/'panel-cage-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(SOURCE),r['sourceBlendSha256'])
        self.assertEqual(s.c.base.sha(ARTIFACT),r['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        for subject in (r,bpy.context.scene,bpy.data.objects[s.RESULT_OBJECT]):s.surface.require_locked(subject)
        self.assertTrue(bpy.data.objects[s.prior.prior.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        self.assertIsNone(r['fullCharacterScore']);self.assertFalse(r['rigBound'])
        self.assertEqual(len(r['renders']),8)
        for row in r['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path);p.add_argument('--budget-only',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    suite=unittest.TestSuite([CageTests('test_real_source_budget_and_shared_hem')]) if a.budget_only else unittest.defaultTestLoader.loadTestsFromTestCase(CageTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
