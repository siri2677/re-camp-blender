import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "merge_current_roster_handoffs.py"
SPEC = importlib.util.spec_from_file_location("merge_current_roster_handoffs", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CurrentRosterHandoffMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = MODULE.load_contract()

    def make_handoff(self, code, **overrides):
        entry = next(item for item in self.contract["characters"] if item["code"] == code)
        handoff = {
            "character": code,
            "sourceStatus": MODULE.EXPECTED_STATUS,
            "gateB": MODULE.EXPECTED_GATE,
            "unityInputAllowed": False,
            "contractVersion": self.contract["contractVersion"],
            "artCommit": MODULE.EXPECTED_ART_COMMIT,
            "toolsCommit": MODULE.EXPECTED_TOOLS_COMMIT,
            "sourceReference": entry["sourceReference"],
            "blend": entry["productionBlend"],
            "blendSha256": "a" * 64,
            "validator": MODULE.EXPECTED_VALIDATOR,
            "validatorReport": f"{code.lower()}-mesh-intake-report.json",
        }
        handoff.update(overrides)
        return handoff

    def test_valid_five_character_handoffs_build_manifest_without_unlocking_unity(self):
        handoffs = [
            (Path(f"{code}/production-mesh-handoff.json"), self.make_handoff(code))
            for code in ("CH101", "CH102", "CH103", "CH104", "CH105")
        ]
        errors, by_code = MODULE.validate_handoffs(
            self.contract,
            handoffs,
            MODULE.EXPECTED_ART_COMMIT,
            MODULE.EXPECTED_TOOLS_COMMIT,
        )
        self.assertEqual(errors, [])
        manifest = MODULE.build_manifest(
            self.contract,
            by_code,
            MODULE.EXPECTED_ART_COMMIT,
            MODULE.EXPECTED_TOOLS_COMMIT,
        )
        self.assertFalse(manifest["unityInputAllowed"])
        self.assertEqual(
            [entry["code"] for entry in manifest["characters"]],
            ["CH101", "CH102", "CH103", "CH104", "CH105"],
        )
        self.assertIn("runtimeSocketAliases", manifest["characters"][0])

    def test_missing_and_duplicate_character_handoffs_fail(self):
        handoffs = [
            (Path(f"{code}/production-mesh-handoff.json"), self.make_handoff(code))
            for code in ("CH101", "CH101", "CH103", "CH104", "CH105")
        ]
        errors, _ = MODULE.validate_handoffs(
            self.contract,
            handoffs,
            MODULE.EXPECTED_ART_COMMIT,
            MODULE.EXPECTED_TOOLS_COMMIT,
        )
        self.assertTrue(any("duplicate character handoff" in error for error in errors))
        self.assertTrue(any("missing character handoffs" in error for error in errors))

    def test_invalid_gate_commit_and_hash_fail(self):
        handoffs = [
            (
                Path(f"{code}/production-mesh-handoff.json"),
                self.make_handoff(
                    code,
                    unityInputAllowed=True if code == "CH101" else False,
                    toolsCommit="wrong-tools-commit" if code == "CH102" else MODULE.EXPECTED_TOOLS_COMMIT,
                    blendSha256="not-a-sha" if code == "CH103" else "a" * 64,
                ),
            )
            for code in ("CH101", "CH102", "CH103", "CH104", "CH105")
        ]
        errors, _ = MODULE.validate_handoffs(
            self.contract,
            handoffs,
            MODULE.EXPECTED_ART_COMMIT,
            MODULE.EXPECTED_TOOLS_COMMIT,
        )
        self.assertTrue(any("unityInputAllowed" in error for error in errors))
        self.assertTrue(any("toolsCommit" in error for error in errors))
        self.assertTrue(any("blendSha256" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
