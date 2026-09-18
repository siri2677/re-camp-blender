#!/usr/bin/env python3
"""Build a deterministic, gate-locked archive of the final CH101 evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
FINAL_STATUS = "REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW"
SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
DEFAULT_EVIDENCE = (
    ROOT / "contracts" / "ch101_ai3d_free_pipeline_v001.json",
    ROOT / "contracts" / "current_roster_ai3d_pipeline_v001.json",
    ROOT
    / "docs"
    / "records"
    / "ch101-ai3d"
    / "2026-08-20-assisted-visual-review-v001.json",
    ROOT
    / "docs"
    / "records"
    / "ch101-ai3d"
    / "2026-08-20-gate-b-review-package-v001.json",
    ROOT
    / "docs"
    / "records"
    / "ch101-ai3d"
    / "assets"
    / "CH101_GateB_ContactSheet_NOT_APPROVED_v001.png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tools-commit", required=True)
    parser.add_argument("--evidence", action="append", type=Path, default=[])
    return parser.parse_args()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_locked_final_ranking(path: Path) -> dict[str, object]:
    ranking = read_json(path)
    if ranking.get("character") != "CH101":
        raise ValueError("final ranking must be for CH101")
    if ranking.get("status") != FINAL_STATUS:
        raise ValueError(f"final ranking status must be {FINAL_STATUS}")
    if ranking.get("selectedCandidate") is not None:
        raise ValueError("visually rejected final ranking must not select a candidate")
    if ranking.get("gateB") != GATE_B:
        raise ValueError("final ranking must remain pending human Gate B review")
    for key in ("unityInputAllowed", "productionPromotionAllowed"):
        if ranking.get(key) is not False:
            raise ValueError(f"final ranking must keep {key}=false")
    assisted = ranking.get("assistedVisualReview")
    if not isinstance(assisted, dict) or assisted.get("rejectedCandidateCount") != 3:
        raise ValueError("final ranking must record all three assisted review rejections")
    return ranking


def _archive_path_for_evidence(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError:
        relative = Path(resolved.name)
    return (Path("repository-evidence") / relative).as_posix()


def collect_payloads(
    evaluation_root: Path,
    evidence_files: Iterable[Path],
) -> dict[str, Path]:
    evaluation_root = evaluation_root.resolve()
    payloads: dict[str, Path] = {}
    for directory_name in ("reference-views", "evaluation-corrected"):
        directory = evaluation_root / directory_name
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.name.endswith("_normalized_NOT_PRODUCTION.blend"):
                continue
            archive_path = (
                Path("candidate-evaluation") / path.relative_to(evaluation_root)
            ).as_posix()
            payloads[archive_path] = path

    for name in (
        "ranking-manifest-hard-gated.json",
        "ranking-manifest-final-reviewed.json",
    ):
        path = evaluation_root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        payloads[(Path("candidate-evaluation") / name).as_posix()] = path

    for path in evidence_files:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        archive_path = _archive_path_for_evidence(resolved)
        if archive_path in payloads:
            raise ValueError(f"duplicate archive path: {archive_path}")
        payloads[archive_path] = resolved
    return payloads


def _write_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def verify_archive(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate paths")
        manifest = json.loads(archive.read("PACKAGE-MANIFEST.json"))
        if manifest.get("status") != FINAL_STATUS:
            raise ValueError("archive manifest final status mismatch")
        if manifest.get("selectedCandidate") is not None:
            raise ValueError("archive manifest unexpectedly selects a candidate")
        for key in ("unityInputAllowed", "productionPromotionAllowed"):
            if manifest.get(key) is not False:
                raise ValueError(f"archive manifest must keep {key}=false")
        payloads = manifest.get("payloads")
        if not isinstance(payloads, list):
            raise ValueError("archive manifest payload list is missing")
        expected_names = {"PACKAGE-MANIFEST.json", "README-NOT-PRODUCTION.txt"}
        for entry in payloads:
            archive_path = entry["path"]
            data = archive.read(archive_path)
            if len(data) != entry["bytes"]:
                raise ValueError(f"archive payload size mismatch: {archive_path}")
            if sha256_bytes(data) != entry["sha256"]:
                raise ValueError(f"archive payload hash mismatch: {archive_path}")
            expected_names.add(archive_path)
        if set(names) != expected_names:
            raise ValueError("archive contains unmanifested or missing paths")
        if any("review-corrected" in name for name in names):
            raise ValueError("rejected Review asset directory cannot be archived")
        if any(name.endswith("_normalized_NOT_PRODUCTION.blend") for name in names):
            raise ValueError("intermediate normalized Blend cannot be archived")
    return {
        "status": "PASS",
        "verifiedPayloadCount": len(payloads),
        "selectedCandidate": None,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def build_archive(
    evaluation_root: Path,
    output: Path,
    tools_commit: str,
    evidence_files: Iterable[Path] = DEFAULT_EVIDENCE,
) -> dict[str, object]:
    evaluation_root = evaluation_root.resolve()
    output = output.resolve()
    ranking = require_locked_final_ranking(
        evaluation_root / "ranking-manifest-final-reviewed.json"
    )
    payloads = collect_payloads(evaluation_root, evidence_files)
    entries = []
    payload_bytes: dict[str, bytes] = {}
    for archive_path, source in sorted(payloads.items()):
        data = source.read_bytes()
        payload_bytes[archive_path] = data
        entries.append(
            {
                "path": archive_path,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )

    package_manifest = {
        "packageVersion": "ch101-ai3d-final-hard-gated-v004",
        "character": "CH101",
        "toolsCommit": tools_commit,
        "artCommit": ranking.get("artCommit"),
        "status": FINAL_STATUS,
        "sourceStatus": SOURCE_STATUS,
        "selectedCandidate": None,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "reviewAssetIncluded": False,
        "reviewAssetExclusionReason": "ALL_TECHNICALLY_ELIGIBLE_CANDIDATES_REJECTED_BY_ASSISTED_VISUAL_QA",
        "payloadEntryCount": len(entries),
        "payloads": entries,
    }
    manifest_bytes = (
        json.dumps(package_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    notice = (
        "Re:Camp CH101 AI3D final evaluation v004\n"
        "Status: REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW\n"
        "This archive is NOT a Production Mesh, Gate B approval, or Unity input.\n"
        "selectedCandidate is null; no Review .blend is included.\n"
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        _write_bytes(archive, "PACKAGE-MANIFEST.json", manifest_bytes)
        _write_bytes(archive, "README-NOT-PRODUCTION.txt", notice)
        for archive_path, data in sorted(payload_bytes.items()):
            _write_bytes(archive, archive_path, data)

    verification = verify_archive(output)

    summary = {
        **{
            key: package_manifest[key]
            for key in (
                "packageVersion",
                "character",
                "toolsCommit",
                "artCommit",
                "status",
                "sourceStatus",
                "selectedCandidate",
                "gateB",
                "unityInputAllowed",
                "productionPromotionAllowed",
                "reviewAssetIncluded",
            )
        },
        "fileName": output.name,
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "entryCount": len(payload_bytes) + 2,
        "payloadEntryCount": len(entries),
        "manifestSha256": sha256_bytes(manifest_bytes),
        "verification": verification,
        "trackedInGit": False,
        "retention": "LOCAL_ARTIFACT_PENDING_GITHUB_RELEASE_UPLOAD",
    }
    sidecar = output.with_suffix(output.suffix + ".manifest.json")
    sidecar.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    summary = build_archive(
        evaluation_root=args.evaluation_root,
        output=args.output,
        tools_commit=args.tools_commit,
        evidence_files=args.evidence or DEFAULT_EVIDENCE,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
