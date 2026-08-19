from __future__ import annotations

import tempfile
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
        command = build_command("triposr", triposr, Path("triposr-repo"), front, output)
        self.assertIn("--model-save-format", command)
        self.assertIn("glb", command)

    def test_notebook_caps_free_candidate_attempts_and_keeps_fallback(self):
        notebook = Path("notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(encoding="utf-8")
        self.assertIn("MAX_ATTEMPTS = 3", notebook)
        self.assertIn("provider_attempts = [PROVIDER, 'triposr'] if PROVIDER == 'sf3d' else [PROVIDER]", notebook)
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
