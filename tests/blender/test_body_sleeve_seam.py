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
import join_ch101_body_sleeve as seam

SOURCE = ARTIFACT = None


class SeamTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(seam.c.base.sha(SOURCE),seam.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body=bpy.data.objects[seam.trim.RESULT_OBJECT]
        self.sleeve=bpy.data.objects[seam.surface.RESULT_OBJECT]
        self.hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']

    def test_shared_seam_and_original_preservation(self):
        old=seam.c.guide.digest([self.body,self.sleeve])
        original_signature=[seam.surface.repair.invariant_signature(o) for o in (self.body,self.sleeve)]
        obj,report=seam.build(self.body,self.sleeve,self.hand)
        parts=[o for o in bpy.context.scene.objects if o.name.startswith('PAIR_STUDY_') and o.type=='MESH']
        qa=seam.assess(obj,parts,report)
        self.assertTrue(qa['eligible'],qa['rejectionReasons'])
        self.assertEqual(qa['topology']['components'],[8075,48])
        self.assertEqual(qa['topology']['vertices'],8123)
        self.assertEqual(qa['topology']['triangles'],16238)
        self.assertEqual(report['bridgeTriangles'],report['sharedBoundaryEdgeCount'])
        self.assertTrue(report['eachSeamEdgeHasOneBridgeAndOneRetainedFace'])
        self.assertEqual(report['copiedUVErrors'],0)
        self.assertEqual(old,seam.c.guide.digest([self.body,self.sleeve]))
        self.assertEqual(original_signature,[seam.surface.repair.invariant_signature(o) for o in (self.body,self.sleeve)])
        offset=report['sourceSleeveVertexOffset']
        for a,b in zip(self.sleeve.data.vertices,obj.data.vertices[offset:]):
            self.assertEqual(self.sleeve.matrix_world@a.co,b.co)
        old_small=seam.surface.repair.components(self.body)[-1]['vertexIndices']
        new_small=seam.surface.repair.components(obj)[-1]['vertexIndices']
        self.assertEqual({tuple(self.body.matrix_world@self.body.data.vertices[i].co) for i in old_small},
                         {tuple(obj.data.vertices[i].co) for i in new_small})
        self.assertFalse(obj['unityInputAllowed'])

    def test_transfer_exact_vertices_and_reject_remote_point(self):
        points=[self.body.matrix_world@v.co for v in self.body.data.vertices]
        values,report=seam.transfer_fields(self.body,points,[seam.trim.upper.MASK,seam.trim.DISTANCE])
        self.assertEqual(report['exactRetainedVertices'],len(points))
        for name in values:
            self.assertEqual(values[name],[x.value for x in self.body.data.attributes[name].data])
        with self.assertRaisesRegex(ValueError,'NOT_ON_SOURCE_SURFACE'):
            seam.transfer_fields(self.body,[Vector((5,5,5))],[seam.trim.upper.MASK])

    def test_degenerate_ring_rejected(self):
        with self.assertRaisesRegex(ValueError,'DEGENERATE_BODY_RING'):
            seam.ring([Vector(),Vector((1,0,0)),Vector((2,0,0))],[0,1,2],Vector(),Vector((0,0,1)),Vector((1,0,0)))

    def test_hash_mismatch_rejected_before_open(self):
        with patch.object(seam.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                seam.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-seam-test')))

    def test_gate_true_rejected(self):
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            seam.surface.require_locked(bpy.context.scene)

    def test_saved_artifact_uv_attributes_and_visibility(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj=bpy.data.objects[seam.RESULT_OBJECT]
        self.assertFalse(obj.hide_get())
        self.assertTrue(bpy.data.objects[seam.trim.RESULT_OBJECT].hide_get())
        self.assertTrue(bpy.data.objects[seam.surface.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        self.assertEqual(obj.data.uv_layers.active.name,'UVMap')
        self.assertIn('SleeveTrimStudy',obj.data.uv_layers)
        for name in (seam.trim.upper.MASK,seam.trim.DISTANCE):
            self.assertIn(name,obj.data.attributes)
        self.assertEqual(seam.surface.repair.crossing_pairs(obj)[2],[])
        seam.surface.require_locked(bpy.context.scene)
        report=json.loads((ARTIFACT.parent/'body-sleeve-seam-report.json').read_text(encoding='utf-8'))
        self.assertEqual(seam.c.base.sha(ARTIFACT),report['blendSha256'])
        self.assertEqual(len(report['renders']),8)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--artifact',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE,ARTIFACT=args.source.resolve(),args.artifact.resolve()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SeamTests))
    if not result.wasSuccessful(): raise SystemExit(1)
