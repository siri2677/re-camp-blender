"""Exercise the actual graph builder and save/reopen of a review fixture."""
import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('continuous', ROOT/'scripts/blender/apply_continuous_review_projection.py')
continuous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(continuous)
face_spec = importlib.util.spec_from_file_location('face', ROOT/'scripts/blender/smooth_review_face_region.py')
face = importlib.util.module_from_spec(face_spec)
face_spec.loader.exec_module(face)


class ContinuousProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=(.4,.2,1))
        self.source = self.root/'source.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(self.source))
        image = bpy.data.images.new('fixture', 16, 16, alpha=True)
        image.pixels = [channel for y in range(16) for x in range(16)
                        for channel in ((.2,.3,.4,1) if 2<=x<14 and 2<=y<14 else (1,1,1,1))]
        self.reference = self.root/'reference.png'
        image.filepath_raw = str(self.reference)
        image.file_format = 'PNG'
        image.save()
        self.args = argparse.Namespace(input_blend=self.source,input_sha256=continuous.sha256_file(self.source),
            front_image=self.reference,back_image=self.reference,right_image=self.reference,
            output_blend=self.root/'result.blend',report=self.root/'report.json')

    def test_continuous_material_preserves_geometry_and_packs_references(self):
        before = self.source.read_bytes()
        continuous.apply(self.args)
        bpy.ops.wm.open_mainfile(filepath=str(self.args.output_blend))
        objects = [o for o in bpy.context.scene.objects if o.type=='MESH']
        self.assertEqual(before,self.source.read_bytes())
        for obj in objects:
            self.assertEqual(len(obj.data.materials),1)
            self.assertEqual(set(p.material_index for p in obj.data.polygons),{0})
        textures = [n for n in objects[0].data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE']
        self.assertEqual({n.label for n in textures},{'front','back','right'})
        self.assertTrue(all(n.image.packed_file for n in textures))
        self.assertFalse(bpy.context.scene['unity_input_allowed'])
        self.assertFalse(bpy.context.scene['production_promotion_allowed'])

    def test_bad_source_hash_cannot_write_a_result(self):
        self.args.input_sha256 = '0'*64
        with self.assertRaisesRegex(ValueError,'SHA256_MISMATCH'):
            continuous.apply(self.args)
        self.assertFalse(self.args.output_blend.exists())

    def test_face_region_smoothing_keeps_body_and_topology_unchanged(self):
        obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
        before=[v.co.copy() for v in obj.data.vertices]
        faces=[tuple(p.vertices) for p in obj.data.polygons]
        report=face.smooth([obj])
        self.assertEqual(faces,[tuple(p.vertices) for p in obj.data.polygons])
        for v,original in zip(obj.data.vertices,before):
            if original.z<.5:
                self.assertEqual(v.co,original)
        self.assertTrue(report[0]['outsideRegionUnchanged'])
        self.assertLessEqual(report[0]['maxDisplacement'],.010001)


if __name__=='__main__':
    if not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContinuousProjectionTests)).wasSuccessful():
        raise RuntimeError('CONTINUOUS_PROJECTION_REGRESSION')
