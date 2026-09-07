import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.ai3d.review_artifact_release import build_bundle, verify_bundle


class ReviewArtifactReleaseTests(unittest.TestCase):
    def test_builds_and_verifies_review_only_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            root.mkdir()
            (root / "candidate.glb").write_bytes(b"review mesh")
            (root / "candidate-score.json").write_text(
                json.dumps({"overallScore": 0.601063}), encoding="utf-8"
            )
            (root / "renders").mkdir()
            (root / "renders" / "front.png").write_bytes(b"render")
            (root / "secrets").mkdir()
            (root / "secrets" / "HF_TOKEN.txt").write_text("must not ship", encoding="utf-8")
            (root / "HF_TOKEN.txt").write_text("must not ship", encoding="utf-8")
            bundle = Path(temporary) / "CH101-review-s074.zip"

            summary = build_bundle(
                root,
                bundle,
                character="CH101",
                candidate_id="CH101-SPAR3D-s074",
                tools_commit="a" * 40,
                art_commit="b" * 40,
            )

            self.assertEqual(summary["verification"]["status"], "PASS")
            self.assertEqual(verify_bundle(bundle)["status"], "PASS")
            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
            self.assertIn("candidate.glb", names)
            self.assertNotIn("secrets/HF_TOKEN.txt", names)
            self.assertNotIn("HF_TOKEN.txt", names)

    def test_rejects_directory_without_3d_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            root.mkdir()
            (root / "score.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no supported 3D result"):
                build_bundle(
                    root,
                    Path(temporary) / "empty.zip",
                    character="CH101",
                    candidate_id="CH101-review",
                    tools_commit="a" * 40,
                    art_commit="b" * 40,
                )


if __name__ == "__main__":
    unittest.main()
