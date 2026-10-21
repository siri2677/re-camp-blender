import sys,math,unittest
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import simplify_ch101_cuff_study as reduction

class ReductionTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        def ring(r,z):return dict(centroid=[0,0,z],points=[(r*math.cos(i*2*math.pi/64),r*math.sin(i*2*math.pi/64),z) for i in range(64)])
        self.source=reduction.cuff.shell(bpy.context.scene.collection,ring(.03,0),ring(.018,-.015),Vector((0,0,1)),Vector((1,0,0)),count=64)
        bpy.ops.mesh.primitive_cube_add(size=.01,location=(.3,0,0));self.hand=bpy.context.object
    def trial(self):return reduction.simplify(self.source,.5)
    def test_copy_reduces_faces_preserves_source_and_false_gates(self):
        before=reduction.cuff.guide.digest([self.source]);obj=self.trial()
        self.assertEqual(before,reduction.cuff.guide.digest([self.source]))
        self.assertIsNot(obj.data,self.source.data)
        self.assertNotIn('ringVertexCount',obj)
        self.assertFalse(obj['unityInputAllowed']);self.assertFalse(obj['productionPromotionAllowed'])
        self.assertLess(reduction.cuff.author.shape_audit(obj)['triangles'],reduction.cuff.author.shape_audit(self.source)['triangles'])
        self.assertEqual(reduction.cuff.author.shape_audit(obj)['nonManifoldEdges'],0)
    def test_displaced_surface_is_rejected(self):
        obj=self.trial();obj.location.x+=.01;bpy.context.view_layer.update()
        report=reduction.assess(self.source,obj,self.hand)
        self.assertFalse(report['eligible']);self.assertIn('SAMPLED_SURFACE_ERROR_EXCEEDED',report['rejectionReasons'])
    def test_true_gate_and_missing_uv_are_rejected(self):
        obj=self.trial();obj['unityInputAllowed']=True
        for layer in list(obj.data.uv_layers):obj.data.uv_layers.remove(layer)
        report=reduction.assess(self.source,obj,self.hand)
        self.assertFalse(report['eligible']);self.assertIn('PROMOTION_GATE_NOT_FALSE',report['rejectionReasons'])
        self.assertIn('UV_MISSING_OR_NONFINITE',report['rejectionReasons'])
    def test_invalid_ratio_is_rejected(self):
        for ratio in (0,1,-1):
            with self.assertRaises(ValueError):reduction.simplify(self.source,ratio)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReductionTests))
    if not result.wasSuccessful():raise RuntimeError('CUFF_REDUCTION_TEST_FAILED')
