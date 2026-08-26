from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from scripts.ai3d.common import (
    DEFAULT_CONTRACT_PATH,
    EXPECTED_GATE,
    EXPECTED_ROSTER_CHARACTERS,
    EXPECTED_SOURCE_STATUS,
    ROSTER_CONTRACT_PATH,
    load_contract,
    load_roster_contract_index,
    require_reference_manifest,
    sha256_file,
)
from scripts.ai3d.colab_runtime_preflight import build_report
from scripts.ai3d.build_final_evaluation_archive import build_archive
from scripts.ai3d.prepare_reference_views import prepare_views
from scripts.ai3d.prepare_roster_reference_views import prepare_roster
from scripts.ai3d.rank_candidates import rank_reports
from scripts.ai3d.register_wonder3d_candidate import build_candidate_manifest
from scripts.ai3d.run_open_source_provider import (
    build_command,
    classify_provider_failure,
    prepare_instantmesh_input,
    run_provider_command,
)
from scripts.ai3d.score_candidate_renders import (
    assess_vertical_polarity,
    evaluate_quality_hard_gates,
)
from scripts.ai3d.build_assisted_visual_review import (
    assess_score_report,
    build_review,
)
from scripts.ai3d.run_wonder3d_multiview import (
    build_generation_command,
    inspect_reusable_generation,
    mark_generation_reused,
    parse_args,
)
from scripts.ai3d.tripo_api import build_multiview_payload
from scripts.run_no_gpu_workstream import run_reference_dry_run, run_runtime_preflight


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

    def test_current_roster_contract_materializes_all_five_characters(self):
        roster = load_roster_contract_index(ROSTER_CONTRACT_PATH)
        self.assertEqual(
            [entry["character"] for entry in roster["characters"]],
            list(EXPECTED_ROSTER_CHARACTERS),
        )
        sources = set()
        for character in EXPECTED_ROSTER_CHARACTERS:
            contract = load_contract(ROSTER_CONTRACT_PATH, character)
            self.assertEqual(contract["character"], character)
            self.assertEqual(
                contract["contractVersion"], "current-roster-ai3d-pipeline-v001"
            )
            self.assertFalse(contract["statusPolicy"]["unityInputAllowed"])
            self.assertGreaterEqual(
                contract["candidateAcceptance"]["geometryHardGates"][
                    "minimumLargestComponentVertexRatio"
                ],
                0.9,
            )
            sources.add(contract["authoritativeSource"])
        self.assertEqual(len(sources), 5)
        ch101 = load_contract(ROSTER_CONTRACT_PATH, "CH101")
        self.assertEqual(
            ch101["generationStrategy"]["profile"],
            "CH101_V005_IDENTITY_RECOVERY",
        )
        self.assertEqual(
            ch101["generationStrategy"]["singleViewReferenceSequence"],
            ["front", "front", "front"],
        )
        self.assertEqual(len(ch101["auxiliaryReferences"]), 3)

    def test_current_roster_reference_preflight_is_no_gpu_and_gate_locked(self):
        roster = load_roster_contract_index(ROSTER_CONTRACT_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            art_root = root / "art"
            output_root = root / "output"
            for entry in roster["characters"]:
                for key in ("authoritativeSource",):
                    path = art_root / entry[key]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(entry["character"].encode("utf-8"))
                generation = art_root / entry["generationSource"]["path"]
                generation.parent.mkdir(parents=True, exist_ok=True)
                generation.write_bytes(entry["character"].encode("utf-8"))
                for reference in entry.get("auxiliaryReferences", []):
                    auxiliary = art_root / reference["path"]
                    auxiliary.parent.mkdir(parents=True, exist_ok=True)
                    auxiliary.write_bytes(entry["character"].encode("utf-8"))
            report = prepare_roster(
                art_root=art_root,
                output_root=output_root,
                contract_path=ROSTER_CONTRACT_PATH,
                dry_run=True,
            )
            self.assertEqual(
                report["status"], "CURRENT_ROSTER_REFERENCE_VIEW_PLAN"
            )
            self.assertEqual(len(report["characters"]), 5)
            self.assertFalse(report["gpuRequired"])
            self.assertFalse(report["actualInference"])
            self.assertFalse(report["unityInputAllowed"])
            ch101_manifest = prepare_views(
                art_root=art_root,
                output_dir=output_root / "CH101" / "reference-views",
                contract_path=ROSTER_CONTRACT_PATH,
                character="CH101",
                dry_run=True,
            )
            self.assertEqual(len(ch101_manifest["auxiliaryReferences"]), 3)
            self.assertEqual(
                ch101_manifest["generationStrategy"]["profile"],
                "CH101_V005_IDENTITY_RECOVERY",
            )

    def test_no_gpu_reference_preflight_materializes_views_before_provider_dry_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            art_root = Path(temporary) / "art"
            art_root.mkdir()
            calls = []

            def record_step(name, command, env=None, cwd=None):
                calls.append((name, command))
                return {
                    "name": name,
                    "status": "PASS",
                    "returnCode": 0,
                    "command": command,
                    "stdoutTail": (
                        "CURRENT_ROSTER_REFERENCE_VIEWS_READY"
                        if name == "prepare-current-roster-reference-views"
                        else "tripo-dry-run-plan.json"
                    ),
                    "stderrTail": "",
                }

            with patch("scripts.run_no_gpu_workstream.run_step", side_effect=record_step):
                steps = run_reference_dry_run(art_root, "CH105")
            self.assertEqual(
                [step["status"] for step in steps], ["PASS", "PASS"], steps
            )
            self.assertIn(
                "CURRENT_ROSTER_REFERENCE_VIEWS_READY",
                steps[0]["stdoutTail"],
            )
            self.assertIn("tripo-dry-run-plan.json", steps[1]["stdoutTail"])
            prepare_command = calls[0][1]
            self.assertIn("prepare_roster_reference_views.py", prepare_command[1])
            self.assertNotIn("--dry-run", prepare_command)
            provider_command = calls[1][1]
            self.assertIn("--character", provider_command)
            self.assertEqual(provider_command[provider_command.index("--character") + 1], "CH105")

    def test_ai3d_notebook_uses_roster_character_switch(self):
        source = Path("notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(
            encoding="utf-8"
        )
        self.assertIn("RE_CAMP_CHARACTER_CODE", source)
        self.assertIn("current_roster_ai3d_pipeline_v001.json", source)
        self.assertIn("--character", source)
        self.assertIn("--integrity-blend", source)

    def test_review_asset_uses_character_specific_socket_contract(self):
        source = Path("scripts/blender/build_ai3d_review_asset.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("character_code = ranking.get", source)
        self.assertIn("socket_locations", source)
        for character in EXPECTED_ROSTER_CHARACTERS:
            self.assertIn(f'"{character}"', source)
        self.assertNotIn('entry["code"] == "CH101"', source)

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
            "RE_CAMP_NEUS_END_ITER",
            "RE_CAMP_NEUS_SAVE_FREQ",
            "RE_CAMP_NEUS_VAL_MESH_FREQ",
            "val_mesh_freq",
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

    def test_wonder3d_command_uses_the_notebook_interpreter(self):
        provider = self.contract["experimentalProviders"]["wonder3D"]
        command = build_generation_command(
            provider,
            Path("wonder3d-repo"),
            Path("references"),
            "CH101_front.png",
            Path("wonder3d-output"),
        )
        self.assertEqual(
            command[:3],
            [sys.executable, "-m", "accelerate.commands.accelerate_cli"],
        )

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

    def test_wonder3d_t4_compatibility_and_neus_staging_are_recorded(self):
        notebook = Path("notebooks/06_ch101_wonder3d_multiview_experiment.ipynb").read_text(
            encoding="utf-8"
        )
        for marker in (
            "transformers==4.38.2",
            "tokenizers==0.15.2",
            "onnxruntime==1.20.1",
            "NEUS_INPUT_ROOT",
            "RE_CAMP_NEUS_WORKERS",
            "NEUS_DIR / 'exp' / 'neus' / NEUS_CASE",
        ):
            self.assertIn(marker, notebook)
        self.assertIn("is_offline_mode", Path("scripts/ai3d/wonder3d_compat/sitecustomize.py").read_text(encoding="utf-8"))
        self.assertIn("torch.matmul", Path("scripts/ai3d/wonder3d_compat/xformers/ops.py").read_text(encoding="utf-8"))

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

    def test_downloaded_reference_manifest_resolves_archived_view_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            views = {}
            for name in ("front", "right", "back"):
                view_path = root / f"CH101_{name}.png"
                view_path.write_bytes(name.encode("utf-8"))
                views[name] = {
                    "path": f"/content/re-camp-ai3d/CH101/reference-views/{view_path.name}",
                    "sha256": sha256_file(view_path),
                }
            manifest_path = root / "reference-views-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "contractVersion": self.contract["contractVersion"],
                        "character": "CH101",
                        "artCommit": self.contract["artLock"]["commit"],
                        "views": views,
                        "unityInputAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            resolved = require_reference_manifest(manifest_path, self.contract)
            for name in views:
                self.assertEqual(Path(resolved["views"][name]["path"]).parent, root.resolve())

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

    def test_instantmesh_foreground_input_is_derived_without_merging_auxiliary_art(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "front.png"
            image = Image.new("RGBA", (128, 128), (255, 255, 255, 255))
            ImageDraw.Draw(image).rectangle((48, 16, 80, 112), fill=(20, 80, 160, 255))
            image.save(source)
            derived, metadata = prepare_instantmesh_input(source, root / "provider", 0.8)
            self.assertTrue(derived.is_file())
            self.assertEqual(metadata["mode"], "SINGLE_VIEW_FOREGROUND_SCALE")
            self.assertEqual(metadata["foregroundRatio"], 0.8)
            self.assertFalse(metadata["auxiliaryReferencesMerged"])
            self.assertEqual(metadata["sourceImageSha256"], sha256_file(source))
            with Image.open(derived) as normalized:
                self.assertEqual(normalized.size, (128, 128))
                self.assertEqual(normalized.getpixel((0, 0))[:3], (255, 255, 255))

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

    def test_provider_failure_classification_is_secret_free_and_actionable(self):
        self.assertEqual(
            classify_provider_failure("", "401 Client Error: Unauthorized; GatedRepoError"),
            "HF_GATED_MODEL_AUTH_REQUIRED",
        )
        self.assertEqual(
            classify_provider_failure("", "CUDA error: 209 nvdiffrast"),
            "CUDA_EXTENSION_INCOMPATIBLE_WITH_DEVICE",
        )
        self.assertEqual(
            classify_provider_failure("", "no kernel image is available for execution on the device"),
            "CUDA_KERNEL_NOT_COMPILED_FOR_DEVICE",
        )

    def test_notebook_caps_free_candidate_attempts_and_keeps_fallback(self):
        notebook = Path("notebooks/05_ch101_ai3d_free_autobuild.ipynb").read_text(encoding="utf-8")
        self.assertIn("MAX_ATTEMPTS = 3", notebook)
        self.assertIn("EVAL_ATTEMPT = os.environ.get('RE_CAMP_EVAL_ATTEMPT', 'ALL')", notebook)
        self.assertIn("APPLY_VERTICAL_POLARITY_CORRECTION = os.environ.get('RE_CAMP_APPLY_VERTICAL_CORRECTION', '1')", notebook)
        self.assertIn("KAGGLE_KERNEL_RUN_TYPE", notebook)
        self.assertIn("RE_CAMP_CONTENT_ROOT", notebook)
        self.assertIn("RE_CAMP_GIT_CLONE_DEPTH", notebook)
        self.assertIn("--depth', GIT_CLONE_DEPTH", notebook)
        self.assertIn("flush=True", notebook)
        self.assertIn("BLENDER_PYTHON_SITE", notebook)
        self.assertIn("bpy/mathutils", notebook)
        self.assertIn("from kaggle_secrets import UserSecretsClient", notebook)
        self.assertIn("read_runtime_secret('HF_TOKEN')", notebook)
        self.assertIn("Archive retained at", notebook)
        self.assertIn("provider_attempts = [PROVIDER, 'triposr', 'instantmesh'] if PROVIDER == 'sf3d' and LEGACY_PASCAL_GPU", notebook)
        self.assertIn("ensure_legacy_torch()", notebook)
        self.assertIn("SKIPPED_NVDIFFRAST_TOOLKIT_INCOMPATIBLE", notebook)
        self.assertIn("foreground_ratios", notebook)
        self.assertIn("reference_views", notebook)
        self.assertIn("generation_strategy", notebook)
        self.assertIn("singleViewReferenceSequence", notebook)
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
        self.assertIn("DEFER_TO_HUMAN_REVIEW", notebook)
        self.assertIn("--assisted-visual-review", notebook)
        self.assertIn("build_gate_b_review_package.py", notebook)
        self.assertIn("GATE_B_CONTACT_SHEET", notebook)
        self.assertIn("GATE_B_PACKAGE_MANIFEST", notebook)

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
        self.assertIn(
            report["status"],
            {"READY_GPU_VISIBLE", "BLOCKED_GPU_UNAVAILABLE", "BLOCKED_GPU_UNSUPPORTED"},
        )
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
        self.assertIn('choices=("neutral", "preserve", "palette")', source)
        self.assertIn('"materialMode": args.material_mode', source)
        self.assertIn("apply_palette_review_materials", source)
        self.assertIn("has_reviewable_imported_material", source)
        self.assertIn("GENERIC_IMPORTED_MATERIAL_NAMES", source)
        self.assertIn('"skin": (0.974, 0.891, 0.814, 1.0)', source)
        self.assertIn('PALETTE_REGION_ALGORITHM = "CH101_REVIEW_BLOCKING_XZ_POSITIVE_X_FRONT_V003"', source)
        self.assertIn("world_normal.x > 0.2", source)
        self.assertIn("global_minimum: Vector | None = None", source)
        self.assertIn("global_height = max(global_maximum.z - global_minimum.z, 1e-6)", source)
        self.assertIn('"review_palette_assignment_counts"', source)
        self.assertIn('"paletteAlgorithm":', source)
        self.assertIn('0.47:', source)
        self.assertIn('abs(normalized_x) > 0.34', source)
        self.assertIn('hasattr(bpy.ops.wm, "obj_import")', source)
        self.assertIn('hasattr(bpy.ops.wm, "ply_import")', source)
        self.assertIn('"paletteFallbackUsed": palette_fallback_used', source)
        self.assertIn('"--invert-up-axis"', source)
        self.assertIn('"verticalPolarityCorrectionApplied"', source)

    def test_vertical_polarity_detection_requires_rerender_before_review(self):
        upright = {"orientationScore": 0.39}
        vertically_flipped = {"orientationScore": 0.46}
        result = assess_vertical_polarity(upright, vertically_flipped, 0.02)
        self.assertEqual(result["status"], "UPSIDE_DOWN_DETECTED")
        self.assertTrue(result["correctionRequired"])
        self.assertAlmostEqual(result["scoreImprovement"], 0.07)
        self.assertEqual(
            self.contract["candidateAcceptance"]["minimumVerticalPolarityImprovement"],
            0.02,
        )

    def test_score_report_labels_face_metric_as_non_semantic(self):
        source = Path("scripts/ai3d/score_candidate_renders.py").read_text(encoding="utf-8")
        self.assertIn("UPPER_IMAGE_EDGE_OVERLAP_NOT_SEMANTIC_FACE_IDENTITY", source)
        self.assertIn("ALPHA_REVIEW_ROUTING_ONLY_NOT_GATE_B_APPROVAL", source)

    def test_evaluation_restores_exported_review_palette_by_material_name(self):
        source = Path("scripts/blender/evaluate_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("REVIEW_PALETTE_DISPLAY_COLORS", source)
        self.assertIn('f"_palette_{key}" in material_name', source)
        self.assertIn("base_color.default_value = color", source)

    def test_strict_visual_review_rejects_current_gray_generic_candidate(self):
        report = {
            "contractVersion": self.contract["contractVersion"],
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "candidateId": "CH101-CURRENT-GRAY-CANDIDATE",
            "candidateSha256": "a" * 64,
            "overallScore": 0.529061,
            "silhouetteScore": 0.452165,
            "appearanceScore": 0.540615,
            "colorScore": 0.300492,
            "faceDetailScore": 0.808445,
            "technicalScore": 1.0,
            "eligibleForHumanReview": True,
            "qualityHardGateAudit": {"status": "PASS"},
            "metricLimitations": {
                "faceDetailScore": "UPPER_IMAGE_EDGE_OVERLAP_NOT_SEMANTIC_FACE_IDENTITY"
            },
            "sourceStatus": EXPECTED_SOURCE_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        }
        decision = assess_score_report(self.contract, report)
        self.assertEqual(decision["disposition"], "REJECT")
        self.assertIn("OUTFIT_COLOR_BLOCKING_WEAK", decision["reasonCodes"])
        self.assertIn("SILHOUETTE_PROPORTION_MISMATCH", decision["reasonCodes"])
        review = build_review(self.contract, [(Path("current-score.json"), report)])
        self.assertEqual(review["recommendation"], "REJECT_GATE_B_AND_REGENERATE")
        self.assertEqual(review["summary"]["rejectedCandidateCount"], 1)
        self.assertEqual(review["humanGateBDecision"], EXPECTED_GATE)
        self.assertFalse(review["unityInputAllowed"])
        self.assertFalse(review["productionPromotionAllowed"])

    def test_strict_visual_review_defers_strong_candidate_without_approving(self):
        report = {
            "contractVersion": self.contract["contractVersion"],
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "candidateId": "CH101-STRONG-CANDIDATE",
            "candidateSha256": "b" * 64,
            "overallScore": 0.65,
            "silhouetteScore": 0.60,
            "appearanceScore": 0.60,
            "colorScore": 0.45,
            "faceDetailScore": 0.35,
            "technicalScore": 0.95,
            "eligibleForHumanReview": True,
            "qualityHardGateAudit": {"status": "PASS"},
            "metricLimitations": {},
            "sourceStatus": EXPECTED_SOURCE_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        }
        decision = assess_score_report(self.contract, report)
        self.assertEqual(decision["disposition"], "DEFER_TO_HUMAN_REVIEW")
        review = build_review(self.contract, [(Path("strong-score.json"), report)])
        self.assertEqual(review["recommendation"], "DEFER_TO_HUMAN_GATE_B_REVIEW")
        self.assertEqual(review["candidateReviews"][0]["disposition"], "DEFER_TO_HUMAN_REVIEW")
        self.assertEqual(review["humanGateBDecision"], EXPECTED_GATE)
        self.assertFalse(review["unityInputAllowed"])
        self.assertFalse(review["productionPromotionAllowed"])

    def test_geometry_hard_gate_rejects_detached_primary_mesh(self):
        policy = self.contract["candidateAcceptance"]
        evaluation = {
            "metrics": {
                "geometryIntegrity": {
                    "status": "GEOMETRY_INTEGRITY_COLLECTED",
                    "largestComponentVertexRatio": 0.84,
                    "significantComponentCount": 4,
                    "looseVertexRatio": 0.0,
                    "nonManifoldEdgeRatio": 0.0,
                    "degenerateTriangleRatio": 0.0,
                }
            }
        }
        render_integrity = {
            "minimumLargestComponentAreaRatio": 0.95,
            "maximumSignificantComponentCount": 2,
        }
        passed, failures, audit = evaluate_quality_hard_gates(
            evaluation, render_integrity, policy
        )
        self.assertFalse(passed)
        self.assertEqual(audit["status"], "FAIL")
        self.assertIn("LARGEST_CONNECTED_COMPONENT_BELOW_MINIMUM", failures)

    def test_geometry_hard_gate_requires_pre_export_integrity_report(self):
        passed, failures, _ = evaluate_quality_hard_gates(
            {"metrics": {}},
            {
                "minimumLargestComponentAreaRatio": 1.0,
                "maximumSignificantComponentCount": 1,
            },
            self.contract["candidateAcceptance"],
        )
        self.assertFalse(passed)
        self.assertIn("GEOMETRY_INTEGRITY_REPORT_MISSING", failures)

    def test_notebooks_use_pre_export_blend_for_topology_hard_gate(self):
        evaluator = Path("scripts/blender/evaluate_ai3d_candidate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"--integrity-blend"', evaluator)
        self.assertIn('"--reuse-normalized-blend"', evaluator)
        self.assertIn('"REUSED_NORMALIZED_BLEND"', evaluator)
        self.assertIn('"PRE_EXPORT_REFINED_BLEND"', evaluator)
        for notebook_name in (
            "05_ch101_ai3d_free_autobuild.ipynb",
            "06_ch101_wonder3d_multiview_experiment.ipynb",
        ):
            source = Path("notebooks", notebook_name).read_text(encoding="utf-8")
            self.assertIn("--integrity-blend", source)

    def test_ai3d_notebooks_auto_correct_upside_down_candidates(self):
        for notebook_name in (
            "05_ch101_ai3d_free_autobuild.ipynb",
            "06_ch101_wonder3d_multiview_experiment.ipynb",
        ):
            source = Path("notebooks", notebook_name).read_text(encoding="utf-8")
            self.assertIn("orientationValidation", source)
            self.assertIn("correctionRequired", source)
            self.assertIn("--invert-up-axis", source)
            self.assertIn("VERTICAL_POLARITY_CORRECTION_FAILED", source)

    def test_ai3d_notebooks_can_reuse_normalized_blend_for_renderer_reruns(self):
        for notebook_name in (
            "05_ch101_ai3d_free_autobuild.ipynb",
            "06_ch101_wonder3d_multiview_experiment.ipynb",
        ):
            source = Path("notebooks", notebook_name).read_text(encoding="utf-8")
            self.assertIn("RE_CAMP_REUSE_NORMALIZED_BLEND", source)
            self.assertIn("--reuse-normalized-blend", source)

    def test_workbench_material_sync_prevents_false_gray_render(self):
        source = Path("scripts/blender/evaluate_ai3d_candidate.py").read_text(encoding="utf-8")
        self.assertIn("sync_workbench_material_colors", source)
        self.assertIn('material.diffuse_color = tuple(base_color.default_value)', source)
        self.assertIn('"workbenchMaterialsSynced": workbench_materials_synced', source)
        self.assertIn('scene.render.engine = "BLENDER_EEVEE_NEXT"', source)
        self.assertIn('"renderEngine": bpy.context.scene.render.engine', source)

    def test_review_asset_audits_and_repairs_failed_bone_heat_weights(self):
        source = Path("scripts/blender/build_ai3d_review_asset.py").read_text(encoding="utf-8")
        self.assertIn("audit_weights", source)
        self.assertIn("apply_nearest_bone_fallback", source)
        self.assertIn("FALLBACK_NEAREST_BONE_WEIGHTED_FOR_REVIEW", source)
        self.assertIn('"weightAudit": weight_audit', source)

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

    def test_complete_local_candidate_evaluation_is_persisted_and_gate_locked(self):
        record = json.loads(
            Path(
                "docs/records/ch101-ai3d/2026-08-20-complete-local-candidate-evaluation-v001.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            record["evaluationCompleteness"],
            "COMPLETE_FOR_ALL_SIX_AVAILABLE_CANDIDATES",
        )
        self.assertEqual(len(record["ranking"]), 6)
        self.assertEqual(record["automatedDecision"]["eligibleCandidateCount"], 3)
        self.assertEqual(
            record["automatedDecision"]["selectedCandidate"],
            "03-CH101-TRIPOSR-001",
        )
        self.assertEqual(record["visualReview"]["humanGateBDecision"], "PENDING_HUMAN_REVIEW")
        self.assertTrue(record["visualReview"]["recommendation"].startswith("REJECT_GATE_B"))
        self.assertEqual(record["reviewAsset"]["weightAudit"]["status"], "PASS")
        self.assertEqual(record["reviewAsset"]["weightAudit"]["unweightedVertexCount"], 0)
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
            "sourceStatus": EXPECTED_SOURCE_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
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

    def test_ranking_rejects_any_production_promotion_flag(self):
        report = {
            "contractVersion": self.contract["contractVersion"],
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "candidateId": "CH101-ILLEGAL",
            "sourceStatus": EXPECTED_SOURCE_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": True,
        }
        with self.assertRaisesRegex(ValueError, "production promotion"):
            rank_reports(self.contract, [(Path("illegal.json"), report)])

    def test_assisted_visual_review_can_reject_but_never_approve_gate_b(self):
        base = {
            "contractVersion": self.contract["contractVersion"],
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "candidateId": "CH101-HIGH",
            "candidatePath": "candidate.glb",
            "candidateSha256": "a" * 64,
            "overallScore": 0.7,
            "silhouetteScore": 0.6,
            "technicalScore": 0.8,
            "eligibleForHumanReview": True,
            "sourceStatus": EXPECTED_SOURCE_STATUS,
            "gateB": EXPECTED_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
        }
        review = {
            "reviewVersion": "test-review-v001",
            "character": "CH101",
            "artCommit": self.contract["artLock"]["commit"],
            "reviewerClass": "ASSISTED_VISUAL_QA_NOT_HUMAN_GATE_B",
            "humanGateBDecision": "PENDING_HUMAN_REVIEW",
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
            "candidateReviews": [
                {
                    "candidateId": "CH101-HIGH",
                    "candidateSha256": "a" * 64,
                    "disposition": "REJECT",
                    "reasonCodes": ["FACE_IDENTITY_NOT_RECOGNIZABLE"],
                }
            ],
        }
        result = rank_reports(
            self.contract, [(Path("high.json"), base)], review
        )
        self.assertIsNone(result["selectedCandidate"])
        self.assertEqual(
            result["status"],
            "REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW",
        )
        self.assertEqual(
            result["automatedSelectedCandidate"]["candidateId"], "CH101-HIGH"
        )
        self.assertFalse(result["unityInputAllowed"])

        review["candidateReviews"][0]["disposition"] = "APPROVE"
        with self.assertRaisesRegex(ValueError, "cannot approve"):
            rank_reports(self.contract, [(Path("high.json"), base)], review)

    def test_final_evaluation_archive_is_deterministic_and_excludes_review_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evaluation_root = root / "evaluation"
            references = evaluation_root / "reference-views"
            candidate = evaluation_root / "evaluation-corrected" / "candidate"
            references.mkdir(parents=True)
            candidate.mkdir(parents=True)
            (references / "front.png").write_bytes(b"front")
            (candidate / "candidate_refined.glb").write_bytes(b"mesh")
            (candidate / "candidate_refined_NOT_PRODUCTION.blend").write_bytes(
                b"blend"
            )
            (candidate / "candidate_normalized_NOT_PRODUCTION.blend").write_bytes(
                b"excluded-normalized"
            )
            (evaluation_root / "ranking-manifest-hard-gated.json").write_text(
                json.dumps({"unityInputAllowed": False}), encoding="utf-8"
            )
            (evaluation_root / "ranking-manifest-final-reviewed.json").write_text(
                json.dumps(
                    {
                        "character": "CH101",
                        "artCommit": "art-commit",
                        "status": "REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW",
                        "selectedCandidate": None,
                        "assistedVisualReview": {"rejectedCandidateCount": 3},
                        "gateB": "PENDING_HUMAN_REVIEW",
                        "unityInputAllowed": False,
                        "productionPromotionAllowed": False,
                    }
                ),
                encoding="utf-8",
            )
            evidence = root / "review.json"
            evidence.write_text("{}\n", encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            first_summary = build_archive(
                evaluation_root, first, "tools-commit", [evidence]
            )
            second_summary = build_archive(
                evaluation_root, second, "tools-commit", [evidence]
            )
            self.assertEqual(first_summary["sha256"], second_summary["sha256"])
            self.assertFalse(first_summary["reviewAssetIncluded"])
            self.assertEqual(first_summary["verification"]["status"], "PASS")
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertIn("PACKAGE-MANIFEST.json", names)
                self.assertFalse(any("review-corrected" in name for name in names))
                self.assertFalse(
                    any("_normalized_NOT_PRODUCTION.blend" in name for name in names)
                )
                manifest = json.loads(archive.read("PACKAGE-MANIFEST.json"))
                self.assertIsNone(manifest["selectedCandidate"])
                self.assertFalse(manifest["unityInputAllowed"])


if __name__ == "__main__":
    unittest.main()
