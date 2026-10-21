"""Real chart partition, preserved originals and explicit non-approval gates."""
import argparse
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/blender'))
import design_ch101_shoulder_deformation_layout as m
SOURCE = ARTIFACT = None


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(m.c.base.sha(SOURCE), m.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[m.prior.RESULT_OBJECT]
        self.originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']

    def restored(self):
        if ARTIFACT is None:
            self.skipTest('Saved artifact required')
        report = json.loads((ARTIFACT.parent / 'deformation-layout-report.json').read_text())
        self.assertEqual(m.c.base.sha(ARTIFACT), report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        return bpy.data.objects[m.prior.RESULT_OBJECT], bpy.data.objects[m.RESULT_OBJECT], report

    def audit(self, source, obj, report):
        return m.audit(source, obj, report['operation'], report['design'],
                       report['harmonicField'], report['qa']['harmonicResidual'])

    def test_actual_chart_build_preserves_all_originals(self):
        digest = m.c.guide.digest(self.originals)
        inv = {o.name: m.surface.repair.invariant_signature(o) for o in self.originals}
        values, lower, outer, features, residual = m.field(self.source)
        obj, op = m.split_chart(self.source, values)
        design = m.layout(self.source, obj, op, values, lower, outer, features)
        qa = m.audit(self.source, obj, op, design, values, residual)
        self.assertTrue(qa['eligible'])
        self.assertEqual(qa['courseSharedEdgeCounts'], [128, 144, 177])
        self.assertEqual((qa['longitudinalRouteCount'], qa['courseBranchCrossings']), (4, 12))
        self.assertEqual(qa['classifiedMajorFoldEdges'], 64)
        self.assertEqual(qa['majorFoldGroupCount'], 5)
        self.assertTrue(all(d['components'] == 1 and d['faces'] > 0 for d in qa['domainCounts']))
        self.assertLess(qa['maximumSourceEdgeErrorMeters'], 1e-6)
        self.assertLess(qa['maximumSourceTriangleRelativeAreaError'], 1e-3)
        self.assertEqual(qa['nonAdjacentSelfIntersectionPairs'], 0)
        self.assertFalse(qa['geometryShapeChanged'])
        self.assertFalse(qa['majorFoldShapeRedesigned'])
        self.assertFalse(qa['garmentStaticQA'])
        self.assertFalse(qa['deformationValidated'])
        self.assertEqual(digest, m.c.guide.digest(self.originals))
        self.assertEqual(inv, {o.name: m.surface.repair.invariant_signature(o) for o in self.originals})

    def test_harmonic_field_uses_original_boundary_roles(self):
        values, lower, outer, _, residual = m.field(self.source)
        self.assertEqual((len(lower), len(outer)), (76, 282))
        self.assertTrue(all(values[i] == 0 for i in lower))
        self.assertTrue(all(values[i] == 1 for i in outer))
        self.assertTrue(all(0 <= x <= 1 for x in values))
        self.assertLess(residual, 1e-10)

    def test_invalid_routes_are_rejected(self):
        self.assertEqual(m.ordered_path([(0, 1), (1, 2)]), [0, 1, 2])
        self.assertEqual(m.ordered_path([(0, 1), (1, 2), (0, 2)], cyclic=True), [0, 1, 2])
        with self.assertRaisesRegex(ValueError, 'NOT_SIMPLE'):
            m.ordered_path([(0, 1), (1, 2), (1, 3)])
        with self.assertRaisesRegex(ValueError, 'DISCONNECTED'):
            m.ordered_path([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)], cyclic=True)

    def test_field_and_boundary_record_tampering_rejected(self):
        source, obj, report = self.restored()
        bad = copy.deepcopy(report)
        bad['harmonicField'][100] += .01
        with self.assertRaisesRegex(ValueError, 'HARMONIC_FIELD_RECORD_CHANGED'):
            self.audit(source, obj, bad)
        bad = copy.deepcopy(report)
        bad['harmonicField'][100] = float('nan')
        with self.assertRaisesRegex(ValueError, 'HARMONIC_FIELD_RECORD_CHANGED'):
            self.audit(source, obj, bad)
        bad = copy.deepcopy(report)
        bad['design']['lowerLoop'], bad['design']['provisionalOuterLoop'] = bad['design']['provisionalOuterLoop'], bad['design']['lowerLoop']
        with self.assertRaisesRegex(ValueError, 'BOUNDARY_ROLE_CHANGED'):
            self.audit(source, obj, bad)

    def test_policy_and_course_crossing_tampering_rejected(self):
        source, obj, report = self.restored()
        bad = copy.deepcopy(report)
        bad['design']['majorFoldGroups'][1]['policy'] = 'APPROVED_FINAL_FOLD'
        with self.assertRaisesRegex(ValueError, 'LAYOUT_RECORD_CHANGED'):
            self.audit(source, obj, bad)
        bad = copy.deepcopy(report)
        bad['design']['transverseCourses'][0]['branchCrossings'].pop()
        with self.assertRaisesRegex(ValueError, 'LAYOUT_RECORD_CHANGED'):
            self.audit(source, obj, bad)

    def test_face_domain_and_point_provenance_tampering_rejected(self):
        source, obj, report = self.restored()
        obj.data.polygons[0].material_index = (obj.data.polygons[0].material_index + 1) % 16
        with self.assertRaisesRegex(ValueError, 'DOMAIN_REGION_CHANGED'):
            self.audit(source, obj, report)
        source, obj, report = self.restored()
        course_vertex = report['design']['transverseCourses'][0]['chartVertices'][0]
        obj.data.vertices[course_vertex].co.x += .005
        obj.data.update()
        with self.assertRaisesRegex(ValueError, 'LAYOUT_RECORD_CHANGED'):
            self.audit(source, obj, report)
        source, obj, report = self.restored()
        bad = copy.deepcopy(report)
        bad['operation']['vertexProvenance'][0]['edgeT'] = 2.
        with self.assertRaisesRegex(ValueError, 'INVALID_SOURCE_EDGE_T'):
            self.audit(source, obj, bad)

    def test_hash_and_gate_guards(self):
        args = SimpleNamespace(source=SOURCE, output=SOURCE.parent / 'unused-layout-test')
        with patch.object(m.c.base, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
                m.run(args)
        args.output = SOURCE.parent
        with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_EXISTS'):
            m.run(args)
        self.source['unityInputAllowed'] = True
        with self.assertRaisesRegex(ValueError, 'GATE_NOT_LOCKED'):
            m.field(self.source)

    def test_saved_guide_position_and_policy_tampering_rejected(self):
        source, obj, report = self.restored()
        design = report['design']
        self.assertEqual(m.audit_guides(source, obj, design)['guideCount'], 12)
        course = bpy.data.objects[m.GUIDE_PREFIX + 'course_0']
        course.data.splines[0].points[0].co.x += .001
        with self.assertRaisesRegex(ValueError, 'GUIDE_POSITION_CHANGED'):
            m.audit_guides(source, obj, design)
        source, obj, report = self.restored()
        fold = bpy.data.objects[m.GUIDE_PREFIX + 'fold_193']
        fold['foldPolicy'] = 'APPROVED_FINAL_FOLD'
        with self.assertRaisesRegex(ValueError, 'GUIDE_FOLD_POLICY_CHANGED'):
            m.audit_guides(source, obj, report['design'])

    def test_saved_artifact_preserves_originals_and_hidden_guides(self):
        names = [o.name for o in self.originals]
        digest = m.c.guide.digest(self.originals)
        inv = {o.name: m.surface.repair.invariant_signature(o) for o in self.originals}
        visible = {o.name for o in bpy.context.scene.objects if o.type in ('MESH', 'CURVE') and not o.hide_get()}
        source, obj, report = self.restored()
        restored_originals = [bpy.data.objects[n] for n in names]
        self.assertEqual(digest, m.c.guide.digest(restored_originals))
        self.assertEqual(inv, {o.name: m.surface.repair.invariant_signature(o) for o in restored_originals})
        self.assertEqual(visible, {o.name for o in bpy.context.scene.objects if o.type in ('MESH', 'CURVE') and not o.hide_get()})
        self.assertTrue(obj.hide_get())
        self.assertTrue(obj.hide_render)
        guides = [o for o in bpy.context.scene.objects if o.type == 'CURVE' and o.name.startswith(m.GUIDE_PREFIX)]
        self.assertEqual(len(guides), 12)
        self.assertTrue(all(o.hide_get() and o.hide_render for o in guides))
        self.assertEqual(m.audit_guides(source, obj, report['design'])['maximumGuidePositionErrorMeters'], 0)
        self.assertIsNone(bpy.data.objects.get('FoldReviewGhost_RENDER_ONLY'))
        for subject in (obj, bpy.context.scene, report, *guides):
            m.surface.require_locked(subject)
        self.assertEqual(self.audit(source, obj, report), report['qa'])
        for key in ('adoptionAllowed', 'completeShoulderPanel', 'rigBound'):
            self.assertFalse(report[key])
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']), 12)
        for row in report['renders']:
            self.assertEqual(m.c.base.sha(ARTIFACT.parent / row['file']), row['sha256'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--artifact', type=Path)
    args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
    SOURCE = args.source.resolve()
    ARTIFACT = args.artifact.resolve() if args.artifact else None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LayoutTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
