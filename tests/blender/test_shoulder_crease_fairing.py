"""Bounded render-surface fairing; no garment or human approval."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import fair_ch101_shoulder_panels as m
SOURCE=ARTIFACT=None


class CreaseFairingTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']

    def restored(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'crease-fairing-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        return bpy.data.objects[m.RESULT_OBJECT],bpy.data.objects[m.prior.RESULT_OBJECT],report

    def test_actual_build_reduces_bending_without_moving_originals(self):
        digest=m.c.guide.digest(self.originals)
        inv={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=m.build(self.source);qa=m.audit(obj,self.source,op)
        self.assertTrue(qa['eligible']);self.assertFalse(qa['garmentStaticQA'])
        self.assertEqual((qa['vertices'],qa['quads'],qa['sharedSeamEdges']),(2258,2079,88))
        self.assertEqual(qa['maximumPinnedMoveMeters'],0)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertGreater(qa['weightedBendingReductionFraction'],.001)
        self.assertLessEqual(qa['maximumMoveMeters'],m.MAX_MOVE+1e-7)
        self.assertLessEqual(max(qa['maximumForwardSampleErrorMeters'],qa['maximumReverseSampleErrorMeters']),m.MAX_SURFACE_ERROR)
        self.assertTrue(all(r['afterEnergy']<=r['beforeEnergy'] for r in op['optimization']))
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):m.build(self.source)

    def test_nonplanar_quad_diagonal_is_measured(self):
        mesh=bpy.data.meshes.new('TwistedQuadTest')
        mesh.from_pydata([(0,0,0),(.01,0,0),(.01,.01,.002),(0,.01,0)],[],[(0,1,2,3)])
        obj=bpy.data.objects.new('TwistedQuadTest',mesh);bpy.context.scene.collection.objects.link(obj)
        _,edges,_,_=m.topology(obj)
        measured=m.bending(obj,edges)
        self.assertEqual(measured['measurement'],'RENDER_TRIANGLE_DIHEDRAL_BENDING')
        self.assertEqual(measured['interiorEdgeCount'],1)
        self.assertGreater(measured['weightedRadiansSquaredMeters'],0)
        obj.data.vertices[2].co.z=0;obj.data.update()
        self.assertAlmostEqual(m.bending(obj,edges)['weightedRadiansSquaredMeters'],0,places=10)

    def test_small_bump_optimizer_preserves_boundary_and_caps_movement(self):
        points=[(.008*x,.008*y,.002 if x==2 and y==2 else 0) for y in range(5) for x in range(5)]
        faces=[(y*5+x,y*5+x+1,(y+1)*5+x+1,(y+1)*5+x) for y in range(4) for x in range(4)]
        mesh=bpy.data.meshes.new('BumpTest');mesh.from_pydata(points,[],faces)
        obj=bpy.data.objects.new('BumpTest',mesh);bpy.context.scene.collection.objects.link(obj)
        original=[v.co.copy() for v in mesh.vertices];adj,edges,pinned,_=m.topology(obj)
        before=m.bending(obj,edges)['weightedRadiansSquaredMeters']
        rows=m.move_points(obj,original,adj,pinned)
        after=m.bending(obj,edges)['weightedRadiansSquaredMeters']
        self.assertLess(after,before)
        self.assertTrue(all(r['afterEnergy']<=r['beforeEnergy'] for r in rows))
        self.assertTrue(all(mesh.vertices[i].co==original[i] for i in pinned))
        self.assertLessEqual(max((v.co-old).length for v,old in zip(mesh.vertices,original)),m.MAX_MOVE+1e-7)

    def test_noop_is_not_counted_as_shape_progress(self):
        with patch.object(m,'ITERATIONS',0):obj,op=m.build(self.source)
        with self.assertRaisesRegex(ValueError,'FAIRING_QA_REJECTED'):m.audit(obj,self.source,op)

    def test_feature_and_pinned_vertex_tampering_rejected(self):
        obj,source,report=self.restored();op=report['operation']
        changed=copy.deepcopy(op);changed['features']['sharedSeamEdges'].pop()
        with self.assertRaisesRegex(ValueError,'FAIRING_FEATURE_PINS_CHANGED'):m.audit(obj,source,changed)
        changed=copy.deepcopy(op);changed['pinnedVertices']=[]
        with self.assertRaisesRegex(ValueError,'FAIRING_FEATURE_PINS_CHANGED'):m.audit(obj,source,changed)
        obj.data.vertices[op['pinnedVertices'][0]].co.x+=.002;obj.data.update()
        with self.assertRaisesRegex(ValueError,'FAIRING_QA_REJECTED'):m.audit(obj,source,op)

    def test_hash_and_gate_rejection(self):
        args=SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-fairing-test')
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):m.run(args)
        self.source['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.build(self.source)

    def test_saved_reopen_geometry_visibility_gates_and_render_hashes(self):
        names=[o.name for o in self.originals];digest=m.c.guide.digest(self.originals)
        inv={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        visible={o.name for o in self.originals if not o.hide_get()}
        obj,source,report=self.restored()
        originals=[bpy.data.objects[n] for n in names]
        self.assertEqual(digest,m.c.guide.digest(originals))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in originals})
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        qa=m.audit(obj,source,report['operation'])
        self.assertTrue(qa['eligible']);self.assertEqual(qa,report['qa'])
        for subject in (obj,bpy.context.scene,report):m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound'):self.assertFalse(report[key])
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),8)
        for row in report['renders']:self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CreaseFairingTests))
    if not result.wasSuccessful():raise SystemExit(1)
