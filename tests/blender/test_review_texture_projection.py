"""Real-bpy regression tests; fixtures are NOT character candidates.

blender -b --factory-startup --python-exit-code 1 --python tests/blender/test_review_texture_projection.py
"""
import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "review_texture", ROOT / "scripts/blender/apply_review_multiview_textures.py"
)
texture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(texture)


class TextureProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ch101-texture-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        image = bpy.data.images.new("fixture", width=16, height=16, alpha=True)
        pixels = []
        for y in range(16):
            for x in range(16):
                # A dark border encloses a white jacket patch, on white canvas.
                color = (0.1, 0.2, 0.3, 1.0) if 3 <= x <= 12 and 2 <= y <= 13 else (1, 1, 1, 1)
                if 6 <= x <= 9 and 5 <= y <= 10:
                    color = (1, 1, 1, 1)
                pixels.extend(color)
        image.pixels = pixels
        self.image = self.root / "reference.png"
        image.filepath_raw = str(self.image)
        image.file_format = "PNG"
        image.save()
        # Two actual mesh objects at different world heights. Per-object UVs
        # must not repeat a whole character sheet on each semantic component.
        for name, z in (("body", 0.5), ("hair", 1.5)):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
            bpy.context.object.name = name
        self.source = self.root / "source.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(self.source))

    def apply(self):
        return texture._apply_textures(argparse.Namespace(
            input_blend=self.source, front_image=self.image,
            back_image=self.image, right_image=self.image,
            output_blend=self.root / "result.blend", output_glb=None,
            report=self.root / "report.json", smooth_level=0,
            background_threshold=0.08,
        ))

    def test_mask_removes_canvas_but_preserves_enclosed_white_outfit(self):
        image, report = texture._foreground_texture("test", self.image, 0.08)
        self.assertEqual(image.pixels[3], 0.0)
        self.assertEqual(image.pixels[(7 * 16 + 7) * 4 + 3], 1.0)
        self.assertGreater(report["backgroundPixelRatio"], 0.25)

    def test_front_camera_neg_y_gets_front_not_back(self):
        self.apply()
        obj = bpy.data.objects["body"]
        face = next(p for p in obj.data.polygons if p.normal.y < -0.9)
        self.assertEqual(obj.data.materials[face.material_index].name, "CH101_REVIEW_TEXTURE_FRONT")

    def test_back_camera_has_correct_horizontal_handedness(self):
        self.apply()
        obj = bpy.data.objects["body"]
        face = next(p for p in obj.data.polygons if p.normal.y > 0.9)
        values = [(obj.data.vertices[obj.data.loops[i].vertex_index].co.x,
                   obj.data.uv_layers.active.data[i].uv.x) for i in face.loop_indices]
        left, right = min(values), max(values)
        self.assertGreater(left[1], right[1], "+Y camera screen-right is world -X")

    def test_semantic_objects_share_world_projection_bounds(self):
        self.apply()
        hair = bpy.data.objects["hair"]
        lowest_v = min(loop.uv.y for loop in hair.data.uv_layers.active.data)
        self.assertGreaterEqual(lowest_v, 0.49, "hair must use the upper half, not the whole sheet")

    def test_gate_locks_survive_texture_changes(self):
        report = self.apply()
        self.assertIs(report["unityInputAllowed"], False)
        self.assertIs(report["productionPromotionAllowed"], False)
        self.assertEqual(bpy.context.scene["source_status"], "AI_GENERATED_CANDIDATE_NOT_PRODUCTION")

    def test_packed_mask_survives_save_and_reopen(self):
        self.apply()
        bpy.ops.wm.open_mainfile(filepath=str(self.root / "result.blend"))
        image = bpy.data.images["CH101_REVIEW_TEXTURE_FRONT_FOREGROUND_MASKED"]
        self.assertEqual(image.pixels[3], 0.0)
        self.assertEqual(image.pixels[(7 * 16 + 7) * 4 + 3], 1.0)

    def test_review_floor_is_not_a_character_surface(self):
        bpy.ops.mesh.primitive_plane_add(size=200)
        bpy.context.object.name = "ReviewFloor_CH101"
        bpy.ops.wm.save_as_mainfile(filepath=str(self.source))
        report = self.apply()
        self.assertEqual(report["meshCount"], 2)
        self.assertEqual(len(bpy.data.objects["ReviewFloor_CH101"].data.materials), 0)
        self.assertEqual(report["projection"]["boundsMax"], [0.5, 0.5, 2.0])

    def test_existing_source_is_preserved_byte_for_byte(self):
        before = self.source.read_bytes()
        report = self.apply()
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(report["outputBlendSha256"], texture.sha256_file(self.root / "result.blend"))

    def test_projection_uses_subject_extent_inside_padded_reference(self):
        self.apply()
        # Subject spans x=3..12 and y=2..13 in the fixture, not the canvas.
        values = [loop.uv for obj in (bpy.data.objects['body'], bpy.data.objects['hair'])
                  for loop in obj.data.uv_layers.active.data]
        self.assertGreater(min(v.x for v in values), .1)
        self.assertLess(max(v.x for v in values), .9)
        self.assertGreater(min(v.y for v in values), .05)
        self.assertLess(max(v.y for v in values), .95)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TextureProjectionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("REVIEW_TEXTURE_PROJECTION_REGRESSION")
