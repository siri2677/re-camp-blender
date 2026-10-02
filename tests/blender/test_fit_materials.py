import sys
import unittest
from pathlib import Path
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_fit_materials as refine
import build_ch101_equipment_detail_study as hardware


class MaterialTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.objects=hardware.build_details()

    def test_consolidation_preserves_face_inputs_geometry_and_gates(self):
        before=refine.topology(self.objects)
        assignments={o.name:[o.data.materials[p.material_index].name for p in o.data.polygons] for o in self.objects}
        result=refine.consolidate(self.objects)
        self.assertEqual(before,refine.topology(self.objects))
        self.assertEqual(len({m.name for o in self.objects for m in o.data.materials}),3)
        for obj in self.objects:
            self.assertFalse(obj['unityInputAllowed'])
            for poly,original in zip(obj.data.polygons,assignments[obj.name]):
                if original not in refine.SOLID_NAMES:
                    self.assertEqual(obj.data.materials[poly.material_index].name,original)
                    continue
                expected=result['sourceValues'][original]
                self.assertEqual(obj.data.materials[poly.material_index].name,'Equipment_SolidSurface_Attributes')
                self.assertAlmostEqual(obj.data.attributes['Equipment_Metallic'].data[poly.index].value,expected['metallic'])
                self.assertAlmostEqual(obj.data.attributes['Equipment_Roughness'].data[poly.index].value,expected['roughness'])
                for i in poly.loop_indices:
                    self.assertEqual(list(obj.data.attributes['Equipment_BaseColor'].data[i].color),expected['color'])
        self.assertFalse(result['unityShaderExportReady'])

    def test_missing_expected_shader_is_rejected(self):
        bpy.data.materials['Gold'].name='UnknownGold'
        with self.assertRaisesRegex(ValueError,'EXPECTED_FOUR'):
            refine.consolidate(self.objects)

    def test_linked_solid_shader_is_rejected(self):
        mat=bpy.data.materials['Gold']; node=mat.node_tree.nodes.new('ShaderNodeRGB')
        mat.node_tree.links.new(node.outputs[0],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SOLID_SHADER'):
            refine.consolidate(self.objects)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MaterialTests))
    if not result.wasSuccessful(): raise RuntimeError('MATERIAL_TEST_FAILED')
