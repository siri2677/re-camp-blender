import argparse
from pathlib import Path
import sys
import unittest

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import restore_ch101_upper_sleeve_trim as study

SOURCE = ARTIFACT = None


class TrimTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(study.c.base.sha(SOURCE), study.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body = bpy.data.objects[study.upper.RESULT_OBJECT]
        hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
        self.axis = (hand.matrix_world.to_3x3()@Vector((0, 0, -1))).normalized()
        self.args = [bpy.data.objects[study.surface.RESULT_OBJECT],
                     bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
                     bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], self.axis]
        self.anchors, self.normal, self.width = study.trim_plane(*self.args)

    def test_plane_contains_both_anchors_and_axis(self):
        self.assertAlmostEqual(self.normal.length, 1, delta=1e-6)
        self.assertAlmostEqual(self.normal.dot(self.axis), 0, delta=1e-6)
        for p in self.anchors:
            self.assertLess(abs((p-self.anchors[0]).dot(self.normal)), 1e-7)
        self.assertTrue(.0005 < self.width < .002)

    def test_geometry_mask_and_original_material_unchanged(self):
        signature = study.surface.repair.invariant_signature(self.body)
        counts = [(len(m.node_tree.nodes), len(m.node_tree.links)) for m in self.body.data.materials]
        mask = [v.value for v in self.body.data.attributes[study.upper.MASK].data]
        obj = study.trim_copy(self.body, self.anchors, self.normal, self.width)
        self.assertEqual(signature, study.surface.repair.invariant_signature(self.body))
        self.assertEqual(counts, [(len(m.node_tree.nodes), len(m.node_tree.links)) for m in self.body.data.materials])
        self.assertEqual(mask, [v.value for v in obj.data.attributes[study.upper.MASK].data])
        self.assertEqual(study.surface.structure_signature(obj), study.surface.structure_signature(self.body))
        self.assertNotIn(study.DISTANCE, self.body.data.attributes)
        self.assertEqual(study.surface.repair.crossing_pairs(obj)[2], [])
        for item, v in zip(obj.data.attributes[study.DISTANCE].data, obj.data.vertices):
            self.assertAlmostEqual(item.value, (obj.matrix_world@v.co-self.anchors[0]).dot(self.normal), delta=1e-6)
        for material in obj.data.materials:
            if material.name.startswith('INTERNAL_STUDY_CAP'):
                continue
            nodes = material.node_tree.nodes
            self.assertEqual(nodes['LocalGraphiteCloth'].inputs['Base Color'].links[0].from_node.type, 'MIX_RGB')
            self.assertEqual(nodes['BoundedClothingMask'].inputs[0].links[0].from_node.attribute_name, study.upper.MASK)

    def test_bad_axis_and_width_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AXIS_MUST_BE_UNIT'):
            study.trim_plane(*self.args[:3], self.axis*2)
        count = len(bpy.data.objects)
        for width in (0, .1, float('nan')):
            with self.assertRaisesRegex(ValueError, 'INVALID_TRIM'):
                study.trim_copy(self.body, self.anchors, self.normal, width)
        self.assertEqual(count, len(bpy.data.objects))

    def test_missing_mask_rejected(self):
        self.body.data.attributes.remove(self.body.data.attributes[study.upper.MASK])
        with self.assertRaisesRegex(ValueError, 'EXISTING_MASK_REQUIRED'):
            study.trim_copy(self.body, self.anchors, self.normal, self.width)

    def test_gate_true_rejected(self):
        bpy.context.scene['productionPromotionAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            study.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_keeps_original_hidden_and_rejects_reapply(self):
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj = bpy.data.objects[study.RESULT_OBJECT]
        original = bpy.data.objects[study.upper.RESULT_OBJECT]
        self.assertEqual(study.surface.structure_signature(obj), study.surface.structure_signature(original))
        self.assertFalse(obj.hide_get())
        self.assertTrue(original.hide_get())
        study.surface.require_locked(bpy.context.scene)
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 14)
        with self.assertRaisesRegex(ValueError, 'TRIM_ALREADY_APPLIED'):
            study.trim_copy(obj, self.anchors, self.normal, self.width)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path, required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE, ARTIFACT = args.source.resolve(), args.artifact.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TrimTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
