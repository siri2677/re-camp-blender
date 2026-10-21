"""Real topology improvement and preservation; no animation/garment approval."""
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
import author_ch101_shoulder_edge_flow as m
SOURCE=ARTIFACT=None


class EdgeFlowTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']

    def restored(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'edge-flow-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        return bpy.data.objects[m.RESULT_OBJECT],bpy.data.objects[m.prior.RESULT_OBJECT],report

    def test_hexagon_reconnection_preserves_oriented_perimeter(self):
        old=((0,1,2,3),(3,4,5,0));choices=m.alternatives(*old)
        self.assertEqual(len(choices),2)
        boundary=lambda fs:{e for e,ids in m.edge_faces(fs).items() if len(ids)==1}
        for pair in choices:
            self.assertTrue(all(len(f)==4 for f in pair))
            self.assertEqual(boundary(pair),boundary(old))
            self.assertNotIn((0,3),m.edge_faces(pair))
        self.assertEqual(m.alternatives((0,1,2,3),(0,1,4,5)),[])

    def test_build_improves_connectivity_without_moving_source(self):
        digest=m.c.guide.digest(self.originals)
        invariants={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=m.build(self.source);qa=m.audit(obj,self.source,op)
        self.assertTrue(qa['eligible']);self.assertFalse(qa['garmentStaticQA'])
        self.assertFalse(qa['majorFoldShapeRedesigned']);self.assertFalse(qa['deformationValidated'])
        self.assertEqual((qa['vertices'],qa['quads']),(2258,2079))
        self.assertEqual((qa['rotations'],qa['changedFaces']),(276,520))
        self.assertLessEqual(qa['maximumSourceVertexMoveMeters'],m.MAX_NEW_MOVE+1e-7)
        self.assertLessEqual(qa['maximumCumulativeQuadVertexMoveMeters'],m.MAX_TOTAL_MOVE+1e-7)
        self.assertEqual(qa['maximumPinnedVertexMoveMeters'],0)
        self.assertEqual((qa['preservedSharedBranchEdges'],qa['preservedMajorCreaseEdges']),(88,64))
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertEqual(qa['beforeValence']['regularInteriorVertices'],950)
        self.assertGreater(qa['afterValence']['regularInteriorVertices'],950)
        self.assertLess(qa['afterValence']['squaredValenceError'],qa['beforeValence']['squaredValenceError'])
        self.assertLessEqual(qa['afterBending']['weightedRadiansSquaredMeters'],qa['beforeBending']['weightedRadiansSquaredMeters']+1e-5)
        self.assertTrue(all(r['afterEnergy']<=r['beforeEnergy'] for r in op['geometryCorrection']))
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(invariants,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):m.build(self.source)

    def test_local_triangle_probe_matches_actual_blender_source(self):
        from collections import defaultdict
        self.source.data.calc_loop_triangles();expected=defaultdict(set)
        for tri in self.source.data.loop_triangles:expected[tri.polygon_index].add(frozenset(tri.vertices))
        points=[self.source.matrix_world@v.co for v in self.source.data.vertices]
        for face in self.source.data.polygons:
            self.assertEqual({frozenset(t) for t in m.triangulate(points,tuple(face.vertices))},expected[face.index])
        self.assertFalse(any(mesh.name.startswith('EdgeFlowTriangleProbe') for mesh in bpy.data.meshes))

    def test_noop_is_not_a_topology_improvement(self):
        with patch.object(m,'PASSES',0):obj,op=m.build(self.source)
        self.assertFalse(m.audit(obj,self.source,op)['eligible'])

    def test_unrepaired_rotation_is_rejected_despite_valence_improvement(self):
        with patch.object(m,'CORRECTION_ITERATIONS',0):obj,op=m.build(self.source)
        qa=m.audit(obj,self.source,op)
        self.assertGreater(qa['afterValence']['regularInteriorVertices'],qa['beforeValence']['regularInteriorVertices'])
        self.assertGreater(qa['afterBending']['weightedRadiansSquaredMeters'],qa['beforeBending']['weightedRadiansSquaredMeters'])
        self.assertFalse(qa['eligible'])

    def test_rotation_and_valence_tampering_rejected(self):
        obj,source,report=self.restored();op=report['operation']
        bad=copy.deepcopy(op);bad['rotations'][0]['newFaces'][0][0]=bad['rotations'][0]['newFaces'][0][1]
        with self.assertRaisesRegex(ValueError,'INVALID_ROTATION_PROVENANCE'):m.audit(obj,source,bad)
        bad=copy.deepcopy(op);bad['rotations'][0]['addedEdge']=[0,1]
        with self.assertRaisesRegex(ValueError,'ROTATION_EDGE_RECORD_CHANGED'):m.audit(obj,source,bad)
        bad=copy.deepcopy(op);bad['afterValence']['regularInteriorVertices']+=1
        with self.assertRaisesRegex(ValueError,'VALENCE_RECORD_CHANGED'):m.audit(obj,source,bad)

    def test_major_fold_locks_and_fixed_points_enforced(self):
        obj,source,report=self.restored();op=report['operation']
        bad=copy.deepcopy(op);bad['features']['majorCreaseEdges'].pop()
        with self.assertRaisesRegex(ValueError,'PROTECTED_FEATURE_RECORD_CHANGED'):m.audit(obj,source,bad)
        bad=copy.deepcopy(op);bad['lockedFaceIndices']=[]
        with self.assertRaisesRegex(ValueError,'MAJOR_FOLD_LOCKS_CHANGED'):m.audit(obj,source,bad)
        obj.data.vertices[0].co.x+=.002;obj.data.update()
        self.assertFalse(m.audit(obj,source,op)['eligible'])

    def test_hash_and_gate_rejection(self):
        args=SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-edge-flow-test')
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):m.run(args)
        self.source['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.build(self.source)

    def test_saved_artifact_reopens_with_originals_visibility_and_locks(self):
        names=[o.name for o in self.originals];digest=m.c.guide.digest(self.originals)
        inv={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        visible={o.name for o in self.originals if not o.hide_get()}
        obj,source,report=self.restored()
        original_objects=[bpy.data.objects[n] for n in names]
        self.assertEqual(digest,m.c.guide.digest(original_objects))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in original_objects})
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        qa=m.audit(obj,source,report['operation']);self.assertTrue(qa['eligible']);self.assertEqual(qa,report['qa'])
        for subject in (obj,bpy.context.scene,report):m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound'):self.assertFalse(report[key])
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),12)
        for row in report['renders']:self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])
        self.assertIsNone(bpy.data.objects.get('EdgeFlowWireReview'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EdgeFlowTests))
    if not result.wasSuccessful():raise SystemExit(1)
