"""Blender tests with mandatory hash-pinned source fixture."""
import argparse
from pathlib import Path
import sys
import unittest

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_sleeve_surface as surface

SOURCE = ARTIFACT = None


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(surface.c.base.sha(SOURCE), surface.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[surface.SOURCE_OBJECT]
        self.joined = bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION']
        self.cloth = bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION']

    def test_preserved_structure_and_material_isolation(self):
        signature = surface.repair.invariant_signature(self.source)
        old_materials = list(self.source.data.materials)
        old_colors = [tuple(m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value)
                      for m in old_materials]
        obj, report = surface.surface_copy(self.source, self.joined, self.cloth)
        self.assertEqual(signature, surface.repair.invariant_signature(self.source))
        self.assertEqual(surface.structure_signature(self.source), surface.structure_signature(obj))
        self.assertEqual(old_colors, [tuple(m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value)
                                    for m in self.source.data.materials])
        self.assertEqual(len(obj.data.vertices), 1664)
        self.assertEqual(report['trimTriangleCount'], 28)
        self.assertEqual(report['smoothSideTriangleCount'], 896)
        self.assertEqual(obj.data.uv_layers.active.name, self.source.data.uv_layers.active.name)
        self.assertEqual(surface.repair.crossing_pairs(obj)[2], [])
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])
        for p, old in zip(obj.data.polygons, self.source.data.polygons):
            self.assertEqual(p.material_index, old.material_index)
        gold = next(m for m in obj.data.materials if m.name.startswith('SleeveSurface_narrow'))
        self.assertAlmostEqual(gold.node_tree.nodes['TrimHalfWidth'].inputs[1].default_value, .12)

    def test_bad_width_rejected_without_copy(self):
        count = len(bpy.data.objects)
        for width in (0, -.1, .8, float('nan')):
            with self.assertRaisesRegex(ValueError, 'TRIM_WIDTH'):
                surface.surface_copy(self.source, self.joined, self.cloth, width)
        self.assertEqual(count, len(bpy.data.objects))

    def test_changed_topology_rejected(self):
        altered = self.source.copy()
        altered.data = self.source.data.copy()
        altered.data.clear_geometry()
        with self.assertRaisesRegex(ValueError, 'TOPOLOGY_CORRESPONDENCE'):
            surface.surface_copy(altered, self.joined, self.cloth)

    def test_existing_uv_mutation_detected(self):
        old = surface.structure_signature(self.source)
        self.source.data.uv_layers.active.data[0].uv.x += .125
        self.assertNotEqual(old, surface.structure_signature(self.source))

    def test_gate_true_and_missing_gate_rejected(self):
        scene = bpy.context.scene
        surface.require_locked(scene)
        for key in surface.c.base.GATES:
            previous = scene[key]
            scene[key] = True
            with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
                surface.require_locked(scene)
            scene[key] = previous
        del scene['unityInputAllowed']
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            surface.require_locked(scene)

    def test_color_conversion_matches_reference_token(self):
        self.assertAlmostEqual(surface.linear_color('151518')[0], .007499032, places=8)
        self.assertEqual(surface.linear_color('000000'), (0, 0, 0))
        self.assertEqual(surface.linear_color('FFFFFF'), (1, 1, 1))

    def test_saved_artifact_reopen(self):
        joined_name, cloth_name = self.joined.name, self.cloth.name
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj = bpy.data.objects[surface.RESULT_OBJECT]
        original = bpy.data.objects[surface.SOURCE_OBJECT]
        self.assertEqual(surface.structure_signature(obj), surface.structure_signature(original))
        self.assertFalse(obj.hide_get())
        self.assertTrue(original.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 14)
        surface.require_locked(bpy.context.scene)
        with self.assertRaisesRegex(ValueError, 'ALREADY_APPLIED'):
            surface.surface_copy(obj, bpy.data.objects[joined_name], bpy.data.objects[cloth_name])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path, required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE, ARTIFACT = args.source.resolve(), args.artifact.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SurfaceTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
