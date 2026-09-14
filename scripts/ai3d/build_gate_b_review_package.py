#!/usr/bin/env python3
"""Build a deterministic Gate B comparison sheet without approving Gate B."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from .common import (
        DEFAULT_CONTRACT_PATH,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )
except ImportError:
    from common import (  # type: ignore
        DEFAULT_CONTRACT_PATH,
        load_contract,
        read_json,
        require_reference_manifest,
        sha256_file,
        write_json,
    )


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--ranking-manifest", required=True, type=Path)
    parser.add_argument("--assisted-visual-review", required=True, type=Path)
    parser.add_argument("--evaluation-dir", required=True, type=Path)
    parser.add_argument("--contact-sheet", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character")
    parser.add_argument("--top-count", type=int, default=3)
    return parser.parse_args()


def _load_font(size: int):
    from PIL import ImageFont

    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _resolve_render(
    entry: dict[str, Any], render_name: str, evaluation_dir: Path
) -> Path:
    recorded = Path(entry.get("renders", {}).get(render_name, ""))
    candidates = (
        recorded,
        evaluation_dir / entry["candidateId"] / "renders" / recorded.name,
        evaluation_dir / entry["candidateId"] / "renders" / f"{render_name}.png",
    )
    resolved = next((path.resolve() for path in candidates if path.is_file()), None)
    if resolved is None:
        raise FileNotFoundError(
            f"missing render for {entry['candidateId']} view {render_name}"
        )
    return resolved


def _fit_image(path: Path, size: tuple[int, int]):
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (245, 247, 250))
    offset = ((size[0] - image.width) // 2, (size[1] - image.height) // 2)
    canvas.paste(image, offset)
    return canvas


def build_review_package(
    contract: dict[str, Any],
    references: dict[str, Any],
    ranking: dict[str, Any],
    assisted_review: dict[str, Any],
    evaluation_dir: Path,
    contact_sheet_path: Path,
    manifest_path: Path,
    ranking_path: Path,
    review_path: Path,
    top_count: int = 3,
) -> dict[str, Any]:
    from PIL import Image, ImageDraw

    if ranking.get("character") != contract["character"]:
        raise ValueError("ranking character mismatch")
    if ranking.get("artCommit") != contract["artLock"]["commit"]:
        raise ValueError("ranking art commit mismatch")
    if ranking.get("unityInputAllowed") is not False:
        raise ValueError("ranking cannot enable Unity input")
    if ranking.get("productionPromotionAllowed") is not False:
        raise ValueError("ranking cannot enable production promotion")
    if assisted_review.get("reviewerClass") != "ASSISTED_VISUAL_QA_NOT_HUMAN_GATE_B":
        raise ValueError("review package requires a non-authoritative assisted review")
    if assisted_review.get("humanGateBDecision") != GATE_B:
        raise ValueError("assisted review must keep Gate B pending")
    if assisted_review.get("unityInputAllowed") is not False:
        raise ValueError("assisted review cannot enable Unity input")
    if ranking.get("assistedVisualReview", {}).get("reviewVersion") != assisted_review.get(
        "reviewVersion"
    ):
        raise ValueError("ranking was not generated from the supplied assisted review")

    entries = list(ranking.get("ranking", []))[: max(1, top_count)]
    if not entries:
        raise ValueError("ranking contains no candidates")
    decision_by_id = {
        item["candidateId"]: item for item in assisted_review.get("candidateReviews", [])
    }
    reference_paths = {
        name: Path(references["views"][name]["path"]).resolve()
        for name in ("front", "right", "back")
    }

    labels = (
        "Reference Front",
        "Candidate Front",
        "Reference Right",
        "Candidate Right",
        "Reference Back",
        "Candidate Back",
        "Candidate 3/4",
    )
    image_size = (220, 250)
    column_width = 236
    title_height = 108
    row_header_height = 52
    row_height = row_header_height + image_size[1] + 40
    width = column_width * len(labels)
    height = title_height + row_height * len(entries)
    sheet = Image.new("RGB", (width, height), (19, 23, 31))
    draw = ImageDraw.Draw(sheet)
    title_font = _load_font(30)
    body_font = _load_font(18)
    small_font = _load_font(14)
    draw.text((24, 16), "CH101 Gate B Comparison — NOT APPROVED", fill=(255, 232, 128), font=title_font)
    draw.text(
        (24, 60),
        "AI candidate only | Gate B: PENDING_HUMAN_REVIEW | Unity input: false",
        fill=(245, 150, 150),
        font=body_font,
    )

    input_files: list[dict[str, Any]] = []
    for row_index, entry in enumerate(entries):
        row_top = title_height + row_index * row_height
        decision = decision_by_id.get(entry["candidateId"], {})
        disposition = decision.get(
            "disposition", entry.get("assistedVisualReviewDisposition", "NOT_REVIEWED")
        )
        hard_gate = entry.get("qualityHardGateAudit", {}).get("status", "UNKNOWN")
        summary = (
            f"#{entry['rank']} {entry['candidateId']}  overall={entry['overallScore']:.6f}  "
            f"geometry={hard_gate}  assistedVisual={disposition}"
        )
        draw.rectangle(
            (0, row_top, width, row_top + row_header_height),
            fill=(43, 50, 63) if row_index % 2 == 0 else (36, 43, 55),
        )
        draw.text((18, row_top + 14), summary, fill=(240, 243, 247), font=body_font)

        orientation = entry.get("selectedOrientation", {})
        candidate_paths = {
            "front": _resolve_render(entry, orientation["front"], evaluation_dir),
            "right": _resolve_render(entry, orientation["right"], evaluation_dir),
            "back": _resolve_render(entry, orientation["back"], evaluation_dir),
            "three_quarter": _resolve_render(entry, "three_quarter", evaluation_dir),
        }
        paths = (
            reference_paths["front"],
            candidate_paths["front"],
            reference_paths["right"],
            candidate_paths["right"],
            reference_paths["back"],
            candidate_paths["back"],
            candidate_paths["three_quarter"],
        )
        image_top = row_top + row_header_height + 28
        for column_index, (label, path) in enumerate(zip(labels, paths)):
            x = column_index * column_width + 8
            draw.text((x + 4, row_top + row_header_height + 5), label, fill=(195, 205, 218), font=small_font)
            sheet.paste(_fit_image(path, image_size), (x, image_top))
            input_files.append(
                {
                    "candidateId": entry["candidateId"],
                    "label": label,
                    "fileName": path.name,
                    "sha256": sha256_file(path),
                }
            )

    contact_sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact_sheet_path, format="PNG", optimize=True)
    manifest = {
        "packageVersion": "ch101-gate-b-review-package-v001",
        "character": contract["character"],
        "status": "GATE_B_REVIEW_PACKAGE_READY_NOT_APPROVED",
        "sourceStatus": SOURCE_STATUS,
        "artCommit": contract["artLock"]["commit"],
        "rankingManifest": str(ranking_path.resolve()),
        "rankingManifestSha256": sha256_file(ranking_path),
        "assistedVisualReview": str(review_path.resolve()),
        "assistedVisualReviewSha256": sha256_file(review_path),
        "contactSheet": str(contact_sheet_path.resolve()),
        "contactSheetSha256": sha256_file(contact_sheet_path),
        "candidateCount": len(entries),
        "candidateIds": [entry["candidateId"] for entry in entries],
        "inputFiles": input_files,
        "recommendation": assisted_review.get("recommendation", ""),
        "humanGateBDecision": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    reference_path = args.reference_manifest.resolve()
    ranking_path = args.ranking_manifest.resolve()
    review_path = args.assisted_visual_review.resolve()
    references = require_reference_manifest(reference_path, contract)
    ranking = read_json(ranking_path)
    assisted_review = read_json(review_path)
    manifest = build_review_package(
        contract=contract,
        references=references,
        ranking=ranking,
        assisted_review=assisted_review,
        evaluation_dir=args.evaluation_dir.resolve(),
        contact_sheet_path=args.contact_sheet.resolve(),
        manifest_path=args.manifest.resolve(),
        ranking_path=ranking_path,
        review_path=review_path,
        top_count=args.top_count,
    )
    print(args.contact_sheet.resolve())
    print(args.manifest.resolve())
    print(manifest["contactSheetSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
