import argparse
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_upper_sleeve_material as study

SOURCE = ARTIFACT = None


class MaterialStudyTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(study.c.base.sha(SOURCE), study.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body = bpy.data.objects[study.surface.BODY_OBJECT]
        hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
        self.center = hand.matrix_world@Vector()
        self.axis = (hand.matrix_world.to_3x3()@Vector((0, 0, -1))).normalized()

    def test_mask_bounds_connectivity_and_exclusions(self):
        weights, region = study.region_weights(self.body, self.center, self.axis)
        self.assertTrue(region['connectedMask'])
        self.assertGreater(region['fullWeightVertexCount'], 0)
        self.assertGreater(region['weightedVertexCount'], region['fullWeightVertexCount'])
        for v, w in zip(self.body.data.vertices, weights):
            p = self.body.matrix_world@v.co
            if p.x > -.17 or p.z < .91 or p.z > 1.14:
                self.assertEqual(w, 0)
        for p in self.body.data.polygons:
            if self.body.data.materials[p.material_index].name.startswith('INTERNAL_STUDY_CAP'):
                self.assertTrue(all(weights[i] == 0 for i in p.vertices))

    def test_mask_function_fades_and_is_zero_outside(self):
        origin, axis = Vector(), Vector((0, 0, 1))
        for p in [(0, 0, 0), (0, 0, .25), (.1, 0, .15), (0, 0, .074)]:
            self.assertEqual(study.point_weight(Vector(p), origin, axis), 0)
        self.assertEqual(study.point_weight(Vector((0, 0, .14)), origin, axis), 1)
        # mathutils.Vector stores float32: 0.205 is not exactly representable.
        self.assertAlmostEqual(study.point_weight(Vector((0, 0, .205)), origin, axis), .5, delta=1e-6)

    def test_wrong_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AXIS_MUST_BE_UNIT'):
            study.region_weights(self.body, self.center, self.axis*2)
        with self.assertRaises(ValueError):
            study.region_weights(self.body, self.center+Vector((5, 5, 5)), self.axis)

    def test_copy_preserves_geometry_uv_materials_and_old_shader(self):
        signature = study.surface.repair.invariant_signature(self.body)
        materials = list(self.body.data.materials)
        old_outputs = [(m.node_tree.nodes.get('Material Output').inputs['Surface'].links[0].from_node.name,
                        len(m.node_tree.nodes), len(m.node_tree.links)) for m in materials]
        weights, region = study.region_weights(self.body, self.center, self.axis)
        obj = study.material_copy(self.body, weights)
        self.assertEqual(signature, study.surface.repair.invariant_signature(self.body))
        self.assertEqual(study.surface.structure_signature(obj), study.surface.structure_signature(self.body))
        self.assertEqual(old_outputs, [(m.node_tree.nodes.get('Material Output').inputs['Surface'].links[0].from_node.name,
                                       len(m.node_tree.nodes), len(m.node_tree.links)) for m in materials])
        for i, original in enumerate(materials):
            if original.name.startswith('INTERNAL_STUDY_CAP'):
                self.assertEqual(obj.data.materials[i], original)
                continue
            mat = obj.data.materials[i]
            self.assertNotEqual(mat, original)
            mix = mat.node_tree.nodes['BoundedClothingMask']
            self.assertEqual(mix.inputs[1].links[0].from_node.name, old_outputs[i][0])
            self.assertEqual(mix.inputs[0].links[0].from_node.attribute_name, study.MASK)
        self.assertEqual(study.surface.repair.crossing_pairs(obj)[2], [])
        self.assertNotIn(study.MASK, self.body.data.attributes)

    def test_invalid_weights_rejected_before_copy(self):
        count = len(bpy.data.objects)
        for weights in ([], [-1]*len(self.body.data.vertices), [float('nan')]*len(self.body.data.vertices)):
            with self.assertRaisesRegex(ValueError, 'INVALID_MASK'):
                study.material_copy(self.body, weights)
        self.assertEqual(count, len(bpy.data.objects))

    def test_hash_mismatch_rejected(self):
        with patch.object(study.c.base, 'sha', return_value='0'*64):
            with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
                study.run(SimpleNamespace(source=SOURCE, output=Path('artifacts/unused-test-output')))

    def test_unity_gate_true_rejected(self):
        bpy.context.scene['unityInputAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            study.surface.require_locked(bpy.context.scene)

    def test_saved_artifact_and_reapplication_guard(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj = bpy.data.objects[study.RESULT_OBJECT]
        original = bpy.data.objects[study.surface.BODY_OBJECT]
        self.assertEqual(study.surface.structure_signature(obj), study.surface.structure_signature(original))
        self.assertFalse(obj.hide_get())
        self.assertTrue(original.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 14)
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])
        with self.assertRaisesRegex(ValueError, 'MASK_ALREADY_PRESENT'):
            study.material_copy(obj, [0]*len(obj.data.vertices))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE, ARTIFACT = args.source.resolve(), args.artifact.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MaterialStudyTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
