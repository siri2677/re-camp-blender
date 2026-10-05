import sys,math,unittest
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_cuff_interface_study as cuff

class CuffTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_shell_is_connected_hollow_manifold(self):
        def ring(radius,z,n): return dict(centroid=[0,0,z],points=[(radius*math.cos(i*2*math.pi/n),radius*math.sin(i*2*math.pi/n),z) for i in range(n)])
        obj=cuff.shell(bpy.context.scene.collection,ring(.03,0,29),ring(.016,-.015,82),Vector((0,0,1)),Vector((1,0,0)))
        audit=cuff.author.shape_audit(obj)
        self.assertEqual(audit['nonManifoldEdges'],0); self.assertEqual(len(audit['components']),1)
        self.assertEqual(len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons),0)
        self.assertEqual(cuff.wrist.self_surface_pairs(obj),0)
        self.assertFalse(obj['designApproved']); self.assertFalse(obj['unityInputAllowed'])
    def test_offset_rejects_collapsing_loop(self):
        with self.assertRaisesRegex(ValueError,'COLLAPSES_LOOP'):
            cuff.radial_offset([(.001,0,0)],(0,0,0),Vector((0,0,1)),-.002)
    def test_different_elliptical_profiles_keep_inner_outer_walls_separate(self):
        def ellipse(rx,ry,z,angle,n):
            points=[]
            for i in range(n):
                x=rx*math.cos(i*2*math.pi/n); y=ry*math.sin(i*2*math.pi/n)
                points.append((x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle),z))
            return dict(centroid=[0,0,z],points=points)
        obj=cuff.shell(bpy.context.scene.collection,ellipse(.02,.035,0,.4,29),ellipse(.022,.010,-.015,1.2,82),Vector((0,0,1)),Vector((1,0,0)))
        self.assertEqual(cuff.wrist.self_surface_pairs(obj),0)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CuffTests))
    if not result.wasSuccessful(): raise RuntimeError('CUFF_TEST_FAILED')
