"""Real Blender tests; run using --background --python-exit-code 1 --python."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bpy

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('equipment',ROOT/'scripts/blender/build_ch101_equipment_study.py')
equipment=importlib.util.module_from_spec(spec); spec.loader.exec_module(equipment)


class EquipmentStudyTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_three_connected_parts_uv_budget_and_single_alias(self):
        objects=equipment.build_geometry()
        audit=equipment.audit(objects)
        self.assertEqual(len(audit),3)
        self.assertLessEqual(sum(x['triangles'] for x in audit),2000)
        self.assertTrue(all(x['connectedComponents']==1 and x['nonManifoldEdges']==0 and x['hasUV'] for x in audit))
        self.assertEqual(sum('Ribbon' in o.name for o in objects),1)
        self.assertNotIn('Socket_Equipment_Primary',bpy.data.objects)
        self.assertEqual(bpy.data.objects['Socket_Weapon_R']['runtimeAlias'],'Socket_Equipment_Primary')
        self.assertFalse(bpy.context.scene['unityInputAllowed'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path))
            bpy.ops.wm.open_mainfile(filepath=str(path))
            self.assertFalse(bpy.context.scene['productionPromotionAllowed'])
            self.assertEqual(len([o for o in bpy.data.objects if o.type=='MESH']),3)

    def test_hash_mismatch_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(equipment.subprocess,'check_output',return_value=equipment.ART_COMMIT):
                with self.assertRaisesRegex(ValueError,'REFERENCE_SHA256_MISMATCH'):
                    equipment.run(Path(temp),Path(temp)/'out')
            self.assertFalse((Path(temp)/'out').exists())

    def test_commit_mismatch_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(equipment.subprocess,'check_output',return_value='0'*40):
                with self.assertRaisesRegex(ValueError,'ART_COMMIT_MISMATCH'):
                    equipment.run(Path(temp),Path(temp)/'out')

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(equipment,'verify_references',return_value=[]):
                with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
                    equipment.run(Path(temp),Path(temp))

    def test_blade_uv_pattern_covers_physical_length_not_ring_count(self):
        saber=equipment.build_geometry()[0]
        mesh=saber.data
        def uv_v(vertex):
            return next(mesh.uv_layers.active.data[i].uv.y for i,loop in enumerate(mesh.loops) if loop.vertex_index==vertex)
        # The blade occupies 0.625 / 0.931 of the length, not 1 / 11 rings.
        self.assertGreater(uv_v(16)-uv_v(8),.65)

    def test_ribbon_broad_face_uses_full_pattern_width(self):
        ribbon=equipment.build_geometry()[2]
        face=ribbon.data.polygons[1]
        values=[ribbon.data.uv_layers.active.data[i].uv.x for i in face.loop_indices]
        self.assertAlmostEqual(max(values)-min(values),1)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EquipmentStudyTests))
    if not result.wasSuccessful():
        raise RuntimeError('BLENDER_EQUIPMENT_TEST_FAILED')
