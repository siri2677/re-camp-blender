#!/usr/bin/env python3
"""Prepare locked no-GPU reference views for CH101 through CH105."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .common import (
        EXPECTED_ROSTER_CHARACTERS,
        ROSTER_CONTRACT_PATH,
        load_roster_contract_index,
        sha256_file,
        write_json,
    )
    from .prepare_reference_views import prepare_views
except ImportError:
    from common import (  # type: ignore
        EXPECTED_ROSTER_CHARACTERS,
        ROSTER_CONTRACT_PATH,
        load_roster_contract_index,
        sha256_file,
        write_json,
    )
    from prepare_reference_views import prepare_views  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=ROSTER_CONTRACT_PATH)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def prepare_roster(
    art_root: Path,
    output_root: Path,
    contract_path: Path = ROSTER_CONTRACT_PATH,
    dry_run: bool = False,
    contact_sheet_path: Path | None = None,
) -> dict[str, object]:
    roster = load_roster_contract_index(contract_path)
    output_root = output_root.resolve()
    characters = []
    prepared_manifests: dict[str, dict[str, object]] = {}
    for character in EXPECTED_ROSTER_CHARACTERS:
        output_dir = output_root / character / "reference-views"
        manifest = prepare_views(
            art_root=art_root,
            output_dir=output_dir,
            contract_path=contract_path,
            character=character,
            dry_run=dry_run,
        )
        manifest_path = output_dir / "reference-views-manifest.json"
        write_json(manifest_path, manifest)
        prepared_manifests[character] = manifest
        characters.append(
            {
                "character": character,
                "status": manifest["status"],
                "manifest": str(manifest_path),
                "manifestSha256": sha256_file(manifest_path),
                "generationSourceRole": manifest["generationSourceRole"],
                "viewSha256": {
                    name: entry["sha256"]
                    for name, entry in manifest["views"].items()
                },
            }
        )
    report = {
        "contractVersion": roster["contractVersion"],
        "status": (
            "CURRENT_ROSTER_REFERENCE_VIEW_PLAN"
            if dry_run
            else "CURRENT_ROSTER_REFERENCE_VIEWS_READY"
        ),
        "characters": characters,
        "characterOrder": list(EXPECTED_ROSTER_CHARACTERS),
        "gpuRequired": False,
        "actualInference": False,
        "gateB": "PENDING_HUMAN_REVIEW",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }
    if not dry_run and contact_sheet_path is not None:
        from PIL import Image, ImageDraw, ImageFont

        image_size = (260, 260)
        label_height = 30
        title_height = 70
        sheet = Image.new(
            "RGB",
            (image_size[0] * 3, title_height + (image_size[1] + label_height) * 5),
            (22, 27, 35),
        )
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default()
        draw.text(
            (18, 18),
            "Current Roster Locked Reference Views | NO GPU | NOT PRODUCTION",
            fill=(255, 232, 128),
            font=font,
        )
        for row, character in enumerate(EXPECTED_ROSTER_CHARACTERS):
            manifest = prepared_manifests[character]
            for column, view_name in enumerate(("front", "right", "back")):
                path = Path(manifest["views"][view_name]["path"])
                with Image.open(path) as source:
                    image = source.convert("RGB")
                image.thumbnail(image_size, Image.Resampling.LANCZOS)
                x = column * image_size[0]
                y = title_height + row * (image_size[1] + label_height)
                canvas = Image.new("RGB", image_size, (248, 249, 251))
                canvas.paste(
                    image,
                    ((image_size[0] - image.width) // 2, (image_size[1] - image.height) // 2),
                )
                sheet.paste(canvas, (x, y))
                draw.text(
                    (x + 8, y + image_size[1] + 8),
                    f"{character} {view_name}",
                    fill=(225, 230, 238),
                    font=font,
                )
        contact_sheet_path = contact_sheet_path.resolve()
        contact_sheet_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(contact_sheet_path, format="PNG", optimize=True)
        report["contactSheet"] = str(contact_sheet_path)
        report["contactSheetSha256"] = sha256_file(contact_sheet_path)
    write_json(output_root / "current-roster-reference-summary.json", report)
    return report


def main() -> int:
    args = parse_args()
    report = prepare_roster(
        art_root=args.art_root.resolve(),
        output_root=args.output_root.resolve(),
        contract_path=args.contract.resolve(),
        dry_run=args.dry_run,
        contact_sheet_path=args.contact_sheet,
    )
    print(args.output_root.resolve() / "current-roster-reference-summary.json")
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
