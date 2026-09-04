#!/usr/bin/env python3
"""Generate CH101 multiview candidates with the optional Tripo free trial.

The command is a dry-run unless --execute is supplied. API keys are read only
from TRIPO_API_KEY and are never written to reports.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        VIEW_ORDER,
        candidate_gate_fields,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        VIEW_ORDER,
        candidate_gate_fields,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )


TERMINAL_FAILURES = {"failed", "cancelled", "banned"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_multiview_payload(
    contract: dict[str, Any], file_tokens: dict[str, str], seed: int
) -> dict[str, Any]:
    if set(file_tokens) != set(VIEW_ORDER):
        raise ValueError(f"file tokens must contain exactly {VIEW_ORDER!r}")
    provider = contract["providers"]["tripoApi"]
    return {
        "inputs": [{view_name: file_tokens[view_name]} for view_name in VIEW_ORDER],
        "model": provider["model"],
        "texture": provider["texture"],
        "pbr": provider["pbr"],
        "geometry_quality": provider["geometryQuality"],
        "model_seed": seed,
    }


def strip_expiring_urls(task: dict[str, Any]) -> dict[str, Any]:
    output = task.get("output") if isinstance(task.get("output"), dict) else {}
    return {
        "task_id": task.get("task_id", ""),
        "type": task.get("type", ""),
        "status": task.get("status", ""),
        "progress": task.get("progress", 0),
        "credits_consumed": task.get("credits_consumed", task.get("consumed_credit", 0)),
        "outputKeys": sorted(output),
    }


class TripoClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 120) -> None:
        if not api_key:
            raise ValueError("TRIPO_API_KEY is required for --execute")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if body is not None:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"Tripo HTTP {exc.code}: {details}") from exc
        if not isinstance(result, dict) or result.get("code") != 0:
            raise RuntimeError(f"Tripo API error: {result}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Tripo response has no data object: {result}")
        return data

    def upload_file(self, path: Path) -> str:
        boundary = f"----ReCamp{secrets.token_hex(12)}"
        content = path.read_bytes()
        prefix = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            "Content-Type: image/png\r\n\r\n"
        ).encode("utf-8")
        body = prefix + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        data = self._request_json(
            "POST",
            "/files",
            body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        token = data.get("file_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError(f"Tripo upload did not return file_token: {data}")
        return token

    def create_multiview_task(self, payload: dict[str, Any]) -> str:
        data = self._request_json("POST", "/generation/multiview-to-model", payload=payload)
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"Tripo generation did not return task_id: {data}")
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/tasks/{task_id}")

    def poll_task(self, task_id: str, interval: float, deadline: float) -> dict[str, Any]:
        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            status = str(task.get("status", "")).lower()
            print(f"{task_id}: {status} {task.get('progress', 0)}%")
            if status == "success":
                return task
            if status in TERMINAL_FAILURES:
                raise RuntimeError(f"Tripo task {task_id} ended with {status}: {task}")
            time.sleep(interval)
        raise TimeoutError(f"Tripo task timed out: {task_id}")

    def download(self, url: str, destination: Path) -> None:
        if not url.startswith("https://"):
            raise ValueError("Tripo download URL must use HTTPS")
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "re-camp-ai3d/1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            with destination.open("wb") as stream:
                shutil.copyfileobj(response, stream)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument("--candidate-count", type=int, default=4)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser.parse_args()


def _initial_manifest(
    contract: dict[str, Any], reference_manifest_path: Path, dry_run: bool
) -> dict[str, Any]:
    provider = contract["providers"]["tripoApi"]
    return {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "provider": "tripoApi",
        "providerMode": provider["mode"],
        "model": provider["model"],
        "status": "DRY_RUN" if dry_run else "GENERATION_IN_PROGRESS",
        "createdAt": utc_now(),
        "artCommit": contract["artLock"]["commit"],
        "referenceManifest": str(reference_manifest_path.resolve()),
        "referenceManifestSha256": sha256_file(reference_manifest_path.resolve()),
        "candidates": [],
        "creditsConsumedReported": 0,
        **candidate_gate_fields(contract),
    }


def _load_or_initialize_manifest(
    output_path: Path,
    contract: dict[str, Any],
    reference_manifest_path: Path,
) -> dict[str, Any]:
    if not output_path.is_file():
        return _initial_manifest(contract, reference_manifest_path, dry_run=False)
    manifest = read_json(output_path)
    if manifest.get("contractVersion") != contract["contractVersion"]:
        raise ValueError("existing candidate manifest contract mismatch")
    if manifest.get("referenceManifestSha256") != sha256_file(reference_manifest_path):
        raise ValueError("existing candidate manifest points to different reference views")
    if manifest.get("unityInputAllowed") is not False:
        raise ValueError("existing candidate manifest illegally enables Unity input")
    return manifest


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    reference_manifest_path = args.reference_manifest.resolve()
    references = require_reference_manifest(reference_manifest_path, contract)
    provider = contract["providers"]["tripoApi"]
    seeds = provider["candidateSeeds"]
    if args.candidate_count < 1 or args.candidate_count > len(seeds):
        raise ValueError(f"candidate-count must be between 1 and {len(seeds)}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "candidate-manifest.json"

    if not args.execute:
        dry_tokens = {view: f"DRY_RUN_{view.upper()}_FILE_TOKEN" for view in VIEW_ORDER}
        manifest = _initial_manifest(contract, reference_manifest_path, dry_run=True)
        manifest["plannedPayloads"] = [
            build_multiview_payload(contract, dry_tokens, seed)
            for seed in seeds[: args.candidate_count]
        ]
        manifest["secretSource"] = provider["requiresSecret"]
        write_json(output_dir / "tripo-dry-run-plan.json", manifest)
        print(output_dir / "tripo-dry-run-plan.json")
        return 0

    api_key = os.environ.get(provider["requiresSecret"], "")
    client = TripoClient(provider["baseUrl"], api_key)
    file_tokens = {}
    for view_name in VIEW_ORDER:
        path = Path(references["views"][view_name]["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"missing prepared {view_name} reference: {path}")
        if sha256_file(path) != references["views"][view_name]["sha256"]:
            raise ValueError(f"prepared {view_name} reference hash mismatch")
        print(f"Uploading {view_name}: {path.name}")
        file_tokens[view_name] = client.upload_file(path)

    manifest = _load_or_initialize_manifest(manifest_path, contract, reference_manifest_path)
    candidates = manifest.setdefault("candidates", [])
    by_seed = {entry.get("seed"): entry for entry in candidates if isinstance(entry, dict)}
    for index, seed in enumerate(seeds[: args.candidate_count], start=1):
        entry = by_seed.get(seed)
        destination = output_dir / f"{contract['character']}_tripo_cand_{index:03d}.glb"
        if (
            entry
            and entry.get("status") == "DOWNLOADED"
            and destination.is_file()
            and entry.get("sha256") == sha256_file(destination)
        ):
            print(f"Skipping completed candidate for seed {seed}: {destination.name}")
            continue
        if entry is None:
            payload = build_multiview_payload(contract, file_tokens, seed)
            task_id = client.create_multiview_task(payload)
            entry = {
                "candidateId": f"{contract['character']}-TRIPO-{index:03d}",
                "seed": seed,
                "taskId": task_id,
                "status": "SUBMITTED",
                "submittedAt": utc_now(),
                **candidate_gate_fields(contract),
            }
            candidates.append(entry)
            by_seed[seed] = entry
            write_json(manifest_path, manifest)
        task_id = entry.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"candidate seed {seed} has no resumable taskId")
        try:
            task = client.poll_task(
                task_id,
                interval=max(args.poll_seconds, 1.0),
                deadline=time.monotonic() + args.timeout_seconds,
            )
            output = task.get("output") if isinstance(task.get("output"), dict) else {}
            model_url = output.get("model_url")
            if not isinstance(model_url, str) or not model_url:
                raise RuntimeError(f"successful task has no model_url: {task}")
            client.download(model_url, destination)
            entry.update(
                {
                    "status": "DOWNLOADED",
                    "completedAt": utc_now(),
                    "modelPath": str(destination),
                    "sha256": sha256_file(destination),
                    "bytes": destination.stat().st_size,
                    "taskSummary": strip_expiring_urls(task),
                }
            )
        except Exception as exc:
            entry.update({"status": "FAILED", "error": str(exc), "failedAt": utc_now()})
            write_json(manifest_path, manifest)
            raise
        write_json(manifest_path, manifest)

    manifest["status"] = "CANDIDATES_DOWNLOADED"
    manifest["completedAt"] = utc_now()
    manifest["creditsConsumedReported"] = sum(
        int(entry.get("taskSummary", {}).get("credits_consumed", 0) or 0)
        for entry in candidates
        if isinstance(entry, dict)
    )
    manifest.update(candidate_gate_fields(contract))
    write_json(manifest_path, manifest)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
