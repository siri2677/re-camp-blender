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

### 1. Stable Fast 3D 무료 기본 경로

- API 크레딧 없이 Colab GPU에서 단일 정면 이미지 기반 후보를 만든다.
- UV, 텍스처, 기본 재질이 포함된 GLB를 생성하고 Blender에서 다중 방향으로 평가한다.
- Hugging Face 모델 접근 승인과 `HF_TOKEN`이 필요할 수 있다.
- 공식 저장소를 커밋 `ff21fc491b4dc5314bf6734c7c0dabd86b5f5bb2`로 고정한다.
- 약 6GB VRAM이 필요할 수 있다.
- 저장소: https://github.com/Stability-AI/stable-fast-3d

### 2. TripoSR 무료 fallback

- Stable Fast 3D 모델 접근 또는 실행이 막힐 때 사용하는 단일 이미지 경로다.
- 공식 저장소를 커밋 `107cefdc244c39106fa830359024f6a2f1c78871`로 고정한다.
- GLB와 vertex color 중심의 기술 후보를 만들며 최종 Texture 품질은 기대하지 않는다.
- 저장소: https://github.com/VAST-AI-Research/TripoSR

### 3. InstantMesh 무료 sparse-view fallback

- Stable Fast 3D가 gated 모델 접근에 실패하면 InstantMesh를 먼저 시도한다.
- 단일 정면 입력에서 내부적으로 sparse-view 이미지를 생성한 뒤 OBJ를 재구성한다.
- 공식 저장소 commit `08822c52fdc399b93ea00e4fa9e596344ed52ccc`와 Apache-2.0 라이선스를 고정한다.
- 텍스처 맵을 요청하되, 결과는 여전히 AI Review 후보로만 취급한다.
- T4 실행 가능 여부와 실제 점수는 CH101 1회 실험으로 확인한다.
- 저장소: https://github.com/TencentARC/InstantMesh

### 4. Tripo API 선택 경로

- 무료 Provider로 충분한 후보가 나오지 않을 때만 선택한다.
- 정면·우측면·후면을 동시에 사용하는 다중 시점 후보 생성 경로다.
- API 키는 Colab Secret 또는 `TRIPO_API_KEY` 환경 변수에서만 읽는다.
- API 크레딧 소비와 서비스 약관을 확인한 뒤 실행한다.
- 가격·API 기준: https://docs.tripo3d.ai/get-started/pricing.html

InstantMesh 재시도도 `front`·`right`·`back` 입력을 시도별로 순환한다. 이는
다중 이미지를 한 번에 입력하는 기능이 아니라, sparse-view provider 후보를 서로 다른
승인 방향으로 생성해 비교하는 무료 보강 경로다. 후보가 기준을 통과하지 않으면
여전히 `REGENERATE_REQUIRED`로 유지한다.

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

상태: `IMPLEMENTED / FREE-FIRST / REAL COLAB PASS / VARIANT RETRY EXECUTED / REGENERATE_REQUIRED`

1. 기본 Provider는 Stable Fast 3D이며 최대 3회 후보를 생성한다.
2. Stable Fast 3D가 실패하면 각 시도에서 TripoSR로 동일한 정면 입력을 재시도한다.
3. 각 시도는 `attempts/01`~`attempts/03` 아래 manifest와 후보 파일을 보존한다.
4. 재실행 시 검증된 후보 manifest와 실제 파일이 있으면 기본적으로 재사용해 GPU를
   다시 소모하지 않는다. 강제 재생성은 `RE_CAMP_REUSE_CANDIDATES=0`으로 지정한다.
5. TripoSR fallback은 시도별 foreground ratio `0.75`, `0.85`, `0.95`를 적용해
   동일한 deterministic 결과를 반복하지 않도록 하고, 적용값을 manifest에 기록한다.
6. Tripo를 선택한 경우에만 정면·우측면·후면을 업로드하고 seed 네 개로 후보를 생성한다.
7. Tripo API 키가 없으면 크레딧을 소비하지 않는 Dry-run plan만 생성한다.
8. 어떤 Provider를 사용해도 생성 결과는 검토 후보이며 Production Mesh로 승격하지 않는다.

### Phase C — Blender 자동 평가

상태: `IMPLEMENTED / REAL COLAB PASS / REGENERATE_REQUIRED`

1. GLB/FBX/OBJ를 headless Blender로 연다.
2. 키를 1.68m로 맞추고 바닥·중심을 정규화한다.
3. 네 방향과 3/4 Review 렌더를 생성한다.
4. triangle, UV, Material, 비율을 기록한다.
5. 후보의 네 방향 중 승인 Turnaround와 가장 가까운 front/right/back 방향을 자동 선택한다.
6. 실루엣 IoU와 기술 점수를 결합해 후보 순위를 만든다.

자동 점수는 사람의 시각 승인이 아니며, 기준 미달이면 `REGENERATE_REQUIRED`로 끝난다.

### Phase C-1 — Blender 후보 자동 보정

상태: `IMPLEMENTED / REAL COLAB PASS / REGENERATE_REQUIRED`

선정 전 후보마다 별도 review 산출물을 만든다.

- Y-up/X-up 방향, 중심, 1.68m 높이 정규화
- 중복 정점 제거와 법선 재계산
- UV가 없을 때 Smart UV Project 실행
- 최종 재질이 아닌 중립 Review Material 부여
- 보정 GLB·정규화 `.blend`·refinement report 생성
- 원본 후보 SHA256, 시도 번호, Provider, 부모 hash 기록

이 단계는 얼굴·헤어·의상 의미를 복원하거나 Production Mesh로 승격하지 않는다.

### Phase D — Blender Review Asset 자동 구성

상태: `IMPLEMENTED / BLOCKED UNTIL ELIGIBLE REFINED CANDIDATE`

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
  attempts/01/candidates/<provider>/candidate-manifest.json
  attempts/01/candidates/<provider>/CH101_<provider>_cand_001.glb
evaluation/<candidate-id>/
  <candidate-id>_refined.glb
  <candidate-id>_refined_NOT_PRODUCTION.blend
  refinement-report.json
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
- 최대 3회 후보 생성과 Stable Fast 3D → TripoSR fallback 정적 검증 PASS
- 후보별 Blender 보정 GLB·UV·중립 재질·SHA256 report 생성
- 후보 manifest 재개·중복 방지 테스트 PASS
- 점수·순위 manifest가 Unity를 잠근 상태로 생성됨
- 실제 후보 확보 후 자동 렌더·평가·Review `.blend` 생성

Reference crop, Tripo 4-candidate dry-run, Blender 평가, 자동 점수 탈락,
LOD·22본 Rig·Socket Review Asset 생성, Production validator 역검증까지 로컬에서
통과했다. 실행 근거는
[ch101-free-ai3d-local-verification-2026-08-18.md](ch101-free-ai3d-local-verification-2026-08-18.md)에
기록한다.

실제 T4 실행에서는 Stable Fast 3D가 gated model 접근에서 실패했고 TripoSR fallback이
후보 3개를 생성했다. 세 후보 모두 자동 점수 기준 미달로 `REGENERATE_REQUIRED`가
되었으므로 Review `.blend`, Gate B, Unity 입력은 아직 차단되어 있다. Tripo API는
무료 경로의 필수 조건이 아니다.

추가로 TripoSR의 공식 `--foreground-ratio`를 `0.75`, `0.85`, `0.95`로 나누어
재실행했다. 후보 SHA는 각각 달라졌지만 overall 점수는 `0.439426`, `0.455933`,
`0.456930`으로 모두 `0.50` 기준에 미달했다. 따라서 최고 후보도 선택하지 않았고
Review `.blend`를 만들지 않았다.

다음 무료 Provider로 InstantMesh fallback을 추가했다. 초기 Colab T4 bootstrap에서는
필수 `nvdiffrast.torch` CUDA 확장 빌드가 실패했으므로, build isolation을 끄고
`setuptools`·`wheel`·`ninja`·T4용 `TORCH_CUDA_ARCH_LIST`를 준비하는 재시도 경로를
추가했다. 이 보강 경로의 실제 품질 점수는 재실행 전까지 `PENDING`이며, 실제 후보가
없는 상태에서 Alpha Review나 Unity 입력을 만들지 않는다.

TripoSR fallback은 승인 Turnaround의 입력 방향도 시도별로 바꾸도록 확장했다.
`front`·`right`·`back` 후보를 실제 T4에서 비교했지만 최고 overall은 `0.452043`으로
여전히 기준 미달이었다. 따라서 이 입력 다양화만으로도 Unity 승격 조건을 충족하지
않으며, `REGENERATE_REQUIRED`를 유지한다.

2026-08-19 최신 branch commit `382d1d4`를 새 Colab T4에서 위 순서대로 자동 실행했다.
Stable Fast 3D와 InstantMesh는 provider 실행 단계에서 실패했고 TripoSR이 세 후보를
생성했다. 최신 후보 점수는 `0.452120`, `0.451603`, `0.463577`이며 모두
`REGENERATE_REQUIRED`였다. 최고 후보는 기술 점수 `1.0`, 색상 점수 `0.261198`로
기술·색상 파이프라인은 통과했지만, 선택된 오른쪽 방향 실루엣이 `0.262132`로 낮아
단일 시점 형상 복원의 측면 불일치가 반복 미달의 주원인으로 확인됐다. 다음 무료
시도는 단일 시점 TripoSR 반복보다 다중 시점 또는 reference-conditioned provider를
우선 검증한다. 이번 실행 기록은
`docs/records/ch101-ai3d/2026-08-19-colab-t4-automatic-run.json`에 남긴다.
