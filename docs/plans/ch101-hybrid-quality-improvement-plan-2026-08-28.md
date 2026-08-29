# CH101 무료 하이브리드 품질 개선 계획

## 목적

Wonder3D의 동일 전략 반복을 중단하고, 무료 환경에서 의미론적 구조가 실제로
늘어나는 두 경로를 각각 한 번만 평가한다.

- `TRELLIS_SINGLE_VIEW_V001`: TRELLIS 단일 이미지 연구 경로. GPU, VRAM 24576 MB
  이상, CUDA 커널, upstream/checkpoint 약관 확인이 모두 통과할 때만 실행한다.
- `SEMANTIC_PROXY_REFERENCE_FITTED_V001`: 승인 Character/Turnaround/Equipment/
  Expression reference를 검증하고 CPU Blender로 body/face, hair, outfit,
  equipment를 별도 구조로 만드는 review-only proxy.
- `UNIFIED_SEMANTIC_AUTHORING_V002`: V001 거절 이후의 1회성 semantic pivot. V001의
  분리 primitive를 반복하지 않고, primary shell을 실제 connected mesh로 voxel
  remesh한 뒤 body/face, hair, outfit, equipment label을 보존한다.
- `SEMANTIC_DETAIL_AUTHORING_V003`: V002 품질 정체 이후의 1회성 Blender semantic
  detail pivot. body shell만 remesh하고 face detail, hair, outfit, equipment를
  별도 그룹으로 보존해 얼굴·헤어·의상 판독성을 확인한다. 연결형 primary shell
  외의 세부 그룹은 review-only이며 Gate B/Unity 입력을 열지 않는다.

두 경로 모두 `refine_ai3d_candidate.py` → `evaluate_ai3d_candidate.py` →
`score_candidate_renders.py` → `build_assisted_visual_review.py` →
`rank_candidates.py` 순서를 사용한다. slab·voxel·gray-box 또는 단일 표면은
strict visual QA 후보로 인정하지 않는다.

## 자동 Gate

실행 전 `scripts/ai3d/quality_progress_gate.py`가 동일 `strategyId`의 이전
거절 기록을 조회한다. 기록이 있으면 `QUALITY_PLATEAU_SAME_STRATEGY`로 끝내고
새 Provider 또는 semantic 경로로 전환한다. 각 전략의 최대 실행 횟수는 1회다.

TRELLIS는 `scripts/ai3d/colab_runtime_preflight.py --provider trellis`가
`READY_GPU_VISIBLE`와 `providerPreflight.heavyweightInstallAllowed=true`를
동시에 반환할 때만 설치·실행한다. 라이선스 확인은
`RE_CAMP_TRELLIS_LICENSE_ACK=1`로 명시적으로 기록한다. upstream CLI가 고정되지
않으면 `run_trellis_candidate.py`가 `BLOCKED_PROVIDER_ENTRYPOINT_UNVERIFIED`로
종료한다.

V001 semantic proxy는 `scripts/blender/build_ch101_semantic_proxy.py`가 네 개의
reference SHA256과 `current_roster_socket_contract_v001.json`을 검증한다. V001이
이미 거절된 경우에는 `scripts/blender/build_ch101_unified_semantic_mesh.py`가
V002로 선택되어 review-only `.blend`, transport mesh, 렌더, rig/LOD/socket/face
placeholder report를 만든다. V002는 object join만으로 연결됐다고 주장하지 않고
voxel remesh 성공 여부를 별도 기록한다. 실제 얼굴 BlendShape는 자동 생성하지
않으며 `BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER`로 남긴다.

V002가 strict visual QA에서 거절되면 `quality_progress_gate.py`가 기록된
`QUALITY_PLATEAU_SAME_STRATEGY`를 읽고 V003으로 전환한다. V003은
`scripts/blender/build_ch101_semantic_detail_candidate.py`를 통해 body shell만
연결형 remesh하고 나머지 semantic detail 그룹을 보존한다. V003 역시 자동 Gate B
승인을 하지 않으며, 얼굴 드라이버·소켓은 검토용 placeholder/자동 추정 상태다.

## 고정 상태와 중단

모든 산출물은 다음 상태를 유지한다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

기준은 overall 0.60, silhouette 0.50, appearance 0.55, color 0.38,
face detail 0.25, technical 0.90, geometry hard gate PASS와 네 semantic
component의 식별 가능성이다. 실패하면 `REGENERATE_REQUIRED`와 원인 코드를
기록하고 같은 전략을 반복하지 않는다. 두 경로가 모두 실패하면 더 강한 무료
Provider, Blender semantic authoring, 또는 3D 제작자의 semantic mesh 보강이
필요하다.

## 실행

Kaggle 또는 Colab에서 다음 Notebook을 연다.

```text
notebooks/07_ch101_hybrid_quality_strategies.ipynb
```

GPU가 없으면 TRELLIS는 heavyweight 설치 없이 차단된다. V001/V002 거절 이력이
있으면 동일 전략은 실행하지 않고, CPU Blender가 있으면 다음 semantic pivot을
한 번만 실행한다. GPU가
사전검사를 통과해도 TRELLIS entrypoint가 검증되지 않거나 mesh를 만들지 못하면
남은 semantic fallback을 한 번만 사용한다. Blender와 GPU가 모두 없으면
orchestration report만 남기고 후보·Review `.blend`를 만들지 않는다. Gate B 승인
전 Unity/Android 단계는 항상 차단된다. V003은 현재 로컬에서 실행·평가된
review-only 후보이며 strict visual QA를 통과하지 못했으므로 Kaggle 재실행 시에도
동일 strategy를 반복하지 않고 더 강한 제작자/Provider 입력으로 전환한다.
