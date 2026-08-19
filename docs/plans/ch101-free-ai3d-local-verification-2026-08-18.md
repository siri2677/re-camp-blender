# CH101 무료 AI 3D 로컬 검증 기록

검증일: 2026-08-18

## 결론

실제 외부 AI 생성 호출을 제외한 로컬 자동화 경로가 통과했다. 승인 참조 이미지
분리, Provider 요청 계획, Blender 정규화·렌더, 자동 점수·순위, LOD·Review Rig·Socket
생성까지 실행했다. 기존 CH101 primitive blockout은 색상 기준 미달로 자동 탈락했고,
강제로 만든 smoke Review Asset은 Production validator에서 의도대로 거부됐다.

이 기록의 smoke source는 파이프라인 검증 전용이다. AI 후보나 Production Mesh로
간주하지 않으며 저장소에 생성 바이너리를 커밋하지 않는다.

## 입력 잠금

- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 승인 Character Sheet SHA256: `0ce9c2d94236059966f3159737a6b056716720ff9e3b9f3f75592f4d9b6f561c`
- Turnaround crop helper SHA256: `87d7583cd28081b5bd109ea24e9b00a81e43f2decd621e48225ca3f151ad4b35`
- front crop SHA256: `054b38e963091a03664ae002694d327516b6d09f0370cc77a56e74f7127b286b`
- right crop SHA256: `20c0aa20e1bf8a30045a8321d3a6eb7071bad81187c052e47969e8064057561e`
- back crop SHA256: `21de4d3667a842e4e8a5b010604384e717be7d03e4f8eff68fed3775eeaa2473`

세 crop은 모두 1024×1024 PNG로 생성됐다.

## Provider dry-run

- Tripo multiview 후보 4개의 upload·generation payload 생성 PASS
- seed: `101001`, `101002`, `101003`, `101004`
- 실제 HTTP 생성 호출: 실행하지 않음
- 소비한 API credit: 0
- secret 또는 signed download URL 저장: 없음
- 모든 manifest의 `unityInputAllowed`: `false`

## Blender 평가 smoke

Blender 5.2.0 LTS에서 기존 blockout FBX를 오직 실행 검증용으로 평가했다.

- source triangles: 35,177
- UV 누락: 없음
- material: 6
- overall: 0.548381
- silhouette: 0.560532
- appearance: 0.336140
- color: 0.141123
- face detail: 0.412129
- 결과: `REGENERATE_REQUIRED`
- 탈락 원인: color 0.20 최소 기준 미달

기술 점수가 높더라도 디자인 색상 일치도가 낮으면 후보가 자동 선택되지 않음을
확인했다.

## Review Asset smoke

자동 Review Builder를 강제로 실행해 후처리 코드 자체를 검증했다.

- LOD0: 19,788 triangles
- LOD1: 10,748 triangles
- LOD2: 5,815 triangles
- heuristic humanoid rig: 22 bones
- weight 상태: `AUTO_WEIGHTED_FOR_REVIEW`
- 공용·상세 Socket: 7개
- 공용 `Socket_Equipment_Primary`와 상세 `Socket_Weapon_R` world transform 최대 오차:
  `2.9802322387695312e-08`
- Face Driver: `BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER`
- Unity export: 없음

## Production Gate 역검증

Review Asset에 Production validator를 실행한 결과 `FAIL`이었다.

- Production 컬렉션 4개 없음
- scene status: `AI_GENERATED_REVIEW_NOT_PRODUCTION`
- Socket 누락: 없음
- Socket alias mismatch: 없음
- `unity_input_allowed`: `false`

따라서 자동 Review 파일의 이름이나 기술 구성만으로 Production Mesh가 되지 않는다.

## Colab 실행 기록

이 절은 2026-08-18 당시 Tripo dry-run을 실행한 역사적 기록이다. 이후 무료 전용
운영으로 전환하면서 Notebook 기본 Provider는 Stable Fast 3D로 변경되었고,
Tripo는 선택 경로로 남겼다.

GitHub `feature/ch101-free-ai3d-autobuild` 브랜치의 Notebook을 Colab T4
runtime에서 실행했다.

- 도구 commit: `f7b1481ae072013b74329b406b3a11c428d47d24`
- 승인 참조 준비: PASS (`REFERENCE_VIEWS_READY`)
- 당시 Tripo 후보 계획: 4개
- `TRIPO_API_KEY`: 없음
- 실제 외부 생성 호출 및 credit 소비: 없음
- 다운로드 후보: 0개
- ranking: 후보가 없어 실행하지 않음
- 산출 ZIP: `/content/re-camp-CH101-ai3d-review-NOT-PRODUCTION.zip`
- 실행 결과: PASS (dry-run 완료)

초기 실행에서 짧은 Git SHA fetch가 실패했으며, Notebook을 전체 도구 commit SHA로
고정한 뒤 재실행해 통과했다. 현재 Notebook은 재현성이 필요한 실행에서는
`RE_CAMP_BLENDER_TOOLS_COMMIT`으로 전체 SHA를 고정하고, 값을 지정하지 않은 경우
`feature/` branch tip을 checkout한 뒤 실제 SHA를 기록한다. 따라서 최신 로컬 변경을
실행하려면 먼저 해당 변경이 원격 branch에 반영되어야 한다.

## Colab 직접 실행 결과

같은 날짜에 T4 runtime에서 무료 경로를 실제 실행했다.

- Stable Fast 3D: provider 의존성 보정 후 실행했으나 Hugging Face gated model 접근에서
  `401 Unauthorized`로 중단됐다. `HF_TOKEN` 값은 저장하거나 출력하지 않았다.
- TripoSR fallback: 실행 PASS
- 생성 후보: `CH101_triposr_cand_001.glb` (911,180 bytes)
- 후보 SHA256: `1c735d95df588e1aebcf30398f8d75df6e231ba6c231b05bc89284e1674d2a52`
- Blender 평가: `EVALUATION_RENDERED`, 정규화 `.blend`와 5방향 PNG 생성 PASS
- 점수: overall `0.415234`, silhouette `0.432620`, appearance `0.336122`, color
  `0.169909`, face detail `0.612969`, technical `0.500000`
- 자동 판정: `REGENERATE_REQUIRED` (overall 최소 기준 `0.5` 미달)
- 아카이브: `/content/re-camp-CH101-ai3d-review-NOT-PRODUCTION.zip`
- Tripo API 호출 및 credit 소비: 0
- `unityInputAllowed`: `false`

이 결과는 무료 AI 후보 생성 경로가 실제로 동작한다는 증거이며, 품질 기준 미달
후보를 Production Mesh로 승격하지 않는 것도 확인한 것이다. Colab 세션이 종료되면
`/content` 산출물은 사라질 수 있으므로 필요한 ZIP은 사용자 Drive 또는 로컬로
다운로드해 보관해야 한다.

## 남은 외부 차단

실제 AI 후보 생성에는 다음 중 하나가 필요하다.

- Stable Fast 3D를 사용하려면 GPU가 배정된 Colab과 gated 모델 접근 권한
- 현재 확인된 무료 대체 경로는 GPU가 배정된 Colab의 TripoSR 실행 환경
- 선택적으로 Tripo API 무료 체험이 활성화된 `TRIPO_API_KEY`

실제 후보를 확보하면 같은 Notebook이 평가·선택·Review Asset 단계로 이어진다. 결과가
자동 기준을 통과해도 사람 Gate B 승인, 얼굴 BlendShape 보정, Unity 검증 전까지
Production 또는 Unity 입력 상태로 승격하지 않는다.

## Colab 무료 TripoSR 재실행 기록

2026-08-19에 같은 참조 입력으로 무료 TripoSR 경로를 재실행했다. 첫 시도는
최신 NumPy에서 구버전 `trimesh`의 `ndarray.ptp` 호출이 실패했으므로, Notebook의
TripoSR 의존성을 `trimesh>=4.4.0`으로 보정했다. 새 Colab 세션에서 rembg가 사용할
ONNX Runtime backend가 없을 수 있어 `onnxruntime-gpu` 자동 설치도 추가했다.

- 생성: PASS (`TRIPOSR_RETURN_CODE: 0`)
- 후보: `CH101_triposr_cand_001.glb`
- 후보 SHA256: `9be9e35b1c578fc5f0d9a975133162c2db866f6913a5192521fd7501e01d873e`
- Blender 평가: PASS (`EVALUATION_RETURN_CODE: 0`)
- 원본 up-axis: `Y`; 평가 보정: `Y_TO_Z`
- 정규화 dimensions: `0.6502 × 0.8803 × 1.6800`
- triangle: `46,738`; UV 누락: `geometry_0`
- technical: `0.650000`
- 점수: overall `0.422463`, silhouette `0.420287`, appearance `0.337104`, color
  `0.156070`, face `null`
- 자동 판정: `REGENERATE_REQUIRED`
- `unityInputAllowed`: `false`
- Tripo API credit 소비: 0

Colab의 `onnxruntime-gpu`가 CUDA 라이브러리 `libcublasLt.so.13`을 찾지 못하는
경고는 있었지만 rembg가 CPU fallback으로 계속 실행되어 후보 생성은 완료됐다.
따라서 이 결과는 무료 자동화 경로와 방향 보정 평가기의 실행 증거이지, 최종
Production Mesh 또는 Unity 입력 승인 결과가 아니다.

## 후보 자동 보정 구현 상태

2026-08-19에 `refine_ai3d_candidate.py`와 Notebook 최대 3회 후보 반복 루프를
추가했다. 로컬 Notebook JSON, Blender/Python compile, AI3D·Colab package validator,
전체 unittest 10개가 모두 PASS했다.

- 보정 단계: 방향·스케일·중복 정점·법선·UV·중립 Review Material
- 후보 상태: `REFINED_REVIEW_CANDIDATE`
- 얼굴 상태: `BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER`
- Socket 상태: `AUTO_ESTIMATED_NOT_APPROVED`
- 반복 한도: `MAX_ATTEMPTS = 3`
- 실제 새 보정 루프 T4 실행: 최신 로컬 Notebook이 아직 GitHub에 push되지 않았고,
  이전 Colab runtime도 유휴 종료되어 `PENDING_EXTERNAL_COLAB_RUN`으로 유지
