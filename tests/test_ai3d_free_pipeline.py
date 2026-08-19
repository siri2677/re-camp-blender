from __future__ import annotations

import tempfile
import json
from pathlib import Path
import unittest

from scripts.ai3d.common import (
    DEFAULT_CONTRACT_PATH,
    EXPECTED_GATE,
    EXPECTED_SOURCE_STATUS,
    load_contract,
)
from scripts.ai3d.prepare_reference_views import prepare_views
from scripts.ai3d.rank_candidates import rank_reports
from scripts.ai3d.run_open_source_provider import build_command
from scripts.ai3d.tripo_api import build_multiview_payload


class AI3DFreePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract(DEFAULT_CONTRACT_PATH)

    def test_contract_cannot_promote_ai_candidate_to_production(self):
        policy = self.contract["statusPolicy"]
        self.assertEqual(policy["sourceStatus"], EXPECTED_SOURCE_STATUS)
        self.assertEqual(policy["gateB"], EXPECTED_GATE)
        self.assertFalse(policy["unityInputAllowed"])
        self.assertFalse(policy["productionPromotionAllowed"])
        self.assertIn("hunyuan3d2", self.contract["excludedProviders"])

    def test_tripo_multiview_payload_uses_three_named_views_and_seed(self):
        tokens = {"front": "front-token", "right": "right-token", "back": "back-token"}
        payload = build_multiview_payload(self.contract, tokens, 101003)
        self.assertEqual(
            payload["inputs"],
            [
                {"front": "front-token"},
                {"right": "right-token"},
                {"back": "back-token"},
            ],
        )
        self.assertEqual(payload["model_seed"], 101003)
        self.assertTrue(payload["texture"])
        self.assertTrue(payload["pbr"])

    def test_reference_dry_run_keeps_gate_locked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                self.contract["authoritativeSource"],
                self.contract["generationSource"]["path"],
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(relative.encode("utf-8"))
            manifest = prepare_views(
                art_root=root,
                output_dir=root / "output",
                contract_path=DEFAULT_CONTRACT_PATH,
                dry_run=True,
            )
            self.assertEqual(manifest["status"], "REFERENCE_VIEW_PLAN")
            self.assertFalse(manifest["unityInputAllowed"])
            self.assertEqual(set(manifest["views"]), {"front", "right", "back"})

    def test_open_source_commands_are_pinned_provider_commands(self):
        front = Path("front.png")
        output = Path("provider-output")
        sf3d = self.contract["providers"]["stableFast3D"]
        command = build_command("sf3d", sf3d, Path("sf3d-repo"), front, output)
        self.assertIn("--target_vertex_count", command)
        self.assertIn(str(sf3d["targetVertexCount"]), command)
        triposr = self.contract["providers"]["tripoSR"]
        command = build_command(
            "triposr", triposr, Path("triposr-repo"), front, output, foreground_ratio=0.75
        )
        self.assertIn("--model-save-format", command)
        self.assertIn("glb", command)
        self.assertIn("--foreground-ratio", command)
        self.assertIn("0.75", command)
        self.assertEqual(
            self.contract["providers"]["tripoSR"]["referenceViews"],
            ["front", "right", "back"],
        )
        instantmesh = self.contract["providers"]["instantMesh"]
        command = build_command(
            "instantmesh", instantmesh, Path("instantmesh-repo"), front, output
        )
        self.assertIn("instant-mesh-large.yaml", " ".join(command))
        self.assertIn("--export_texmap", command)

    def test_notebook_caps_free_candidate_attempts_and_keeps_fallback(self):
        notebook = Path("notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(encoding="utf-8")
        self.assertIn("MAX_ATTEMPTS = 3", notebook)
        self.assertIn("provider_attempts = [PROVIDER, 'instantmesh', 'triposr'] if PROVIDER == 'sf3d' else [PROVIDER]", notebook)
        self.assertIn("foreground_ratios", notebook)
        self.assertIn("reference_views", notebook)
        self.assertIn("huggingface-hub==0.25.2", notebook)
        self.assertIn("git+https://github.com/tatsy/torchmcubes.git", notebook)
        self.assertIn("InstantMesh setup failed; continuing to next fallback", notebook)
        self.assertIn("--material-mode", notebook)
        self.assertIn("'preserve'", notebook)
        self.assertIn("REFINED_REVIEW_CANDIDATE", notebook)
        self.assertIn("AUTO_ESTIMATED_NOT_APPROVED", notebook)

    def test_refinement_script_preserves_locked_gate(self):
        source = Path("scripts/blender/refine_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("import sys", source)
        self.assertIn('sys.argv[sys.argv.index("--") + 1 :]', source)
        self.assertIn('SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"', source)
        self.assertIn('GATE_B = "PENDING_HUMAN_REVIEW"', source)
        self.assertIn('"unityInputAllowed": False', source)
        self.assertIn('"productionPromotionAllowed": False', source)
        self.assertIn('choices=("neutral", "preserve")', source)
        self.assertIn('"materialMode": args.material_mode', source)
        self.assertIn("apply_palette_review_materials", source)
        self.assertIn('"paletteFallbackUsed": palette_fallback_used', source)

    def test_workbench_material_sync_prevents_false_gray_render(self):
        source = Path("scripts/blender/evaluate_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("sync_workbench_material_colors", source)
        self.assertIn('material.diffuse_color = tuple(base_color.default_value)', source)
        self.assertIn('"workbenchMaterialsSynced": workbench_materials_synced', source)
        self.assertIn('scene.render.engine = "BLENDER_EEVEE_NEXT"', source)
        self.assertIn('"renderEngine": bpy.context.scene.render.engine', source)

    def test_persisted_ch101_run_record_is_secret_free_and_gate_locked(self):
        record = json.loads(
            Path(
                "docs/records/ch101-ai3d/2026-08-19-triposr-reference-and-material-preserve.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(record["character"], "CH101")
        self.assertEqual(len(record["providerRuns"]), 3)
        self.assertIsNone(record["gate"]["selectedCandidate"])
        self.assertFalse(record["gate"]["unityInputAllowed"])
        self.assertFalse(record["gate"]["productionPromotionAllowed"])
        self.assertEqual(record["runtimeVerification"]["accelerator"], "Tesla T4")
        self.assertTrue(record["runtimeVerification"]["actualInference"])
        self.assertEqual(record["runtimeVerification"]["generatedAttempts"], [1, 2, 3])
        self.assertEqual(record["runtimeVerification"]["fallbackResilienceCommit"], "bdf21ae")
        self.assertEqual(
            record["runtimeVerification"]["fallbackResilienceVerification"]["notebookJson"],
            "PASS",
        )
        self.assertFalse(
            record["runtimeVerification"]["fallbackResilienceVerification"][
                "actualAutomaticColabRerun"
            ]
        )
        self.assertIn("SYNC_PRINCIPLED_BASE_COLOR_TO_WORKBENCH_DIFFUSE_COLOR", record["scoreDiagnosis"]["implementedFixes"])
        self.assertEqual(record["scoreDiagnosis"]["nextColabVerification"], "PENDING")
        serialized = json.dumps(record)
        self.assertNotIn("API_KEY", serialized)
        self.assertNotIn("HF_TOKEN", serialized)

    def test_color_render_rerun_is_persisted_and_stays_gate_locked(self):
        record = json.loads(
            Path(
                "docs/records/ch101-ai3d/2026-08-19-color-render-rerun.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(record["tools"]["pipelineCommit"], "e6d9c1946ede26fe7669fcfa1b49597981877811")
        self.assertEqual(len(record["candidateRuns"]), 3)
        self.assertTrue(record["appliedReviewFixes"]["renderedMaterialPixelsVerified"])
        self.assertGreater(record["candidateRuns"][2]["improved"]["color"], record["candidateRuns"][2]["baseline"]["color"])
        self.assertLess(record["candidateRuns"][2]["improved"]["overall"], 0.50)
        self.assertIsNone(record["gate"]["selectedCandidate"])
        self.assertFalse(record["gate"]["unityInputAllowed"])
        self.assertFalse(record["gate"]["productionPromotionAllowed"])
        serialized = json.dumps(record)
        self.assertNotIn("API_KEY", serialized)
        self.assertNotIn("HF_TOKEN", serialized)

    def test_ranking_selects_only_eligible_candidate_without_unlocking_unity(self):
        base = {
            "contractVersion": self.contract["contractVersion"],
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "candidatePath": "candidate.glb",
            "candidateSha256": "a" * 64,
            "silhouetteScore": 0.6,
            "technicalScore": 0.8,
            "unityInputAllowed": False,
            "selectedOrientation": {"front": "neg_y", "back": "pos_y", "right": "pos_x"},
        }
        low = dict(base, candidateId="CH101-LOW", overallScore=0.45, eligibleForHumanReview=False)
        high = dict(base, candidateId="CH101-HIGH", overallScore=0.7, eligibleForHumanReview=True)
        result = rank_reports(
            self.contract,
            [(Path("low.json"), low), (Path("high.json"), high)],
        )
        self.assertEqual(result["selectedCandidate"]["candidateId"], "CH101-HIGH")
        self.assertFalse(result["unityInputAllowed"])
        self.assertEqual(result["gateB"], EXPECTED_GATE)


if __name__ == "__main__":
    unittest.main()
