"""Pinned real-shoulder topology, texture transfer and locked-state regressions."""
import argparse
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import build_ch101_shoulder_domain as s
SOURCE=ARTIFACT=None


class ShoulderDomainTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT];self.interface=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
        self.parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]

    def test_real_offset_has_no_nonadjacent_self_crossings(self):
        obj,_=s.build(self.body,self.interface,self.frame)
        tree,_,faces=s.c.fit.bvh(obj)
        crossings={(a,b) for a,b in tree.overlap(tree) if a<b and not set(faces[a])&set(faces[b])}
        self.assertEqual(len(crossings),0,crossings)

    def test_actual_static_gap_and_wall(self):
        obj,_=s.build(self.body,self.interface,self.frame)
        qa=s.audit(obj,self.body,self.interface,self.parts)
        self.assertLess(qa['sampledWallRangeMeters'][1],.0012)
        self.assertTrue(qa['eligible'],qa)

    def test_domain_and_corner_uv_materials_are_preserved(self):
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];digest=s.c.guide.digest(originals)
        signature=s.surface.repair.invariant_signature(self.body)
        obj,op=s.build(self.body,self.interface,self.frame);domain=op['domain'];count=op['sourceVertexCount']
        self.assertEqual(len(domain['faces']),506);self.assertEqual(len(domain['boundaryLoops']),2)
        self.assertEqual(domain['euler'],0)
        self.assertEqual(op['maximumUVCornerError'],0)
        self.assertFalse(op['joinedToSleeveTopology'])
        self.assertEqual(list(obj.data.materials),list(self.body.data.materials))
        for f in list(obj.data.polygons)[:2*len(domain['faces'])]:
            source=self.body.data.polygons[domain['faces'][f.index%len(domain['faces'])]]
            self.assertEqual(f.material_index,source.material_index)
            source_loops={v:l for v,l in zip(source.vertices,source.loop_indices)}
            for uv in self.body.data.uv_layers:
                for j in f.loop_indices:
                    old_vertex=domain['vertices'][obj.data.loops[j].vertex_index%count]
                    self.assertLess((obj.data.uv_layers[uv.name].data[j].uv-uv.data[source_loops[old_vertex]].uv).length,1e-8)
        for attr in self.body.data.attributes:
            if attr.is_internal or attr.name=='position' or attr.domain!='POINT' or attr.data_type not in ('FLOAT','FLOAT_VECTOR','INT','BOOLEAN'):continue
            self.assertIn(attr.name,obj.data.attributes)
            key='vector' if attr.data_type=='FLOAT_VECTOR' else 'value'
            for j,i in enumerate(domain['vertices']):
                for layer in (0,1):self.assertEqual(getattr(obj.data.attributes[attr.name].data[j+layer*count],key),getattr(attr.data[i],key))
        self.assertEqual(digest,s.c.guide.digest(originals))
        self.assertEqual(signature,s.surface.repair.invariant_signature(self.body))

    def test_gate_hash_output_duplicate_and_frame_rejected(self):
        for subject in (self.body,self.interface):
            subject['unityInputAllowed']=True
            with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):s.build(self.body,self.interface,self.frame)
            subject['unityInputAllowed']=False
        center,axis,u=self.frame
        with self.assertRaisesRegex(ValueError,'INVALID_SHOULDER_FRAME'):s.face_domain(self.body,(center,axis*2,u))
        s.build(self.body,self.interface,self.frame)
        with self.assertRaisesRegex(ValueError,'SHOULDER_DOMAIN_ALREADY_EXISTS'):s.build(self.body,self.interface,self.frame)
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(SimpleNamespace(source=SOURCE,output=Path('artifacts/unused-shoulder-test')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))

    def test_open_shell_rejected(self):
        obj,_=s.build(self.body,self.interface,self.frame)
        bm=s.bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        s.bmesh.ops.delete(bm,geom=[bm.faces[0]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        self.assertFalse(s.audit(obj,self.body,self.interface,self.parts)['eligible'])

    def test_body_crossing_rejected(self):
        obj,_=s.build(self.body,self.interface,self.frame)
        tree=s.c.fit.bvh(self.body)[0];points=[obj.matrix_world@v.co for v in obj.data.vertices]
        nearest=[tree.find_nearest(p) for p in points];i=min(range(len(points)),key=lambda j:nearest[j][3])
        obj.location=(nearest[i][0]-points[i])*2;bpy.context.view_layer.update()
        qa=s.audit(obj,self.body,self.interface,self.parts)
        self.assertGreater(qa['intersectionPairsByObject'][self.body.name],0)
        self.assertFalse(qa['eligible'])

    def test_saved_scene_and_hashes(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        originals=[o for o in bpy.context.scene.objects if o.type=='MESH'];names=[o.name for o in originals];digest=s.c.guide.digest(originals)
        inv={o.name:s.surface.repair.invariant_signature(o) for o in originals}
        report=json.loads((ARTIFACT.parent/'shoulder-domain-report.json').read_text(encoding='utf-8'))
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertTrue(all(s.surface.repair.invariant_signature(bpy.data.objects[n])==inv[n] for n in names))
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),14)
        self.assertTrue(bpy.data.objects[s.RESULT_OBJECT].hide_get());self.assertFalse(report['adoptionAllowed'])
        for subject in (bpy.context.scene,report,bpy.data.objects[s.RESULT_OBJECT]):s.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore']);self.assertFalse(report['rigBound'])
        self.assertEqual(len(report['renders']),10)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ShoulderDomainTests))
    if not result.wasSuccessful():raise SystemExit(1)
