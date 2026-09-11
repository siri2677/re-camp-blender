import argparse
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_adaptive_workstream.py"
SPEC = importlib.util.spec_from_file_location("run_adaptive_workstream", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AdaptiveWorkstreamTests(unittest.TestCase):
    def make_args(self, provider="wonder3D", force_mode="auto"):
        return argparse.Namespace(
            provider=provider,
            art_root=ROOT.parent / "re-camp-art",
            skip_reference=True,
            output=None,
            force_mode=force_mode,
        )

    @staticmethod
    def preflight(provider, status, gpu_count=0):
        return {
            "provider": provider,
            "status": status,
            "requiresGpu": provider != "tripo",
            "gpuCount": gpu_count,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        }

    @staticmethod
    def successful_no_gpu(_args):
        return {
            "workstream": "NO_GPU",
            "status": "PASS_WITH_BLOCKED_OR_SKIPPED_EXTERNAL_STEPS",
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        }

    def test_visible_gpu_selects_provider_notebook_without_running_no_gpu(self):
        calls = []

        def unexpected_no_gpu(args):
            calls.append(args)
            return self.successful_no_gpu(args)

        report = MODULE.build_adaptive_report(
            self.make_args(),
            runtime_preflight=self.preflight("wonder3D", "READY_GPU_VISIBLE", 1),
            no_gpu_builder=unexpected_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "GPU")
        self.assertEqual(report["status"], "READY_GPU_WORKSTREAM")
        self.assertTrue(report["gpuExecutionAllowed"])
        self.assertEqual(calls, [])

    def test_missing_gpu_automatically_runs_no_gpu_workstream(self):
        calls = []

        def record_no_gpu(args):
            calls.append(args)
            return self.successful_no_gpu(args)

        report = MODULE.build_adaptive_report(
            self.make_args(),
            runtime_preflight=self.preflight("wonder3D", "BLOCKED_GPU_UNAVAILABLE"),
            no_gpu_builder=record_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "NO_GPU")
        self.assertEqual(report["status"], "ADAPTIVE_NO_GPU_COMPLETED")
        self.assertEqual(len(calls), 1)
        self.assertFalse(report["gpuExecutionAllowed"])

    def test_visible_but_unsupported_gpu_automatically_runs_no_gpu_workstream(self):
        calls = []

        def record_no_gpu(args):
            calls.append(args)
            return self.successful_no_gpu(args)

        preflight = self.preflight("wonder3D", "READY_GPU_VISIBLE", 1)
        preflight["torch"] = {"torchKernelSupportsDevice": False}
        report = MODULE.build_adaptive_report(
            self.make_args(),
            runtime_preflight=preflight,
            no_gpu_builder=record_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "NO_GPU")
        self.assertEqual(report["status"], "ADAPTIVE_NO_GPU_COMPLETED")
        self.assertEqual(len(calls), 1)
        self.assertFalse(report["gpuExecutionAllowed"])

    def test_tripo_remains_available_without_gpu_but_never_unlocks_gate(self):
        report = MODULE.build_adaptive_report(
            self.make_args(provider="tripo"),
            runtime_preflight=self.preflight("tripo", "READY_NO_GPU_REQUIRED"),
            no_gpu_builder=self.successful_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "NON_GPU_PROVIDER")
        self.assertEqual(report["status"], "READY_NON_GPU_PROVIDER")
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_force_no_gpu_runs_maintenance_even_when_gpu_is_visible(self):
        report = MODULE.build_adaptive_report(
            self.make_args(force_mode="no-gpu"),
            runtime_preflight=self.preflight("wonder3D", "READY_GPU_VISIBLE", 1),
            no_gpu_builder=self.successful_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "NO_GPU")
        self.assertEqual(report["status"], "ADAPTIVE_NO_GPU_COMPLETED")

    def test_forced_gpu_mode_fails_closed_when_gpu_is_missing(self):
        report = MODULE.build_adaptive_report(
            self.make_args(force_mode="gpu"),
            runtime_preflight=self.preflight("wonder3D", "BLOCKED_GPU_UNAVAILABLE"),
            no_gpu_builder=self.successful_no_gpu,
        )
        self.assertEqual(report["selectedWorkstream"], "BLOCKED_FORCED_GPU")
        self.assertEqual(report["status"], "BLOCKED_FORCED_GPU_UNAVAILABLE")
        self.assertFalse(report["gpuExecutionAllowed"])

    def test_provider_notebooks_use_adaptive_runner_and_guard_heavy_cells(self):
        for notebook_name in (
            "05_ch101_ai3d_free_autobuild.ipynb",
            "06_ch101_wonder3d_multiview_experiment.ipynb",
        ):
            notebook = json.loads((ROOT / "notebooks" / notebook_name).read_text(encoding="utf-8"))
            code = "\n".join(
                "".join(cell.get("source", []))
                for cell in notebook["cells"]
                if cell.get("cell_type") == "code"
            )
            self.assertIn("run_adaptive_workstream.py", code)
            self.assertIn("ADAPTIVE_NO_GPU_COMPLETED", code)
            self.assertIn("GPU_PROVIDER_WORKSTREAM_NOT_SELECTED", code)
            self.assertIn("unityInputAllowed': False", code)

        wonder_notebook = (
            ROOT / "notebooks" / "06_ch101_wonder3d_multiview_experiment.ipynb"
        ).read_text(encoding="utf-8")
        self.assertIn("adaptive_report['selectedWorkstream'] == 'GPU'", wonder_notebook)
        self.assertNotIn("GPU_PROBE = 0, 'reused-existing-output'", wonder_notebook)


if __name__ == "__main__":
    unittest.main()
