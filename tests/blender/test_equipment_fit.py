import importlib.util
import unittest
import tempfile
from pathlib import Path
from mathutils import Vector
import bpy

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('fit',ROOT/'scripts/blender/review_ch101_equipment_fit.py')
fit=importlib.util.module_from_spec(spec); spec.loader.exec_module(fit)


class FitTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_anchor_transform_is_exact(self):
        obj=bpy.data.objects.new('test',None); bpy.context.scene.collection.objects.link(obj)
        matrix=fit.pose_at_anchor(obj,(0,0,.82),(-.36,0,.85),(.4,0,.8))
        self.assertLess((matrix@Vector((0,0,.82))-Vector((-.36,0,.85))).length,1e-6)

    def test_surface_overlap_detects_crossing(self):
        bpy.ops.mesh.primitive_cube_add(); body=bpy.context.object
        bpy.ops.mesh.primitive_cube_add(location=(1.5,0,0)); equipment=bpy.context.object
        bpy.context.view_layer.update()
        audit=fit.overlap_report(body,[equipment],(100,0,0))[0]
        self.assertGreater(audit['awayFromHandCrossingTriangles'],0)

    def test_loaded_collection_can_receive_review_properties(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'hardware.blend'
            collection=bpy.data.collections.new('MODEL_EQUIPMENT')
            bpy.context.scene.collection.children.link(collection)
            for name in ['CH101_SignalRibbon_SINGLE','Socket_Ribbon_L','Socket_Ribbon_R','CH101_Saber']:
                collection.objects.link(bpy.data.objects.new(name,None))
            bpy.data.libraries.write(str(path),{collection})
            bpy.ops.wm.read_factory_settings(use_empty=True)
            with bpy.data.libraries.load(str(path),link=False) as (available,loaded):
                loaded.collections=['MODEL_EQUIPMENT']
            collection=loaded.collections[0]; bpy.context.scene.collection.children.link(collection)
            fit.tag_hardware(collection)
            self.assertTrue(all(o.get('fitStatus') for o in list(collection.all_objects)))

    def test_waist_roi_does_not_hit_outer_arm_first(self):
        bpy.ops.mesh.primitive_cube_add(location=(0,0,.84),scale=(.15,.10,.84)); body=bpy.context.object
        bpy.ops.mesh.primitive_cube_add(location=(.33,0,1.05),scale=(.04,.04,.2)); arm=bpy.context.object
        bpy.context.view_layer.update()
        # Triangulated torso side centers need to lie in the target waist band.
        bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active=body
        bpy.ops.object.join()
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=12); bpy.ops.object.mode_set(mode='OBJECT')
        tree,points,faces=fit.bvh(body)
        hit=fit.waist_surface(tree,points,faces)
        self.assertLess(hit['position'][0],.20)

    def test_disjoint_surfaces_report_zero_crossing(self):
        bpy.ops.mesh.primitive_cube_add(); body=bpy.context.object
        bpy.ops.mesh.primitive_cube_add(location=(4,0,0)); item=bpy.context.object
        bpy.context.view_layer.update()
        self.assertEqual(fit.overlap_report(body,[item],(0,0,0))[0]['overlapTrianglePairCount'],0)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FitTests))
    if not result.wasSuccessful(): raise RuntimeError('FIT_TEST_FAILED')
