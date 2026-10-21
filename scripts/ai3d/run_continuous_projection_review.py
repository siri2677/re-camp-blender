"""One-shot, pinned-reference continuous projection experiment and strict review."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from common import load_contract, require_reference_manifest, sha256_file, write_json, candidate_gate_fields
from quality_progress_gate import build_progress_gate, collect_history

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = 'CH101_CONTINUOUS_WORLD_PROJECTION_V001'


def run(args):
    contract = load_contract(ROOT/'contracts/ch101_ai3d_free_pipeline_v001.json','CH101')
    refs = require_reference_manifest(args.reference_manifest.resolve(),contract)
    if sha256_file(args.reference_manifest) != args.reference_sha256:
        raise ValueError('REFERENCE_MANIFEST_SHA256_MISMATCH')
    if sha256_file(args.input_blend) != args.input_sha256:
        raise ValueError('INPUT_BLEND_SHA256_MISMATCH')
    if args.output_dir.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    args.output_dir.mkdir(parents=True)
    out = args.output_dir.resolve()
    history = collect_history(out.parent, (ROOT/'docs/records/ch101-ai3d').glob('*.json'))
    gate = build_progress_gate(provider='spar3d-postprocess',strategy_id=STRATEGY,history=history)
    write_json(out/'quality-progress.json',gate)
    if gate['status'] != 'READY_NEW_STRATEGY':
        return 2
    report = {'strategyId':STRATEGY,'candidateId':STRATEGY,'status':'RUNNING',
              'artCommit':contract['artLock']['commit'],'inputBlendSha256':args.input_sha256,
              'referenceManifestSha256':args.reference_sha256,
              'providerInferenceExecuted':False,**candidate_gate_fields(contract)}
    write_json(out/'run-report.json',report)
    env = os.environ.copy()
    env['RE_CAMP_REVIEW_RENDER_ENGINE'] = 'EEVEE'

    def execute(stage,command):
        result = subprocess.run([str(x) for x in command],env=env,capture_output=True,text=True,errors='replace')
        if result.returncode:
            raise RuntimeError(f'{stage}_FAILED_EXIT_{result.returncode}')

    def blender(stage,script,*opts):
        execute(stage,[args.blender,'-b','--python-exit-code','1','--python',ROOT/'scripts/blender'/script,'--',*opts])

    try:
        model = out/'CH101_ContinuousProjection_NOT_PRODUCTION.blend'
        options=[]
        for role in ('front','right','back'):
            options.extend(['--'+role+'-image',refs['views'][role]['path']])
        blender('PROJECTION','apply_continuous_review_projection.py',
                '--input-blend',args.input_blend,'--input-sha256',args.input_sha256,
                '--output-blend',model,'--report',out/'projection-report.json',*options)
        evaluation = out/'evaluation-report.json'
        blender('EVALUATION','evaluate_ai3d_candidate.py','--candidate',model,
                '--candidate-id',STRATEGY,'--strategy-id',STRATEGY,'--output-dir',out,
                '--report',evaluation,'--reuse-normalized-blend',model,'--integrity-blend',model,
                '--normalized-blend',out/'CH101_Review_NOT_PRODUCTION.blend')
        score=out/'candidate-score.json'
        execute('SCORE',[sys.executable,ROOT/'scripts/ai3d/score_candidate_renders.py',
                '--reference-manifest',args.reference_manifest,'--evaluation-report',evaluation,'--output',score])
        review=out/'assisted-visual-review.json'
        execute('QA',[sys.executable,ROOT/'scripts/ai3d/build_assisted_visual_review.py',
                '--score-report',score,'--output',review])
        execute('RANK',[sys.executable,ROOT/'scripts/ai3d/rank_candidates.py',
                '--score-report',score,'--assisted-visual-review',review,'--output',out/'ranking.json'])
        verdict=json.loads(review.read_text(encoding='utf-8'))
        report['status']='REGENERATE_REQUIRED' if verdict['summary']['rejectedCandidateCount'] else 'PENDING_HUMAN_REVIEW'
        report['outputBlendSha256']=sha256_file(model)
    except RuntimeError as error:
        report.update(status='EXECUTION_FAILED',reason=str(error))
    write_json(out/'run-report.json',report)
    print(json.dumps(report,indent=2))
    return 1 if report['status']=='EXECUTION_FAILED' else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for field in ('input-blend','reference-manifest','output-dir','blender'):
        parser.add_argument('--'+field,required=True,type=Path)
    parser.add_argument('--input-sha256',required=True)
    parser.add_argument('--reference-sha256',required=True)
    raise SystemExit(run(parser.parse_args()))
