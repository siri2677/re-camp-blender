from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.ai3d.common import (
    DEFAULT_CONTRACT_PATH,
    EXPECTED_GATE,
    EXPECTED_SOURCE_STATUS,
    load_contract,
    sha256_file,
)
from scripts.ai3d.colab_runtime_preflight import build_report
from scripts.ai3d.prepare_reference_views import prepare_views
from scripts.ai3d.rank_candidates import rank_reports
from scripts.ai3d.register_wonder3d_candidate import build_candidate_manifest
from scripts.ai3d.run_open_source_provider import build_command, run_provider_command
from scripts.ai3d.run_wonder3d_multiview import (
    build_generation_command,
    inspect_reusable_generation,
    mark_generation_reused,
    parse_args,
)
from scripts.ai3d.tripo_api import build_multiview_payload
from scripts.run_no_gpu_workstream import run_runtime_preflight


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

    def test_wonder3d_is_pinned_as_research_only_multiview_provider(self):
        wonder3d = self.contract["experimentalProviders"]["wonder3D"]
        self.assertEqual(len(wonder3d["commit"]), 40)
        self.assertEqual(wonder3d["generatedViewCount"], 6)
        self.assertEqual(wonder3d["generatedAzimuths"], [0, 45, 90, 180, -90, -45])
        self.assertEqual(wonder3d["meshExtraction"], "NeuS")
        self.assertFalse(wonder3d["fallbackEnabled"])
        self.assertFalse(wonder3d["unityInputAllowed"])
        self.assertNotIn("wonder3D", self.contract["providerPolicy"]["freeFallbackOrder"])

    def test_wonder3d_notebook_and_mesh_registration_keep_gate_locked(self):
        notebook = json.loads(
            (Path(__file__).parents[1] / "notebooks/06_ch101_wonder3d_multiview_experiment.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        for marker in (
            "run_wonder3d_multiview.py",
            "register_wonder3d_candidate.py",
            "test_mvdiffusion_seq.py",
            "NeuS",
            "REUSE_WONDER3D",
            "--reuse-existing",
            "REUSED",
            "unityInputAllowed",
        ):
            self.assertIn(marker, source)
        registration_source = Path("scripts/ai3d/register_wonder3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("WONDER3D_MULTIVIEW_NEUS_MESH", registration_source)
        self.assertIn("candidate_gate_fields", registration_source)

    def test_wonder3d_command_uses_pinned_six_view_pipeline(self):
        provider = self.contract["experimentalProviders"]["wonder3D"]
        command = build_generation_command(
            provider,
            Path("wonder3d-repo"),
            Path("references"),
            "CH101_front.png",
            Path("wonder3d-output"),
        )
        serialized = " ".join(command)
        self.assertIn("1gpu.yaml", serialized)
        self.assertIn("test_mvdiffusion_seq.py", serialized)
        self.assertIn("mvdiffusion-joint-ortho-6views.yaml", serialized)
        self.assertIn("CH101_front.png", serialized)
        self.assertEqual(provider["generatedViewCount"], 6)

    def test_wonder3d_notebook_preflights_gpu_before_heavy_setup(self):
        notebook = Path("notebooks/06_ch101_wonder3d_multiview_experiment.ipynb").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_adaptive_workstream.py", notebook)
        self.assertIn("ADAPTIVE_NO_GPU_COMPLETED", notebook)
        self.assertIn("GPU_PREFLIGHT", notebook)
        self.assertLess(
            notebook.index("run_adaptive_workstream.py"),
            notebook.index("tiny-cuda-nn"),
        )

    def test_wonder3d_candidate_registration_preserves_hash_and_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference_manifest = root / "reference-views-manifest.json"
            mesh = root / "mesh.ply"
            destination = root / "candidate" / "mesh.ply"
            reference_manifest.write_text("{\"reference\": true}\n", encoding="utf-8")
            destination.parent.mkdir(parents=True, exist_ok=True)
            mesh.write_bytes(b"ply\n")
            destination.write_bytes(mesh.read_bytes())
            manifest = build_candidate_manifest(
                self.contract,
                reference_manifest,
                mesh,
                destination,
            )
            self.assertEqual(manifest["sourceStage"], "WONDER3D_MULTIVIEW_NEUS_MESH")
            self.assertEqual(manifest["candidates"][0]["modelPath"], str(destination.resolve()))
            self.assertFalse(manifest["unityInputAllowed"])
            self.assertFalse(manifest["productionPromotionAllowed"])
            self.assertEqual(len(manifest["candidates"][0]["sha256"]), 64)

    def test_wonder3d_reuses_complete_six_view_report_and_keeps_gate_locked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "multiview"
            views_dir = output_dir / "views"
            views_dir.mkdir(parents=True)
            reference_manifest = root / "reference-views-manifest.json"
            reference_manifest.write_text('{"artCommit": "reference"}\n', encoding="utf-8")
            generated_files = []
            for index in range(6):
                view = views_dir / f"view_{index:02d}.png"
                view.write_bytes(f"view-{index}".encode("utf-8"))
                generated_files.append(str(view.relative_to(output_dir)))
            report_path = output_dir / "wonder3d-generation-report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "provider": "wonder3D",
                        "providerCommit": self.contract["experimentalProviders"]["wonder3D"]["commit"],
                        "providerRepoHead": self.contract["experimentalProviders"]["wonder3D"]["commit"],
                        "referenceManifestSha256": sha256_file(reference_manifest),
                        "generatedViewCount": 6,
                        "generatedAzimuths": [0, 45, 90, 180, -90, -45],
                        "generationStatus": "MULTIVIEW_GENERATED",
                        "status": "MULTIVIEW_GENERATED",
                        "generatedFiles": generated_files,
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            validation = inspect_reusable_generation(self.contract, reference_manifest, report_path)
            self.assertTrue(validation["reusable"], validation["reasons"])
            reused = mark_generation_reused(self.contract, report_path, validation)
            self.assertEqual(reused["status"], "REUSED")
            self.assertEqual(reused["generationStatus"], "MULTIVIEW_GENERATED")
            self.assertFalse(reused["actualInference"])
            self.assertFalse(reused["unityInputAllowed"])
            self.assertFalse(reused["productionPromotionAllowed"])

    def test_wonder3d_reuse_rejects_hash_commit_and_missing_file_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "multiview"
            output_dir.mkdir(parents=True)
            reference_manifest = root / "reference-views-manifest.json"
            reference_manifest.write_text('{"artCommit": "reference"}\n', encoding="utf-8")
            report_path = output_dir / "wonder3d-generation-report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "provider": "wonder3D",
                        "providerCommit": "wrong-commit",
                        "providerRepoHead": "wrong-commit",
                        "referenceManifestSha256": "0" * 64,
                        "generatedViewCount": 6,
                        "generatedAzimuths": [0, 45, 90, 180, -90, -45],
                        "generationStatus": "MULTIVIEW_GENERATED",
                        "generatedFiles": ["missing.png"] * 6,
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            validation = inspect_reusable_generation(self.contract, reference_manifest, report_path)
            self.assertFalse(validation["reusable"])
            self.assertIn("PROVIDER_COMMIT_MISMATCH", validation["reasons"])
            self.assertIn("REFERENCE_MANIFEST_SHA256_MISMATCH", validation["reasons"])
            self.assertIn("GENERATED_FILE_MISSING:missing.png", validation["reasons"])

    def test_wonder3d_reuse_environment_flag_can_force_regeneration(self):
        with patch.dict(os.environ, {"RE_CAMP_REUSE_WONDER3D": "0"}, clear=False):
            with patch(
                "sys.argv",
                [
                    "run_wonder3d_multiview.py",
                    "--provider-repo",
                    "provider",
                    "--reference-manifest",
                    "reference.json",
                    "--output-dir",
                    "output",
                ],
            ):
                args = parse_args()
        self.assertFalse(args.reuse_existing)

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
        self.assertIn("instant-mesh-base.yaml", " ".join(command))
        self.assertIn("--export_texmap", command)
        self.assertEqual(instantmesh["memoryProfile"], "T4_SAFE_BASE")
        self.assertEqual(instantmesh["view"], 4)

    def test_notebook_keeps_numeric_attempt_label_for_all_providers(self):
        notebook = json.loads(
            (Path(__file__).parents[1] / "notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        self.assertIn(
            "attempt_labels = [parent.name for parent in manifest_path.parents if parent.name.isdigit()]",
            source,
        )
        self.assertIn("attempt_label = attempt_labels[0] if attempt_labels else 'attempt_00'", source)

    def test_provider_failure_persists_diagnostic_logs_without_unlocking_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "provider-output"
            command = [
                "python",
                "-c",
                "import sys; print('stdout-diagnostic'); print('stderr-diagnostic', file=sys.stderr); sys.exit(7)",
            ]
            with self.assertRaises(Exception):
                run_provider_command(
                    command,
                    repo_dir=root,
                    output_dir=output_dir,
                    provider="instantmesh",
                    reference_view="right",
                )
            failure = json.loads((output_dir / "provider-failure.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "FAILED_PROVIDER_EXECUTION")
            self.assertEqual(failure["returnCode"], 7)
            self.assertFalse(failure["unityInputAllowed"])
            self.assertIn("stdout-diagnostic", (output_dir / "provider-stdout.log").read_text(encoding="utf-8"))
            self.assertIn("stderr-diagnostic", (output_dir / "provider-stderr.log").read_text(encoding="utf-8"))

    def test_notebook_caps_free_candidate_attempts_and_keeps_fallback(self):
        notebook = Path("notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(encoding="utf-8")
        self.assertIn("MAX_ATTEMPTS = 3", notebook)
        self.assertIn("provider_attempts = [PROVIDER, 'instantmesh', 'triposr'] if PROVIDER == 'sf3d' else [PROVIDER]", notebook)
        self.assertIn("foreground_ratios", notebook)
        self.assertIn("reference_views", notebook)
        self.assertIn("huggingface-hub==0.25.2", notebook)
        self.assertIn("huggingface-hub>=0.26.0,<1.0", notebook)
        self.assertIn("split_torch_state_dict_into_shards", notebook)
        self.assertIn("instantmesh_hf_compat_sitecustomize.py", notebook)
        self.assertIn("from diffusers import DiffusionPipeline", notebook)
        self.assertIn("KeyArray", Path("scripts/ai3d/instantmesh_hf_compat_sitecustomize.py").read_text(encoding="utf-8"))
        self.assertIn("SF3D model access may be gated", notebook)
        self.assertIn("git+https://github.com/tatsy/torchmcubes.git", notebook)
        self.assertIn("InstantMesh setup failed; continuing to next fallback", notebook)
        self.assertIn("--no-build-isolation", notebook)
        self.assertIn("TORCH_CUDA_ARCH_LIST", notebook)
        self.assertIn("import nvdiffrast.torch", notebook)
        self.assertIn("attempt_provider in {'instantmesh', 'triposr'}", notebook)
        self.assertIn("['front', 'right', 'back']", notebook)
        self.assertIn("RE_CAMP_REUSE_CANDIDATES", notebook)
        self.assertIn("status': 'REUSED'", notebook)
        self.assertIn("colab_runtime_preflight.py", notebook)
        self.assertIn("--material-mode", notebook)
        self.assertIn("'preserve'", notebook)
        self.assertIn("REFINED_REVIEW_CANDIDATE", notebook)
        self.assertIn("AUTO_ESTIMATED_NOT_APPROVED", notebook)

    def test_runtime_preflight_is_secret_free_and_gate_locked(self):
        source = Path("scripts/ai3d/colab_runtime_preflight.py").read_text(encoding="utf-8")
        self.assertIn("BLOCKED_GPU_UNAVAILABLE", source)
        self.assertIn("READY_NO_GPU_REQUIRED", source)
        self.assertIn('"wonder3D"', source)
        self.assertIn('"unityInputAllowed": False', source)
        self.assertNotIn("TRIPO_API_KEY", source)

    def test_wonder3d_runtime_preflight_requires_gpu_and_stays_locked(self):
        report = build_report("wonder3D")
        self.assertTrue(report["requiresGpu"])
        self.assertIn(report["status"], {"READY_GPU_VISIBLE", "BLOCKED_GPU_UNAVAILABLE"})
        self.assertFalse(report["unityInputAllowed"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_no_gpu_workstream_is_inference_free_and_gate_locked(self):
        source = Path("scripts/run_no_gpu_workstream.py").read_text(encoding="utf-8")
        self.assertIn('"workstream": "NO_GPU"', source)
        self.assertIn('"unityInputAllowed": False', source)
        self.assertIn("--skip-reference", source)
        self.assertIn('RE_CAMP_SOURCE_DIR', source)
        self.assertIn("validate_unity_character_handoff.py", source)
        self.assertNotIn("--execute", source)

    def test_no_gpu_runner_records_provider_preflight_without_treating_gpu_block_as_failure(self):
        result = run_runtime_preflight()
        self.assertIn(result["status"], {"PASS", "PASS_WITH_BLOCKED_PROVIDERS"})
        self.assertEqual(set(result["providers"]), {"sf3d", "instantmesh", "triposr", "wonder3D", "tripo"})
        self.assertEqual(result["providers"]["tripo"]["status"], "READY_NO_GPU_REQUIRED")
        for report in result["providers"].values():
            self.assertFalse(report["unityInputAllowed"])
            self.assertFalse(report["productionPromotionAllowed"])

    def test_no_gpu_execution_record_is_gate_locked_and_inference_free(self):
        record = json.loads(
            Path(
                "docs/records/ch101-ai3d/2026-08-19-no-gpu-workstream.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(record["actualInference"])
        self.assertEqual(record["sourceTreeCheck"], "PASS")
        self.assertEqual(record["unityHandoffValidation"], "PASS")
        self.assertEqual(record["runtimePreflight"]["stableFast3D"], "BLOCKED_GPU_UNAVAILABLE")
        self.assertEqual(record["runtimePreflight"]["tripoApi"], "READY_NO_GPU_REQUIRED_DRY_RUN_ONLY")
        self.assertEqual(record["steps"]["unitTests"]["count"], 16)
        self.assertEqual(record["steps"]["tripoMultiviewPayload"], "PASS_DRY_RUN")
        self.assertFalse(record["gate"]["unityInputAllowed"])
        self.assertFalse(record["gate"]["productionPromotionAllowed"])
        self.assertIn("Android build and device validation", record["blocked"])
        serialized = json.dumps(record)
        self.assertNotIn("API_KEY", serialized)
        self.assertNotIn("HF_TOKEN", serialized)

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
