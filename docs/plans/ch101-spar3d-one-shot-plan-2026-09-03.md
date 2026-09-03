# CH101 SPAR3D one-shot low-VRAM plan

## 목적

PartCrafter 결과가 `REGENERATE_REQUIRED`이고 같은 전략 재실행이 차단된 뒤,
새 Provider를 한 번만 비교한다. 대상은 Stability AI의 SPAR3D이며, 기존
PartCrafter·TRELLIS·semantic proxy의 점수나 실패 기록을 덮어쓰지 않는다.

공식 구현은 [SPAR3D 저장소](https://github.com/Stability-AI/stable-point-aware-3d),
모델 접근 조건과 라이선스는 [공식 Hugging Face 모델 카드](https://huggingface.co/stabilityai/stable-point-aware-3d)를
기준으로 한다. 공식 README의 `--low-vram-mode`는 기본 약 10.5GB에서 약 7GB
수준으로 줄이는 경로이므로, 저장소 preflight는 여유를 둔 8192MB를 최소값으로
사용한다. 이는 품질이나 성공을 보장하는 수치가 아니다.

## 고정 계약

- Provider: `spar3d`
- Strategy: `SPAR3D_SINGLE_VIEW_V001`
- Provider commit: `fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1`
- Model: `stabilityai/stable-point-aware-3d`
- Entrypoint: upstream `run.py` only
- Input: CH101 front reference view
- Memory mode: `--low-vram-mode`
- Max runs: 1
- Output: review-only GLB candidate

Notebook은 `HF_TOKEN`, `HUGGINGFACE_HUB_TOKEN`,
`HUGGINGFACEHUB_API_TOKEN` 중 하나가 존재하는지만 기록한다. 토큰 값과 Kaggle
Secret은 report, log, archive, Git에 기록하지 않는다. 모델 terms 접근 승인은
`RE_CAMP_SPAR3D_ACCESS_ACK=1`, 라이선스 확인은
`RE_CAMP_SPAR3D_LICENSE_ACK=1`로 명시해야 한다.

## 실행 순서

1. Notebook 07이 tools/art commit과 CH101 reference manifest를 고정한다.
2. `colab_runtime_preflight.py --provider spar3d`가 GPU, CUDA, PyTorch kernel,
   VRAM, token 존재 여부, 접근·라이선스 acknowledgement를 확인한다.
3. 조건이 하나라도 빠지면 heavyweight 설치·추론 없이
   `BLOCKED_PROVIDER_PREFLIGHT`로 종료한다.
4. 조건이 모두 충족될 때만 Notebook이 pinned checkout과 사용자가 제공한 setup
   command를 실행한다.
5. `run_spar3d_candidate.py`가 `run.py`를 Notebook과 같은 Python interpreter로
   실행하고, 정확히 하나의 non-empty `mesh.glb`를 확인한다.
6. GLB는 `register_review_candidate.py`로 등록한 뒤 기존 Blender refine →
   evaluate → score → strict visual QA → rank 경로를 통과한다.
7. 점수·geometry·시각 경계 중 하나라도 실패하면
   `REGENERATE_REQUIRED`를 기록하고 SPAR3D를 다시 실행하지 않는다.

## Gate

추론에 성공해도 아래 상태는 바꾸지 않는다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

자동 점수 통과는 사람 Gate B 승인이 아니다. 얼굴 BlendShape, 장비·리본 Socket,
CH101 디자인 일치 여부는 자동 승격 대상이 아니며, Gate B 승인 전에는 FBX/GLB
Unity package·Prefab·Android 작업을 시작하지 않는다.

## 현재 차단과 완료 기준

2026-09-03 기준 실제 SPAR3D 추론 결과는 아직 없다. 직전 Kaggle hybrid 실행은
T4 15GB에서 기존 전략 plateau와 TRELLIS VRAM preflight로
`NO_CANDIDATE_STRATEGY_READY`였다. 이번 변경은 다음 호환 Kaggle 세션에서
SPAR3D preflight를 먼저 실행하도록 준비한 것이다.

완료로 기록하려면 SPAR3D report, mesh SHA256, candidate manifest, Blender
evaluation/score/ranking 결과가 모두 있어야 한다. Kaggle GPU나 gated model
access가 없을 때는 차단 기록만 남기며 성공으로 표시하지 않는다.
