import argparse
from pathlib import Path
import sys
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_seam_contour as contour

SOURCE=ARTIFACT=None


class ContourTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(contour.c.base.sha(SOURCE),contour.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[contour.seam.RESULT_OBJECT]
        hand=bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
        self.axis=(hand.matrix_world.to_3x3()@Vector((0,0,-1))).normalized()
        _,self.normal,_=contour.seam.trim.trim_plane(bpy.data.objects[contour.surface.RESULT_OBJECT],
            bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
            bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'],self.axis)

    def test_thin_bridge_default_refinement_has_no_inverted_faces(self):
        obj,report=contour.refine(self.source,self.axis,self.normal)
        self.assertGreaterEqual(report['minimumBridgeNormalDot'],.90)
        self.assertGreaterEqual(report['subtriangleAreaRatioRange'][0],.05)
        self.assertLessEqual(report['subtriangleAreaRatioRange'][1],.85)
        self.assertEqual(contour.surface.repair.crossing_pairs(obj)[2],[])

    def test_unbounded_relative_offset_reproduces_rejection_without_leaving_copy(self):
        before=contour.c.guide.digest([self.source])
        names=set(bpy.data.objects.keys())
        with self.assertRaisesRegex(ValueError,'CONTOUR_DISTORTION_REJECTED'):
            contour.refine(self.source,self.axis,self.normal,local_safety=False)
        self.assertEqual(names,set(bpy.data.objects.keys()))
        self.assertEqual(before,contour.c.guide.digest([self.source]))

    def test_original_vertices_faces_uv_fields_and_rims_preserved(self):
        signature=contour.surface.repair.invariant_signature(self.source)
        obj,report=contour.refine(self.source,self.axis,self.normal)
        self.assertEqual(signature,contour.surface.repair.invariant_signature(self.source))
        self.assertEqual(len(obj.data.vertices),8196)
        obj.data.calc_loop_triangles()
        self.assertEqual(len(obj.data.loop_triangles),16384)
        self.assertEqual(report['addedMidpointVertices'],73)
        self.assertEqual(report['bridgeTrianglesAfter'],219)
        self.assertEqual(report['sharedBoundaryEdges'],73)
        for i,vertex in enumerate(self.source.data.vertices):
            self.assertEqual(obj.data.vertices[i].co,self.source.matrix_world@vertex.co)
        for name in (contour.seam.trim.upper.MASK,contour.seam.trim.DISTANCE):
            self.assertEqual([x.value for x in self.source.data.attributes[name].data],
                             [x.value for x in obj.data.attributes[name].data][:8123])
        for name in ('BodySeam','SleeveSeam','UpperOpening_inner','UpperOpening_outer'):
            self.assertEqual(contour.group_ids(self.source,name),contour.group_ids(obj,name))
        for old,new in report['unchangedFaceMapping']:
            a,b=self.source.data.polygons[old],obj.data.polygons[new]
            self.assertEqual(list(a.vertices),list(b.vertices))
            self.assertEqual(a.material_index,b.material_index)
            for layer in self.source.data.uv_layers:
                self.assertEqual([tuple(layer.data[i].uv)for i in a.loop_indices],
                                 [tuple(obj.data.uv_layers[layer.name].data[i].uv)for i in b.loop_indices])
        for entry in report['offsets']:
            self.assertLessEqual(entry['actualStoredOffsetMeters'],entry['localLimitMeters']+1e-7)
            self.assertLessEqual(entry['actualAxialDriftMeters'],1e-7)
        self.assertEqual(contour.surface.repair.components(obj)[-1]['vertexCount'],48)
        self.assertFalse(obj['unityInputAllowed'])

    def test_invalid_limit_frame_hash_and_gate_rejected(self):
        for limit in (0,.001,float('nan')):
            with self.assertRaisesRegex(ValueError,'UNSAFE_CONTOUR_OFFSET'):
                contour.refine(self.source,self.axis,self.normal,max_offset=limit)
        with self.assertRaisesRegex(ValueError,'FRAME_NOT_UNIT'):
            contour.refine(self.source,self.axis*2,self.normal)
        with patch.object(contour.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                contour.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-contour-test')))
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            contour.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_and_final_qa(self):
        if ARTIFACT is None:self.skipTest('Artifact not yet supplied during regression red/green loop')
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj=bpy.data.objects[contour.RESULT_OBJECT]
        self.assertFalse(obj.hide_get())
        self.assertTrue(bpy.data.objects[contour.seam.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        report=json.loads((ARTIFACT.parent/'seam-contour-report.json').read_text(encoding='utf-8'))
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        qa=contour.seam.assess(obj,parts,report['operation'])
        self.assertTrue(qa['eligible'])
        self.assertEqual(qa['topology']['components'],[8148,48])
        self.assertEqual(contour.c.base.sha(ARTIFACT),report['blendSha256'])
        contour.surface.require_locked(bpy.context.scene)
        with self.assertRaisesRegex(ValueError,'SOURCE_BRIDGE_CONTRACT_CHANGED'):
            contour.refine(obj,self.axis,self.normal)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContourTests))
    if not result.wasSuccessful():raise SystemExit(1)
