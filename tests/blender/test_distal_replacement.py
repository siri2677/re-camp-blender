from pathlib import Path
import sys
import unittest
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import replace_ch101_distal_source_study as replacement


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def body(self, remote=False):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.03,depth=.25)
        obj=bpy.context.object
        if remote:
            bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.03,depth=.25,location=(.5,0,0))
            obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.object.join()
        obj.data.materials.append(replacement.c.base.material('SourceFixture',(.2,.3,.4)))
        return obj

    def test_clipping_interpolates_uv_and_retains_winding(self):
        points=[Vector((-1,0,-1)),Vector((1,0,1)),Vector((0,1,1))]
        clipped=replacement.clip_triangle([(0,(0,0)),(1,(1,0)),(2,(0,1))],points,Vector(),Vector((0,0,1)))
        self.assertEqual(len(clipped),4)
        self.assertEqual(clipped[0][0],('e',0,1))
        self.assertEqual(clipped[0][2],(.5,0.))
        self.assertEqual(clipped[-1][2],(0.,.5))
        self.assertTrue(all(row[1].z>=0 for row in clipped))

    def test_capped_copy_is_manifold_uv_preserved_original_unchanged(self):
        source=self.body();before=replacement.c.guide.digest([source])
        obj,report=replacement.replacement_copy(source,Vector(),(0,0,1))
        audit=replacement.c.author.shape_audit(obj)
        self.assertEqual(audit['nonManifoldEdges'],0)
        self.assertEqual(audit['zeroAreaFaces'],0)
        self.assertEqual(len(audit['components']),1)
        self.assertEqual(report['retainedUVMaterialErrors'],0)
        self.assertLess(report['capNormalDotAxis'],-.99)
        self.assertTrue(report['removedSourceTriangleIndices'])
        self.assertTrue(report['clippedSourceTriangleIndices'])
        self.assertEqual(before,replacement.c.guide.digest([source]))
        self.assertEqual(replacement.self_crossing_signatures(obj),set())
        self.assertFalse(obj['unityInputAllowed']);self.assertFalse(obj['originalSourceModified'])

    def test_remote_component_remains_exactly_in_place(self):
        source=self.body(remote=True)
        before={tuple(v.co) for v in source.data.vertices if v.co.x>.2}
        obj,report=replacement.replacement_copy(source,Vector(),(0,0,1))
        after={tuple(v.co) for v in obj.data.vertices if v.co.x>.2}
        self.assertEqual(before,after)
        self.assertEqual(len(replacement.c.author.shape_audit(obj)['components']),2)

    def test_invalid_axis_and_plane_vertex_are_rejected(self):
        source=self.body()
        with self.assertRaisesRegex(ValueError,'INVALID_REPLACEMENT_AXIS'):
            replacement.replacement_copy(source,Vector(),(0,0,0))
        with self.assertRaisesRegex(ValueError,'PLANE_VERTEX_AMBIGUOUS'):
            replacement.replacement_copy(source,Vector(),(0,0,1),height=.125)


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReplacementTests))
    if not r.wasSuccessful():raise RuntimeError('DISTAL_REPLACEMENT_TEST_FAILED')
