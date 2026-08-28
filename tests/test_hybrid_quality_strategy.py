import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ai3d.colab_runtime_preflight import build_report
from scripts.ai3d.common import load_contract, sha256_file
from scripts.ai3d.register_review_candidate import build_candidate_manifest
from scripts.ai3d.quality_progress_gate import build_progress_gate, collect_history


ROOT = Path(__file__).resolve().parents[1]


class HybridQualityStrategyTests(unittest.TestCase):
    def test_trellis_low_vram_fails_provider_preflight_without_install_authorization(self):
        with patch(
            "scripts.ai3d.colab_runtime_preflight.nvidia_gpus",
            return_value=[{"name": "NVIDIA T4", "memoryMb": 16384, "driverVersion": "test"}],
        ), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status",
            return_value={
                "available": True,
                "cudaAvailable": True,
                "torchKernelSupportsDevice": True,
            },
        ):
            report = build_report("trellis")
        self.assertEqual(report["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertFalse(report["providerPreflight"]["heavyweightInstallAllowed"])
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_trellis_high_memory_requires_explicit_terms_acknowledgement(self):
        gpu = [{"name": "NVIDIA A10G", "memoryMb": 24576, "driverVersion": "test"}]
        torch = {
            "available": True,
            "cudaAvailable": True,
            "torchKernelSupportsDevice": True,
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {"RE_CAMP_TRELLIS_LICENSE_ACK": "1"}):
            report = build_report("trellis")
        self.assertEqual(report["status"], "READY_GPU_VISIBLE")
        self.assertTrue(report["providerPreflight"]["heavyweightInstallAllowed"])

    def test_same_hybrid_strategy_is_one_shot_after_rejection(self):
        history = [
            {
                "candidateId": "CH101-SEMANTICPROXY-001",
                "strategyId": "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
                "overallScore": 0.44,
                "status": "REGENERATE_REQUIRED",
                "rejected": True,
            }
        ]
        report = build_progress_gate(
            provider="semanticProxy",
            strategy_id="SEMANTIC_PROXY_REFERENCE_FITTED_V001",
            history=history,
        )
        self.assertEqual(report["status"], "QUALITY_PLATEAU_SAME_STRATEGY")
        self.assertEqual(report["nextAction"], "PIVOT_TO_SEMANTIC_RECONSTRUCTION_OR_NEW_PROVIDER")
        self.assertFalse(report["unityInputAllowed"])

    def test_assisted_visual_rejection_counts_as_strategy_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review = root / "assisted-visual-review.json"
            review.write_text(
                json.dumps(
                    {
                        "candidateReviews": [
                            {
                                "candidateId": "CH101-SEMANTICPROXY-001",
                                "strategyId": "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
                                "disposition": "REJECT",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            history = collect_history(root, [])
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["rejected"])
        self.assertEqual(history[0]["strategyId"], "SEMANTIC_PROXY_REFERENCE_FITTED_V001")

    def test_generic_candidate_registration_records_provider_strategy_and_hashes(self):
        contract = load_contract(ROOT / "contracts" / "ch101_ai3d_free_pipeline_v001.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference_dir = root / "references"
            reference_dir.mkdir()
            views = {}
            for name in ("front", "right", "back"):
                path = reference_dir / f"{name}.png"
                path.write_bytes(name.encode("ascii"))
                views[name] = {"path": str(path), "sha256": sha256_file(path)}
            reference_manifest = reference_dir / "reference-views-manifest.json"
            reference_manifest.write_text(
                json.dumps(
                    {
                        "contractVersion": contract["contractVersion"],
                        "character": "CH101",
                        "artCommit": contract["artLock"]["commit"],
                        "views": views,
                        "unityInputAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            mesh = root / "proxy.obj"
            mesh.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            destination = root / "proxy-copy.obj"
            destination.write_bytes(mesh.read_bytes())
            manifest = build_candidate_manifest(
                contract,
                reference_manifest,
                mesh,
                destination,
                provider="semanticProxy",
                strategy_id="SEMANTIC_PROXY_REFERENCE_FITTED_V001",
                source_stage="SEMANTIC_PROXY_REFERENCE_FITTED",
                candidate_label="001",
            )
        candidate = manifest["candidates"][0]
        self.assertEqual(manifest["provider"], "semanticProxy")
        self.assertEqual(candidate["strategyId"], "SEMANTIC_PROXY_REFERENCE_FITTED_V001")
        self.assertEqual(candidate["artCommit"], contract["artLock"]["commit"])
        self.assertFalse(manifest["unityInputAllowed"])
        self.assertFalse(manifest["productionPromotionAllowed"])

    def test_hybrid_notebook_and_semantic_builder_are_static_and_gate_locked(self):
        notebook_path = ROOT / "notebooks" / "07_ch101_hybrid_quality_strategies.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell.get("cell_type") == "code"
        )
        for marker in (
            "TRELLIS_SINGLE_VIEW_V001",
            "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
            "quality_progress_gate",
            "strict visual QA",
            "BLOCKED_PROVIDER_PREFLIGHT",
            "REGENERATE_REQUIRED",
            "unityInputAllowed",
            "productionPromotionAllowed",
        ):
            self.assertIn(marker, source)

        builder = (ROOT / "scripts" / "blender" / "build_ch101_semantic_proxy.py").read_text(encoding="utf-8")
        for marker in (
            "MODEL_HIGH_BODY",
            "MODEL_CLOTH_OUTFIT",
            "MODEL_HAIR",
            "MODEL_EQUIPMENT",
            "LOD0",
            "LOD1",
            "LOD2",
            "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER",
            "AUTO_ESTIMATED_NOT_APPROVED",
            "SLAB_GRAYBOX_NOT_ACCEPTED",
        ):
            self.assertIn(marker, builder)


if __name__ == "__main__":
    unittest.main()
