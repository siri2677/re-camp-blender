#!/usr/bin/env python3
"""Create visual and artifact QA records for the current pre-Unity package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


CHARACTERS = ("CH101", "CH102", "CH103", "CH104", "CH105")
VIEWS = ("front", "side", "back")
POSES = ("A_Pose_Check", "Idle", "Run", "Attack")
EXPORT_CONTRACT = {
    "version": "pre-unity-export-v001",
    "unit_scale": 1.0,
    "axis_forward": "-Z",
    "axis_up": "Y",
    "leaf_bones": False,
    "animation_bake": True,
    "lod_policy": "LOD0 source plus generated LOD1/LOD2 proxies; Unity LODGroup pending",
    "collider_policy": "7 bone-parented box proxies; Unity physics review pending",
    "face_policy": "8 named placeholder targets; Unity driver wiring pending",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_paths(output_root: Path, row: dict) -> list[Path]:
    character = row["id"]
    output_dir = output_root / character
    return [
        output_dir / f"{character}_Blockout_REVIEW_v007.blend",
        output_dir / f"{character}_Blockout_REVIEW_v007.fbx",
        output_dir / "reports" / f"{character}_validation.json",
        *(output_dir / "renders" / f"{view}.png" for view in VIEWS),
        *(output_dir / "renders" / "poses" / f"{character}_{pose}.png" for pose in POSES),
    ]


def load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_contact_sheet(output_root: Path, art_root: Path, roster: list[dict], destination: Path) -> None:
    tile_width, tile_height = 320, 300
    label_height = 34
    columns = 4
    rows = len(roster)
    sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "#1b1d22")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(18)
    label_font = load_font(16)

    for row_index, row in enumerate(roster):
        character = row["id"]
        output_dir = output_root / character
        paths = [
            ("APPROVED SHEET", art_root / row["source_asset"]),
            ("3D FRONT", output_dir / "renders" / "front.png"),
            ("3D SIDE", output_dir / "renders" / "side.png"),
            ("3D BACK", output_dir / "renders" / "back.png"),
        ]
        y = row_index * (tile_height + label_height)
        draw.text((8, y + 6), f"{character} {row.get('name', '')}", fill="white", font=title_font)
        for column, (label, path) in enumerate(paths):
            x = column * tile_width
            tile = Image.new("RGB", (tile_width, tile_height), "#30343b")
            with Image.open(path).convert("RGB") as source:
                preview = ImageOps.contain(source, (tile_width - 16, tile_height - 16))
                tile.paste(preview, ((tile_width - preview.width) // 2, (tile_height - preview.height) // 2))
            sheet.paste(tile, (x, y + label_height))
            draw.text((x + 8, y + label_height + 8), label, fill="#f5d76e", font=label_font)

    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--art-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--contact-sheet", type=Path, required=True)
    parser.add_argument("--fbx-smoke-report", type=Path)
    parser.add_argument("--budget-report", type=Path)
    args = parser.parse_args()

    roster_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    roster = roster_manifest.get("roster", [])
    if [row.get("id") for row in roster] != list(CHARACTERS):
        raise RuntimeError("Roster manifest must contain CH101 through CH105 in order")

    missing_by_character: dict[str, list[str]] = {}
    validation_status: dict[str, str] = {}
    for row in roster:
        missing = [str(path.relative_to(args.output_root)) for path in required_paths(args.output_root, row) if not path.is_file()]
        missing_by_character[row["id"]] = missing
        report = args.output_root / row["id"] / "reports" / f"{row['id']}_validation.json"
        validation_status[row["id"]] = json.loads(report.read_text(encoding="utf-8")).get("status", "MISSING") if report.is_file() else "MISSING"

    if any(missing_by_character.values()):
        raise RuntimeError(f"Missing pre-Unity artifacts: {missing_by_character}")
    fbx_smoke = None
    if args.fbx_smoke_report:
        fbx_smoke = json.loads(args.fbx_smoke_report.read_text(encoding="utf-8"))
        if fbx_smoke.get("status") != "PASS":
            raise RuntimeError("FBX re-import smoke test did not PASS")
    budget = None
    if args.budget_report:
        budget = json.loads(args.budget_report.read_text(encoding="utf-8"))
        if budget.get("status") != "PASS":
            raise RuntimeError("Pre-Unity performance budget check did not PASS")
    make_contact_sheet(args.output_root, args.art_root, roster, args.contact_sheet)

    files = []
    for path in sorted(args.output_root.rglob("*")):
        if path.is_file() and path.name != "pre_unity_package_manifest.json":
            files.append({
                "path": str(path.relative_to(args.output_root)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    package_manifest = {
        "status": "PASS",
        "characters": list(CHARACTERS),
        "validation_status": validation_status,
        "visual_qa": {
            "contact_sheet": str(args.contact_sheet.relative_to(args.output_root)).replace("\\", "/"),
            "approved_sheet_vs_front_side_back": "REVIEW_READY",
            "views": list(VIEWS),
        },
        "artifact_contract": {
            "blend_count": 5,
            "fbx_count": 5,
            "validation_report_count": 5,
            "view_render_count": 15,
            "pose_render_count": 20,
        },
        "export_contract": EXPORT_CONTRACT,
        "fbx_reimport_smoke_test": fbx_smoke,
        "performance_budget": budget,
        "files": files,
    }
    destination = args.output_root / "pre_unity_package_manifest.json"
    destination.write_text(json.dumps(package_manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "contact_sheet": str(args.contact_sheet), "files": len(files)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
