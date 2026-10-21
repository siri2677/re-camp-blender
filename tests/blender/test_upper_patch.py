import argparse
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch as mock_patch

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import rebuild_ch101_upper_patch as patch

SOURCE = ARTIFACT = None


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(patch.c.base.sha(SOURCE), patch.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[patch.contour.RESULT_OBJECT]
        hand = bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION']
        self.center = hand.matrix_world @ Vector()
        self.axis = (hand.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        self.u = hand.matrix_world.to_3x3() @ Vector((1, 0, 0))
        _, self.normal, _ = patch.seam.trim.trim_plane(bpy.data.objects[patch.surface.RESULT_OBJECT],
            bpy.data.objects['CH101_JoinedSleeveCuff_STUDY_NOT_PRODUCTION'],
            bpy.data.objects['CH101_SleeveEnd_HYPOTHESIS_NOT_PRODUCTION'], self.axis)

    def test_patch_transfer_does_not_extrapolate(self):
        obj, report = patch.build(self.source, self.center, self.axis, self.u, self.normal)
        self.assertLessEqual(report['maxProjectionDistanceMeters'], patch.MAX_PROJECTION)
        for sample in report['projectionSamples'].values():
            self.assertGreaterEqual(min(sample['barycentric']), -1e-5)
            self.assertLessEqual(max(sample['barycentric']), 1.00001)
        self.assertEqual(report['sharedBoundaryEdges'], 65)
        self.assertEqual(patch.surface.repair.crossing_pairs(obj)[2], [])

    def test_exact_vertex_and_invalid_barycentric_cases(self):
        triangle = [Vector(v) for v in [(-.2602105140686035, -.01477697491645813, .9585214853286743),
                    (-.2670934200286865, -.015377067029476166, .9557964205741882),
                    (-.2669386565685272, -.012958886101841927, .9556275010108948)]]
        self.assertEqual(patch.stable_barycentric(triangle[2], triangle), (0., 0., 1.))
        with self.assertRaisesRegex(ValueError, 'EXTRAPOLATION'):
            patch.stable_barycentric(triangle[0]+(triangle[1]-triangle[0])*2, triangle)
        with self.assertRaisesRegex(ValueError, 'DEGENERATE_TRANSFER_TRIANGLE'):
            patch.stable_barycentric(Vector((.3, 0, 0)), [Vector((i, 0, 0)) for i in range(3)])
        with self.assertRaisesRegex(ValueError, 'TRIANGLE_MISMATCH'):
            patch.stable_barycentric(Vector((.2, .2, .01)), [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))])

    def test_retained_faces_uv_groups_and_source_preserved(self):
        digest = patch.c.guide.digest([self.source])
        signature = patch.surface.repair.invariant_signature(self.source)
        obj, report = patch.build(self.source, self.center, self.axis, self.u, self.normal)
        self.assertEqual(digest, patch.c.guide.digest([self.source]))
        self.assertEqual(signature, patch.surface.repair.invariant_signature(self.source))
        self.assertEqual(report['sourcePolygonCountRemoved'], 221)
        self.assertEqual(report['newPatchTriangles'], 321)
        self.assertEqual(report['newInteriorVertices'], 128)
        remap = report['retainedVertexMap']
        for old, new in remap.items():
            self.assertEqual(obj.data.vertices[new].co, self.source.matrix_world @ self.source.data.vertices[old].co)
            for name in (patch.seam.trim.upper.MASK, patch.seam.trim.DISTANCE):
                self.assertEqual(obj.data.attributes[name].data[new].value, self.source.data.attributes[name].data[old].value)
            for membership in self.source.data.vertices[old].groups:
                group = self.source.vertex_groups[membership.group]
                self.assertEqual(obj.vertex_groups[group.name].weight(new), membership.weight)
        for new_index, old_index in enumerate(report['retainedFaceMapping']):
            old, new = self.source.data.polygons[old_index], obj.data.polygons[new_index]
            self.assertEqual([remap[i] for i in old.vertices], list(new.vertices))
            self.assertEqual((old.material_index, old.use_smooth), (new.material_index, new.use_smooth))
            for layer in self.source.data.uv_layers:
                self.assertEqual([tuple(layer.data[i].uv) for i in old.loop_indices],
                                 [tuple(obj.data.uv_layers[layer.name].data[i].uv) for i in new.loop_indices])
        for name in ('BodySeam', 'SleeveSeam', 'SeamContourMidpoints'):
            self.assertEqual({remap[i] for i in patch.contour.group_ids(self.source, name)}, patch.contour.group_ids(obj, name))
        self.assertEqual(patch.surface.repair.components(obj)[-1]['vertexCount'], 48)
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])

    def test_invalid_projection_frame_hash_and_gate_rejected(self):
        names = set(bpy.data.objects.keys())
        for limit in (0, .013, float('nan')):
            with self.assertRaisesRegex(ValueError, 'UNSAFE_PROJECTION_LIMIT'):
                patch.build(self.source, self.center, self.axis, self.u, self.normal, max_projection=limit)
        with self.assertRaisesRegex(ValueError, 'INVALID_PATCH_FRAME'):
            patch.build(self.source, self.center, self.axis*2, self.u, self.normal)
        with self.assertRaisesRegex(ValueError, 'INVALID_TRIM_NORMAL'):
            patch.build(self.source, self.center, self.axis, self.u, self.normal*2)
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_BOUNDED_SOURCE'):
            patch.build(self.source, self.center, self.axis, self.u, self.normal, max_projection=1e-7)
        self.assertEqual(names, set(bpy.data.objects.keys()))
        with mock_patch.object(patch.c.base, 'sha', return_value='0'*64):
            with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
                patch.run(SimpleNamespace(source=SOURCE, output=Path('artifacts/unused-upper-patch-test')))
        bpy.context.scene['unityInputAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            patch.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_static_qa_and_render_hashes(self):
        if ARTIFACT is None:
            self.skipTest('Supply artifact for final saved-scene validation')
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        obj = bpy.data.objects[patch.RESULT_OBJECT]
        report = json.loads((ARTIFACT.parent/'upper-patch-report.json').read_text(encoding='utf-8'))
        self.assertEqual(patch.c.base.sha(ARTIFACT), report['blendSha256'])
        self.assertFalse(obj.hide_get())
        self.assertTrue(bpy.data.objects[patch.contour.RESULT_OBJECT].hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 13)
        parts = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(patch.seam.assess(obj, parts, report['operation'])['eligible'])
        patch.surface.require_locked(bpy.context.scene)
        self.assertEqual(len(report['renders']), 10)
        for row in report['renders']:
            self.assertEqual(patch.c.base.sha(ARTIFACT.parent/row['file']), row['sha256'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE = args.source.resolve()
    ARTIFACT = args.artifact.resolve() if args.artifact else None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
