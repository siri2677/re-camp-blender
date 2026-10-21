import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from scripts.ai3d import recover_spar3d_reference_artifact as recovery
from scripts.ai3d import review_recovered_spar3d_artifact as review


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.front = self.root / "front.png"
        Image.new("RGBA", (16, 16), (30, 90, 160, 255)).save(self.front)
        self.out = self.root / "recovery"
        self.argv = ["recover", "--front-image", str(self.front), "--output-dir", str(self.out)]

    def test_input_mismatch_never_invokes_provider(self):
        with patch("sys.argv", self.argv + ["--execute"]), patch.object(recovery.subprocess, "run") as run:
            self.assertEqual(recovery.main(), 2)
            run.assert_not_called()
        report = json.loads((self.out / "recovery-report.json").read_text())
        self.assertEqual(report["status"], "BLOCKED_RECOVERY_INPUT_HASH_MISMATCH")
        self.assertFalse(report["actualInference"])
        self.assertFalse(report["productionPromotionAllowed"])

    def test_prepare_only_cannot_run_inference_or_register_candidate(self):
        with patch("sys.argv", self.argv), patch.object(recovery, "sha256_file", return_value=recovery.ORIGINAL_INPUT_SHA), patch.object(recovery.subprocess, "run") as run:
            self.assertEqual(recovery.main(), 0)
            run.assert_not_called()
        report = json.loads((self.out / "recovery-report.json").read_text())
        self.assertFalse(report["candidateRegistrationAllowed"])
        self.assertFalse(report["qualityRetry"])
        self.assertFalse(report["unityInputAllowed"])

    def test_used_recovery_directory_is_rejected(self):
        self.out.mkdir()
        (self.out / "recovery-attempt.json").write_text("{}")
        with patch("sys.argv", self.argv), self.assertRaisesRegex(RuntimeError, "RECOVERY_ALREADY_ATTEMPTED"):
            recovery.main()

    def test_blocked_gpu_never_invokes_provider(self):
        preflight = self.root / "preflight.json"
        preflight.write_text(json.dumps({"status": "BLOCKED_GPU_UNAVAILABLE"}))
        argv = self.argv + ["--execute", "--preflight", str(preflight), "--provider-repo", str(self.root)]
        with patch("sys.argv", argv), patch.object(recovery, "sha256_file", return_value=recovery.ORIGINAL_INPUT_SHA), patch.object(recovery.subprocess, "run") as run:
            self.assertEqual(recovery.main(), 2)
            run.assert_not_called()

    def test_review_rejects_missing_mesh_before_blender(self):
        args = Namespace(contract=review.ROOT / "contracts/ch101_ai3d_free_pipeline_v001.json",
                         mesh=self.root / "missing.glb", mesh_sha256="a"*64)
        with patch.object(review.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "SOURCE_MESH_MISSING"):
            review.execute(args)
        run.assert_not_called()

    def test_review_rejects_reference_hash_mismatch_before_blender(self):
        reference = self.root / "reference.json"
        reference.write_text("{}")
        args = Namespace(contract=review.ROOT / "contracts/ch101_ai3d_free_pipeline_v001.json",
                         mesh=self.front, mesh_sha256=recovery.sha256_file(self.front),
                         reference_manifest=reference, reference_sha256="a"*64)
        with patch.object(review.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "REFERENCE_MANIFEST_SHA256"):
            review.execute(args)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
