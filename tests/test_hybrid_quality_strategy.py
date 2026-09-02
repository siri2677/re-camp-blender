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
from scripts.ai3d.run_trellis2_candidate import (
    build_report as build_trellis2_report,
    dependency_preflight,
)
from scripts.ai3d.run_trellis16_candidate import (
    build_report as build_trellis16_report,
    dependency_preflight as dependency_preflight_trellis16,
)
from scripts.ai3d.run_partcrafter_candidate import (
    build_report as build_partcrafter_report,
    dependency_preflight as dependency_preflight_partcrafter,
)
from scripts.ai3d import run_partcrafter_candidate
from scripts.ai3d.quality_progress_gate import build_progress_gate, collect_history


ROOT = Path(__file__).resolve().parents[1]


class HybridQualityStrategyTests(unittest.TestCase):
    def test_partcrafter_preflight_accepts_8gb_gpu_only_with_explicit_terms_acknowledgement(self):
        gpu = [{"name": "NVIDIA T4", "memoryMb": 15360, "driverVersion": "test"}]
        torch = {
            "available": True,
            "cudaAvailable": True,
            "torchKernelSupportsDevice": True,
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {}, clear=True):
            blocked = build_report("partcrafter")
        self.assertEqual(blocked["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertEqual(blocked["providerPreflight"]["minimumVramMb"], 8192)
        self.assertEqual(
            blocked["providerPreflight"]["licenseAcknowledgementEnv"],
            "RE_CAMP_PARTCRAFTER_LICENSE_ACK",
        )
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {"RE_CAMP_PARTCRAFTER_LICENSE_ACK": "1"}, clear=True):
            ready = build_report("partcrafter")
        self.assertEqual(ready["status"], "READY_GPU_VISIBLE")
        self.assertTrue(ready["providerPreflight"]["heavyweightInstallAllowed"])

    def test_partcrafter_dependency_preflight_uses_notebook_python(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_partcrafter_candidate.subprocess.run",
            return_value=type("Result", (), {"returncode": 0})(),
        ) as run_process:
            ready, status = dependency_preflight_partcrafter(Path(temporary))
        self.assertTrue(ready)
        self.assertEqual(status, "READY_IMPORTS")
        command = run_process.call_args.args[0]
        self.assertEqual(command[0], __import__("sys").executable)
        self.assertIn("PartCrafterPipeline", command[2])

    def test_partcrafter_inference_adds_provider_root_to_pythonpath(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "provider"
            repo.mkdir()
            image = root / "front.png"
            image.write_bytes(b"image")
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "provider": "partcrafter",
                        "status": "READY_GPU_VISIBLE",
                        "providerPreflight": {
                            "vramSufficient": True,
                            "heavyweightInstallAllowed": True,
                            "licenseTermsAcknowledged": True,
                        },
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            result = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with patch(
                "scripts.ai3d.run_partcrafter_candidate.git_head",
                return_value="3d773bf02fad51c7ab31a5615573fec93b287b30",
            ), patch(
                "scripts.ai3d.run_partcrafter_candidate.subprocess.run",
                side_effect=[result, result],
            ) as run_process, patch(
                "scripts.ai3d.run_partcrafter_candidate.sys.argv",
                [
                    "run_partcrafter_candidate.py",
                    "--provider-repo",
                    str(repo),
                    "--input-image",
                    str(image),
                    "--output-dir",
                    str(root / "output"),
                    "--preflight",
                    str(preflight),
                    "--output-report",
                    str(report),
                    "--execute",
                ],
            ):
                self.assertEqual(run_partcrafter_candidate.main(), 2)
            inference_call = run_process.call_args_list[-1]
            provider_env = inference_call.kwargs["env"]
            self.assertEqual(
                provider_env["PYTHONPATH"].split(os.pathsep)[0], str(repo.resolve())
            )

    def test_partcrafter_wrapper_keeps_review_gates_locked_and_requires_part_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "provider"
            repo.mkdir()
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "provider": "partcrafter",
                        "status": "BLOCKED_PROVIDER_PREFLIGHT",
                        "providerPreflight": {
                            "vramSufficient": False,
                            "heavyweightInstallAllowed": False,
                            "licenseTermsAcknowledged": False,
                        },
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            image = root / "front.png"
            image.write_bytes(b"image")
            args = type(
                "Args",
                (),
                {
                    "provider_repo": repo,
                    "input_image": image,
                    "output_dir": root / "output",
                    "preflight": preflight,
                    "output_report": root / "report.json",
                    "num_parts": 6,
                    "num_tokens": 1024,
                    "num_inference_steps": 50,
                    "guidance_scale": 7.0,
                    "seed": 101001,
                    "execute": False,
                },
            )()
            with patch(
                "scripts.ai3d.run_partcrafter_candidate.git_head",
                return_value="3d773bf02fad51c7ab31a5615573fec93b287b30",
            ):
                report = build_partcrafter_report(args)
        self.assertEqual(report["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertIn("PROVIDER_PREFLIGHT_NOT_READY", report["blockers"])
        self.assertIn("PARTCRAFTER_VRAM_INSUFFICIENT", report["blockers"])
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_orchestrator_prioritizes_partcrafter_for_a_ready_8gb_class_lane(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_runtime(provider):
            if provider == "partcrafter":
                return {
                    "provider": provider,
                    "status": "READY_GPU_VISIBLE",
                    "providerPreflight": {
                        "heavyweightInstallAllowed": True,
                        "vramSufficient": True,
                    },
                }
            return {
                "provider": provider,
                "status": "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": False},
            }

        def fake_gate(provider, strategy_id, score_dir, history_records):
            return {
                "status": "READY_NEW_STRATEGY",
                "provider": provider,
                "strategyId": strategy_id,
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            }

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.hybrid_quality_orchestrator.build_runtime_report",
            side_effect=fake_runtime,
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

        self.assertEqual(report["selectedStrategies"], ["PARTCRAFTER_PART_LEVEL_V001"])
        self.assertTrue(
            report["strategies"]["PARTCRAFTER_PART_LEVEL_V001"]["runAllowed"]
        )
        self.assertFalse(report["unityInputAllowed"])

    def test_trellis16_accepts_16gb_class_gpu_only_with_explicit_terms_acknowledgement(self):
        gpu = [{"name": "NVIDIA T4", "memoryMb": 16384, "driverVersion": "test"}]
        torch = {
            "available": True,
            "cudaAvailable": True,
            "torchKernelSupportsDevice": True,
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch("scripts.ai3d.colab_runtime_preflight.platform.system", return_value="Linux"), patch.dict(os.environ, {}, clear=True):
            blocked = build_report("trellis16")
        self.assertEqual(blocked["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertEqual(blocked["providerPreflight"]["minimumVramMb"], 16384)
        self.assertEqual(
            blocked["providerPreflight"]["licenseAcknowledgementEnv"],
            "RE_CAMP_TRELLIS16_LICENSE_ACK",
        )
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch("scripts.ai3d.colab_runtime_preflight.platform.system", return_value="Linux"), patch.dict(os.environ, {"RE_CAMP_TRELLIS16_LICENSE_ACK": "1"}, clear=True):
            ready = build_report("trellis16")
        self.assertEqual(ready["status"], "READY_GPU_VISIBLE")
        self.assertTrue(ready["providerPreflight"]["heavyweightInstallAllowed"])

    def test_trellis16_dependency_preflight_uses_notebook_python(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_trellis16_candidate.subprocess.run",
            return_value=type("Result", (), {"returncode": 0})(),
        ) as run_process:
            ready, status = dependency_preflight_trellis16(Path(temporary))
        self.assertTrue(ready)
        self.assertEqual(status, "READY_IMPORTS")
        command = run_process.call_args.args[0]
        self.assertEqual(command[0], __import__("sys").executable)
        self.assertIn("import trellis", command[2])

    def test_trellis16_wrapper_keeps_review_gates_locked_and_requires_provider_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "provider"
            repo.mkdir()
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "provider": "trellis16",
                        "status": "BLOCKED_PROVIDER_PREFLIGHT",
                        "providerPreflight": {
                            "vramSufficient": False,
                            "heavyweightInstallAllowed": False,
                        },
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            image = root / "front.png"
            image.write_bytes(b"image")
            args = type(
                "Args",
                (),
                {
                    "provider_repo": repo,
                    "input_image": image,
                    "output_dir": root / "output",
                    "preflight": preflight,
                    "output_report": root / "report.json",
                    "texture_size": 1024,
                    "simplify": 0.95,
                    "seed": 1,
                    "attention_backend": "",
                    "execute": False,
                },
            )()
            with patch(
                "scripts.ai3d.run_trellis16_candidate.git_head",
                return_value="442aa1e1afb9014e80681d3bf604e8d728a86ee7",
            ):
                report = build_trellis16_report(args)
        self.assertEqual(report["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertIn("PROVIDER_PREFLIGHT_NOT_READY", report["blockers"])
        self.assertIn("TRELLIS16_VRAM_INSUFFICIENT", report["blockers"])
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

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

    def test_orchestrator_prioritizes_trellis2_when_strict_gpu_preflight_is_ready(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_runtime(provider):
            ready = provider == "trellis2"
            return {
                "provider": provider,
                "status": "READY_GPU_VISIBLE" if ready else "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": ready},
            }

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.hybrid_quality_orchestrator.build_runtime_report",
            side_effect=fake_runtime,
        ), patch(
            "scripts.ai3d.hybrid_quality_orchestrator._gate",
            return_value={
                "status": "READY_NEW_STRATEGY",
                "provider": "trellis2",
                "strategyId": "TRELLIS2_SINGLE_VIEW_V001",
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            },
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

        self.assertEqual(report["selectedStrategies"], ["TRELLIS2_SINGLE_VIEW_V001"])
        self.assertTrue(
            report["strategies"]["TRELLIS2_SINGLE_VIEW_V001"]["runAllowed"]
        )
        self.assertFalse(report["unityInputAllowed"])

    def test_orchestrator_selects_original_trellis16_when_trellis2_is_blocked(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_runtime(provider):
            ready = provider == "trellis16"
            return {
                "provider": provider,
                "status": "READY_GPU_VISIBLE" if ready else "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": ready},
            }

        def fake_gate(provider, strategy_id, score_dir, history_records):
            ready = strategy_id == "TRELLIS_SINGLE_VIEW_16GB_V002"
            return {
                "status": "READY_NEW_STRATEGY" if ready else "QUALITY_PLATEAU_SAME_STRATEGY",
                "provider": provider,
                "strategyId": strategy_id,
                "unityInputAllowed": False,
                "productionPromotionAllowed": False,
            }

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.hybrid_quality_orchestrator.build_runtime_report",
            side_effect=fake_runtime,
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

        self.assertEqual(report["selectedStrategies"], ["TRELLIS_SINGLE_VIEW_16GB_V002"])
        self.assertTrue(
            report["strategies"]["TRELLIS_SINGLE_VIEW_16GB_V002"]["runAllowed"]
        )
        self.assertFalse(report["unityInputAllowed"])

    def test_trellis2_high_memory_requires_its_own_terms_acknowledgement(self):
        gpu = [{"name": "NVIDIA A10G", "memoryMb": 24576, "driverVersion": "test"}]
        torch = {
            "available": True,
            "cudaAvailable": True,
            "torchKernelSupportsDevice": True,
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {}, clear=True):
            blocked = build_report("trellis2")
        self.assertEqual(blocked["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertEqual(
            blocked["providerPreflight"]["licenseAcknowledgementEnv"],
            "RE_CAMP_TRELLIS2_LICENSE_ACK",
        )
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {"RE_CAMP_TRELLIS2_LICENSE_ACK": "1"}, clear=True):
            ready = build_report("trellis2")
        self.assertEqual(ready["status"], "READY_GPU_VISIBLE")
        self.assertTrue(ready["providerPreflight"]["heavyweightInstallAllowed"])

    def test_trellis2_wrapper_refuses_unpinned_checkout_and_locked_gate_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "provider"
            repo.mkdir()
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "provider": "trellis2",
                        "status": "READY_GPU_VISIBLE",
                        "providerPreflight": {
                            "vramSufficient": True,
                            "heavyweightInstallAllowed": True,
                        },
                        "unityInputAllowed": True,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            image = root / "front.png"
            image.write_bytes(b"image")
            args = type(
                "Args",
                (),
                {
                    "provider_repo": repo,
                    "input_image": image,
                    "output_dir": root / "output",
                    "preflight": preflight,
                    "output_report": root / "report.json",
                    "texture_size": 2048,
                    "decimation_target": 100000,
                    "execute": False,
                },
            )()
            with patch(
                "scripts.ai3d.run_trellis2_candidate.git_head",
                return_value="not-the-pinned-commit",
            ):
                report = build_trellis2_report(args)
        self.assertEqual(report["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertIn("TRELLIS2_COMMIT_MISMATCH", report["blockers"])
        self.assertIn("PROJECT_GATE_ALREADY_OPEN", report["blockers"])
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_trellis2_dependency_preflight_is_import_only(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_trellis2_candidate.subprocess.run",
            return_value=type("Result", (), {"returncode": 0})(),
        ) as run_process:
            ready, status = dependency_preflight(Path(temporary))
        self.assertTrue(ready)
        self.assertEqual(status, "READY_IMPORTS")
        command = run_process.call_args.args[0]
        self.assertEqual(command[1:3], ["-c", "import torch; import trellis2; import o_voxel"])

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
            "TRELLIS2_SINGLE_VIEW_V001",
            "SEMANTIC_PROXY_REFERENCE_FITTED_V001",
            "UNIFIED_SEMANTIC_AUTHORING_V002",
            "SEMANTIC_DETAIL_AUTHORING_V003",
            "2026-08-29-local-blender-v003-review-v001.json",
            "2026-08-31-kaggle-semantic-authoring-v002-review.json",
            "build_ch101_unified_semantic_mesh.py",
            "build_ch101_semantic_detail_candidate.py",
            "BLOCKED_PROVIDER_ENTRYPOINT_UNVERIFIED",
            "run_trellis2_candidate.py",
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
