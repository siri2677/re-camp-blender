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
6. Stable Fast 3D·InstantMesh·TripoSR·Wonder3D provider 명령과 fallback 정적 검증
7. Colab runtime preflight와 후보 manifest 재사용 로직 검증
8. Wonder3D Notebook은 GPU preflight를 Blender·CUDA 의존성 설치보다 먼저 수행
9. 검증된 Wonder3D 6-view 출력은 GPU preflight 전에 재사용하고, 불일치하면 신규 실행으로 전환
10. README·실행 계획·실행 기록·CI 동기화

로컬에 art 저장소가 있으면 runner가 `RE_CAMP_SOURCE_DIR`를 자동으로 연결해
source lock의 커밋과 권위 CH101 원본 파일까지 확인한다. art 저장소가 없는 CI나
새 환경에서는 이 교차 저장소 확인만 건너뛰고 나머지 정적 검증을 계속한다.
Unity handoff validator가 art 저장소에 있으면 CH101~CH105 계약 검증도 같은
실행에 포함한다.

실행 명령:

```text
python scripts/run_no_gpu_workstream.py
```

art 저장소가 준비되지 않은 CI에서는 reference dry-run만 건너뛴다.

```text
python scripts/run_no_gpu_workstream.py --skip-reference
```

이 runner는 위 명령에 포함된 `provider-runtime-preflight` 단계에서 다섯 Provider를
동시에 확인한다. GPU Provider의 `BLOCKED_GPU_UNAVAILABLE`은 예상된 외부 차단으로
분류하고, 예기치 않은 preflight 오류만 runner 실패로 처리한다.

## GPU가 다시 연결될 때까지 보류하는 작업

- Stable Fast 3D, InstantMesh, TripoSR 실제 inference
- Wonder3D multiview inference와 NeuS mesh extraction
- 새 후보의 Blender 렌더·점수 산정
- Alpha Review 후보 생성
- Gate B 사람 승인
- 실제 FBX/GLB export와 Unity Import
- Android build·실기기 성능 측정

Tripo API는 GPU가 없어도 호출 준비는 가능하지만 선택적 유료·비밀키 경로이므로
무료 Provider workstream에서는 사용하지 않는다. 키와 비용 승인이 별도로 없으면
계속 payload dry-run만 수행한다.

## 단계 상태

| 단계 | 상태 |
|---|---|
| 저장소 정적 검증 runner | IMPLEMENTED |
| 계약·handoff·Gate 음성 검증 | IMPLEMENTED |
| reference·Tripo payload dry-run | IMPLEMENTED WHEN ART ROOT EXISTS |
| Unity handoff 정적 검증 | IMPLEMENTED WHEN ART ROOT EXISTS |
| GPU runtime preflight | IMPLEMENTED |
| 실제 무료 Provider 후보 생성 | BLOCKED_COLAB_GPU_QUOTA |
| Unity·Android | BLOCKED_EXTERNAL_ENVIRONMENT |

## 최근 실행 기록

2026-08-20 기준으로 No-GPU runner를 art 저장소 연결 모드와 CI 모드에서 모두
실행했다. Colab 패키지(7개 Notebook/7개 Blender script/12개 유틸리티), 무료
AI3D 패키지, Python compile, 전체 25개 unittest, 다섯 Provider runtime preflight,
front/right/back reference
준비, Tripo multiview payload dry-run, CH101~CH105 Unity handoff 정적 검증이
통과했다. Wonder3D 실행 Notebook과 PLY 후보 등록 경로도 정적 검증에 포함된다.
실제 Provider 추론은 실행하지 않았고, Gate와 Unity 입력 잠금은 유지했다.

상세 기록: `docs/records/ch101-ai3d/2026-08-19-no-gpu-workstream.json`
최신 art 연결 실행: `docs/records/ch101-ai3d/2026-08-20-no-gpu-workstream-v001.json`
최신 CI 모드 실행: `docs/records/ch101-ai3d/2026-08-20-no-gpu-ci-mode-v001.json`
최신 Provider preflight와 Wonder3D pinned-command dry-run:
`docs/records/ch101-ai3d/2026-08-20-no-gpu-preflight-wonder3d-dry-run-v001.json`
최신 runner 통합 Provider preflight 실행:
`docs/records/ch101-ai3d/2026-08-20-no-gpu-runner-provider-preflight-v001.json`
최신 art 연결 전체 runner 실행(reference crop·Tripo dry-run·Unity handoff 포함):
`docs/records/ch101-ai3d/2026-08-20-no-gpu-runner-art-connected-v001.json`
Wonder3D 재사용 gate와 28개 테스트 검증 결과:
`docs/records/ch101-ai3d/2026-08-20-wonder3d-reuse-gate-validation-v001.json`
최신 Colab GPU 연결 재시도 결과는 사용량 제한으로 `BLOCKED_GPU_QUOTA`였으며,
CPU fallback은 선택하지 않았다:
`docs/records/ch101-ai3d/2026-08-20-wonder3d-colab-gpu-retry-v001.json`

## 재개 규칙

GPU가 연결되면 먼저 runtime preflight를 실행하고, `READY_GPU_VISIBLE`일 때만
provider 셀을 실행한다. 기존 `candidate-manifest.json`과 모델 파일이 유효하면
자동 재사용하고, 새 후보가 필요할 때만
`RE_CAMP_REUSE_CANDIDATES=0`으로 강제 재생성한다.

Wonder3D Notebook은 이 규칙을 실행 순서로도 보장한다. GPU가 보이지 않으면
`BLOCKED_GPU_UNAVAILABLE`을 출력하고 즉시 중단하므로 Blender·CUDA·tiny-cuda-nn
설치를 시작하지 않는다. 따라서 GPU quota가 막힌 세션에서는 설치 시간과 세션
디스크를 소비하지 않고, quota가 복구된 뒤 같은 Notebook을 재실행하면 된다.

기존 Wonder3D report가 pinned provider commit, reference manifest SHA256, 6개 view
파일, Gate 잠금 조건을 모두 만족하면 `REUSED`로 표시하고 inference를 생략한다.
`RE_CAMP_REUSE_WONDER3D=0`이면 이 재사용을 비활성화하고 GPU preflight부터 다시
수행한다. hash·파일·commit 중 하나라도 어긋나면 기존 파일은 삭제하지 않고
`NOT_REUSABLE` 사유를 기록한 뒤 신규 실행 경로로 전환한다.

No-GPU runner 결과는 실행 환경별 정보이므로 기본적으로 Git에 저장하지 않는다.
중요한 판정·SHA256·Gate 결과만 `docs/records/`에 별도 기록한다.
