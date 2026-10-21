"""Verify real Blender row order and deformation invariants before fitting art."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
import bpy

spec = importlib.util.spec_from_file_location('fit', Path(__file__).resolve().parents[2] / 'scripts/blender/fit_review_silhouette.py')
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)


class SilhouetteFitTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_blender_bottom_row_maps_to_feet_not_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = bpy.data.images.new('profile_fixture', 32, 32, alpha=True)
            values = []
            for y in range(32):
                for x in range(32):
                    half = 10 if y < 16 else 3
                    values.extend((.1, .2, .3, 1) if abs(x - 16) <= half and 2 <= y <= 29 else (1, 1, 1, 1))
            img.pixels = values
            p = Path(tmp) / 'reference.png'
            img.filepath_raw = str(p)
            img.file_format = 'PNG'
            img.save()
            profile, _ = fit.read_reference_profile(p, 32)
            self.assertGreater(profile[3][1], profile[-4][1] * 2)

    def test_zero_strength_preserves_vertices_including_offset_center(self):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
        obj = bpy.context.object
        original = [v.co.copy() for v in obj.data.vertices]
        fit.deform_to_profile([obj], [(.3, .8)] * 32, 'neg_y', 0)
        self.assertLess(max((v.co - before).length for v, before in zip(obj.data.vertices, original)), 1e-6)

    def test_floor_is_excluded_from_fitting(self):
        bpy.ops.mesh.primitive_uv_sphere_add()
        bpy.context.object.name = 'Body'
        bpy.ops.mesh.primitive_plane_add(size=100)
        bpy.context.object.name = 'ReviewFloor_CH101'
        self.assertEqual([o.name for o in fit.mesh_objects()], ['Body'])


if __name__ == '__main__':
    if not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SilhouetteFitTests)).wasSuccessful():
        raise RuntimeError('SILHOUETTE_FIT_REGRESSION')
