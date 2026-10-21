import importlib.util
import unittest
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('landmark',ROOT/'scripts/blender/prepare_ch101_landmark_rig_review.py')
landmark=importlib.util.module_from_spec(spec); spec.loader.exec_module(landmark)


class LandmarkTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def points(self):
        points=[Vector((-.4,0,0)),Vector((.4,0,1.68))]
        for sign in [-1,1]:
            for x,z in [(.9,.51),(.65,.63),(.35,.75),(.20,.60)]:
                points.extend(Vector((sign*x*.4+dx*.001,dy*.001,z*1.68+dz*.001))
                              for dx in [-1,1] for dy in [-1,1] for dz in [-1,1])
        return points

    def test_guide_unbound_and_source_unchanged(self):
        points=self.points(); estimates=landmark.estimate(points)
        mesh=bpy.data.meshes.new('fixture'); mesh.from_pydata(points,[],[])
        obj=bpy.data.objects.new('fixture',mesh); bpy.context.scene.collection.objects.link(obj)
        before=landmark.digest([obj]); arm=landmark.guide(estimates)
        self.assertEqual(len(estimates),8)
        self.assertEqual(len(arm.data.bones),7)
        self.assertTrue(all(not b.use_deform for b in arm.data.bones))
        self.assertEqual(landmark.digest([obj]),before)
        self.assertFalse(arm['unityInputAllowed'])
        self.assertFalse(any(o.name.startswith('Socket_') for o in bpy.data.objects))

    def test_sparse_band_refuses_silent_joint_guess(self):
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_SURFACE_SAMPLES'):
            landmark.estimate([Vector((-.4,0,0)),Vector((.4,0,1.68))])

    def test_sides_are_geometric_not_claimed_anatomical_mapping(self):
        estimates=landmark.estimate(self.points())
        self.assertLess(estimates['NegX_Hand']['position'][0],0)
        self.assertGreater(estimates['PosX_Hand']['position'][0],0)
        self.assertTrue(all(e['status'].endswith('NOT_ANATOMY_VERIFIED') for e in estimates.values()))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LandmarkTests))
    if not result.wasSuccessful(): raise RuntimeError('LANDMARK_TEST_FAILED')
