import sys
import unittest
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_hand_authoring_study as hand
import build_ch101_equipment_detail_study as hardware

class HandTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_grip_and_open_have_six_groups_one_closed_surface(self):
        for pose in ('grip','open'):
            obj=hand.make_hand(bpy.context.scene.collection,pose); audit=hand.shape_audit(obj)
            self.assertEqual(len(audit['components']),1)
            self.assertEqual(audit['nonManifoldEdges'],0)
            self.assertEqual(audit['zeroAreaFaces'],0)
            self.assertEqual(set(audit['semanticGroups']),{'Palm','Thumb','Index','Middle','Ring','Little'})
            self.assertFalse(obj['sourceReplacementAllowed'])
            self.assertFalse(obj['unityInputAllowed'])
    def test_pose_input_validation(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_HAND_POSE'):
            hand.make_hand(bpy.context.scene.collection,'approved')
    def test_subdivided_grip_clears_actual_saber_and_hardware_surfaces(self):
        objects=hardware.build_details(); saber=bpy.data.objects['CH101_Saber']
        obj=hand.make_hand(bpy.context.scene.collection)
        bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
        modifier=obj.modifiers.new('Study_surface_subdivision','SUBSURF'); modifier.levels=1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.context.view_layer.update(); hand.align_to_saber(obj,saber); bpy.context.view_layer.update()
        audits=hand.fit.overlap_report(obj,[o for o in objects if o==saber or o.get('equipmentOwner')==saber.name],obj.matrix_world@hand.GRIP_CENTER)
        self.assertEqual(sum(a['uniqueEquipmentTrianglesCrossing'] for a in audits),0)
    def test_handle_center_alignment_is_exact(self):
        obj=hand.make_hand(bpy.context.scene.collection)
        saber=bpy.data.objects.new('Saber',None); bpy.context.scene.collection.objects.link(saber)
        saber.location=(2,3,4); bpy.context.view_layer.update()
        self.assertLess(hand.align_to_saber(obj,saber),1e-6)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HandTests))
    if not result.wasSuccessful(): raise RuntimeError('HAND_TEST_FAILED')
