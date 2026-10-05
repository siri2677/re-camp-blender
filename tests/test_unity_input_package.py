import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_unity_input_package.py"
SPEC = importlib.util.spec_from_file_location("validate_unity_input_package", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UnityInputPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = MODULE.load_contract()
        cls.source_lock = MODULE.load_source_lock()
        cls.tools_commit = "1" * 40

    def make_manifest(self, **overrides):
        characters = []
        for entry in self.contract["characters"]:
            required = sorted(
                set(self.contract["commonRuntimeSockets"])
                | set(entry["detailSockets"])
                | set(entry["runtimeSocketMap"])
                | set(entry["runtimeSocketMap"].values())
            )
            characters.append(
                {
                    "code": entry["code"],
                    "modelNamePrefix": entry["modelNamePrefix"],
                    "productionBlend": entry["productionBlend"],
                    "sourceReference": entry["sourceReference"],
                    "blendSha256": "a" * 64,
                    "requiredSockets": required,
                    "runtimeSocketAliases": [
                        {"runtimeName": runtime, "sourceName": source}
                        for runtime, source in entry["runtimeSocketMap"].items()
                    ],
                    "validatorReport": f"{entry['code'].lower()}-report.json",
                }
            )
        manifest = {
            "manifestVersion": 2,
            "socketContractVersion": self.contract["contractVersion"],
            "artCommit": self.source_lock["commit"],
            "toolsCommit": self.tools_commit,
            "sourceStatus": MODULE.EXPECTED_SOURCE_STATUS,
            "gateB": MODULE.PENDING_GATE,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
            "packageName": MODULE.PENDING_PACKAGE,
            "packageSha256": MODULE.PENDING_PACKAGE,
            "characters": characters,
        }
        manifest.update(overrides)
        return manifest

    def validate(self, manifest, **kwargs):
        return MODULE.validate_manifest(
            manifest,
            contract=self.contract,
            source_lock=self.source_lock,
            expected_tools_commit=self.tools_commit,
            **kwargs,
        )

    def test_locked_production_manifest_passes(self):
        self.assertEqual(self.validate(self.make_manifest()), [])

    def test_candidate_status_is_rejected_before_unity(self):
        errors = self.validate(
            self.make_manifest(sourceStatus="AI_GENERATED_CANDIDATE_NOT_PRODUCTION")
        )
        self.assertTrue(any("sourceStatus" in error for error in errors))

    def test_malformed_character_shape_reports_errors_without_crashing(self):
        errors = self.validate(self.make_manifest(characters=None))
        self.assertTrue(any("characters must be an array" in error for error in errors))

    def test_commit_mismatch_is_rejected(self):
        errors = self.validate(self.make_manifest(toolsCommit="2" * 40))
        self.assertTrue(any("toolsCommit" in error for error in errors))

    def test_socket_alias_and_duplicate_failures_are_rejected(self):
        manifest = self.make_manifest()
        manifest["characters"][0]["requiredSockets"].remove("Socket_BladeTip")
        manifest["characters"][0]["runtimeSocketAliases"].append(
            {"runtimeName": "Socket_VFXCenter", "sourceName": "Socket_VFXCenter"}
        )
        errors = self.validate(manifest)
        self.assertTrue(any("Socket_BladeTip" in error for error in errors))
        self.assertTrue(any("duplicate runtime socket alias" in error for error in errors))

    def test_unlock_requires_approved_gate_and_package(self):
        manifest = self.make_manifest(
            unityInputAllowed=True,
            packageName="re-camp-unity-input-v001.zip",
            packageSha256="b" * 64,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            package_path = Path(temp_dir) / manifest["packageName"]
            package_path.write_bytes(b"package")
            manifest["packageSha256"] = hashlib.sha256(package_path.read_bytes()).hexdigest()
            errors = self.validate(manifest, package_path=package_path)
        self.assertTrue(any("gateB=APPROVED" in error for error in errors))

    def test_approved_package_hash_passes_and_mismatch_fails(self):
        manifest = self.make_manifest(
            gateB=MODULE.APPROVED_GATE,
            unityInputAllowed=True,
            packageName="re-camp-unity-input-v001.zip",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            package_path = Path(temp_dir) / manifest["packageName"]
            package_path.write_bytes(b"package")
            manifest["packageSha256"] = hashlib.sha256(package_path.read_bytes()).hexdigest()
            self.assertEqual(
                self.validate(
                    manifest,
                    package_path=package_path,
                    require_unity_input=True,
                ),
                [],
            )
            package_path.write_bytes(b"tampered")
            errors = self.validate(
                manifest,
                package_path=package_path,
                require_unity_input=True,
            )
        self.assertTrue(any("package SHA256 mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
