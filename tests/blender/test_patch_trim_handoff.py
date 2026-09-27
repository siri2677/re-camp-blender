"""Pinned real-asset and serialized shader-only trim handoff regressions."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_patch_trim_handoff as s
SOURCE=ARTIFACT=None


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.frame=s.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])[:2]

    def test_support_does_not_expand_existing_cloth_mask(self):
        for mask in (0,.5,.979,.98):
            self.assertEqual(s.weight(mask,.11),0)
        for z in (.185,.20,1):self.assertEqual(s.weight(1,z),0)
        self.assertEqual(s.weight(.995,.11),1)
        self.assertEqual(s.weight(1.0000091791152954,.11),1)
        self.assertAlmostEqual(s.weight(1,.1775),.5)
        for mask,z in ((-1,.11),(1.01,.11),(1,float('nan'))):
            with self.assertRaisesRegex(ValueError,'INVALID_HANDOFF_SAMPLE'):s.weight(mask,z)

    def test_real_asset_preservation_and_shader_contract(self):
        digest=s.c.guide.digest([self.source]);atlas=s.atlas_hash(self.source)
        obj,r=s.refine(self.source,*self.frame)
        s.verify_preservation(self.source,obj)
        self.assertEqual(s.c.guide.digest([self.source]),digest)
        self.assertEqual(s.atlas_hash(obj),atlas)
        self.assertEqual(r['geometryMovedVertices'],0)
        self.assertEqual(r['sharedBoundaryEdges'],41)
        self.assertEqual(r['trimCrossingBoundaryEdges'],4)
        self.assertGreaterEqual(r['minimumTrimBoundaryWeight'],1-1e-6)
        self.assertEqual(r['minimumBoundaryWeight'],0)
        self.assertFalse(r['wholeBoundaryContinuity'])
        self.assertIsNot(obj.data.materials[-1],self.source.data.materials[-1])
        nodes=obj.data.materials[-1].node_tree.nodes
        self.assertEqual(nodes['HandoffSameSeamHalfWidth'].inputs[1].default_value,r['planarHalfWidthMeters'])
        self.assertEqual(nodes['HandoffAtlasBlend'].inputs[1].links[0].from_node.type,'TEX_IMAGE')
        self.assertEqual(nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node.name,'HandoffAtlasBlend')
        ranges=[n for n in nodes if n.type=='MAP_RANGE']
        self.assertEqual(len(ranges),2)
        for node,pair in zip(ranges,[(s.MASK_LOW,s.MASK_HIGH),(s.FADE_LOW,s.FADE_HIGH)]):
            self.assertEqual(node.interpolation_type,'SMOOTHSTEP');self.assertTrue(node.clamp)
            for name,v in zip(('From Min','From Max'),pair):self.assertAlmostEqual(node.inputs[name].default_value,v,places=6)
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(s.seam.assess(obj,parts,r)['eligible'])

    def test_mutation_guards(self):
        obj,_=s.refine(self.source,*self.frame)
        obj.data.vertices[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'GEOMETRY_UV_WEIGHTS'):s.verify_preservation(self.source,obj)
        obj.data.vertices[0].co=self.source.data.vertices[0].co
        uv=s.surface.UV_NAME
        obj.data.uv_layers[uv].data[0].uv.x+=.1
        with self.assertRaisesRegex(ValueError,'HANDOFF_UV_CHANGED'):s.verify_preservation(self.source,obj)
        obj.data.uv_layers[uv].data[0].uv=self.source.data.uv_layers[uv].data[0].uv
        mask=s.seam.trim.upper.MASK
        obj.data.attributes[mask].data[0].value+=.1
        with self.assertRaisesRegex(ValueError,'EXISTING_MASK'):s.verify_preservation(self.source,obj)

    def test_failed_guard_cleanup_and_reapply_rejection(self):
        names=set(bpy.data.objects.keys());materials=set(bpy.data.materials.keys())
        with patch.object(s,'verify_preservation',side_effect=ValueError('TEST_GUARD')):
            with self.assertRaisesRegex(ValueError,'TEST_GUARD'):s.refine(self.source,*self.frame)
        self.assertEqual(names,set(bpy.data.objects.keys()));self.assertEqual(materials,set(bpy.data.materials.keys()))
        obj,_=s.refine(self.source,*self.frame)
        with self.assertRaisesRegex(ValueError,'ALREADY_APPLIED'):s.refine(obj,*self.frame)

    def test_input_gate_frame_and_path_rejection(self):
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        with self.assertRaisesRegex(ValueError,'INVALID_HANDOFF_FRAME'):s.refine(self.source,self.frame[0],Vector())
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_and_render_hashes(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        r=json.loads((ARTIFACT.parent/'patch-trim-handoff-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),r['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        source=bpy.data.objects[s.prior.RESULT_OBJECT];obj=bpy.data.objects[s.RESULT_OBJECT]
        s.verify_preservation(source,obj)
        self.assertTrue(source.hide_get());self.assertFalse(obj.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        for subject in (obj,bpy.context.scene,r):s.surface.require_locked(subject)
        self.assertIsNone(r['fullCharacterScore']);self.assertFalse(r['rigBound'])
        self.assertEqual(len(r['renders']),8)
        for row in r['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HandoffTests))
    if not result.wasSuccessful():raise SystemExit(1)
