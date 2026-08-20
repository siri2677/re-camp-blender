#!/usr/bin/env python3
"""Crop locked roster generation views while retaining the approved source lock."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        VIEW_ORDER,
        candidate_gate_fields,
        load_contract,
        sha256_file,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        VIEW_ORDER,
        candidate_gate_fields,
        load_contract,
        sha256_file,
        write_json,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def prepare_views(
    art_root: Path,
    output_dir: Path,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    character: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    contract = load_contract(contract_path, character)
    art_root = art_root.resolve()
    output_dir = output_dir.resolve()
    approved_path = art_root / contract["authoritativeSource"]
    generation_path = art_root / contract["generationSource"]["path"]
    for source in (approved_path, generation_path):
        if not source.is_file():
            raise FileNotFoundError(f"missing locked art source: {source}")

    auxiliary_references = []
    for reference in contract.get("auxiliaryReferences", []):
        auxiliary_path = art_root / reference["path"]
        if not auxiliary_path.is_file():
            raise FileNotFoundError(f"missing locked auxiliary art source: {auxiliary_path}")
        auxiliary_references.append(
            {
                **reference,
                "path": str(auxiliary_path),
                "sha256": sha256_file(auxiliary_path),
            }
        )

    manifest: dict[str, object] = {
        "contractVersion": contract["contractVersion"],
        "character": contract["character"],
        "subject": contract["subject"],
        "status": "REFERENCE_VIEW_PLAN" if dry_run else "REFERENCE_VIEWS_READY",
        "artCommit": contract["artLock"]["commit"],
        "authoritativeSource": str(approved_path),
        "authoritativeSourceSha256": sha256_file(approved_path),
        "generationSource": str(generation_path),
        "generationSourceRole": contract["generationSource"]["role"],
        "generationSourceSha256": sha256_file(generation_path),
        "auxiliaryReferences": auxiliary_references,
        "generationStrategy": contract.get("generationStrategy", {}),
        "views": {},
        **candidate_gate_fields(contract),
    }

    if dry_run:
        for view_name in VIEW_ORDER:
            view_contract = contract["referenceViews"][view_name]
            manifest["views"][view_name] = {
                "path": str(output_dir / f"{contract['character']}_{view_name}.png"),
                "crop": view_contract["crop"],
                "providerKey": view_contract["providerKey"],
                "sha256": "DRY_RUN_NOT_GENERATED",
            }
        return manifest

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install pillow") from exc

    with Image.open(generation_path) as source_image:
        source = source_image.convert("RGBA")
        expected_size = tuple(contract["generationSource"]["expectedSize"])
        if source.size != expected_size:
            raise ValueError(
                f"generation source size changed: expected {expected_size}, got {source.size}"
            )
        canvas_contract = contract["referenceCanvas"]
        canvas_size = (canvas_contract["width"], canvas_contract["height"])
        margin = canvas_contract["margin"]
        available = (canvas_size[0] - 2 * margin, canvas_size[1] - 2 * margin)
        background = tuple(canvas_contract["background"])
        output_dir.mkdir(parents=True, exist_ok=True)

        for view_name in VIEW_ORDER:
            view_contract = contract["referenceViews"][view_name]
            crop = source.crop(tuple(view_contract["crop"]))
            crop.thumbnail(available, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", canvas_size, background)
            offset = ((canvas_size[0] - crop.width) // 2, (canvas_size[1] - crop.height) // 2)
            canvas.alpha_composite(crop, offset)
            output_path = output_dir / f"{contract['character']}_{view_name}.png"
            canvas.convert("RGB").save(output_path, format="PNG", optimize=True)
            manifest["views"][view_name] = {
                "path": str(output_path),
                "crop": view_contract["crop"],
                "providerKey": view_contract["providerKey"],
                "sha256": sha256_file(output_path),
                "size": list(canvas_size),
            }
    return manifest


def main() -> int:
    args = parse_args()
    manifest = prepare_views(
        art_root=args.art_root,
        output_dir=args.output_dir,
        contract_path=args.contract,
        character=args.character,
        dry_run=args.dry_run,
    )
    manifest_path = args.output_dir.resolve() / "reference-views-manifest.json"
    write_json(manifest_path, manifest)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
