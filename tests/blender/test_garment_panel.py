"""Pinned panel-layout scope, preservation, shader semantics and saved review."""
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
import design_ch101_garment_panel as s
SOURCE=ARTIFACT=None


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.frame=s.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_explicit_panel_classes_and_compact_domain(self):
        self.assertEqual(s.classify(.002,0),'WHITE_OVERSLEEVE')
        self.assertEqual(s.classify(0,0),'GRAPHITE_HEM_BINDING')
        self.assertEqual(s.classify(-.01,0),'GOLD_UNDERSLEEVE_TRIM')
        self.assertEqual(s.classify(-.01,.02),'GRAPHITE_UNDERSLEEVE')
        self.assertEqual(s.classify(.0015,0),'GRAPHITE_HEM_BINDING')
        self.assertEqual(s.classify(-.0015,0),'GOLD_UNDERSLEEVE_TRIM')
        for z,r in ((.14,.03),(.29,.03),(.2,.07)):
            self.assertEqual(s.influence(z,r),0)
        self.assertEqual(s.influence(.245,.04),1)
        for z,r in ((float('nan'),.04),(.2,-1)):
            with self.assertRaisesRegex(ValueError,'INVALID_PANEL_SAMPLE'):s.influence(z,r)

    def test_connected_bounded_domain_and_preserved_originals(self):
        digest=s.c.guide.digest([self.source]);atlas=s.prior.atlas_hash(self.source)
        obj,r=s.design(self.source,*self.frame)
        s.verify(self.source,obj,r['faceIndices'],r['materialMapping'])
        self.assertEqual(s.c.guide.digest([self.source]),digest)
        self.assertEqual(s.prior.atlas_hash(self.source),atlas)
        self.assertEqual(r['geometryMovedVertices'],0)
        self.assertTrue(r['connectedFaceRegion']);self.assertFalse(r['exactReferenceBoundaryRecovered'])
        self.assertEqual(set(r['materialMapping']),{0,1,2,10})
        for slot in r['materialMapping'].values():
            nodes=obj.data.materials[slot].node_tree.nodes
            self.assertEqual(nodes['PanelBoundedShader'].type,'MIX_SHADER')
            self.assertEqual(nodes['PanelAuthoredCloth'].type,'BSDF_PRINCIPLED')
            for got,want in zip(nodes['PanelWhiteOversleeve'].inputs[2].default_value[:3],s.surface.linear_color('F5F4EF')):self.assertAlmostEqual(got,want,places=6)
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(s.seam.assess(obj,parts,r)['eligible'])

    def test_mutation_rejection(self):
        obj,r=s.design(self.source,*self.frame)
        args=(self.source,obj,r['faceIndices'],r['materialMapping'])
        obj.data.vertices[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'GEOMETRY_UV_WEIGHTS'):s.verify(*args)
        obj.data.vertices[0].co=self.source.data.vertices[0].co
        locked=next(p for p in obj.data.polygons if p.index not in set(r['faceIndices']))
        original=locked.material_index;locked.material_index=11
        with self.assertRaisesRegex(ValueError,'FACE_ASSIGNMENT'):s.verify(*args)
        locked.material_index=original
        name=s.seam.trim.upper.MASK;obj.data.attributes[name].data[0].value+=.1
        with self.assertRaisesRegex(ValueError,'OLD_FIELDS'):s.verify(*args)

    def test_failure_cleanup_and_reapply_rejection(self):
        objects=set(bpy.data.objects.keys());materials=set(bpy.data.materials.keys())
        with patch.object(s,'verify',side_effect=ValueError('TEST_GUARD')):
            with self.assertRaisesRegex(ValueError,'TEST_GUARD'):s.design(self.source,*self.frame)
        self.assertEqual(objects,set(bpy.data.objects.keys()));self.assertEqual(materials,set(bpy.data.materials.keys()))
        obj,_=s.design(self.source,*self.frame)
        with self.assertRaisesRegex(ValueError,'ALREADY_APPLIED'):s.design(obj,*self.frame)

    def test_fail_closed_input_frame_gate_and_path(self):
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        with self.assertRaisesRegex(ValueError,'INVALID_PANEL_FRAME'):s.design(self.source,self.frame[0],Vector(),self.frame[2])
        with self.assertRaisesRegex(ValueError,'PANEL_SUPPORT_OUTSIDE'):s.design(self.source,self.frame[0]+Vector((0,0,.6)),*self.frame[1:])
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_and_render_hashes(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'garment-panel-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        source=bpy.data.objects[s.prior.RESULT_OBJECT];obj=bpy.data.objects[s.RESULT_OBJECT];r=report['operation']
        s.verify(source,obj,r['faceIndices'],{int(k):v for k,v in r['materialMapping'].items()})
        _,dz,rr,hem,faces,slots=s.values(source,*self.frame)
        self.assertEqual(faces,r['faceIndices'])
        for field,vals in ((s.Z,dz),(s.R,rr),(s.HEM,hem)):
            for item,v in zip(obj.data.attributes[field].data,vals):self.assertAlmostEqual(item.value,v,places=6)
        self.assertTrue(source.hide_get());self.assertFalse(obj.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        for subject in (obj,bpy.context.scene,report):s.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore']);self.assertFalse(report['rigBound'])
        self.assertEqual(len(report['renders']),9)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PanelTests))
    if not result.wasSuccessful():raise SystemExit(1)
