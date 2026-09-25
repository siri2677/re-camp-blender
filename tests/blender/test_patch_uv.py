"""Pinned-asset regression: original shader RED, baked artifact GREEN."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch as mock_patch
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import bake_ch101_patch_albedo as bake
uv = bake.uv
SOURCE = ARTIFACT = None


class PatchUVTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(uv.c.base.sha(SOURCE), uv.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT or SOURCE))
        self.original = bpy.data.objects[uv.patch.contour.RESULT_OBJECT]
        self.target = bpy.data.objects[uv.patch.RESULT_OBJECT]
        self.operation = json.loads((SOURCE.parent/'upper-patch-report.json').read_text(encoding='utf-8'))['operation']

    def test_baseline_mixed_charts(self):
        report = uv.audit(self.original, self.target, self.operation)
        self.assertEqual(report['sourceChartCount'], 7)
        self.assertEqual(report['originalPerVertexMappingMixedChartTriangles'], 52)
        self.assertEqual(report['originalContinuousBoundaryEdges'], 23)
        self.assertEqual(report['originalSeamBoundaryEdges'], 42)
        self.assertEqual(len(report['newBoundaryDiscontinuities']), 3)

    def test_chart_transfer_rejects_without_mutation(self):
        names = set(bpy.data.objects.keys())
        signature = uv.surface.repair.invariant_signature(self.target)
        with self.assertRaisesRegex(ValueError, 'CORNER_OUTSIDE_SOURCE_CHART'):
            uv.attempt_face_chart_transfer(self.original, self.target, self.operation)
        self.assertEqual(names, set(bpy.data.objects.keys()))
        self.assertEqual(signature, uv.surface.repair.invariant_signature(self.target))

    def test_runtime_shader_uses_isolated_atlas(self):
        obj = bpy.data.objects[bake.RESULT_OBJECT] if ARTIFACT else self.target
        first = self.operation['retainedPolygonCount']
        self.assertIn(bake.ATLAS_UV, obj.data.uv_layers, 'Original mixed-chart shader must fail')
        self.assertEqual(len(obj.data.materials), len(self.target.data.materials)+1)
        self.assertEqual({p.material_index for p in obj.data.polygons[first:]}, {len(obj.data.materials)-1})
        mat = obj.data.materials[-1]
        texture = mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].links[0].from_node
        self.assertEqual(texture.type, 'TEX_IMAGE')
        self.assertEqual(texture.inputs['Vector'].links[0].from_node.uv_map, bake.ATLAS_UV)
        self.assertIsNotNone(texture.image.packed_file)
        self.assertEqual(tuple(texture.image.size), (1024, 1024))
        self.assertEqual(len(obj.data.uv_layers), len(self.target.data.uv_layers)+1)
        self.assertEqual(obj.data.uv_layers.active.name, self.target.data.uv_layers.active.name)
        layer = obj.data.uv_layers[bake.ATLAS_UV]
        for index, face in enumerate(obj.data.polygons[first:]):
            for loop in face.loop_indices:
                u, v = layer.data[loop].uv
                self.assertEqual((int(u*18), int(v*18)), (index % 18, index//18))

    def test_saved_preservation_qa_hashes(self):
        if not ARTIFACT:
            self.skipTest('Saved artifact required')
        obj = bpy.data.objects[bake.RESULT_OBJECT]
        checks = bake.verify_preservation(self.target, obj, self.operation['retainedPolygonCount'])
        parts = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(uv.seam.assess(obj, parts, checks)['eligible'])
        self.assertEqual(sorted(x['vertexCount'] for x in uv.surface.repair.components(obj)), [48, 8188])
        self.assertEqual(len(obj.data.vertices), 8236)
        obj.data.calc_loop_triangles()
        self.assertEqual(len(obj.data.loop_triangles), 16464)
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_get()]), 13)
        self.assertTrue(self.target.hide_get())
        self.assertFalse(obj.hide_get())
        report = json.loads((ARTIFACT.parent/'patch-albedo-bake-report.json').read_text(encoding='utf-8'))
        self.assertEqual(uv.c.base.sha(ARTIFACT), report['blendSha256'])
        self.assertEqual(report['bake']['bakeCoverageSamples'], 1926)
        self.assertEqual(report['bake']['missedCoverageSamples'], 0)
        self.assertEqual(report['bake']['addedSourceCollarFaces'], 60)
        self.assertEqual(len(report['renders']), 8)
        for row in report['renders']:
            self.assertEqual(uv.c.base.sha(ARTIFACT.parent/row['file']), row['sha256'])
        for key in ('albedo', 'coverage'):
            self.assertEqual(uv.c.base.sha(ARTIFACT.parent/report['bake'][key+'File']), report['bake'][key+'Sha256'])
        for subject in (obj, bpy.context.scene, report):
            uv.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore'])

    def test_preservation_rejects_mutations(self):
        if not ARTIFACT:
            self.skipTest('Saved artifact required')
        obj = bpy.data.objects[bake.RESULT_OBJECT]
        first = self.operation['retainedPolygonCount']
        obj.data.vertices[0].co.x += .01
        with self.assertRaisesRegex(ValueError, 'BAKE_CHANGED_GEOMETRY'):
            bake.verify_preservation(self.target, obj, first)
        obj.data.vertices[0].co = self.target.data.vertices[0].co
        obj.data.uv_layers['UVMap'].data[0].uv.x += .1
        with self.assertRaisesRegex(ValueError, 'BAKE_CHANGED_ORIGINAL_UV'):
            bake.verify_preservation(self.target, obj, first)
        obj.data.uv_layers['UVMap'].data[0].uv = self.target.data.uv_layers['UVMap'].data[0].uv
        obj.data.attributes[uv.seam.trim.upper.MASK].data[0].value += .1
        with self.assertRaisesRegex(ValueError, 'BAKE_CHANGED_MASK'):
            bake.verify_preservation(self.target, obj, first)

    def test_fail_closed_inputs_gate(self):
        with mock_patch.object(uv.c.base, 'sha', return_value='0'*64):
            with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
                bake.run(SimpleNamespace(source=SOURCE, output=Path('artifacts/unused-bake-test')))
        with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_EXISTS'):
            bake.run(SimpleNamespace(source=SOURCE, output=SOURCE.parent))
        with self.assertRaisesRegex(ValueError, 'PATCH_FACE_COUNT_CHANGED'):
            bake.atlas_layout(self.target)
        bpy.context.scene['unityInputAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            uv.surface.require_locked(bpy.context.scene)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE = args.source.resolve()
    ARTIFACT = args.artifact.resolve() if args.artifact else None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PatchUVTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
