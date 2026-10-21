"""Domain-conforming real disk edits, original preservation and strict gates."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import rebuild_ch101_underarm_disks as m
SOURCE=LAYOUT_REPORT=ARTIFACT=None


class UnderarmTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE),m.SOURCE_SHA)
        self.assertEqual(m.c.base.sha(LAYOUT_REPORT),m.LAYOUT_SHA)
        self.cap_report=json.loads((SOURCE.parent/'cap-replacement-report.json').read_text())
        self.layout_report=json.loads(LAYOUT_REPORT.read_text())
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[m.cap.RESULT_OBJECT]
        self.originals=[o for o in bpy.context.scene.objects if o.type=='MESH']

    def restored(self):
        if ARTIFACT is None:
            self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'underarm-disks-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        return bpy.data.objects[m.RESULT_OBJECT],bpy.data.objects[m.cap.RESULT_OBJECT],report

    def audit(self,obj,source,op,require_selection=True):
        return m.audit(obj,source,self.cap_report,self.layout_report,op,require_selection)

    def test_actual_partition_and_replacements_preserve_all_originals(self):
        digest=m.c.guide.digest(self.originals)
        signatures={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        obj,op=m.build(self.source,self.cap_report,self.layout_report)
        qa=self.audit(obj,self.source,op)
        self.assertTrue(qa['eligible'])
        self.assertEqual((qa['vertices'],qa['triangles']),(2699,5040))
        self.assertEqual((qa['patchCount'],qa['removedTriangles'],qa['replacementTriangles']),(5,46,36))
        self.assertEqual([r['seedVertex'] for r in op['disks']],[900,757,1014,1030,914])
        self.assertEqual(qa['preservedLayoutEdges'],907)
        self.assertEqual(qa['maximumRetainedVertexMoveMeters'],0)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertTrue(all(r['after']['edgesAbove55Degrees']==0 for r in qa['patches']))
        self.assertLessEqual(max(qa['maximumForwardOriginalChartSampleErrorMeters'],qa['maximumReverseOriginalChartSampleErrorMeters']),.0015)
        self.assertTrue(qa['previousCapPatchPreserved'])
        self.assertFalse(qa['fullUnderarmRebuilt'])
        self.assertFalse(qa['garmentStaticQA'])
        self.assertFalse(qa['deformationValidated'])
        self.assertEqual(digest,m.c.guide.digest(self.originals))
        self.assertEqual(signatures,{o.name:m.surface.repair.invariant_signature(o) for o in self.originals})
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):
            m.build(self.source,self.cap_report,self.layout_report)

    def test_seed_provenance_and_policy_guards(self):
        ctx=m.context(self.source,self.cap_report,self.layout_report)
        self.assertEqual(len(ctx['seeds']),45)
        self.assertEqual(len(set(ctx['seeds'])&ctx['protectedVertices']),2)
        row=m.disk(self.source,ctx,900)
        self.assertEqual(row['domain'],7)
        self.assertEqual(len(row['boundaryVertices']),14)
        bad=copy.deepcopy(self.cap_report)
        bad['operation']['keptSourceVertices'][0]=bad['operation']['keptSourceVertices'][1]
        with self.assertRaisesRegex(ValueError,'UPSTREAM_VERTEX_MAP_CHANGED'):
            m.context(self.source,bad,self.layout_report)
        bad=copy.deepcopy(self.layout_report)
        next(g for g in bad['design']['majorFoldGroups'] if g['id']==193)['sourceEdges'].pop()
        with self.assertRaisesRegex(ValueError,'UNDERARM_POLICY_CHANGED'):
            m.context(self.source,self.cap_report,bad)

    def test_protected_vertices_noop_and_duplicate_disks_rejected(self):
        ctx=m.context(self.source,self.cap_report,self.layout_report)
        protected=min(set(ctx['seeds'])&ctx['protectedVertices'])
        with self.assertRaisesRegex(ValueError,'PROTECTED_LAYOUT_VERTEX'):
            m.disk(self.source,ctx,protected)
        with self.assertRaisesRegex(ValueError,'NO_REPLACEMENT_DISKS'):
            m.compose(self.source,ctx,[])
        row=m.disk(self.source,ctx,900)
        with self.assertRaisesRegex(ValueError,'DISK_NEIGHBORHOODS_OVERLAP'):
            m.compose(self.source,ctx,[row,row])

    def test_good_local_bending_is_not_cumulative_source_approval(self):
        ctx=m.context(self.source,self.cap_report,self.layout_report)
        row=m.disk(self.source,ctx,713)
        obj,op=m.compose(self.source,ctx,[row])
        qa=self.audit(obj,self.source,op,False)
        self.assertTrue(all(r['eligible'] for r in qa['patches']))
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'],0)
        self.assertGreater(qa['maximumForwardOriginalChartSampleErrorMeters'],.0015)
        self.assertFalse(qa['eligible'])

    def test_disk_and_face_map_provenance_tampering_rejected(self):
        obj,source,report=self.restored()
        bad=copy.deepcopy(report['operation'])
        bad['disks'][0]['replacementSourceTriangles'][0][0]=0
        with self.assertRaisesRegex(ValueError,'DISK_PROVENANCE_CHANGED'):
            self.audit(obj,source,bad)
        bad=copy.deepcopy(report['operation'])
        bad['keptSourceVertices'].pop()
        with self.assertRaisesRegex(ValueError,'UNDERARM_SOURCE_MAP_CHANGED'):
            self.audit(obj,source,bad)
        bad=copy.deepcopy(report['operation'])
        bad['patchFaceIndices'][0].pop()
        with self.assertRaisesRegex(ValueError,'UNDERARM_FACE_MAP_CHANGED'):
            self.audit(obj,source,bad)

    def test_selection_trace_and_nonfinite_decision_tampering_rejected(self):
        obj,source,report=self.restored()
        bad=copy.deepcopy(report['operation'])
        bad.pop('selectionDecisions')
        with self.assertRaisesRegex(ValueError,'MISSING_SELECTION_RECORD'):
            self.audit(obj,source,bad)
        bad=copy.deepcopy(report['operation'])
        next(r for r in bad['selectionDecisions'] if r['status']=='ACCEPTED')['status']='REJECTED_GLOBAL_QA'
        with self.assertRaisesRegex(ValueError,'SELECTION_RECORD_CHANGED'):
            self.audit(obj,source,bad)
        bad=copy.deepcopy(report['operation'])
        next(r for r in bad['selectionDecisions'] if r['status']=='ACCEPTED')['maximumForwardOriginalChartSampleErrorMeters']=float('nan')
        with self.assertRaisesRegex(ValueError,'ACCEPTED_DECISION_EXCEEDS_QA'):
            self.audit(obj,source,bad)

    def test_changed_retained_point_is_not_eligible(self):
        obj,source,report=self.restored()
        obj.data.vertices[0].co.x+=.004
        obj.data.update()
        self.assertFalse(self.audit(obj,source,report['operation'])['eligible'])
        obj,source,report=self.restored()
        obj.data.vertices[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'NONFINITE_UNDERARM_VERTEX'):
            self.audit(obj,source,report['operation'])

    def test_outside_region_change_rejected(self):
        obj,source,report=self.restored()
        obj.data.polygons[0].material_index=(obj.data.polygons[0].material_index+1)%16
        with self.assertRaisesRegex(ValueError,'UNDERARM_OUTSIDE_TOPOLOGY_OR_REGION_CHANGED'):
            self.audit(obj,source,report['operation'])

    def test_editable_guide_position_tampering_rejected(self):
        _,source,report=self.restored()
        self.assertEqual(m.audit_guides(source,report['operation'])['guideCount'],5)
        name=m.GUIDE_PREFIX+str(report['operation']['disks'][0]['seedVertex'])
        bpy.data.objects[name].data.splines[0].points[0].co.x+=.001
        with self.assertRaisesRegex(ValueError,'UNDERARM_GUIDE_POSITION_CHANGED'):
            m.audit_guides(source,report['operation'])
        _,source,report=self.restored()
        bpy.data.objects[name].data.splines[0].points[0].co.x=float('nan')
        with self.assertRaisesRegex(ValueError,'UNDERARM_GUIDE_POSITION_CHANGED'):
            m.audit_guides(source,report['operation'])

    def test_source_hash_gates_and_existing_output_guards(self):
        args=SimpleNamespace(source=SOURCE,layout_report=LAYOUT_REPORT,output=SOURCE.parent)
        with patch.object(m.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                m.run(args)
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            m.run(args)
        self.source['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            m.context(self.source,self.cap_report,self.layout_report)

    def test_preceding_cap_and_inherited_layout_guides_remain_valid(self):
        _,source,_=self.restored()
        old_layout=bpy.data.objects[m.layout.RESULT_OBJECT]
        self.assertEqual(m.cap.audit(source,old_layout,self.layout_report,self.cap_report['operation']),self.cap_report['qa'])
        original_edgeflow=bpy.data.objects[m.edgeflow.RESULT_OBJECT]
        self.assertEqual(m.layout.audit_guides(original_edgeflow,old_layout,self.layout_report['design'])['guideCount'],12)

    def test_saved_artifact_reopens_with_originals_visibility_and_locks(self):
        names=[o.name for o in self.originals]
        digest=m.c.guide.digest(self.originals)
        signatures={o.name:m.surface.repair.invariant_signature(o) for o in self.originals}
        visible={o.name for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()}
        obj,source,report=self.restored()
        restored=[bpy.data.objects[n] for n in names]
        self.assertEqual(digest,m.c.guide.digest(restored))
        self.assertEqual(signatures,{o.name:m.surface.repair.invariant_signature(o) for o in restored})
        self.assertEqual(visible,{o.name for o in bpy.context.scene.objects if o.type in ('MESH','CURVE') and not o.hide_get()})
        self.assertTrue(obj.hide_get() and obj.hide_render)
        guides=[o for o in bpy.context.scene.objects if o.name.startswith(m.GUIDE_PREFIX)]
        self.assertEqual(len(guides),5)
        self.assertTrue(all(o.hide_get() and o.hide_render for o in guides))
        self.assertEqual(m.audit_guides(source,report['operation']),report['guideQA'])
        self.assertIsNone(bpy.data.objects.get('UnderarmWire_RENDER_ONLY'))
        self.assertIsNone(bpy.data.objects.get('FoldReviewGhost_RENDER_ONLY'))
        self.assertEqual(self.audit(obj,source,report['operation']),report['qa'])
        for subject in (obj,bpy.context.scene,report,*guides):
            m.surface.require_locked(subject)
        for key in ('adoptionAllowed','completeShoulderPanel','rigBound'):
            self.assertFalse(report[key])
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),16)
        for row in report['renders']:
            self.assertEqual(m.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--layout-report',type=Path,required=True)
    p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    SOURCE=args.source.resolve()
    LAYOUT_REPORT=args.layout_report.resolve()
    ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnderarmTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
