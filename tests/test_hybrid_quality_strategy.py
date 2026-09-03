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
from scripts.ai3d import run_spar3d_candidate
from scripts.ai3d.patch_spar3d_t4_compat import patch_runner
from scripts.ai3d.run_spar3d_candidate import (
    build_report as build_spar3d_report,
    dependency_preflight as dependency_preflight_spar3d,
    sanitize_provider_output,
)
from scripts.ai3d.quality_progress_gate import build_progress_gate, collect_history


ROOT = Path(__file__).resolve().parents[1]


class HybridQualityStrategyTests(unittest.TestCase):
    def test_spar3d_t4_compat_patch_switches_bfloat16_to_supported_dtype(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            runner = repo / "run.py"
            runner.write_text(
                '    print("Device used: ", device)\n'
                '                torch.autocast(device_type=device, dtype=torch.bfloat16)\n',
                encoding="utf-8",
            )
            with patch(
                "scripts.ai3d.patch_spar3d_t4_compat.git_head",
                return_value="fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1",
            ):
                report = patch_runner(repo)
                second = patch_runner(repo)
                patched = runner.read_text(encoding="utf-8")
        self.assertIn("torch.cuda.is_bf16_supported()", patched)
        self.assertIn("dtype=amp_dtype", patched)
        self.assertTrue(report["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(second["alreadyPresent"], ["runner.dynamic_amp_dtype", "runner.autocast_dtype"])
        self.assertTrue(second["providerCommitUnchanged"])

    def test_spar3d_preflight_requires_gpu_access_and_license_acknowledgements(self):
        gpu = [{"name": "NVIDIA T4", "memoryMb": 15360, "driverVersion": "test"}]
        torch = {
            "available": True,
            "cudaAvailable": True,
            "torchKernelSupportsDevice": True,
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, {}, clear=True):
            blocked = build_report("spar3d")
        self.assertEqual(blocked["status"], "BLOCKED_PROVIDER_PREFLIGHT")
        self.assertEqual(blocked["providerPreflight"]["minimumVramMb"], 8192)
        self.assertFalse(blocked["providerPreflight"]["hfTokenPresent"])
        self.assertFalse(blocked["providerPreflight"]["heavyweightInstallAllowed"])
        env = {
            "HF_TOKEN": "secret-is-not-recorded",
            "RE_CAMP_SPAR3D_ACCESS_ACK": "1",
            "RE_CAMP_SPAR3D_LICENSE_ACK": "1",
        }
        with patch("scripts.ai3d.colab_runtime_preflight.nvidia_gpus", return_value=gpu), patch(
            "scripts.ai3d.colab_runtime_preflight.torch_status", return_value=torch
        ), patch.dict(os.environ, env, clear=True):
            ready = build_report("spar3d")
        self.assertEqual(ready["status"], "READY_GPU_VISIBLE")
        self.assertTrue(ready["providerPreflight"]["heavyweightInstallAllowed"])
        self.assertNotIn("secret-is-not-recorded", json.dumps(ready))

    def test_spar3d_dependency_preflight_uses_notebook_python_and_import_only(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_spar3d_candidate.subprocess.run",
            return_value=type("Result", (), {"returncode": 0})(),
        ) as run_process:
            ready, status = dependency_preflight_spar3d(Path(temporary))
        self.assertTrue(ready)
        self.assertEqual(status, "READY_IMPORTS")
        command = run_process.call_args.args[0]
        self.assertEqual(command[0], __import__("sys").executable)
        self.assertIn("spar3d.system", command[2])

    def test_spar3d_dependency_preflight_reports_sanitized_import_failure(self):
        failure = type(
            "Result",
            (),
            {
                "returncode": 1,
                "stdout": '{"failures": [{"errorMessage": "No module named transparent_background", "errorType": "ModuleNotFoundError", "module": "spar3d.system"}]}\n',
                "stderr": "provider path and secret material must not be persisted",
            },
        )()
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_spar3d_candidate.subprocess.run",
            return_value=failure,
        ):
            ready, status = dependency_preflight_spar3d(Path(temporary))
        self.assertFalse(ready)
        self.assertEqual(
            status,
            "SPAR3D_DEPENDENCIES_IMPORT_FAILED:spar3d.system:ModuleNotFoundError:No module named transparent_background",
        )
        self.assertNotIn("provider path", status)
        self.assertNotIn("SHOULD_NOT_LEAK", status)

    def test_spar3d_dependency_preflight_isolates_each_import(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.ai3d.run_spar3d_candidate.subprocess.run",
            return_value=type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
        ) as run_process:
            ready, status = dependency_preflight_spar3d(Path(temporary))
        self.assertTrue(ready)
        self.assertEqual(status, "READY_IMPORTS")
        self.assertEqual(run_process.call_count, 1)
        command = run_process.call_args.args[0]
        self.assertIn("child = subprocess.run", command[2])
        self.assertIn("one child", command[2])
        self.assertIn("reversed(output_lines)", command[2])

    def test_spar3d_execution_diagnostic_is_sanitized_and_bounded(self):
        raw = (
            "Traceback (most recent call last):\n"
            "  File /kaggle/working/provider/run.py, line 7\n"
            "RuntimeError: CUDA out of memory for hf_abcdefghijklmnopqrstuvwxyz\n"
            "Authorization: Bearer secret-value-must-not-appear\n"
            "https://example.test/private?token=should-not-appear\n"
        )
        sanitized = sanitize_provider_output(raw)
        self.assertIn("RuntimeError", sanitized)
        self.assertIn("CUDA out of memory", sanitized)
        self.assertNotIn("/kaggle/working/provider", sanitized)
        self.assertNotIn("hf_abcdefghijklmnopqrstuvwxyz", sanitized)
        self.assertNotIn("secret-value-must-not-appear", sanitized)
        self.assertNotIn("should-not-appear", sanitized)
        self.assertLessEqual(len(sanitized.split(" | ")), 6)

    def test_spar3d_diagnostic_only_records_runtime_failure_without_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "provider"
            repo.mkdir()
            (repo / "run.py").write_text(
                '    print("Device used: ", device)\n'
                '                torch.autocast(device_type=device, dtype=torch.bfloat16)\n',
                encoding="utf-8",
            )
            image = root / "front.png"
            image.write_bytes(b"image")
            preflight = root / "preflight.json"
            preflight.write_text(
                json.dumps(
                    {
                        "provider": "spar3d",
                        "status": "READY_GPU_VISIBLE",
                        "providerPreflight": {
                            "vramSufficient": True,
                            "heavyweightInstallAllowed": True,
                            "hfTokenPresent": True,
                            "modelAccessAcknowledged": True,
                            "licenseTermsAcknowledged": True,
                        },
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "report.json"
            dependency_result = type(
                "Result",
                (),
                {"returncode": 0, "stdout": '{"failures": []}', "stderr": ""},
            )()
            provider_result = type(
                "Result",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "RuntimeError: CUDA out of memory token=secret-value",
                },
            )()
            with patch(
                "scripts.ai3d.run_spar3d_candidate.git_head",
                return_value="fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1",
            ), patch(
                "scripts.ai3d.run_spar3d_candidate.patch_runner",
                return_value={
                    "patchId": "SPAR3D_T4_BF16_TO_FP16_V001",
                    "providerCommitActual": "fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1",
                    "missing": [],
                    "providerCommitUnchanged": True,
                },
            ), patch(
                "scripts.ai3d.run_spar3d_candidate.subprocess.run",
                side_effect=[dependency_result, provider_result],
            ), patch(
                "scripts.ai3d.run_spar3d_candidate.sys.argv",
                [
                    "run_spar3d_candidate.py",
                    "--provider-repo",
                    str(repo),
                    "--input-image",
                    str(image),
                    "--output-dir",
                    str(root / "output"),
                    "--preflight",
                    str(preflight),
                    "--output-report",
                    str(report_path),
                    "--diagnostic-only",
                    "--execute",
                ],
            ):
                self.assertEqual(run_spar3d_candidate.main(), 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "SPAR3D_DIAGNOSTIC_FAILED")
        self.assertFalse(report["actualInference"])
        self.assertIn("CUDA out of memory", report["executionFailureDetail"])
        self.assertNotIn("secret-value", report["executionFailureDetail"])
        self.assertNotIn("candidateManifest", report)

    def test_spar3d_notebook_pins_transparent_background_flet_compatibility(self):
        notebook = json.loads(
            (ROOT / "notebooks" / "07_ch101_hybrid_quality_strategies.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        self.assertIn('flet==0.23.1', source)
        self.assertIn("OFFICIAL_REQUIREMENTS_NO_BUILD_ISOLATION_FLET_COMPAT", source)

    def test_spar3d_diagnostic_notebook_is_candidate_free_and_secret_safe(self):
        notebook = json.loads(
            (ROOT / "notebooks" / "08_ch101_spar3d_diagnostic.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        self.assertIn("--diagnostic-only", source)
        self.assertIn("candidateRegistered': False", source)
        self.assertIn("flet==0.23.1", source)
        self.assertIn("media.githubusercontent.com/media/siri2677/re-camp", source)
        self.assertIn("downloaded_image.verify()", source)
        self.assertNotIn("files.download", source)

    def test_spar3d_wrapper_requires_pinned_repo_and_keeps_review_gates_locked(self):
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
                        "provider": "spar3d",
                        "status": "READY_GPU_VISIBLE",
                        "providerPreflight": {
                            "vramSufficient": True,
                            "heavyweightInstallAllowed": True,
                            "hfTokenPresent": True,
                            "modelAccessAcknowledged": True,
                            "licenseTermsAcknowledged": True,
                        },
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            args = type(
                "Args",
                (),
                {
                    "provider_repo": repo,
                    "input_image": image,
                    "preflight": preflight,
                    "texture_resolution": 1024,
                    "target_count": 20000,
                },
            )()
            with patch(
                "scripts.ai3d.run_spar3d_candidate.git_head",
                return_value="fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1",
            ):
                report = build_spar3d_report(args)
        self.assertEqual(report["status"], "READY_TO_RUN_ONCE")
        self.assertEqual(report["officialEntrypoint"], "run.py")
        self.assertTrue(report["lowVramMode"])
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

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

    def test_orchestrator_pivots_to_spar3d_after_partcrafter_plateau(self):
        contract_path = ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json"

        def fake_runtime(provider):
            ready = provider == "spar3d"
            return {
                "provider": provider,
                "status": "READY_GPU_VISIBLE" if ready else "BLOCKED_PROVIDER_PREFLIGHT",
                "providerPreflight": {"heavyweightInstallAllowed": ready},
            }

        def fake_gate(provider, strategy_id, score_dir, history_records):
            plateau = strategy_id == "PARTCRAFTER_PART_LEVEL_V001"
            return {
                "status": "QUALITY_PLATEAU_SAME_STRATEGY" if plateau else "READY_NEW_STRATEGY",
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

        self.assertEqual(report["selectedStrategies"], ["SPAR3D_SINGLE_VIEW_V001"])
        self.assertTrue(report["strategies"]["SPAR3D_SINGLE_VIEW_V001"]["runAllowed"])
        self.assertTrue(report["strategies"]["SPAR3D_SINGLE_VIEW_V001"]["preflight"]["providerPreflight"]["heavyweightInstallAllowed"])
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

    def test_top_level_partcrafter_review_record_blocks_same_strategy(self):
        record = (
            ROOT
            / "docs"
            / "records"
            / "ch101-ai3d"
            / "2026-09-02-kaggle-partcrafter-v002-review.json"
        )
        history = collect_history(None, [record])
        matching = [
            item
            for item in history
            if item["strategyId"] == "PARTCRAFTER_PART_LEVEL_V001"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["overallScore"], 0.462276)
        self.assertTrue(matching[0]["rejected"])
        gate = build_progress_gate(
            provider="partcrafter",
            strategy_id="PARTCRAFTER_PART_LEVEL_V001",
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
            "OFFICIAL_REQUIREMENTS_NO_BUILD_ISOLATION",
            "SPAR3D_SETUP_FAILED",
            "setupFailureStep",
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
