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

진단 로깅을 추가한 `30b2263` 기준으로 Colab T4 재실행도 완료했다. SF3D는
`stabilityai/stable-fast-3d` gated 모델의 `401 Unauthorized`로 3회 실패했고,
InstantMesh는 `huggingface_hub`에 `split_torch_state_dict_into_shards`가 없어 3회
실패했다. TripoSR fallback은 기존 후보 manifest를 재사용해 GPU 재생성을 피했고,
최고 overall `0.463577`로 다시 `REGENERATE_REQUIRED`가 되었다. 다음 코드 보정은
InstantMesh의 `huggingface-hub>=0.26.0` 설치·import smoke test이며, SF3D는 사용자가
Hugging Face 접근 약관을 승인하고 `HF_TOKEN`을 Colab Secret으로 제공할 때만
재시도한다. 토큰은 출력·저장하지 않는다. 상세 JSON은
`docs/records/ch101-ai3d/2026-08-19-colab-t4-provider-diagnostics.json`에 남긴다.

`0fa542b`의 첫 호환성 보정 실행에서는 import smoke test는 통과했지만 최신
`huggingface_hub==1.28.0`이 InstantMesh의 요구 범위 `<1.0`을 벗어나 provider
실행 단계에서 거부되었다. 따라서 Notebook의 범위를 `huggingface-hub>=0.26.0,<1.0`
으로 다시 고정했다. 이번 재실행은 실제 후보 생성이 아니라 이 의존성 보정과
fallback gate를 검증하는 목적이며, 결과는 별도 compatibility 기록에 남긴다.

`6d33b19`의 상한 버전 재실행에서는 Hub helper import smoke test는 통과했지만,
InstantMesh의 `diffusers==0.20.2`가 `huggingface_hub.cached_download`를 import하는
단계에서 다시 실패했다. 이 심볼은 Hub `0.26` 이후 제거된 것으로 확인되어,
`scripts/ai3d/instantmesh_hf_compat_sitecustomize.py`를 provider subprocess에만
`sitecustomize`로 주입하는 보정을 추가했다. 이 shim은 raw community-pipeline URL만
격리 캐시에 저장하고, 일반 Hub 다운로드와 provider checkout은 수정하지 않는다.
보정 전 실행의 세 TripoSR 점수는 기존과 같은 `0.452120`, `0.451603`, `0.463577`이고
최고 후보도 `REGENERATE_REQUIRED`였다. 보정 후 InstantMesh 실제 inference는 아직
검증 전이며, SF3D gated 접근·Gate B·Unity 입력은 계속 차단한다.

`933c162` 최신 Colab T4 재실행에서는 `cached_download`와 레거시 JAX `KeyArray`
호환 shim이 모두 적용되어 InstantMesh dependency smoke test와 provider 초기화가
통과했고 실제 geometry inference까지 진입했다. 그러나 T4의 총 VRAM 14.56GB에서
15.00GB CUDA 할당을 요구해 OOM으로 중단되었다. TripoSR fallback은 front/right/back
세 후보를 생성·평가했지만 점수 `0.452120`, `0.451603`, `0.463577` 모두
`REGENERATE_REQUIRED`였다. 따라서 Review `.blend`, Gate B, Unity 입력은 여전히
생성하지 않았고, 상세 실행 기록은
`docs/records/ch101-ai3d/2026-08-19-colab-t4-provider-compatibility-rerun-v003.json`에
보관한다. 다음 무료 시도는 T4에 맞춘 InstantMesh 저메모리 설정 또는 다른 다중 시점
provider의 정적·실행 가능성을 먼저 검토한다.

다음 실행을 위해 InstantMesh 계약을 upstream의 `configs/instant-mesh-base.yaml`과
`--view 4`로 낮추고 `memoryProfile: T4_SAFE_BASE`를 기록했다. 이는 large 모델의
품질을 보장하는 변경이 아니며, T4에서 실제 후보 생성까지 도달하는지 확인하기 위한
보수적 실행 프로파일이다. texture map 출력과 모든 Production·Unity gate는 그대로
잠겨 있다.

base 프로파일 T4 실행에서는 InstantMesh가 front/right/back 세 OBJ 후보를 모두
생성했고, 기존의 15GB CUDA OOM은 해소되었다. 첫 실행의 후처리 셀에서
InstantMesh manifest의 `attempts/<n>` 경로를 숫자로 인식하지 못해 모든 결과가
`attempt_00`으로 덮어쓰이는 기록 결함이 발견되었다. Notebook은 이제 모든 Provider의
숫자 시도 디렉터리를 보존하도록 수정되었고, 기존 산출물도 올바른 시도 번호로
재평가했다. 수정된 점수는 `0.461022`, `0.454798`, `0.458890`이며 최고 점수도
`0.461022`로 기준 `0.50`에 미달했다. 따라서 `selectedCandidate: null`과
`REGENERATE_REQUIRED`를 유지하고, Review `.blend` 생성 및 Unity 입력을 진행하지
않는다. 상세 해시와 결과는
`docs/records/ch101-ai3d/2026-08-19-colab-t4-instantmesh-base-rerun-v001.json`에
기록한다.

2026-08-20 조사에서는 Wonder3D를 다음 무료 후보로 고정했다. Wonder3D는 단일
front 입력에서 일관된 6개 RGB·normal 뷰를 생성한 뒤 NeuS 또는 Instant-NSR로
메시를 추출하는 구조라, 현재처럼 front/right/back을 서로 독립적으로 생성하는
InstantMesh 경로의 뒷면 불일치 문제를 검증할 수 있다. 공식 저장소는 MIT 라이선스와
256 해상도·6-view 제약, `tiny-cuda-nn` 의존성, T4에서 아직 검증되지 않은 GPU
실행 단계를 명시한다. 따라서 `experimentalProviders.wonder3D`에 commit을 고정했지만
기존 `freeFallbackOrder`에는 넣지 않았고, `RESEARCH_ONLY`, `fallbackEnabled: false`,
`unityInputAllowed: false`를 유지한다. 실행 전 feasibility 기록은
`docs/records/ch101-ai3d/2026-08-20-free-multiview-provider-feasibility-v001.json`에
보관한다.

다음 Colab 작업은 Wonder3D RGB·normal 6-view 생성 → NeuS mesh extraction → 기존
`refine_ai3d_candidate.py`·`evaluate_ai3d_candidate.py`·`rank_candidates.py`를
통과시키는 1회 검증이다. T4에서 설치·메모리·mesh extraction 중 하나라도 실패하면
기존 InstantMesh/TripoSR 결과를 대체하지 않고 실패 진단만 기록한다.
이를 위해 `notebooks/06_ch101_wonder3d_multiview_experiment.ipynb`와
`scripts/ai3d/run_wonder3d_multiview.py`,
`scripts/ai3d/register_wonder3d_candidate.py`를 추가했다. PLY/OBJ/GLB/GLTF를
후처리 입력으로 허용하지만, 등록 manifest의 sourceStatus와 Unity/Production gate는
기존과 동일하게 잠긴다.

2026-08-20 첫 Wonder3D Colab 실행 시도는 Notebook을 열고 GPU 런타임 연결 단계까지
도달했지만 Colab 사용량 제한으로 GPU 백엔드가 할당되지 않았다. Provider 설치·추론은
시작하지 않았으며, 이 결과는 `BLOCKED_GPU_QUOTA`로 기록했다. 사용량 제한이 풀리면
동일한 pinned Notebook을 재실행하고, CPU로 우회하거나 Unity 입력을 활성화하지 않는다.

Wonder3D 재개 경로는 기존 6-view 출력의 `generationStatus`, provider commit,
reference manifest SHA256, 생성 파일 존재 여부와 Gate 잠금을 먼저 검증한다. 모두
통과하면 `REUSED`로 표시하고 inference를 반복하지 않으며, 하나라도 실패하면
기존 파일을 보존한 채 신규 실행 여부를 GPU preflight로 판단한다. 강제 재생성은
`RE_CAMP_REUSE_WONDER3D=0`으로만 요청한다.
