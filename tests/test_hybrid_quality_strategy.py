import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ai3d.colab_runtime_preflight import build_report
from scripts.ai3d.common import load_contract, sha256_file
from scripts.ai3d import hybrid_quality_orchestrator
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

    def test_quality_plateau_record_without_candidate_id_blocks_same_strategy(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "quality-progress-gate.json"
            path.write_text(
                json.dumps(
                    {
                        "status": "QUALITY_PLATEAU_SAME_STRATEGY",
                        "provider": "blenderSemanticAuthoring",
                        "strategyId": "UNIFIED_SEMANTIC_AUTHORING_V002",
                        "bestOverallScore": 0.608431,
                    }
                ),
                encoding="utf-8",
            )
            history = collect_history(None, [path])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["candidateId"], "STRATEGY_GATE:UNIFIED_SEMANTIC_AUTHORING_V002")
        self.assertTrue(history[0]["rejected"])
        gate = build_progress_gate(
            provider="blenderSemanticAuthoring",
            strategy_id="UNIFIED_SEMANTIC_AUTHORING_V002",
            history=history,
        )
        self.assertEqual(gate["status"], "QUALITY_PLATEAU_SAME_STRATEGY")

    def test_nested_review_record_blocks_recorded_semantic_detail_strategy(self):
        record = (
            ROOT
            / "docs"
            / "records"
            / "ch101-ai3d"
            / "2026-08-29-local-blender-v003-review-v001.json"
        )
        history = collect_history(None, [record])
        matching = [
            item
            for item in history
            if item["strategyId"] == "SEMANTIC_DETAIL_AUTHORING_V003"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["overallScore"], 0.479447)
        self.assertEqual(matching[0]["appearanceScore"], 0.369244)
        self.assertTrue(matching[0]["rejected"])
        gate = build_progress_gate(
            provider="blenderSemanticDetailAuthoring",
            strategy_id="SEMANTIC_DETAIL_AUTHORING_V003",
            history=history,
        )
        self.assertEqual(gate["status"], "QUALITY_PLATEAU_SAME_STRATEGY")

    def test_nested_kaggle_review_record_preserves_strategy_and_score(self):
        record = (
            ROOT
            / "docs"
            / "records"
            / "ch101-ai3d"
            / "2026-08-31-kaggle-semantic-authoring-v002-review.json"
        )
        history = collect_history(None, [record])
        matching = [
            item
            for item in history
            if item["strategyId"] == "MPFB_SEMANTIC_AUTHORING_CLOTHING_SEMANTIC_V002"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["overallScore"], 0.682993)
        self.assertEqual(matching[0]["appearanceScore"], 0.373505)
        self.assertTrue(matching[0]["rejected"])

    def test_kaggle_execution_record_strategy_map_blocks_semantic_proxy(self):
        record = ROOT / "docs" / "records" / "ch101-ai3d" / "2026-08-28-kaggle-hybrid-semantic-proxy-v077.json"
        history = collect_history(None, [record])
        matching = [
            item
            for item in history
            if item["strategyId"] == "SEMANTIC_PROXY_REFERENCE_FITTED_V001"
        ]
        self.assertTrue(matching)
        self.assertTrue(any(item["rejected"] for item in matching))

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

    def test_unified_semantic_strategy_is_the_single_pivot_after_v001_rejection(self):
        contract = load_contract(ROOT / "contracts" / "ch101_ai3d_free_pipeline_v001.json")
        self.assertEqual(
            contract["qualityStrategies"]["UNIFIED_SEMANTIC_AUTHORING_V002"]["provider"],
            "blenderSemanticAuthoring",
        )
        history = [
            {
                "candidateId": "CH101-SEMANTICPROXY-001",
                "strategyId": "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
                "overallScore": 0.505845,
                "status": "REGENERATE_REQUIRED",
                "rejected": True,
            }
        ]
        old_gate = build_progress_gate(
            provider="semanticProxy",
            strategy_id="SEMANTIC_PROXY_REFERENCE_FITTED_V001",
            history=history,
        )
        pivot_gate = build_progress_gate(
            provider="blenderSemanticAuthoring",
            strategy_id="UNIFIED_SEMANTIC_AUTHORING_V002",
            history=history,
        )
        self.assertEqual(old_gate["status"], "QUALITY_PLATEAU_SAME_STRATEGY")
        self.assertEqual(pivot_gate["status"], "READY_NEW_STRATEGY")
        self.assertFalse(pivot_gate["unityInputAllowed"])

    def test_semantic_detail_strategy_is_the_next_pivot_after_v002_plateau(self):
        contract = load_contract(ROOT / "contracts" / "ch101_ai3d_free_pipeline_v001.json")
        self.assertEqual(
            contract["qualityStrategies"]["SEMANTIC_DETAIL_AUTHORING_V003"]["provider"],
            "blenderSemanticDetailAuthoring",
        )
        history = [
            {
                "candidateId": "CH101-BLENDERSEMANTICAUTHORING-002",
                "strategyId": "UNIFIED_SEMANTIC_AUTHORING_V002",
                "overallScore": 0.608431,
                "status": "REGENERATE_REQUIRED",
                "rejected": True,
            }
        ]
        old_gate = build_progress_gate(
            provider="blenderSemanticAuthoring",
            strategy_id="UNIFIED_SEMANTIC_AUTHORING_V002",
            history=history,
        )
        pivot_gate = build_progress_gate(
            provider="blenderSemanticDetailAuthoring",
            strategy_id="SEMANTIC_DETAIL_AUTHORING_V003",
            history=history,
        )
        self.assertEqual(old_gate["status"], "QUALITY_PLATEAU_SAME_STRATEGY")
        self.assertEqual(pivot_gate["status"], "READY_NEW_STRATEGY")
        self.assertFalse(pivot_gate["productionPromotionAllowed"])

    def test_orchestrator_selects_v002_after_v001_plateau_without_gpu(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_gate(provider, strategy_id, score_dir, history_records):
            return {
                "status": (
                    "QUALITY_PLATEAU_SAME_STRATEGY"
                    if strategy_id == "SEMANTIC_PROXY_REFERENCE_FITTED_V001"
                    else "READY_NEW_STRATEGY"
                ),
                "provider": provider,
                "strategyId": strategy_id,
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            }

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.hybrid_quality_orchestrator.build_runtime_report",
            return_value={
                "status": "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": False},
            },
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator._gate", side_effect=fake_gate
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator.prepare_handoff",
            return_value={"status": "READY_INPUTS_BLOCKED_AUTHORING"},
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator.shutil.which",
            return_value="blender",
        ), patch("scripts.ai3d.hybrid_quality_orchestrator.write_json"):
            report = hybrid_quality_orchestrator.build_hybrid_report(
                art_root=Path(temporary),
                output=Path(temporary) / "orchestration.json",
                contract_path=contract_path,
                socket_contract_path=ROOT / "contracts" / "current_roster_socket_contract_v001.json",
                character="CH101",
            )

        self.assertEqual(report["selectedStrategies"], ["UNIFIED_SEMANTIC_AUTHORING_V002"])
        self.assertFalse(
            report["strategies"]["SEMANTIC_PROXY_REFERENCE_FITTED_V001"]["runAllowed"]
        )
        self.assertTrue(
            report["strategies"]["UNIFIED_SEMANTIC_AUTHORING_V002"]["runAllowed"]
        )
        self.assertFalse(report["unityInputAllowed"])

    def test_orchestrator_selects_v003_after_v002_plateau_without_gpu(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_gate(provider, strategy_id, score_dir, history_records):
            status = "READY_NEW_STRATEGY"
            if strategy_id in {
                "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
                "UNIFIED_SEMANTIC_AUTHORING_V002",
            }:
                status = "QUALITY_PLATEAU_SAME_STRATEGY"
            return {
                "status": status,
                "provider": provider,
                "strategyId": strategy_id,
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            }

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.hybrid_quality_orchestrator.build_runtime_report",
            return_value={
                "status": "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": False},
            },
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator._gate", side_effect=fake_gate
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator.prepare_handoff",
            return_value={"status": "READY_INPUTS_BLOCKED_AUTHORING"},
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator.shutil.which",
            return_value="blender",
        ), patch("scripts.ai3d.hybrid_quality_orchestrator.write_json"):
            report = hybrid_quality_orchestrator.build_hybrid_report(
                art_root=Path(temporary),
                output=Path(temporary) / "orchestration.json",
                contract_path=contract_path,
                socket_contract_path=ROOT / "contracts" / "current_roster_socket_contract_v001.json",
                character="CH101",
            )

        self.assertEqual(report["selectedStrategies"], ["SEMANTIC_DETAIL_AUTHORING_V003"])
        self.assertFalse(
            report["strategies"]["UNIFIED_SEMANTIC_AUTHORING_V002"]["runAllowed"]
        )
        self.assertTrue(
            report["strategies"]["SEMANTIC_DETAIL_AUTHORING_V003"]["runAllowed"]
        )
        self.assertFalse(report["productionPromotionAllowed"])

    def test_unified_candidate_metadata_preserves_semantic_audit(self):
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
            mesh = root / "unified.obj"
            mesh.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            destination = root / "unified-copy.obj"
            destination.write_bytes(mesh.read_bytes())
            manifest = build_candidate_manifest(
                contract,
                reference_manifest,
                mesh,
                destination,
                provider="blenderSemanticAuthoring",
                strategy_id="UNIFIED_SEMANTIC_AUTHORING_V002",
                source_stage="UNIFIED_SEMANTIC_AUTHORING",
                candidate_label="002",
                metadata={
                    "schemaVersion": "ch101-unified-semantic-authoring-report-v001",
                    "strategyId": "UNIFIED_SEMANTIC_AUTHORING_V002",
                    "meshFormat": "OBJ",
                    "semanticComponentAudit": {
                        "status": "PASS",
                        "partObjectCountsLOD0": {
                            "body_face": 1,
                            "hair": 1,
                            "outfit": 1,
                            "equipment": 1,
                        },
                        "slabGrayboxAccepted": False,
                    },
                },
            )
        candidate = manifest["candidates"][0]
        self.assertEqual(candidate["provider"], "blenderSemanticAuthoring")
        self.assertEqual(candidate["semanticComponentAudit"]["status"], "PASS")
        self.assertFalse(candidate["unityInputAllowed"])
        self.assertEqual(candidate["sourceMetadata"]["meshFormat"], "OBJ")

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
            "UNIFIED_SEMANTIC_AUTHORING_V002",
            "SEMANTIC_DETAIL_AUTHORING_V003",
            "2026-08-29-local-blender-v003-review-v001.json",
            "2026-08-31-kaggle-semantic-authoring-v002-review.json",
            "build_ch101_unified_semantic_mesh.py",
            "build_ch101_semantic_detail_candidate.py",
            "BLOCKED_PROVIDER_ENTRYPOINT_UNVERIFIED",
            "quality_progress_gate",
            "strict visual QA",
            "BLOCKED_PROVIDER_PREFLIGHT",
            "REGENERATE_REQUIRED",
            "unityInputAllowed",
            "productionPromotionAllowed",
            "Kaggle archive retained in the output workspace",
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
            "export_obj_compat",
            "meshFormat",
        ):
            self.assertIn(marker, builder)

        unified_builder = (
            ROOT / "scripts" / "blender" / "build_ch101_unified_semantic_mesh.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "UNIFIED_PRIMARY_SHELL_WITH_SEMANTIC_LABELS",
            "apply_connectivity_remesh",
            "AI_REVIEW_SEMANTIC_LABELS_NOT_PRODUCTION",
            "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER",
            "AUTO_ESTIMATED_NOT_APPROVED",
            "unityInputAllowed",
            "productionPromotionAllowed",
        ):
            self.assertIn(marker, unified_builder)

        detail_builder = (
            ROOT / "scripts" / "blender" / "build_ch101_semantic_detail_candidate.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "SEMANTIC_DETAIL_AUTHORING_V003",
            "CONNECTED_BODY_WITH_PRESERVED_DETAIL_GROUPS",
            "preservedFaceDetail",
            "MODEL_HAIR",
            "MODEL_CLOTH_OUTFIT",
            "productionPromotionAllowed",
        ):
            self.assertIn(marker, detail_builder)

        refinement = (ROOT / "scripts" / "blender" / "refine_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("refinedTransportPath", refinement)
        self.assertIn("OBJ transport fallback", refinement)

        evaluator = (ROOT / "scripts" / "blender" / "evaluate_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("is_review_helper_mesh", evaluator)
        self.assertIn("candidate_meshes", evaluator)
        self.assertIn('startswith("ReviewFloor_")', evaluator)
        self.assertIn("geometry_meshes", evaluator)
        self.assertIn('"PRIMARY_SHELL"', evaluator)
        self.assertIn("technicalAspectSourceObjects", evaluator)


if __name__ == "__main__":
    unittest.main()
