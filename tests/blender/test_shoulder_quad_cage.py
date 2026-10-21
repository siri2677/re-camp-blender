"""Shared cage provenance and failure rejection; no garment approval."""
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
import retopologize_ch101_shoulder_regions as m
SOURCE=ARTIFACT=None

class QuadCageTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.report=json.loads((SOURCE.parent/'branch-boundary-report.json').read_text())
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']

    def test_shared_quad_cage_preserves_source_and_every_region(self):
        digest=m.c.guide.digest(self.originals)
        inv={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=m.build(self.source,self.report);qa=m.audit(obj,self.source,op)
        self.assertTrue(qa['eligible']);self.assertFalse(qa['garmentStaticQA'])
        self.assertEqual((qa['vertices'],qa['quads'],qa['triangles']),(2258,2079,4158))
        self.assertEqual(qa['regionQuadCounts'],[453,663,486,477])
        self.assertEqual(qa['sharedBranchEdges'],88)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertEqual(qa['nonContiguousInteriorEdges'],0)
        self.assertLess(qa['maximumForwardSampleErrorMeters'],.00002)
        self.assertLess(qa['maximumReverseSampleErrorMeters'],.000001)
        for old,new in op['originalCornerVertexMap'].items():
            self.assertEqual(obj.data.vertices[new].co,self.source.matrix_world@self.source.data.vertices[int(old)].co)
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(inv,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):m.build(self.source,self.report)

    def test_unsafe_structured_grid_rejected_despite_positive_parameter(self):
        obj,op=m.build_structured_trial(self.source,self.report)
        with self.assertRaisesRegex(ValueError,'STRUCTURED_SURFACE_QA_REJECTED'):
            m.audit(obj,self.source,op)

    def test_region_and_barycentric_tampering_rejected(self):
        bad=copy.deepcopy(self.report);bad['design']['faceRegions'][0].pop()
        with self.assertRaisesRegex(ValueError,'INVALID_SOURCE_REGION_PARTITION'):m.build(self.source,bad)
        obj,op=m.build(self.source,self.report)
        changed=copy.deepcopy(op);changed['vertexProvenance'][0]['weights'][0]=-1
        with self.assertRaisesRegex(ValueError,'INVALID_BARYCENTRIC'):m.audit(obj,self.source,changed)
        obj.data.polygons[0].material_index=3
        with self.assertRaisesRegex(ValueError,'REGION_FACE_PROVENANCE'):m.audit(obj,self.source,op)

    def test_shared_branch_and_vertex_tampering_rejected(self):
        obj,op=m.build(self.source,self.report)
        changed=copy.deepcopy(op);path=next(iter(changed['sharedBranchPaths'].values()));path[1]=path[-1]
        with self.assertRaisesRegex(ValueError,'BRANCH_NOT_SHARED'):m.audit(obj,self.source,changed)
        obj.data.vertices[op['originalCornerVertexMap']['0']].co.x+=.002
        with self.assertRaises(ValueError):m.audit(obj,self.source,op)

    def test_hash_and_gate_validation(self):
        args=SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-quad-cage-test')
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):m.run(args)
        self.source['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):m.build(self.source,self.report)

    def test_saved_artifact_preserves_geometry_visibility_and_locks(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        names=[o.name for o in self.originals];digest=m.c.guide.digest(self.originals)
        visible={o.name for o in self.originals if not o.hide_get()}
        report=json.loads((ARTIFACT.parent/'quad-cage-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,m.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        obj=bpy.data.objects[m.RESULT_OBJECT];source=bpy.data.objects[m.prior.RESULT_OBJECT]
        self.assertTrue(m.audit(obj,source,report['operation'])['eligible'])
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        for subject in (obj,bpy.context.scene,report):m.surface.require_locked(subject)
        self.assertFalse(report['adoptionAllowed']);self.assertFalse(report['completeShoulderPanel'])
        self.assertFalse(report['rigBound']);self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),12)
        for row in report['renders']:self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])
        self.assertFalse(any(o.modifiers.get('QuadTopologyReview') for o in bpy.context.scene.objects))
        self.assertIsNone(bpy.data.objects.get('QuadTopologyReview'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(QuadCageTests))
    if not result.wasSuccessful():raise SystemExit(1)
