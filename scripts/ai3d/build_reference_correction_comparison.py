"""Compare fixed reference masks, actual renders and strict QA on one basis.

Produces diagnostic contact sheets, not generated art or approval evidence.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    from .common import load_contract, require_reference_manifest, sha256_file, write_json, candidate_gate_fields
    from .score_candidate_renders import build_score_report, _normalize_view
    from .build_assisted_visual_review import build_review
except ImportError:
    from common import load_contract, require_reference_manifest, sha256_file, write_json, candidate_gate_fields
    from score_candidate_renders import build_score_report, _normalize_view
    from build_assisted_visual_review import build_review

ROOT = Path(__file__).resolve().parents[2]


def build(args):
    contract = load_contract(ROOT / 'contracts/ch101_ai3d_free_pipeline_v001.json', 'CH101')
    refs = require_reference_manifest(args.reference_manifest.resolve(), contract)
    if args.output_dir.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    args.output_dir.mkdir(parents=True)
    evaluated = []
    reports = []
    for index, path in enumerate(args.evaluation):
        evaluation = json.loads(path.read_text(encoding='utf-8'))
        score = build_score_report(contract, refs, evaluation)
        score_path = args.output_dir / f'{index}-candidate-score.json'
        write_json(score_path, score)
        reports.append((score_path, score))
        rendered_blend = Path(evaluation['normalizedBlend'])
        evaluated.append({
            'candidateId': score['candidateId'],
            'strategyId': score['strategyId'],
            'scores': {k: score[k] for k in ('overallScore', 'silhouetteScore', 'appearanceScore',
                                           'colorScore', 'faceDetailScore', 'technicalScore')},
            'evaluationSha256': sha256_file(path),
            'renderedBlendSha256': sha256_file(rendered_blend),
            'renderedBlendPath': str(rendered_blend),
            'rendersSha256': {k: sha256_file(Path(p)) for k, p in evaluation['renders'].items()},
        })
    review = build_review(contract, reports)
    write_json(args.output_dir / 'assisted-visual-review.json', review)
    for entry, decision in zip(evaluated, review['candidateReviews']):
        entry['disposition'] = decision['disposition']
        entry['reasonCodes'] = decision['reasonCodes']

    width, height = 320, 380
    canvas = Image.new('RGB', (width * (len(reports) + 1), height * 3 + 60), '#202631')
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 12), 'CH101: reference / candidate variants in evaluation input order', fill='white')
    draw.text((12, 32), 'NOT PRODUCTION - compare geometry and texture; numeric scores do not approve identity.', fill='white')
    for row, (ref_view, render_view) in enumerate((('front', 'neg_y'), ('right', 'pos_x'), ('back', 'pos_y'))):
        paths = [Path(refs['views'][ref_view]['path'])] + [Path(s['evaluationReport']['renders'][render_view]) for _, s in reports]
        for col, path in enumerate(paths):
            with Image.open(path) as src:
                picture = src.convert('RGBA')
                picture = ImageOps.contain(picture, (width - 12, height - 32))
            tile = Image.new('RGBA', picture.size, '#9299a4')
            tile.alpha_composite(picture)
            x = col * width + (width - picture.width) // 2
            y = 60 + row * height + 24
            canvas.paste(tile.convert('RGB'), (x, y))
            draw.text((col * width + 8, 60 + row * height + 4), ref_view if col == 0 else f'{render_view}  variant {col}', fill='white')
    canvas.save(args.output_dir / 'CH101_before_after_NOT_APPROVED.png')
    masks = Image.new('RGB', (256 * 3, 280), '#202631')
    for index, role in enumerate(('front', 'right', 'back')):
        normalized = _normalize_view(Path(refs['views'][role]['path']), False)
        masks.paste(normalized['detailMask'].convert('RGB'), (index * 256, 24))
        ImageDraw.Draw(masks).text((index * 256 + 8, 4), role + ' reference foreground', fill='white')
    masks.save(args.output_dir / 'reference-mask-audit.png')
    record = {
        'schemaVersion': 'ch101-reference-correction-comparison-v001',
        'artCommit': contract['artLock']['commit'],
        'referenceManifestSha256': sha256_file(args.reference_manifest),
        'status': 'REGENERATE_REQUIRED' if review['summary']['rejectedCandidateCount'] else 'PENDING_HUMAN_REVIEW',
        'candidates': evaluated,
        'historicalScoreComparisonAllowed': False,
        'comparisonBasis': 'ALL_INPUTS_RESCORED_WITH_LIGHT_NEUTRAL_BORDER_CANVAS_V002',
        'selectedCandidate': None,
        **candidate_gate_fields(contract),
    }
    write_json(args.output_dir / 'comparison.json', record)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-manifest', required=True, type=Path)
    parser.add_argument('--evaluation', required=True, action='append', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    build(parser.parse_args())
