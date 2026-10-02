"""Pinned real-asset and serialization regressions for coordinated seam motion."""
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
import refine_ch101_shared_interface as study

SOURCE = ARTIFACT = None


class SharedInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(study.c.base.sha(SOURCE),study.SOURCE_SHA)
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        self.source = bpy.data.objects[study.bake.RESULT_OBJECT]
        self.frame = study.frame(bpy.data.objects['PAIR_STUDY_CH101_TaperedHand_NOT_PRODUCTION'])

    def test_shared_rims_move_together_and_locked_region_stays_exact(self):
        signature = study.c.guide.digest([self.source])
        atlas = study.atlas_signature(self.source)
        obj, report = study.refine(self.source,*self.frame)
        ids = set(report['movedVertexIndices'])
        self.assertEqual(len(ids),320)
        self.assertEqual(report['sharedGroupMovedCounts'],dict(SleeveSeam=32,BodySeam=41,SeamContourMidpoints=73,UpperOpening_inner=32))
        self.assertLessEqual(report['maxActualMoveMeters'],.003+1e-7)
        self.assertLess(report['maxAxialDriftMeters'],1e-7)
        self.assertLess(report['metricsAfter']['radialSlopeJumpRms'],report['metricsBefore']['radialSlopeJumpRms'])
        self.assertGreaterEqual(report['minimumAffectedNormalDot'],.90)
        self.assertGreaterEqual(report['sampledRimWallAfterMeters'][0],.001)
        self.assertEqual(atlas,study.atlas_signature(obj))
        study.verify_preservation(self.source,obj,ids)
        self.assertEqual(signature,study.c.guide.digest([self.source]))
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(study.seam.assess(obj,parts,report)['eligible'])
        self.assertEqual(study.surface.repair.components(self.source)[1:],study.surface.repair.components(obj)[1:])

    def test_mutation_guard_rejects_uv_fields_and_distant_geometry(self):
        obj, report = study.refine(self.source,*self.frame)
        selected=set(report['movedVertexIndices'])
        obj.data.uv_layers[study.bake.ATLAS_UV].data[-1].uv.x+=.01
        with self.assertRaisesRegex(ValueError,'TOPOLOGY_UV'):
            study.verify_preservation(self.source,obj,selected)
        obj.data.uv_layers[study.bake.ATLAS_UV].data[-1].uv=self.source.data.uv_layers[study.bake.ATLAS_UV].data[-1].uv
        name=study.seam.trim.upper.MASK
        obj.data.attributes[name].data[0].value+=.1
        with self.assertRaisesRegex(ValueError,'MASK_OR_TRIM'):
            study.verify_preservation(self.source,obj,selected)
        obj.data.attributes[name].data[0].value=self.source.data.attributes[name].data[0].value
        locked=next(i for i in range(len(obj.data.vertices)) if i not in selected)
        obj.data.vertices[locked].co.x+=.001
        with self.assertRaisesRegex(ValueError,'LOCKED_VERTEX'):
            study.verify_preservation(self.source,obj,selected)

    def test_unsafe_limits_frames_and_insufficient_cap_reject(self):
        for kwargs in (dict(strength=.5),dict(max_move=.01),dict(strength=float('nan'))):
            with self.assertRaisesRegex(ValueError,'UNSAFE_INTERFACE_LIMIT'):
                study.refine(self.source,*self.frame,**kwargs)
        with self.assertRaisesRegex(ValueError,'DISPLACEMENT_REJECTED'):
            study.refine(self.source,*self.frame,max_move=.0001)
        with self.assertRaisesRegex(ValueError,'INVALID_INTERFACE_FRAME'):
            study.refine(self.source,self.frame[0],Vector(),self.frame[2])

    def test_failed_guard_removes_only_temporary_copy(self):
        names=set(bpy.data.objects.keys())
        signature=study.c.guide.digest([self.source])
        with patch.object(study,'verify_preservation',side_effect=ValueError('TEST_GUARD')):
            with self.assertRaisesRegex(ValueError,'TEST_GUARD'):
                study.refine(self.source,*self.frame)
        self.assertEqual(names,set(bpy.data.objects.keys()))
        self.assertEqual(signature,study.c.guide.digest([self.source]))

    def test_cli_fail_closed_hash_path_gate(self):
        with patch.object(study.c.base,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
                study.run(SimpleNamespace(source=SOURCE,output=Path('unused')))
        with self.assertRaisesRegex(ValueError,'OUTPUT_ALREADY_EXISTS'):
            study.run(SimpleNamespace(source=SOURCE,output=SOURCE.parent))
        bpy.context.scene['unityInputAllowed']=True
        with self.assertRaisesRegex(ValueError,'GATE_NOT_LOCKED'):
            study.surface.require_locked(bpy.context.scene)

    def test_saved_qa_reopen_preservation_and_render_hashes(self):
        if ARTIFACT is None:
            self.skipTest('Saved artifact required')
        report=json.loads((ARTIFACT.parent/'shared-interface-report.json').read_text(encoding='utf-8'))
        self.assertEqual(study.c.base.sha(ARTIFACT),report['blendSha256'])
        bpy.ops.wm.open_mainfile(filepath=str(ARTIFACT))
        original=bpy.data.objects[study.bake.RESULT_OBJECT]
        obj=bpy.data.objects[study.RESULT_OBJECT]
        study.verify_preservation(original,obj,set(report['operation']['movedVertexIndices']))
        self.assertTrue(original.hide_get())
        self.assertFalse(obj.hide_get())
        self.assertEqual(len([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_get()]),13)
        self.assertEqual(len(obj.data.vertices),8236)
        self.assertEqual(len(obj.data.polygons),16435)
        parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('PAIR_STUDY_')]
        self.assertTrue(study.seam.assess(obj,parts,report['operation'])['eligible'])
        for subject in (obj,bpy.context.scene,report):study.surface.require_locked(subject)
        self.assertIsNone(report['fullCharacterScore'])
        self.assertEqual(len(report['renders']),10)
        for row in report['renders']:
            self.assertEqual(study.c.base.sha(ARTIFACT.parent/row['file']),row['sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--artifact',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve();ARTIFACT=args.artifact.resolve() if args.artifact else None
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SharedInterfaceTests))
    if not result.wasSuccessful():raise SystemExit(1)
