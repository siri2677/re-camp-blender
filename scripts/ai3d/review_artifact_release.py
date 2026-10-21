#!/usr/bin/env python3
"""Package, publish, and fetch review-only AI 3D artifacts.

Normal Git stores the reproducibility metadata.  The actual generated binary
is uploaded as a versioned GitHub Release asset, and a small latest pointer is
committed back to this repository.  This keeps the workflow free and usable
from Kaggle, Blender workstations, and other environments without putting
large generated files in ordinary Git history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MAX_RELEASE_ASSET_BYTES = 2 * 1024 * 1024 * 1024
SAFE_SUFFIXES = {
    ".blend",
    ".fbx",
    ".glb",
    ".gltf",
    ".jpeg",
    ".jpg",
    ".json",
    ".mtl",
    ".obj",
    ".ply",
    ".png",
    ".txt",
}
FORBIDDEN_PARTS = {
    ".env",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "token",
    "tokens",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"artifact path escapes root: {path}")
    return relative.as_posix()


def collect_payloads(artifact_root: Path, output_bundle: Path | None = None) -> list[tuple[str, Path]]:
    root = artifact_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"artifact root is not a directory: {root}")
    output_resolved = output_bundle.resolve() if output_bundle else None
    payloads: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (output_resolved and path.resolve() == output_resolved):
            continue
        relative = _safe_relative(path, root)
        lowered_parts = {part.lower() for part in Path(relative).parts}
        lowered_relative = relative.lower()
        if lowered_parts & FORBIDDEN_PARTS or any(
            token in lowered_relative for token in ("secret", "credential", "token")
        ) or any(part.startswith(".env") for part in lowered_parts):
            continue
        if path.suffix.lower() not in SAFE_SUFFIXES:
            continue
        if path.stat().st_size > MAX_RELEASE_ASSET_BYTES:
            raise ValueError(f"single artifact file exceeds GitHub Release limit: {path}")
        payloads.append((relative, path))
    if not any(path.suffix.lower() in {".blend", ".fbx", ".glb", ".gltf", ".obj", ".ply"} for _, path in payloads):
        raise ValueError("artifact root contains no supported 3D result file")
    return payloads


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        raise RuntimeError("review release publishing requires a named Git branch")
    return branch


def _write_zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_bundle(
    artifact_root: Path,
    output_bundle: Path,
    *,
    character: str,
    candidate_id: str,
    tools_commit: str,
    art_commit: str,
) -> dict[str, Any]:
    if not candidate_id or any(value in candidate_id for value in ("/", "\\", "..")):
        raise ValueError("candidate-id must be a simple versioned identifier")
    if len(tools_commit) != 40 or len(art_commit) != 40:
        raise ValueError("tools-commit and art-commit must be full 40-character commits")
    output = output_bundle.resolve()
    payloads = collect_payloads(artifact_root, output)
    entries = [
        {
            "path": archive_path,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for archive_path, path in payloads
    ]
    manifest: dict[str, Any] = {
        "schemaVersion": "ch101-review-artifact-bundle-v001",
        "character": character,
        "candidateId": candidate_id,
        "toolsCommit": tools_commit,
        "artCommit": art_commit,
        "status": "REVIEW_ARTIFACT_READY_NOT_APPROVED",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "payloads": entries,
    }
    manifest_data = _manifest_bytes(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        _write_zip_entry(archive, "ARTIFACT-MANIFEST.json", manifest_data)
        _write_zip_entry(
            archive,
            "README-NOT-PRODUCTION.txt",
            (
                f"{character} review artifact {candidate_id}\n"
                "This bundle is not a Production Mesh, Gate B approval, or Unity input.\n"
            ).encode("utf-8"),
        )
        for archive_path, path in payloads:
            _write_zip_entry(archive, archive_path, path.read_bytes())
    verification = verify_bundle(output)
    summary = {
        "schemaVersion": "ch101-review-artifact-summary-v001",
        "character": character,
        "candidateId": candidate_id,
        "fileName": output.name,
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "manifestSha256": sha256_bytes(manifest_data),
        "payloadCount": len(payloads),
        "verification": verification,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "trackedInGit": False,
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("sourceStatus") != SOURCE_STATUS:
        raise ValueError("artifact manifest must remain review-only")
    if manifest.get("gateB") != GATE_B:
        raise ValueError("artifact manifest Gate B must remain pending")
    if manifest.get("unityInputAllowed") is not False:
        raise ValueError("artifact manifest cannot enable Unity input")
    if manifest.get("productionPromotionAllowed") is not False:
        raise ValueError("artifact manifest cannot enable production promotion")
    payloads = manifest.get("payloads")
    if not isinstance(payloads, list) or not payloads:
        raise ValueError("artifact manifest payloads are missing")


def _validate_pointer(pointer: dict[str, Any]) -> None:
    if pointer.get("sourceStatus") != SOURCE_STATUS:
        raise ValueError("artifact pointer must remain review-only")
    if pointer.get("gateB") != GATE_B:
        raise ValueError("artifact pointer Gate B must remain pending")
    if pointer.get("unityInputAllowed") is not False:
        raise ValueError("artifact pointer cannot enable Unity input")
    if pointer.get("productionPromotionAllowed") is not False:
        raise ValueError("artifact pointer cannot enable production promotion")
    for key in ("candidateId", "releaseTag", "assetName", "downloadUrl", "bundleSha256"):
        if not isinstance(pointer.get(key), str) or not pointer[key]:
            raise ValueError(f"artifact pointer field is missing: {key}")
    if not isinstance(pointer.get("bundleBytes"), int) or pointer["bundleBytes"] <= 0:
        raise ValueError("artifact pointer bundleBytes must be positive")


def verify_bundle(bundle: Path) -> dict[str, Any]:
    with zipfile.ZipFile(bundle.resolve()) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("artifact bundle contains duplicate paths")
        manifest = json.loads(archive.read("ARTIFACT-MANIFEST.json"))
        _validate_manifest(manifest)
        expected = {"ARTIFACT-MANIFEST.json", "README-NOT-PRODUCTION.txt"}
        for entry in manifest["payloads"]:
            archive_path = Path(str(entry["path"]))
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise ValueError(f"unsafe archive path: {archive_path}")
            name = archive_path.as_posix()
            data = archive.read(name)
            if len(data) != entry["bytes"] or sha256_bytes(data) != entry["sha256"]:
                raise ValueError(f"artifact payload hash mismatch: {name}")
            expected.add(name)
        if set(names) != expected:
            raise ValueError("artifact bundle contains unmanifested or missing files")
    return {
        "status": "PASS",
        "payloadCount": len(manifest["payloads"]),
        "candidateId": manifest["candidateId"],
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def _write_latest_pointer(
    pointer: Path,
    *,
    repo: str,
    release_tag: str,
    bundle: Path,
    summary: dict[str, Any],
    character: str,
) -> dict[str, Any]:
    asset_name = bundle.name
    pointer_data = {
        "schemaVersion": "ch101-review-artifact-pointer-v001",
        "character": character,
        "candidateId": summary["candidateId"],
        "status": "REVIEW_ARTIFACT_READY_NOT_APPROVED",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "releaseTag": release_tag,
        "releaseUrl": f"https://github.com/{repo}/releases/tag/{urllib.parse.quote(release_tag, safe='')}",
        "assetName": asset_name,
        "downloadUrl": (
            f"https://github.com/{repo}/releases/download/"
            f"{urllib.parse.quote(release_tag, safe='')}/{urllib.parse.quote(asset_name, safe='')}"
        ),
        "bundleBytes": summary["bytes"],
        "bundleSha256": summary["sha256"],
        "manifestSha256": summary["manifestSha256"],
        "toolsCommit": summary.get("toolsCommit", ""),
        "artCommit": summary.get("artCommit", ""),
    }
    pointer = pointer.resolve()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps(pointer_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pointer_data


def publish_release(
    artifact_root: Path,
    output_bundle: Path,
    *,
    repo: str,
    release_tag: str,
    character: str,
    candidate_id: str,
    tools_commit: str,
    art_commit: str,
    pointer: Path,
) -> dict[str, Any]:
    summary = build_bundle(
        artifact_root,
        output_bundle,
        character=character,
        candidate_id=candidate_id,
        tools_commit=tools_commit,
        art_commit=art_commit,
    )
    target_branch = _current_branch()
    command = [
        "gh",
        "release",
        "create",
        release_tag,
        str(output_bundle.resolve()),
        "--repo",
        repo,
        "--target",
        target_branch,
        "--title",
        f"{character} NOT_PRODUCTION review artifact {candidate_id}",
        "--notes",
        f"Review-only AI 3D artifact {candidate_id}. Gate B remains pending; Unity and Production are disabled.",
        "--prerelease",
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI 'gh' is required for publish; run 'gh auth login' locally") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"GitHub Release creation failed with exit code {exc.returncode}") from exc
    pointer_data = _write_latest_pointer(
        pointer,
        repo=repo,
        release_tag=release_tag,
        bundle=output_bundle,
        summary={**summary, "toolsCommit": tools_commit, "artCommit": art_commit},
        character=character,
    )
    return {"summary": summary, "pointer": pointer_data, "pointerPath": str(pointer.resolve())}


def _safe_extract(archive: zipfile.ZipFile, output: Path) -> None:
    output = output.resolve()
    for member in archive.infolist():
        target = (output / member.filename).resolve()
        if output != target and output not in target.parents:
            raise ValueError(f"unsafe extraction path: {member.filename}")
    archive.extractall(output)


def fetch_release(pointer: Path, output_dir: Path) -> dict[str, Any]:
    pointer_data = json.loads(pointer.resolve().read_text(encoding="utf-8"))
    _validate_pointer(pointer_data)
    url = pointer_data.get("downloadUrl")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        raise ValueError("pointer downloadUrl must be a GitHub HTTPS URL")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / str(pointer_data["assetName"])
    request = urllib.request.Request(url, headers={"User-Agent": "re-camp-review-artifact-fetch"})
    with urllib.request.urlopen(request, timeout=120) as response, bundle.open("wb") as stream:
        shutil.copyfileobj(response, stream)
    if bundle.stat().st_size != pointer_data["bundleBytes"]:
        raise ValueError("downloaded bundle size mismatch")
    if sha256_file(bundle) != pointer_data["bundleSha256"]:
        raise ValueError("downloaded bundle SHA256 mismatch")
    extracted = output_dir / "extracted"
    extracted.mkdir(exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        _safe_extract(archive, extracted)
    verification = verify_bundle(bundle)
    return {
        "status": "FETCHED_AND_VERIFIED",
        "bundle": str(bundle),
        "extracted": str(extracted),
        "verification": verification,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    package = subparsers.add_parser("package", help="build a verified review artifact ZIP")
    package.add_argument("--artifact-root", required=True, type=Path)
    package.add_argument("--output-bundle", required=True, type=Path)
    package.add_argument("--character", default="CH101")
    package.add_argument("--candidate-id", required=True)
    package.add_argument("--tools-commit", required=True)
    package.add_argument("--art-commit", required=True)

    publish = subparsers.add_parser("publish", help="package and publish a prerelease via gh")
    publish.add_argument("--artifact-root", required=True, type=Path)
    publish.add_argument("--output-bundle", required=True, type=Path)
    publish.add_argument("--repo", required=True, help="OWNER/REPOSITORY")
    publish.add_argument("--release-tag", required=True)
    publish.add_argument("--pointer", type=Path, default=ROOT / "docs" / "artifacts" / "CH101-latest-review.json")
    publish.add_argument("--character", default="CH101")
    publish.add_argument("--candidate-id", required=True)
    publish.add_argument("--tools-commit", required=True)
    publish.add_argument("--art-commit", required=True)

    fetch = subparsers.add_parser("fetch", help="download and verify the committed latest pointer")
    fetch.add_argument("--pointer", type=Path, default=ROOT / "docs" / "artifacts" / "CH101-latest-review.json")
    fetch.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "package":
        result = build_bundle(
            args.artifact_root,
            args.output_bundle,
            character=args.character,
            candidate_id=args.candidate_id,
            tools_commit=args.tools_commit,
            art_commit=args.art_commit,
        )
    elif args.command == "publish":
        result = publish_release(
            args.artifact_root,
            args.output_bundle,
            repo=args.repo,
            release_tag=args.release_tag,
            character=args.character,
            candidate_id=args.candidate_id,
            tools_commit=args.tools_commit,
            art_commit=args.art_commit,
            pointer=args.pointer,
        )
    else:
        result = fetch_release(args.pointer, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
