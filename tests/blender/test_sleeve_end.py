import sys,unittest
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_sleeve_end_study as sleeve

class SleeveTests(unittest.TestCase):
    def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_hollow_connected_uv_and_locked_gates(self):
        obj=sleeve.build((0,0,0),(0,0,1),(1,0,0));a=sleeve.c.author.shape_audit(obj)
        self.assertEqual(a['nonManifoldEdges'],0);self.assertEqual(a['zeroAreaFaces'],0);self.assertEqual(len(a['components']),1)
        self.assertEqual(len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons),0)
        self.assertEqual(sleeve.c.wrist.self_surface_pairs(obj),0);self.assertIsNotNone(obj.data.uv_layers.active)
        self.assertFalse(obj['unityInputAllowed']);self.assertFalse(obj['productionPromotionAllowed']);self.assertFalse(obj['attachedToBody'])
    def test_invalid_frames_rejected(self):
        for axis,u in [((0,0,0),(1,0,0)),((0,0,1),(0,0,1))]:
            with self.assertRaises(ValueError):sleeve.build((0,0,0),axis,u)
    def test_collapsing_or_reversed_profiles_rejected(self):
        for profiles in [((0,.001,.01),(.1,.02,.02)),((.1,.02,.02),(0,.02,.02))]:
            with self.assertRaises(ValueError):sleeve.build((0,0,0),(0,0,1),(1,0,0),profiles)

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SleeveTests))
    if not r.wasSuccessful():raise RuntimeError('SLEEVE_TEST_FAILED')
