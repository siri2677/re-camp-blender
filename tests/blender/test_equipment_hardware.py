"""Exercise real mesh hardware and fail-closed character attachment audit."""
import importlib.util
import tempfile
import unittest
import argparse
import os
from unittest.mock import patch
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('hardware',ROOT/'scripts/blender/build_ch101_equipment_detail_study.py')
hardware=importlib.util.module_from_spec(spec); spec.loader.exec_module(hardware)


class HardwareTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_hardware_budget_topology_parenting_and_single_ribbon(self):
        objects=hardware.build_details(); report=hardware.base.audit(objects)
        self.assertGreater(len(objects),3)
        self.assertLessEqual(sum(x['triangles'] for x in report),2000)
        self.assertLessEqual(len({m.name for o in objects for m in o.data.materials}),6)
        self.assertEqual(sum(o.name=='CH101_SignalRibbon_SINGLE' for o in objects),1)
        for o in objects[3:]:
            self.assertIn(o.parent,objects[:3])
            self.assertEqual(o['equipmentOwner'],o.parent.name)
            self.assertFalse(o['unityInputAllowed'])
        self.assertNotIn('Socket_Equipment_Primary',bpy.data.objects)
        # The pommel ring genuinely has an aperture (genus 1), not a capped disc.
        loop=bpy.data.objects['Saber_PommelRing'].data
        self.assertEqual(len(loop.vertices)-len(loop.edges)+len(loop.polygons),0)

    def test_character_without_rig_blocks_attachment_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path))
            before=path.read_bytes()
            audit=hardware.inspect_character(path,hardware.base.sha(path))
            self.assertIn('NO_ARMATURE_IN_SOURCE',audit['reasons'])
            self.assertIn('NO_WEAPON_SOCKET_IN_SOURCE',audit['reasons'])
            self.assertFalse(audit['attachmentPerformed'])
            self.assertEqual(before,path.read_bytes())

    def test_wrong_character_hash_fails_before_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(path))
            with self.assertRaisesRegex(ValueError,'CHARACTER_SHA256_MISMATCH'):
                hardware.inspect_character(path,'0'*64)

    def test_relative_cli_output_reaches_renderer_as_absolute(self):
        with tempfile.TemporaryDirectory() as temp:
            previous=Path.cwd()
            try:
                os.chdir(temp)
                args=argparse.Namespace(art_root=Path('art'),output_dir=Path('result'),
                    character_blend=Path('source.blend'),character_sha256='0'*64)
                def render_boundary(output):
                    self.assertTrue(output.is_absolute(),'Relative path leaked into Blender renderer')
                    self.assertEqual(output,(Path(temp)/'result').resolve())
                    return []
                with patch.object(hardware.base,'verify_references',return_value=[]), \
                     patch.object(hardware,'inspect_character',return_value={}), \
                     patch.object(hardware.base,'render_views',side_effect=render_boundary), \
                     patch.object(hardware,'extra_renders',return_value=[]):
                    hardware.run(args)
            finally:
                os.chdir(previous)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HardwareTests))
    if not result.wasSuccessful(): raise RuntimeError('HARDWARE_TEST_FAILED')
