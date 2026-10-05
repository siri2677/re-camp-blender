"""Real-asset regressions: original cumulative budget, preservation, serialization."""
import argparse
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import refine_ch101_sector_profile as study

SOURCE = ARTIFACT = None


class SectorProfileTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(study.c.base.sha(SOURCE),study.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source=bpy.data.objects[study.shared.RESULT_OBJECT]
        self.baseline=bpy.data.objects[study.shared.bake.RESULT_OBJECT]
        self.frame=study.shared.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_compact_directional_support_and_wrap(self):
        self.assertAlmostEqual(study.angular_weight(2*math.pi,0,.5),1)
        self.assertEqual(study.angular_weight(.5,0,.5),0)
        self.assertEqual(study.angular_weight(math.pi,0,.5),0)
        a=math.radians(326.25)
        self.assertEqual(study.profile_weight(.078,a),0)
        self.assertEqual(study.profile_weight(.132,a),0)
        self.assertAlmostEqual(study.profile_weight(.098,a),1)
        self.assertEqual(study.profile_weight(.098,math.radians(90)),0)
        for width in (0,math.pi,float('nan')):
            with self.assertRaisesRegex(ValueError,'INVALID_SECTOR_ANGLE'):
                study.angular_weight(0,0,width)

    def test_budget_is_cumulative_not_renewed(self):
        zero=Vector()
        current=Vector((.0028,0,0))
        result,limited=study.budgeted_position(zero,current,Vector((.0012,0,0)))
        self.assertTrue(limited)
        self.assertLessEqual(result.length,.003)
        self.assertLess((result-current).length,.000201)
        with self.assertRaisesRegex(ValueError,'INPUT_ALREADY_EXCEEDS'):
            study.budgeted_position(zero,Vector((.0031,0,0)),zero)
        for budget in (0,.006,float('nan')):
            with self.assertRaisesRegex(ValueError,'INVALID_CUMULATIVE_BUDGET'):
                study.budgeted_position(zero,current,zero,budget)
        with self.assertRaisesRegex(ValueError,'INVALID_CUMULATIVE_BUDGET'):
            study.budgeted_position(zero,current,Vector((float('inf'),0,0)))

    def test_real_asset_cumulative_budget_preservation_and_static_qa(self):
        original_digest=study.c.guide.digest([self.source,self.baseline])
        obj,report=study.refine(self.source,self.baseline,*self.frame)
        self.assertEqual(report['selectedVertexCount'],138)
        self.assertEqual(len(report['budgetClippedVertexIndices']),7)
        self.assertLessEqual(report['maxCumulativeMoveMeters'],.003)
        self.assertLessEqual(report['maxIncrementalMoveMeters'],.0012+1e-7)
        self.assertLess(report['maxAxialDriftMeters'],1e-7)
        self.assertLess(report['metricsAfter']['radialSlopeJumpRms'],report['metricsBefore']['radialSlopeJumpRms'])
        for key in ('incrementalDistortion','cumulativeDistortion'):
            self.assertGreaterEqual(report[key]['minimumNormalDot'],.90)
            self.assertGreaterEqual(report[key]['areaRatioRange'][0],.5)
            self.assertLessEqual(report[key]['areaRatioRange'][1],1.5)
        self.assertGreaterEqual(report['sampledRimThicknessMeters'][0],.001)
        study.shared.verify_preservation(self.source,obj,set(report['selectedVertexIndices']))
        self.assertEqual(original_digest,study.c.guide.digest([self.source,self.baseline]))
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(study.seam.assess(obj,parts,report)['eligible'])
        self.assertEqual(study.surface.repair.components(self.source)[1:],study.surface.repair.components(obj)[1:])

    def test_reject_baseline_reset_and_unsafe_inputs(self):
        with self.assertRaisesRegex(ValueError,'ORIGINAL_BUDGET_BASELINE_CHANGED'):
            study.refine(self.source,self.source,*self.frame)
        for amplitude in (.01,0,float('nan')):
            with self.assertRaisesRegex(ValueError,'UNSAFE_SECTOR_AMPLITUDE'):
                study.refine(self.source,self.baseline,*self.frame,amplitude=amplitude)
        with self.assertRaisesRegex(ValueError,'INVALID_SECTOR_FRAME'):
            study.refine(self.source,self.baseline,self.frame[0],Vector(),self.frame[2])

    def test_mutation_guards(self):
        obj,report=study.refine(self.source,self.baseline,*self.frame)
        selected=set(report['selectedVertexIndices'])
        uv=study.shared.bake.ATLAS_UV
        obj.data.uv_layers[uv].data[-1].uv.x+=.01
        with self.assertRaisesRegex(ValueError,'TOPOLOGY_UV'):
            study.shared.verify_preservation(self.source,obj,selected)
        obj.data.uv_layers[uv].data[-1].uv=self.source.data.uv_layers[uv].data[-1].uv
        mask=study.seam.trim.upper.MASK
        obj.data.attributes[mask].data[0].value+=.1
        with self.assertRaisesRegex(ValueError,'MASK_OR_TRIM'):
            study.shared.verify_preservation(self.source,obj,selected)
        obj.data.attributes[mask].data[0].value=self.source.data.attributes[mask].data[0].value
        locked=next(i for i in range(len(obj.data.vertices)) if i not in selected)
        obj.data.vertices[locked].co.x+=.001
        with self.assertRaisesRegex(ValueError,'LOCKED_VERTEX'):
            study.shared.verify_preservation(self.source,obj,selected)

    def test_failed_guard_cleans_copy_only(self):
        names=set(bpy.data.objects.keys())
        digest=study.c.guide.digest([self.source,self.baseline])
        with patch.object(study.shared,'verify_preservation',side_effect=ValueError('TEST_GUARD')):
            with self.assertRaisesRegex(ValueError,'TEST_GUARD'):
                study.refine(self.source,self.baseline,*self.frame)
        self.assertEqual(names,set(bpy.data.objects.keys()))
        self.assertEqual(digest,study.c.guide.digest([self.source,self.baseline]))

    def test_cli_fail_closed(self):
        with patch.object(study.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                study.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            study.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            study.surface.require_locked(bpy.context.scene)

    def test_saved_reopen_budget_hashes_and_gates(self):
        if ARTIFACT is None:self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'sector-profile-report.json').read_text(encoding='utf-8'))
        self.assertEqual(study.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        source=bpy.data.objects[study.shared.RESULT_OBJECT]
        baseline=bpy.data.objects[study.shared.bake.RESULT_OBJECT]
        obj=bpy.data.objects[study.RESULT_OBJECT]
        self.assertEqual(study.c.guide.digest([baseline]),study.BASELINE_DIGEST)
        study.shared.verify_preservation(source,obj,set(report['operation']['selectedVertexIndices']))
        total=max((obj.matrix_world@v.co-baseline.matrix_world@baseline.data.vertices[v.index].co).length for v in obj.data.vertices)
        self.assertLessEqual(total,.003)
        self.assertAlmostEqual(total,report['operation']['maxCumulativeMoveMeters'],places=9)
        self.assertTrue(source.hide_get());self.assertTrue(baseline.hide_get());self.assertFalse(obj.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        self.assertEqual(len(obj.data.vertices),8236);self.assertEqual(len(obj.data.polygons),16435)
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(study.seam.assess(obj,parts,report['operation'])['eligible'])
        for subject in (obj,bpy.context.scene,report):study.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore']);self.assertFalse(report['rigBound'])
        self.assertEqual(len(report['renders']),11)
        for row in report['renders']:self.assertEqual(study.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SectorProfileTests))
    if not result.wasSuccessful():raise SystemExit(1)
