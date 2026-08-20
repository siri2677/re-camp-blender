# GPU/No-GPU 자동 전환 계획

## 단일 실행점

`scripts/run_adaptive_workstream.py`가 런타임의 NVIDIA GPU를 먼저 검사하고
다음 작업 흐름 중 하나를 선택한다.

```text
python scripts/run_adaptive_workstream.py \
  --provider wonder3D \
  --art-root /path/to/re-camp-art \
  --output /path/to/adaptive-workstream-report.json
```

| 감지 결과 | 선택 경로 | 실제 수행 내용 |
|---|---|---|
| `READY_GPU_VISIBLE` | `GPU` | Notebook의 무료 Provider 설치·추론 단계 계속 |
| `BLOCKED_GPU_UNAVAILABLE` | `NO_GPU` | compile, unittest, 계약·CI·reference dry-run, Unity handoff 정적 검증 |
| Tripo 선택 | `NON_GPU_PROVIDER` | API key가 있으면 API 경로, 없으면 zero-credit dry-run |

자동 실행기는 AI 추론을 직접 시작하지 않는다. GPU가 보이는 경우에만 호출한
Notebook이 다음 셀의 실제 Provider 추론을 계속할 수 있도록 허용한다. GPU가
없으면 무거운 CUDA·Blender Provider 설치 전에 `run_no_gpu_workstream.py`를
실행하고 종료 상태를 report에 기록한다.

## GPU 사용 가능 경로

1. runtime preflight에서 NVIDIA GPU 확인
2. 기존 후보 또는 Wonder3D multiview 결과의 hash·commit 재사용 검사
3. Stable Fast 3D → InstantMesh → TripoSR 무료 fallback 또는 Wonder3D 연구 경로
4. Blender refine·4방향 렌더·평가·점수·순위
5. 기준 미달 시 최대 3회 후 `REGENERATE_REQUIRED`
6. 기준 통과 시에도 Alpha Review 후보로만 보관

Wonder3D의 6-view를 재사용해도 NeuS mesh extraction에는 GPU가 필요하므로,
multiview 재사용만으로 GPU preflight를 우회하지 않는다.

## GPU 사용 불가 경로

1. Notebook·Python·Blender script compile
2. 전체 unittest와 Colab/AI3D package validator
3. CH101~CH105 Socket·handoff·Unity package preflight
4. art 저장소가 있으면 reference crop와 SHA256 확인
5. Tripo payload zero-credit dry-run
6. Unity handoff 정적 검증
7. `RETRY_ADAPTIVE_RUNNER_WHEN_GPU_RETURNS` 상태 기록

이 경로에서는 실제 inference, 후보 manifest, Review `.blend`, Unity package를
생성하지 않는다.

## 항상 유지하는 Gate

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

실제 Production Mesh 확보와 사람 Gate B 승인 전에는 자동 전환 여부와 관계없이
Unity Import·Prefab·Android 단계로 승격하지 않는다.
