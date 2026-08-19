# CH101 No-GPU Workstream 계획

## 목적

Colab GPU가 연결되지 않거나 사용량 제한에 걸린 동안에도 저장소의 품질과
재실행 가능성을 계속 높인다. 이 workstream은 AI 모델 추론이나 Production Mesh
승인을 수행하지 않으며, 모든 결과는 다음 상태를 유지한다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## GPU 없이 진행하는 작업

1. Python·Notebook·Blender 스크립트 compile 검증
2. CH101~CH105 Socket 계약과 파일명·source reference 정합성 검증
3. handoff 병합·Unity manifest의 음성 테스트
4. 승인 art commit 기준 front/right/back reference crop 및 SHA256 dry-run
5. Tripo multiview payload dry-run
6. Stable Fast 3D·InstantMesh·TripoSR provider 명령과 fallback 정적 검증
7. Colab runtime preflight와 후보 manifest 재사용 로직 검증
8. README·실행 계획·실행 기록·CI 동기화

로컬에 art 저장소가 있으면 runner가 `RE_CAMP_SOURCE_DIR`를 자동으로 연결해
source lock의 커밋과 권위 CH101 원본 파일까지 확인한다. art 저장소가 없는 CI나
새 환경에서는 이 교차 저장소 확인만 건너뛰고 나머지 정적 검증을 계속한다.

실행 명령:

```text
python scripts/run_no_gpu_workstream.py
```

art 저장소가 준비되지 않은 CI에서는 reference dry-run만 건너뛴다.

```text
python scripts/run_no_gpu_workstream.py --skip-reference
```

## GPU가 다시 연결될 때까지 보류하는 작업

- Stable Fast 3D, InstantMesh, TripoSR 실제 inference
- 새 후보의 Blender 렌더·점수 산정
- Alpha Review 후보 생성
- Gate B 사람 승인
- 실제 FBX/GLB export와 Unity Import
- Android build·실기기 성능 측정

## 단계 상태

| 단계 | 상태 |
|---|---|
| 저장소 정적 검증 runner | IMPLEMENTED |
| 계약·handoff·Gate 음성 검증 | IMPLEMENTED |
| reference·Tripo payload dry-run | IMPLEMENTED WHEN ART ROOT EXISTS |
| GPU runtime preflight | IMPLEMENTED |
| 실제 무료 Provider 후보 생성 | BLOCKED_COLAB_GPU_QUOTA |
| Unity·Android | BLOCKED_EXTERNAL_ENVIRONMENT |

## 최근 실행 기록

2026-08-19 기준으로 No-GPU runner를 실행했다. Colab 패키지, 무료 AI3D
패키지, Python compile, 16개 unittest, front/right/back reference 준비와
Tripo multiview payload dry-run이 모두 통과했다. 실제 Provider 추론은 실행하지
않았고, Gate와 Unity 입력 잠금은 유지했다.

상세 기록: `docs/records/ch101-ai3d/2026-08-19-no-gpu-workstream.json`

## 재개 규칙

GPU가 연결되면 먼저 runtime preflight를 실행하고, `READY_GPU_VISIBLE`일 때만
provider 셀을 실행한다. 기존 `candidate-manifest.json`과 모델 파일이 유효하면
자동 재사용하고, 새 후보가 필요할 때만
`RE_CAMP_REUSE_CANDIDATES=0`으로 강제 재생성한다.

No-GPU runner 결과는 실행 환경별 정보이므로 기본적으로 Git에 저장하지 않는다.
중요한 판정·SHA256·Gate 결과만 `docs/records/`에 별도 기록한다.
