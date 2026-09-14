import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_hand_wrist_study as study

class WristTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_taper_preserves_distal_geometry_and_connectivity(self):
        obj=study.author.make_hand(bpy.context.scene.collection)
        before=[tuple(v.co) for v in obj.data.vertices]
        study.taper_cage(obj)
        for v,old in zip(obj.data.vertices,before):
            if old[2]>=.025: self.assertEqual(tuple(v.co),old)
        report=study.author.shape_audit(obj)
        self.assertEqual(len(report['components']),1); self.assertEqual(report['nonManifoldEdges'],0)
    def test_rotating_or_sliding_keeps_explicit_grip_anchor(self):
        obj=study.author.make_hand(bpy.context.scene.collection)
        saber=bpy.data.objects.new('Saber',None); bpy.context.scene.collection.objects.link(saber)
        for roll in (0,90,-90,180):
            self.assertLess(study.rigid_trial(obj,saber,roll,.03),1e-6)
    def test_plane_intersections_are_not_approved_seams(self):
        bpy.ops.mesh.primitive_cube_add(size=.06)
        report=study.wrist_sections(bpy.context.object,(0,0,-.05),Vector((0,0,1)))
        self.assertEqual(len(report),3)
        self.assertTrue(all(not r['verifiedAnatomicalSeam'] for r in report))
    def test_tangent_plane_fails_closed_without_reliable_samples(self):
        bpy.ops.mesh.primitive_cube_add(size=.06)
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_SAMPLES'):
            study.wrist_sections(bpy.context.object,(0,0,-.06),Vector((0,0,1)))
    def test_self_surface_probe_clean_cube(self):
        bpy.ops.mesh.primitive_cube_add()
        self.assertEqual(study.self_surface_pairs(bpy.context.object),0)
    def test_eight_trials_stop_when_all_cross(self):
        obj=study.author.make_hand(bpy.context.scene.collection)
        saber=bpy.data.objects.new('Saber',None); bpy.context.scene.collection.objects.link(saber)
        with patch.object(study.fit,'overlap_report',return_value=[{'uniqueEquipmentTrianglesCrossing':1}]) as probe:
            with self.assertRaisesRegex(ValueError,'NO_NONCROSSING_WRIST_TRIAL'):
                study.compare_poses(obj,saber,[],(0,0,0),(0,0,1))
            self.assertEqual(probe.call_count,8)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WristTests))
    if not result.wasSuccessful(): raise RuntimeError('WRIST_STUDY_TEST_FAILED')
