import sys
import unittest
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import inspect_ch101_attachment_surface as probe

class SurfaceTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_closed_mesh_is_not_called_grip_or_anatomy(self):
        bpy.ops.mesh.primitive_cube_add(); obj=bpy.context.object
        report=probe.inspect_region(obj,(0,0,0),2)
        self.assertEqual(report['inducedComponentSizes'],[8])
        self.assertEqual(report['originalNonManifoldEdges'],0)
        self.assertFalse(report['anatomicalRegionVerified'])

    def test_open_surface_detects_original_boundaries(self):
        bpy.ops.mesh.primitive_plane_add(); obj=bpy.context.object
        report=probe.inspect_region(obj,(0,0,0),2)
        self.assertEqual(report['originalBoundaryEdges'],4)

    def test_empty_region_rejected(self):
        bpy.ops.mesh.primitive_cube_add()
        with self.assertRaisesRegex(ValueError,'EMPTY_SURFACE_REGION'):
            probe.inspect_region(bpy.context.object,(100,0,0),.01)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SurfaceTests))
    if not result.wasSuccessful(): raise RuntimeError('SURFACE_TEST_FAILED')
