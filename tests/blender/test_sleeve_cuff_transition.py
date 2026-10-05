from pathlib import Path
import sys
import unittest

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import join_ch101_sleeve_cuff_study as transition


class TransitionTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def parts(self):
        # The lower hollow shell is deliberately decimated: its two rim counts
        # differ from the structured 32-point sleeve and from each other.
        cuff = transition.sleeve.build((0, 0, 0), (0, 0, 1), (1, 0, 0),
                                      ((-.015, .022, .031), (0, .022, .031)))
        bpy.context.view_layer.objects.active = cuff
        modifier = cuff.modifiers.new('FixtureDecimation', 'DECIMATE')
        modifier.ratio = .7
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        cloth = transition.sleeve.build((0, 0, 0), (0, 0, 1), (1, 0, 0))
        return cuff, cloth

    def test_unequal_rims_connected_and_originals_preserved(self):
        cuff, cloth = self.parts()
        before = transition.c.guide.digest([cuff, cloth])
        obj, report = transition.join_parts(cuff, cloth, Vector(), (0, 0, 1), (1, 0, 0))
        audit = transition.c.author.shape_audit(obj)
        self.assertEqual(audit['nonManifoldEdges'], 0)
        self.assertEqual(audit['zeroAreaFaces'], 0)
        self.assertEqual(len(audit['components']), 1)
        self.assertEqual(len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons), 0)
        self.assertEqual(transition.c.wrist.self_surface_pairs(obj), 0)
        self.assertEqual(report['retainedNormalMismatches'], 0)
        self.assertFalse(any(report['reversedTransitionFaces'].values()))
        self.assertEqual(before, transition.c.guide.digest([cuff, cloth]))
        self.assertNotEqual(len(report['boundaries'][0]['outer']['vertices']), 32)
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['attachedToBody'])
        # Check the actual retained per-loop UV values, not just a report flag.
        expected = []
        for part, spec in zip((cuff, cloth), report['boundaries']):
            expected.extend(tuple(part.data.uv_layers.active.data[i].uv)
                            for p in part.data.polygons if p.index not in spec['removedCapFaces']
                            for i in p.loop_indices)
        actual = [tuple(obj.data.uv_layers.active.data[i].uv)
                  for p in obj.data.polygons[:report['retainedFaces']] for i in p.loop_indices]
        self.assertEqual(expected, actual)

    def test_world_frame_rotation_translation(self):
        cuff, cloth = self.parts()
        transform = Matrix.Translation((.3, -.7, 1.1)) @ Matrix.Rotation(.65, 4, 'Y')
        for part in (cuff, cloth):
            part.matrix_world = transform
        bpy.context.view_layer.update()
        obj, report = transition.join_parts(cuff, cloth, transform@Vector(),
                                           transform.to_3x3()@Vector((0, 0, 1)),
                                           transform.to_3x3()@Vector((1, 0, 0)))
        self.assertEqual(report['retainedNormalMismatches'], 0)
        self.assertFalse(any(report['reversedTransitionFaces'].values()))
        self.assertEqual(transition.c.wrist.self_surface_pairs(obj), 0)

    def test_missing_cap_and_invalid_frame_rejected(self):
        cuff, cloth = self.parts()
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_CAP_NOT_FOUND'):
            transition.open_rim(cuff, Vector(), (0, 0, 1), (1, 0, 0), .05)
        with self.assertRaisesRegex(ValueError, 'INVALID_TRANSITION_FRAME'):
            transition.join_parts(cuff, cloth, Vector(), (0, 0, 0), (1, 0, 0))
        with self.assertRaisesRegex(ValueError, 'REVERSED_OR_TOO_CLOSE'):
            transition.join_parts(cuff, cloth, Vector(), (0, 0, 1), (1, 0, 0), .002, 0)

    def test_incomplete_annulus_rejected(self):
        cuff, _ = self.parts()
        # Move a cap-only patch enough to break the explicit planar selection.
        spec, _ = transition.open_rim(cuff, Vector(), (0, 0, 1), (1, 0, 0), 0)
        index = spec['outer']['vertices'][0]
        cuff.data.vertices[index].co.z += .0003
        cuff.data.update()
        with self.assertRaises(ValueError):
            transition.open_rim(cuff, Vector(), (0, 0, 1), (1, 0, 0), 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransitionTests))
    if not result.wasSuccessful():
        raise RuntimeError('SLEEVE_CUFF_TRANSITION_TEST_FAILED')
