import argparse
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import relax_ch101_upper_transition as transition

SOURCE = ARTIFACT = None


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(transition.c.base.sha(SOURCE), transition.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[transition.contour.RESULT_OBJECT]
        hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
        self.center = hand.matrix_world @ Vector()
        self.axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        _, self.normal, _ = transition.seam.trim.trim_plane(bpy.data.objects[transition.surface.RESULT_OBJECT],
            bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
            bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], self.axis)

    def test_actual_movement_survives_distortion_checks(self):
        obj, report = transition.relax(self.source, self.center, self.axis, self.normal)
        self.assertGreaterEqual(report['maxMoveMeters'], .0001)
        self.assertLessEqual(report['maxMoveMeters'], .0030001)
        self.assertGreaterEqual(report['lineSearch'][-1]['minimumNormalDot'], .90)
        self.assertGreaterEqual(report['lineSearch'][-1]['areaRatioRange'][0], .5)
        self.assertLessEqual(report['lineSearch'][-1]['areaRatioRange'][1], 1.5)
        self.assertLess(report['radialLaplacianRmsAfterMeters'], report['radialLaplacianRmsBeforeMeters'])
        self.assertEqual(transition.surface.repair.crossing_pairs(obj)[2], [])

    def test_locked_geometry_uv_shading_fields_and_original_preserved(self):
        signature = transition.surface.repair.invariant_signature(self.source)
        digest = transition.c.guide.digest([self.source])
        obj, report = transition.relax(self.source, self.center, self.axis, self.normal)
        self.assertEqual(signature, transition.surface.repair.invariant_signature(obj))
        self.assertEqual(digest, transition.c.guide.digest([self.source]))
        moved = set(report['vertexIndices'])
        locked = set().union(*(transition.contour.group_ids(self.source, name) for name in
                            ('BodySeam', 'SleeveSeam', 'SeamContourMidpoints')))
        self.assertFalse(moved & locked)
        self.assertEqual(report['lockedSeamVertexCount'], 146)
        mask_name = transition.seam.trim.upper.MASK
        distance_name = transition.seam.trim.DISTANCE
        self.assertEqual([x.value for x in self.source.data.attributes[mask_name].data],
                         [x.value for x in obj.data.attributes[mask_name].data])
        for i, vertex in enumerate(self.source.data.vertices):
            delta = obj.data.vertices[i].co-vertex.co
            if i not in report['perVertexMoveCapsMeters']:
                self.assertEqual(delta.length, 0)
            else:
                self.assertLessEqual(delta.length, report['perVertexMoveCapsMeters'][i]+1e-7)
                self.assertLessEqual(abs(delta.dot(self.axis)), 1e-7)
            expected = self.source.data.attributes[distance_name].data[i].value+delta.dot(self.normal)
            self.assertAlmostEqual(obj.data.attributes[distance_name].data[i].value, expected, places=7)
        self.assertEqual(transition.surface.repair.components(obj)[-1]['vertexIndices'],
                         transition.surface.repair.components(self.source)[-1]['vertexIndices'])
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])

    def test_invalid_input_and_rejected_copy_cleanup(self):
        names = set(bpy.data.objects.keys())
        for limit in (0, .004, float('nan')):
            with self.assertRaisesRegex(ValueError, 'UNSAFE_TRANSITION_MOVE'):
                transition.relax(self.source, self.center, self.axis, self.normal, max_move=limit)
        with self.assertRaisesRegex(ValueError, 'INVALID_REGION_FRAME'):
            transition.relax(self.source, self.center, self.axis*2, self.normal)
        with self.assertRaisesRegex(ValueError, 'INVALID_TRIM_NORMAL'):
            transition.relax(self.source, self.center, self.axis, Vector((float('nan'), 0, 1)))
        with self.assertRaisesRegex(ValueError, 'NEGLIGIBLE_GEOMETRY_CHANGE'):
            transition.relax(self.source, self.center, self.axis, self.normal, max_move=.00001)
        self.assertEqual(names, set(bpy.data.objects.keys()))
        with patch.object(transition.c.base, 'sha', return_value='0'*64):
            with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
                transition.run(SimpleNamespace(source=SOURCE, output=Path('artifacts/unused-transition-test')))
        bpy.context.scene['unityInputAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            transition.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_and_full_static_qa(self):
        if ARTIFACT is None:
            self.skipTest('Supply saved artifact for final validation')
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj = bpy.data.objects[transition.RESULT_OBJECT]
        report = json.loads((ARTIFACT.parent/'upper-transition-report.json').read_text(encoding='utf-8'))
        self.assertEqual(transition.c.base.sha(ARTIFACT), report['blendSha256'])
        self.assertFalse(obj.hide_get())
        self.assertTrue(bpy.data.objects[transition.contour.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 13)
        parts = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('PAIR_STUDY_')]
        qa = transition.seam.assess(obj, parts, report['operation'])
        self.assertTrue(qa['eligible'])
        self.assertEqual(qa['topology']['components'], [8148, 48])
        transition.surface.require_locked(bpy.context.scene)
        self.assertEqual(len(report['renders']), 10)
        for row in report['renders']:
            self.assertEqual(transition.c.base.sha(ARTIFACT.parent/row['file']), row['sha256'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE = args.source.resolve()
    ARTIFACT = args.artifact.resolve() if args.artifact else None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransitionTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
