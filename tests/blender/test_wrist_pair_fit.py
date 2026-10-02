import sys
import unittest
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import fit_ch101_hand_saber_pair as pair

class PairTests(unittest.TestCase):
    def setUp(self): bpy.ops.wm.read_factory_settings(use_empty=True)
    def test_closed_cube_section_centroid(self):
        bpy.ops.mesh.primitive_cube_add(size=.06)
        loops=pair.closed_section(bpy.context.object,(0,0,.005),(0,0,1))
        self.assertEqual(len(loops),1); self.assertTrue(loops[0]['closed'])
        self.assertLess((Vector(loops[0]['centroid'])-Vector((0,0,.005))).length,1e-6)
        self.assertFalse(loops[0]['verifiedAnatomicalSeam'])
    def test_open_plane_cannot_be_promoted_to_closed_loop(self):
        bpy.ops.mesh.primitive_plane_add(size=.06)
        with self.assertRaisesRegex(ValueError,'SECTION_NOT_CLOSED'):
            pair.closed_section(bpy.context.object,(.005,0,0),(1,0,0))
    def test_pair_mapping_aligns_without_changing_relative_pose(self):
        hand=bpy.data.objects.new('hand',None); weapon=bpy.data.objects.new('weapon',None)
        bpy.context.scene.collection.objects.link(hand); bpy.context.scene.collection.objects.link(weapon)
        hand.location=(.1,.2,.3); weapon.location=(.1,.3,.4); bpy.context.view_layer.update()
        old=hand.matrix_world.inverted()@weapon.matrix_world
        delta=pair.pair_transform(hand,(.4,.5,.6),(0,1,0))
        collection=bpy.data.collections.new('test'); bpy.context.scene.collection.children.link(collection)
        h,w,_=pair.clone_pair(hand,weapon,delta,collection)
        actual=h.matrix_world.inverted()@w.matrix_world
        self.assertLess(max(abs(old[i][j]-actual[i][j]) for i in range(4) for j in range(4)),1e-6)
        self.assertLess((h.matrix_world.translation-Vector((.4,.5,.6))).length,1e-6)
        self.assertLess((h.matrix_world.to_3x3()@Vector((0,0,-1))-Vector((0,1,0))).length,1e-6)
        self.assertFalse(h['sourceReplacementAllowed'])
    def test_clone_keeps_descendant_world_transform_and_source_unchanged(self):
        objs=[]
        for name in ('hand','saber','detail','socket'):
            obj=bpy.data.objects.new(name,None); bpy.context.scene.collection.objects.link(obj); objs.append(obj)
        h,s,d,k=objs; d.parent=s; k.parent=d
        s.location=(.2,.1,0); d.location=(0,.1,.2); k.location=(.01,.02,.03)
        bpy.context.view_layer.update(); before={o:o.matrix_world.copy() for o in objs}
        delta=pair.pair_transform(h,(1,2,3),(0,1,0))
        collection=bpy.data.collections.new('clones'); bpy.context.scene.collection.children.link(collection)
        ch,cs,parts=pair.clone_pair(h,s,delta,collection)
        for old in objs:
            clone=bpy.data.objects['PAIR_STUDY_'+old.name]
            expected=delta@before[old]
            self.assertLess(max(abs(expected[i][j]-clone.matrix_world[i][j]) for i in range(4) for j in range(4)),1e-6)
            self.assertEqual(old.matrix_world,before[old])
        self.assertEqual(bpy.data.objects['PAIR_STUDY_socket'].parent,bpy.data.objects['PAIR_STUDY_detail'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PairTests))
    if not result.wasSuccessful(): raise RuntimeError('PAIR_TEST_FAILED')
