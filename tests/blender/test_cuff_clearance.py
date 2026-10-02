"""A changing hand profile must clear the entire cuff, not just its end rings."""
import math
import sys
import unittest
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_cuff_interface_study as cuff

def ring(radius,z,n=32):
    return dict(centroid=[0,0,z],points=[(radius*math.cos(i*2*math.pi/n),radius*math.sin(i*2*math.pi/n),z) for i in range(n)])

def bulging_hand(rectangular=False):
    profiles=[ring(.014,.002),ring(.020,-.0074),ring(.014,-.018)]
    if rectangular:
        profiles=[dict(points=[(x*r,y*r*.25,z) for x,y in [(1,1),(-1,1),(-1,-1),(1,-1)]]) for r,z in [(.014,.002),(.020,-.0074),(.014,-.018)]]
    verts=[p for r in profiles for p in r['points']]; faces=[]; n=4 if rectangular else 32
    for k in range(2):
        for j in range(n):faces.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
    faces.extend([tuple(reversed(range(n))),tuple(range(2*n,3*n))])
    mesh=bpy.data.meshes.new('Bulging_hand_fixture');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new('Bulging_hand_fixture',mesh);bpy.context.scene.collection.objects.link(obj)
    return obj

class ClearanceTests(unittest.TestCase):
    def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_bulging_hand_is_clear_between_end_sections(self):
        hand=bulging_hand();axis=Vector((0,0,1));u=Vector((1,0,0))
        before=cuff.guide.digest([hand])
        distal=cuff.pair.closed_section(hand,Vector((0,0,-.015)),axis)[0]
        obj=cuff.shell(bpy.context.scene.collection,ring(.020,0),distal,axis,u,hand=hand)
        overlaps=cuff.fit.overlap_report(hand,[obj],Vector())[0]
        self.assertEqual(overlaps['uniqueEquipmentTrianglesCrossing'],0)
        self.assertEqual(cuff.wrist.self_surface_pairs(obj),0)
        self.assertEqual(cuff.author.shape_audit(obj)['nonManifoldEdges'],0)
        self.assertEqual(cuff.guide.digest([hand]),before)
        self.assertEqual(len(obj.data.vertices)-len(obj.data.edges)+len(obj.data.polygons),0)
    def test_thin_angular_hand_profile_is_not_cut_by_radial_chords(self):
        hand=bulging_hand(rectangular=True);axis=Vector((0,0,1));u=Vector((1,0,0))
        distal=cuff.pair.closed_section(hand,Vector((0,0,-.015)),axis)[0]
        obj=cuff.shell(bpy.context.scene.collection,ring(.023,0),distal,axis,u,hand=hand)
        self.assertEqual(cuff.fit.overlap_report(hand,[obj],Vector())[0]['uniqueEquipmentTrianglesCrossing'],0)
        self.assertEqual(cuff.wrist.self_surface_pairs(obj),0)
        self.assertFalse(obj['unityInputAllowed'])
        self.assertFalse(obj['productionPromotionAllowed'])
        self.assertLessEqual(obj['maxOutwardCorrectionMeters'],.006)
    def test_excessive_middle_profile_correction_is_rejected(self):
        hand=bulging_hand();axis=Vector((0,0,1));u=Vector((1,0,0))
        for v in list(hand.data.vertices)[32:64]:v.co.x*=3;v.co.y*=3
        hand.data.update()
        distal=cuff.pair.closed_section(hand,Vector((0,0,-.015)),axis)[0]
        with self.assertRaisesRegex(ValueError,'EXCEEDS_SIX_MM_BOUND'):
            cuff.shell(bpy.context.scene.collection,ring(.02,0),distal,axis,u,hand=hand)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClearanceTests))
    if not result.wasSuccessful():raise RuntimeError('CUFF_CLEARANCE_TEST_FAILED')
