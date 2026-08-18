# CH101 무료 AI 3D 자동 제작 계획

## 목표와 한계

이 계획의 목표는 사용자가 Blender 조형이나 Weight Paint를 직접 수행하지 않아도 CH101의 AI 생성 후보를 만들고, 자동 평가·정규화·LOD·리그·Socket Review까지 연결하는 것이다.

무료 경로의 완료 목표는 `Unity 연결 전 Alpha Review 후보`다. 생성 모델을 자동으로 `Production Mesh` 또는 Gate B 승인 상태로 승격하지 않는다. 얼굴, 헤어, 겹친 의상, 세이버·리본의 정확한 구조가 승인 시트와 일치한다는 보장도 하지 않는다.

고정 상태 정책:

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## 무료 Provider 순서

### 1. Tripo API 신규 계정 무료 체험

- CH101 정면·우측면·후면 입력을 동시에 사용하는 첫 번째 경로다.
- API 키는 Colab Secret 또는 `TRIPO_API_KEY` 환경 변수에서만 읽는다.
- 2026-08-18 확인 기준 신규 API 계정은 2주 동안 300 무료 크레딧을 제공한다.
- 후보 네 개를 먼저 생성하고 자동 점수가 가장 높은 후보 하나에만 리깅·애니메이션을 적용해 크레딧을 절약한다.
- 무료 체험 산출물은 라이선스 확인 전 개발·평가 후보로만 취급한다.
- 가격·API 기준: https://docs.tripo3d.ai/get-started/pricing.html

### 2. Stable Fast 3D Colab 대체 경로

- Tripo 무료 크레딧이 없거나 API 생성이 실패할 때 사용한다.
- 단일 정면 이미지 기반이므로 다중 시점 일치도는 Tripo 경로보다 낮다.
- 공식 저장소를 커밋 `ff21fc491b4dc5314bf6734c7c0dabd86b5f5bb2`로 고정한다.
- 약 6GB VRAM과 Hugging Face 모델 접근 승인이 필요할 수 있다.
- 저장소: https://github.com/Stability-AI/stable-fast-3d

### 3. TripoSR Colab 최후 대체 경로

- Stable Fast 3D 모델 접근이 막힐 때 사용하는 단일 이미지 경로다.
- 공식 저장소를 커밋 `107cefdc244c39106fa830359024f6a2f1c78871`로 고정한다.
- GLB와 vertex color 중심의 기술 후보를 만들며 최종 Texture 품질은 기대하지 않는다.
- 저장소: https://github.com/VAST-AI-Research/TripoSR

### 제외 경로

- Meshy 무료 플랜: 현재 모델 다운로드와 API 접근이 없어 자동 파이프라인에 사용하지 않는다.
- Hunyuan3D-2: 공식 Community License의 허용 지역에서 대한민국이 제외되어 사용하지 않는다.
- TRELLIS.2: 현재 PC에 지원되는 NVIDIA GPU가 없고 무료 Colab에서 요구 VRAM을 안정적으로 확보할 수 없어 제외한다.

## 실행 단계

### Phase A — 입력 계약과 Reference 준비

상태: `IMPLEMENTED / LOCAL PASS`

1. `CH101_Rin_CharacterSheet_APPROVED_v001.png`를 최종 권위 기준으로 고정한다.
2. 같은 art commit의 `CH101_Rin_Turnaround_REVIEW_v001.png`는 깨끗한 crop helper로만 사용한다.
3. front/right/back를 1024×1024 PNG로 자동 분리한다.
4. 원본·helper·각 crop의 SHA256을 `reference-views-manifest.json`에 기록한다.

crop helper 자체가 Gate A 승인을 대신하지 않으며, 모든 결과는 승인 Character Sheet commit을 계속 기록한다.

### Phase B — 후보 생성

상태: `IMPLEMENTED / DRY-RUN PASS / EXTERNAL EXECUTION BLOCKED`

1. 기본 후보 수는 네 개다.
2. Tripo 입력 이미지는 한 번만 업로드하고 seed만 바꿔 후보를 생성한다.
3. 작업 ID를 즉시 manifest에 저장해 Colab 중단 후 같은 작업을 재조회한다.
4. 완료 URL은 만료되기 전에 GLB와 preview를 즉시 다운로드한다.
5. API 키가 없으면 크레딧을 소비하지 않는 Dry-run plan만 생성한다.
6. Tripo를 사용할 수 없으면 Stable Fast 3D, 이후 TripoSR 순서로 전환한다.

### Phase C — Blender 자동 평가

상태: `IMPLEMENTED / LOCAL SMOKE PASS / REAL CANDIDATE REQUIRED`

1. GLB/FBX/OBJ를 headless Blender로 연다.
2. 키를 1.68m로 맞추고 바닥·중심을 정규화한다.
3. 네 방향과 3/4 Review 렌더를 생성한다.
4. triangle, UV, Material, 비율을 기록한다.
5. 후보의 네 방향 중 승인 Turnaround와 가장 가까운 front/right/back 방향을 자동 선택한다.
6. 실루엣 IoU와 기술 점수를 결합해 후보 순위를 만든다.

자동 점수는 사람의 시각 승인이 아니며, 기준 미달이면 `REGENERATE_REQUIRED`로 끝난다.

### Phase D — Blender Review Asset 자동 구성

상태: `IMPLEMENTED / LOCAL SMOKE PASS / SELECTED REAL CANDIDATE REQUIRED`

선택 후보에 다음 항목을 적용한다.

- 원본 mesh 보존
- 20,000 triangle 상한을 목표로 LOD0 생성
- LOD1 55%, LOD2 30% 생성
- 22본 휴머노이드 추정 Armature 생성
- Blender automatic weights 시도
- 공용 Socket과 CH101 상세 Socket 추정 배치
- Review 전용 `.blend`와 자동화 보고서 생성

Review scene은 의도적으로 `MODEL_HIGH_BODY`, `MODEL_CLOTH_OUTFIT`, `MODEL_HAIR`, `MODEL_EQUIPMENT` Production 컬렉션을 만들지 않는다. 따라서 기존 Production Mesh validator가 이 결과를 최종 자산으로 잘못 통과시킬 수 없다.

### Phase E — 얼굴·장비 정밀화

상태: `PARTIALLY BLOCKED`

- 얼굴 8개 BlendShape는 무료 범용 모델에서 신뢰할 수 있는 3D landmark와 동일 topology가 확보되지 않아 자동 생성하지 않는다.
- 세이버와 리본이 몸 mesh와 결합되어 생성될 수 있으므로 자동 Socket은 `AUTO_ESTIMATED_NOT_APPROVED`다.
- 자동 Weight가 실패하거나 팔꿈치·무릎 변형이 기준 이하라면 후보를 재생성한다. Weight Paint를 자동으로 Production 승인하지 않는다.

## 자동 중단 조건

- 입력 이미지 SHA256 또는 art commit 불일치
- API 응답 실패·취소·금지 상태
- 다운로드 GLB 누락 또는 SHA256 불일치
- mesh 없음, 높이 0, 300,000 triangle 초과
- 실루엣 0.35, 색상 0.20, 외형 0.25, 얼굴 디테일 0.12 또는 종합 점수 0.50 미만
- 후보가 없는데 Review Asset 생성을 요청한 경우
- 어떤 단계에서든 `unityInputAllowed=true`가 발견된 경우

## 산출물

```text
reference-views/
  CH101_front.png
  CH101_right.png
  CH101_back.png
  reference-views-manifest.json
candidates/
  candidate-manifest.json
  CH101_<provider>_cand_001.glb
evaluation/<candidate-id>/
  renders/*.png
  evaluation-report.json
  candidate-score.json
ranking-manifest.json
review/
  CH101_AI_AutoReview_NOT_PRODUCTION_v001.blend
  ai3d-review-report.json
```

## 실행 명령

Reference 준비:

```text
python scripts/ai3d/prepare_reference_views.py --art-root ../re-camp --output-dir /path/to/reference-views
```

Tripo Dry-run:

```text
python scripts/ai3d/tripo_api.py --reference-manifest /path/to/reference-views-manifest.json --output-dir /path/to/candidates --candidate-count 4
```

실제 무료 체험 실행 시에만 환경에 `TRIPO_API_KEY`를 넣고 `--execute`를 추가한다. 키는 `.env`, Notebook, JSON, Git에 기록하지 않는다.

## 완료 기준

- Notebook JSON과 모든 Python/Blender script compile PASS
- Reference crop SHA256 manifest 생성 PASS
- Provider Dry-run payload 검증 PASS
- 후보 manifest 재개·중복 방지 테스트 PASS
- 점수·순위 manifest가 Unity를 잠근 상태로 생성됨
- 실제 후보 확보 후 자동 렌더·평가·Review `.blend` 생성

Reference crop, Tripo 4-candidate dry-run, Blender 평가, 자동 점수 탈락,
LOD·22본 Rig·Socket Review Asset 생성, Production validator 역검증까지 로컬에서
통과했다. 실행 근거는
[ch101-free-ai3d-local-verification-2026-08-18.md](ch101-free-ai3d-local-verification-2026-08-18.md)에
기록한다.

마지막 항목의 실제 AI 후보 생성만 Tripo API 키 또는 Colab GPU가 준비되기 전까지
`Blocked`다. 모든 저장소 변경은 별도 지시 전까지 로컬에만 유지하며 commit/push하지 않는다.
