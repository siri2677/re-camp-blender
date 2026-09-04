#!/usr/bin/env python3
"""Patch the pinned SPAR3D runner for Kaggle's pre-Ampere CUDA devices.

The pinned SPAR3D runner has compatibility and memory problems on a stock Kaggle T4:
it unconditionally enters CUDA autocast with ``torch.bfloat16`` even though
T4 (compute capability 7.5) has no CUDA BF16 support, and it defines the
``reduction_count_type``/``target_count`` CLI arguments only when optional
remeshing packages are installed even though the values are always consumed.
The upstream all-at-once marching-tetrahedra decoder also creates a multi-GB
temporary tensor on a 16GB T4, and the T4 attention backend can materialize a
large score matrix. This idempotent patch keeps BF16 on supported devices,
selects FP16 on older CUDA GPUs, makes those two defaulted arguments
unconditional, decodes the grid in an adaptive bounded loop, and chunks
attention queries.

The provider checkout remains detached at the pinned commit.  The patch is
applied only to the ephemeral runtime copy used by Kaggle and its exact
source change is recorded in a JSON report; no upstream commit is rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1"
PATCH_ID = "SPAR3D_T4_BF16_CLI_CHUNKED_ATTENTION_BACKOFF_V005"

_DEVICE_PRINT = '    print("Device used: ", device)'
_DEVICE_PRINT_PATCHED = '''    print("Device used: ", device)

    # Tesla T4 (sm_75) has no CUDA BF16 support.  Keep BF16 on supported
    # devices, but use FP16 on pre-Ampere GPUs so the official runner can
    # complete inference instead of failing at autocast construction.
    amp_dtype = (
        torch.bfloat16
        if "cuda" not in device or torch.cuda.is_bf16_supported()
        else torch.float16
    )
    print("Autocast dtype: ", amp_dtype)'''
_AUTOCAST = "                torch.autocast(device_type=device, dtype=torch.bfloat16)"
_AUTOCAST_PATCHED = "                torch.autocast(device_type=device, dtype=amp_dtype)"

_OPTIONAL_REDUCTION_BLOCK = '''    if TRIANGLE_REMESH_AVAILABLE or QUAD_REMESH_AVAILABLE:
        parser.add_argument(
            "--reduction_count_type",
            choices=["keep", "vertex", "faces"],
            default="keep",
            help="Vertex count type",
        )
        parser.add_argument(
            "--target_count",
            type=check_positive,
            help="Selected target count.",
            default=2000,
        )'''
_UNCONDITIONAL_REDUCTION_BLOCK = '''    # The runner consumes these values even when optional remeshing
    # packages are unavailable, so define safe defaults unconditionally.
    parser.add_argument(
        "--reduction_count_type",
        choices=["keep", "vertex", "faces"],
        default="keep",
        help="Vertex count type",
    )
    parser.add_argument(
        "--target_count",
        type=check_positive,
        help="Selected target count.",
        default=2000,
    )'''

_FULL_GRID_DECODE_BLOCK = '''            values = self.query_triplane(grid_vertices, triplane)
            decoded = self.decoder(values, include=["vertex_offset", "density"])
            sdf = decoded["density"] - self.cfg.isosurface_threshold

            deform = decoded["vertex_offset"].squeeze(0)

            mesh: Mesh = self.isosurface_helper(
                sdf.view(-1, 1), deform.view(-1, 3) if deform is not None else None
            )'''
_CHUNKED_GRID_DECODE_BLOCK_V003 = '''            # Decode the 160^3 marching-tetrahedra grid in bounded chunks.
            # The upstream all-at-once decoder can request several GiB on a
            # 16GB T4 even with low-vram mode enabled.
            chunk_size = max(
                1, int(os.environ.get("SPAR3D_DECODER_CHUNK_SIZE", "65536"))
            )
            sdf_chunks = []
            deform_chunks = []
            for chunk_start in range(0, grid_vertices.shape[0], chunk_size):
                chunk_end = min(chunk_start + chunk_size, grid_vertices.shape[0])
                chunk_values = self.query_triplane(
                    grid_vertices[chunk_start:chunk_end], triplane
                )
                chunk_decoded = self.decoder(
                    chunk_values, include=["vertex_offset", "density"]
                )
                sdf_chunks.append(
                    chunk_decoded["density"] - self.cfg.isosurface_threshold
                )
                deform_chunks.append(chunk_decoded["vertex_offset"])
            sdf = torch.cat(sdf_chunks, dim=1)
            deform = torch.cat(deform_chunks, dim=1).squeeze(0)

            mesh: Mesh = self.isosurface_helper(
                sdf.view(-1, 1), deform.view(-1, 3) if deform is not None else None
            )'''

_CHUNKED_GRID_DECODE_BLOCK_V004 = '''            # Decode the 160^3 marching-tetrahedra grid in bounded chunks.
            # The upstream all-at-once decoder can request several GiB on a
            # 16GB T4 even with low-vram mode enabled. Keep the default small
            # enough for a T4 and back off again if the runtime is fragmented.
            requested_chunk_size = max(
                1, int(os.environ.get("SPAR3D_DECODER_CHUNK_SIZE", "8192"))
            )
            minimum_chunk_size = max(
                1, int(os.environ.get("SPAR3D_DECODER_MIN_CHUNK_SIZE", "1024"))
            )
            chunk_size = min(requested_chunk_size, grid_vertices.shape[0])
            sdf_chunks = []
            deform_chunks = []
            chunk_start = 0
            print("Grid decode chunk size: ", chunk_size)
            while chunk_start < grid_vertices.shape[0]:
                chunk_end = min(chunk_start + chunk_size, grid_vertices.shape[0])
                chunk_values = None
                chunk_decoded = None
                try:
                    chunk_values = self.query_triplane(
                        grid_vertices[chunk_start:chunk_end], triplane
                    )
                    # Mesh extraction is intentionally outside the runner's
                    # global disabled autocast block. T4 supports FP16, and
                    # the decoder is the peak-memory operation here.
                    decode_context = (
                        torch.autocast(device_type="cuda", dtype=torch.float16)
                        if "cuda" in str(self.device)
                        else nullcontext()
                    )
                    with decode_context:
                        chunk_decoded = self.decoder(
                            chunk_values, include=["vertex_offset", "density"]
                        )
                    sdf_chunks.append(
                        (chunk_decoded["density"] - self.cfg.isosurface_threshold)
                        .float()
                        .detach()
                    )
                    deform_chunks.append(
                        chunk_decoded["vertex_offset"].float().detach()
                    )
                    del chunk_values, chunk_decoded
                    chunk_start = chunk_end
                except torch.cuda.OutOfMemoryError:
                    if chunk_values is not None:
                        del chunk_values
                    if chunk_decoded is not None:
                        del chunk_decoded
                    if "cuda" in str(self.device) and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    if chunk_size <= minimum_chunk_size:
                        raise
                    chunk_size = max(minimum_chunk_size, chunk_size // 2)
                    print("Grid decode OOM backoff chunk size: ", chunk_size)
            sdf = torch.cat(sdf_chunks, dim=1)
            deform = torch.cat(deform_chunks, dim=1).squeeze(0)

            mesh: Mesh = self.isosurface_helper(
                sdf.view(-1, 1), deform.view(-1, 3) if deform is not None else None
            )'''

_FULL_ATTENTION_BLOCK = '''        #  attention
        x = torch.nn.functional.scaled_dot_product_attention(
            q.transpose(1, 2),
            k.transpose(1, 2),
            v.transpose(1, 2),
            attn_mask=None,
            dropout_p=self.attn_drop,
            scale=self.scale,
        ).transpose(1, 2)'''
_BACKBONE_IMPORT = "from typing import Optional\n\nimport torch"
_BACKBONE_IMPORT_PATCHED = "import os\nfrom typing import Optional\n\nimport torch"
_CHUNKED_ATTENTION_BLOCK = '''        # Attention score matrices can exceed the free memory on a 16GB
        # T4. Process query rows in bounded chunks while keeping the exact
        # same scaled dot-product attention operation and output ordering.
        attention_query_chunk = max(
            1, int(os.environ.get("SPAR3D_ATTENTION_QUERY_CHUNK_SIZE", "256"))
        )
        q_heads = q.transpose(1, 2)
        k_heads = k.transpose(1, 2)
        v_heads = v.transpose(1, 2)
        if N_q <= attention_query_chunk:
            x = torch.nn.functional.scaled_dot_product_attention(
                q_heads,
                k_heads,
                v_heads,
                attn_mask=None,
                dropout_p=self.attn_drop,
                scale=self.scale,
            ).transpose(1, 2)
        else:
            x_chunks = []
            for query_start in range(0, N_q, attention_query_chunk):
                query_end = min(query_start + attention_query_chunk, N_q)
                x_chunks.append(
                    torch.nn.functional.scaled_dot_product_attention(
                        q_heads[:, :, query_start:query_end, :],
                        k_heads,
                        v_heads,
                        attn_mask=None,
                        dropout_p=self.attn_drop,
                        scale=self.scale,
                    ).transpose(1, 2)
                )
            x = torch.cat(x_chunks, dim=1)'''


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def patch_runner(provider_repo: Path) -> dict[str, Any]:
    runner = provider_repo / "run.py"
    if not runner.is_file():
        raise FileNotFoundError(runner)

    system = provider_repo / "spar3d" / "system.py"
    backbone = provider_repo / "spar3d" / "models" / "transformers" / "backbone.py"

    original = runner.read_text(encoding="utf-8")
    original_sha256 = sha256_file(runner)
    updated = original
    system_original = system.read_text(encoding="utf-8") if system.is_file() else ""
    system_original_sha256 = sha256_file(system) if system.is_file() else "UNAVAILABLE"
    system_updated = system_original
    backbone_original = backbone.read_text(encoding="utf-8") if backbone.is_file() else ""
    backbone_original_sha256 = (
        sha256_file(backbone) if backbone.is_file() else "UNAVAILABLE"
    )
    backbone_updated = backbone_original
    applied: list[str] = []
    already_present: list[str] = []
    missing: list[str] = []

    if _DEVICE_PRINT_PATCHED in updated:
        already_present.append("runner.dynamic_amp_dtype")
    elif _DEVICE_PRINT in updated:
        updated = updated.replace(_DEVICE_PRINT, _DEVICE_PRINT_PATCHED, 1)
        applied.append("runner.dynamic_amp_dtype:1")
    else:
        missing.append("runner.dynamic_amp_dtype")

    if _AUTOCAST_PATCHED in updated:
        already_present.append("runner.autocast_dtype")
    elif _AUTOCAST in updated:
        updated = updated.replace(_AUTOCAST, _AUTOCAST_PATCHED, 1)
        applied.append("runner.autocast_dtype:1")
    else:
        missing.append("runner.autocast_dtype")

    if _UNCONDITIONAL_REDUCTION_BLOCK in updated:
        already_present.append("runner.cli_defaults")
    elif _OPTIONAL_REDUCTION_BLOCK in updated:
        updated = updated.replace(
            _OPTIONAL_REDUCTION_BLOCK, _UNCONDITIONAL_REDUCTION_BLOCK, 1
        )
        applied.append("runner.cli_defaults:1")
    else:
        missing.append("runner.cli_defaults")

    if not system.is_file():
        missing.append("system.chunked_grid_decode")
    elif _CHUNKED_GRID_DECODE_BLOCK_V004 in system_updated:
        already_present.append("system.chunked_grid_decode")
    elif _CHUNKED_GRID_DECODE_BLOCK_V003 in system_updated:
        system_updated = system_updated.replace(
            _CHUNKED_GRID_DECODE_BLOCK_V003, _CHUNKED_GRID_DECODE_BLOCK_V004, 1
        )
        applied.append("system.chunked_grid_decode_backoff:1")
    elif _FULL_GRID_DECODE_BLOCK in system_updated:
        system_updated = system_updated.replace(
            _FULL_GRID_DECODE_BLOCK, _CHUNKED_GRID_DECODE_BLOCK_V004, 1
        )
        applied.append("system.chunked_grid_decode:1")
    else:
        missing.append("system.chunked_grid_decode")

    if updated != original:
        runner.write_text(updated, encoding="utf-8")
    if system_updated != system_original:
        system.write_text(system_updated, encoding="utf-8")

    if not backbone.is_file():
        missing.append("backbone.chunked_attention")
    else:
        if _BACKBONE_IMPORT_PATCHED in backbone_updated:
            already_present.append("backbone.attention_env_import")
        elif _BACKBONE_IMPORT in backbone_updated:
            backbone_updated = backbone_updated.replace(
                _BACKBONE_IMPORT, _BACKBONE_IMPORT_PATCHED, 1
            )
            applied.append("backbone.attention_env_import:1")
        else:
            missing.append("backbone.attention_env_import")

        if _CHUNKED_ATTENTION_BLOCK in backbone_updated:
            already_present.append("backbone.chunked_attention")
        elif _FULL_ATTENTION_BLOCK in backbone_updated:
            backbone_updated = backbone_updated.replace(
                _FULL_ATTENTION_BLOCK, _CHUNKED_ATTENTION_BLOCK, 1
            )
            applied.append("backbone.chunked_attention:1")
        else:
            missing.append("backbone.chunked_attention")

    if backbone_updated != backbone_original:
        backbone.write_text(backbone_updated, encoding="utf-8")

    changed = (
        updated != original
        or system_updated != system_original
        or backbone_updated != backbone_original
    )

    return {
        "patchId": PATCH_ID,
        "path": str(runner),
        "paths": (
            [str(runner), str(system), str(backbone)]
            if system.is_file() and backbone.is_file()
            else [str(runner), str(system)]
            if system.is_file()
            else [str(runner)]
        ),
        "providerCommitExpected": EXPECTED_COMMIT,
        "providerCommitActual": git_head(provider_repo),
        "originalSha256": original_sha256,
        "patchedSha256": sha256_file(runner),
        "systemOriginalSha256": system_original_sha256,
        "systemPatchedSha256": sha256_file(system) if system.is_file() else "UNAVAILABLE",
        "backboneOriginalSha256": backbone_original_sha256,
        "backbonePatchedSha256": (
            sha256_file(backbone) if backbone.is_file() else "UNAVAILABLE"
        ),
        "changed": changed,
        "applied": applied,
        "alreadyPresent": already_present,
        "missing": missing,
        "providerCommitUnchanged": True,
        "productionMesh": False,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-repo", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider_repo = args.provider_repo.resolve()
    report = patch_runner(provider_repo)
    if report["providerCommitActual"] != EXPECTED_COMMIT:
        report["status"] = "BLOCKED_PROVIDER_COMMIT_MISMATCH"
        report["missing"].append("provider.commit")
    elif report["missing"]:
        report["status"] = "PATCH_PARTIAL"
    else:
        report["status"] = "PATCHED" if report["changed"] else "ALREADY_PATCHED"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PATCHED", "ALREADY_PATCHED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
