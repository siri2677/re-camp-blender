"""Verify topology/provenance and fail-closed handling of a rejected trial.

Passing these tests does NOT mean the pinned garment trial passes static QA.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import author_ch101_connected_shoulder as s
SOURCE=ARTIFACT=ART_ROOT=None


class ConnectedTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(s.c.base.sha(SOURCE),s.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.body=bpy.data.objects[s.panel.RESULT_OBJECT]
        self.source=bpy.data.objects[s.interface_module.RESULT_OBJECT]
        self.chart=bpy.data.objects[s.prior.RESULT_OBJECT]
        self.frame=s.panel.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])
        self.operation=json.loads((SOURCE.parent/'clipped-shoulder-report.json').read_text())['operation']
        self.parts=[o for o in self.originals if o.name.startswith('PAIR_STUDY_')]
        self.parts.append(bpy.data.objects[s.interface_module.prior.prior.prior.RESULT_OBJECT])

    def build(self):return s.build(self.source,self.body,self.chart,self.operation,self.frame)

    def test_parameter_fold_regression_and_exact_source_seam(self):
        with patch.object(s,'PARAMETER_OUTER_RADIUS',2):
            with self.assertRaisesRegex(ValueError,'HARMONIC_CHART_FOLDS'):
                s.chart_parameter(self.chart,self.operation,self.frame)
        targets,report=s.grid_targets(self.chart,self.operation,self.frame,self.source)
        self.assertEqual(len(targets),(s.ROWS+1)*s.N)
        self.assertGreater(report['parameterization']['minimumAbsoluteParameterTriangleArea'],1e-10)
        self.assertLess(report['maximumGridSeamTargetErrorMeters'],1e-6)
        mapping=s.prior.seam_map(self.chart,self.source,self.frame,self.operation['seamLoop'])
        for k,row in enumerate(mapping['samples']):
            self.assertLess((targets[k]-Vector(row['chartPoint'])).length,1e-6)
        self.chart.data.calc_loop_triangles()
        for point,record in zip(targets,report['gridProvenance']):
            ids=self.chart.data.loop_triangles[record['chartTriangle']].vertices
            expected=sum((self.chart.data.vertices[i].co*w for i,w in zip(ids,record['weights'])),Vector())
            self.assertLess((point-expected).length,1e-7)

    def test_shared_topology_budget_preservation_and_collision_rejection(self):
        digest=s.c.guide.digest(self.originals)
        signatures={o.name:s.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op,index=s.build(self.source,self.body,self.chart,self.operation,self.frame)
        self.assertEqual(len(obj.data.vertices),10368)
        self.assertEqual(op['sourceVerticesRetained'],2176)
        self.assertEqual(op['sourceVertexMoveMeters'],0)
        self.assertEqual(op['removedUpperWallFaces'],128)
        self.assertFalse(op['newPanelUVAuthored']);self.assertFalse(op['sourceTextureTransferred'])
        targets,_=s.grid_targets(self.chart,self.operation,self.frame,self.source)
        for layer in (0,1):
            for row in range(1,s.ROWS+1):
                for k in range(s.N):
                    self.assertLessEqual((obj.data.vertices[index[layer,row,k]].co-targets[row*s.N+k]).length,s.MAX_NEW_OFFSET+2e-7)
        qa=s.audit(obj,self.body,self.parts,op,index)
        self.assertFalse(qa['eligible'])
        self.assertEqual(qa['sharedSeamEdgeCountsInnerOuter'],[128,128])
        self.assertTrue(qa['seamManifold'])
        self.assertEqual(qa['components'],[10368]);self.assertEqual(qa['euler'],0)
        self.assertEqual(qa['nonManifoldEdges'],0)
        self.assertGreater(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertIn('NON_ADJACENT_SELF_INTERSECTION',qa['failedCriteria'])
        self.assertGreater(qa['constraintFailureCount'],0)
        self.assertEqual(digest,s.c.guide.digest(self.originals))
        self.assertEqual(signatures,{o.name:s.surface.repair.invariant_signature(o) for o in self.originals})
        for subject in (obj,bpy.context.scene):s.surface.require_locked(subject)
        # A forged zero in metadata cannot conceal an actual preserved-vertex move.
        obj.data.vertices[0].co.x+=.0001
        mutated=s.audit(obj,self.body,self.parts,op,index)
        self.assertGreater(mutated['sourceVertexMoveMeters'],.00009)
        self.assertIn('SOURCE_VERTEX_CHANGED',mutated['failedCriteria'])
        bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[bm.faces[-1]],context='FACES_ONLY');bm.to_mesh(obj.data);bm.free()
        broken=s.audit(obj,self.body,self.parts,op,index)
        self.assertFalse(broken['eligible']);self.assertGreater(broken['nonManifoldEdges'],0)

    def test_invalid_input_gate_and_duplicate_fail_closed(self):
        args=SimpleNamespace(source=SOURCE,output=SOURCE.parent/'unused-connected-test')
        with patch.object(s.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):s.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            s.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        original_sha=s.c.base.sha
        with patch.object(s.c.base,'sha',side_effect=lambda p: '0'*64 if p.name=='clipped-shoulder-report.json' else original_sha(p)):
            with self.assertRaisesRegex(ValueError,'SOURCE_REPORT_SHA256_MISMATCH'):s.run(args)
        with self.assertRaisesRegex(ValueError,'INVALID_CONNECTED_PANEL_FRAME'):
            s.build(self.source,self.body,self.chart,self.operation,(self.frame[0],Vector(),self.frame[2]))
        self.body['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):self.build()
        self.body['unityInputAllowed']=False
        duplicate=bpy.data.objects.new(s.RESULT_OBJECT,None);bpy.context.scene.collection.objects.link(duplicate)
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):self.build()

    def test_default_run_rejects_before_output(self):
        output=SOURCE.parent/'must-not-export-rejected-connected-trial'
        self.assertFalse(output.exists())
        args=SimpleNamespace(source=SOURCE,output=output,art_root=ART_ROOT,no_render=True,save_rejected_diagnostic=False)
        with self.assertRaisesRegex(ValueError,'CONNECTED_PANEL_QA_REJECTED'):s.run(args)
        self.assertFalse(output.exists())

    def test_saved_rejected_artifact_remains_hidden_locked_and_rejected(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'connected-shoulder-report.json').read_text())
        digest=s.c.guide.digest(self.originals);names=[o.name for o in self.originals]
        visible={o.name for o in self.originals if not o.hide_get()}
        self.assertEqual(s.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        self.assertEqual(digest,s.c.guide.digest([bpy.data.objects[n] for n in names]))
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()})
        obj=bpy.data.objects[s.RESULT_OBJECT]
        self.assertTrue(obj.hide_get());self.assertTrue(obj.hide_render)
        self.assertFalse(obj['staticQAEligible']);self.assertTrue(obj['diagnosticOnly'])
        self.assertFalse(report['qa']['eligible']);self.assertTrue(report['diagnosticOnly'])
        self.assertEqual(report['status'],'CONNECTED_PANEL_REJECTED_DIAGNOSTIC')
        self.assertFalse(report['adoptionAllowed']);self.assertIsNone(report['fullCharacterScore'])
        for subject in (obj,bpy.context.scene,report):s.surface.require_locked(subject)
        index={}
        for layer in (0,1):
            for row in range(s.ROWS+1):
                for k in range(s.N):
                    index[layer,row,k]=s.interface_module.idx(layer,s.interface_module.M-1,k) if row==0 else 2176+layer*s.ROWS*s.N+(row-1)*s.N+k
        body=bpy.data.objects[s.panel.RESULT_OBJECT]
        parts=[bpy.data.objects[o] for o in report['qa']['intersectionPairsByObject'] if o!=body.name]
        qa=s.audit(obj,body,parts,report['operation'],index)
        for field in ('eligible','nonAdjacentSelfIntersectionPairs','intersectionPairsByObject','sharedSeamEdgeCountsInnerOuter','failedCriteria'):
            self.assertEqual(qa[field],report['qa'][field])
        self.assertEqual(len(report['renders']),8)
        for row in report['renders']:self.assertEqual(s.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    p.add_argument('--art-root',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=a.source.resolve();ART_ROOT=a.art_root.resolve()
    ARTIFACT=a.artifact.resolve() if a.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConnectedTests))
    if not result.wasSuccessful():raise SystemExit(1)
