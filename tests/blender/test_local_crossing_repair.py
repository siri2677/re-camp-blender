"""Run in Blender; pass -- --source <verified distal-replacement Blend> for integration fixtures."""
import argparse
from pathlib import Path
import sys
import unittest

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/blender'))
import repair_ch101_local_crossing as repair

SOURCE = None
ARTIFACT = None


class GeometryTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_finite_edges_confirm_segment_and_reject_remote_plane(self):
        a = [Vector(p) for p in [(-1, -1, 0), (1, -1, 0), (0, 1, 0)]]
        b = [Vector(p) for p in [(0, -.5, -1), (0, -.5, 1), (0, .5, 1)]]
        self.assertEqual(len(repair.finite_crossing_hits(a, b)), 2)
        self.assertEqual(repair.finite_crossing_hits(a, [p+Vector((0, 0, 3)) for p in b]), [])

    def test_closed_mesh_without_crossings_is_not_modified(self):
        bpy.ops.mesh.primitive_cube_add()
        source = bpy.context.object
        before = repair.c.guide.digest([source])
        with self.assertRaisesRegex(ValueError, 'NO_CROSSING'):
            repair.bounded_repair(source, 0)
        self.assertEqual(before, repair.c.guide.digest([source]))

    def test_signature_detects_uv_changes(self):
        bpy.ops.mesh.primitive_cube_add()
        source = bpy.context.object
        before = repair.invariant_signature(source)
        source.data.uv_layers.active.data[0].uv.x += .125
        self.assertNotEqual(before, repair.invariant_signature(source))

    def test_unsafe_limits_are_rejected(self):
        bpy.ops.mesh.primitive_cube_add()
        with self.assertRaisesRegex(ValueError, 'UNSAFE_REPAIR_LIMIT'):
            repair.bounded_repair(bpy.context.object, 0, max_move=.001)


class SourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        if SOURCE is None:
            self.skipTest('Verified source Blend not supplied')
        self.assertEqual(repair.c.base.sha(SOURCE), repair.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[repair.SOURCE_OBJECT]

    def test_repair_preserves_original_uv_components_and_other_vertices(self):
        before = repair.c.guide.digest([self.source])
        signature = repair.invariant_signature(self.source)
        groups = repair.components(self.source)
        obj, report = repair.bounded_repair(self.source, repair.PATCH_VERTEX)
        self.assertEqual(len(report['beforePairs']), 3)
        self.assertEqual(report['afterNonAdjacentPairs'], 0)
        self.assertEqual(report['changedVertexIndices'], [repair.PATCH_VERTEX])
        self.assertLessEqual(report['actualDisplacementMeters'], .0005)
        self.assertGreaterEqual(report['minimumIncidentNormalDot'], .95)
        self.assertEqual(signature, repair.invariant_signature(obj))
        self.assertEqual(before, repair.c.guide.digest([self.source]))
        self.assertEqual(groups[1:], repair.components(obj)[1:])
        self.assertEqual(report['topology']['components'], [6438, 48])
        self.assertEqual(report['topology']['nonManifoldEdges'], 0)
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])

    def test_wrong_patch_vertex_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'VERTEX_OUTSIDE_CROSSING_PATCH'):
            repair.bounded_repair(self.source, 0)

    def test_failed_repair_does_not_leave_copy_or_modify_source(self):
        before = repair.c.guide.digest([self.source])
        names = set(bpy.data.objects.keys())
        with self.assertRaises(ValueError):
            repair.bounded_repair(self.source, repair.PATCH_VERTEX, distance=.00004)
        self.assertEqual(names, set(bpy.data.objects.keys()))
        self.assertEqual(before, repair.c.guide.digest([self.source]))

    def test_saved_artifact_reopens_with_repair_and_hidden_original(self):
        if ARTIFACT is None:
            self.skipTest('Saved repaired Blend not supplied')
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        original = bpy.data.objects[repair.SOURCE_OBJECT]
        obj = bpy.data.objects['CH101_SourceBody_DistalReplacement_TopologyRepair_NOT_PRODUCTION']
        self.assertEqual(len(repair.crossing_pairs(original)[2]), 3)
        self.assertEqual(repair.crossing_pairs(obj)[2], [])
        self.assertEqual(repair.invariant_signature(obj), repair.invariant_signature(original))
        self.assertEqual(repair.components(original)[1:], repair.components(obj)[1:])
        self.assertEqual([v.index for v, w in zip(original.data.vertices, obj.data.vertices) if v.co != w.co], [repair.PATCH_VERTEX])
        self.assertFalse(obj.hide_get())
        self.assertTrue(original.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 14)
        self.assertFalse(bpy.context.scene['unityInputAllowed'])
        self.assertFalse(bpy.context.scene['productionPromotionAllowed'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    SOURCE = args.source.resolve() if args.source else None
    ARTIFACT = args.artifact.resolve() if args.artifact else None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        raise RuntimeError('LOCAL_CROSSING_REPAIR_TEST_FAILED')
