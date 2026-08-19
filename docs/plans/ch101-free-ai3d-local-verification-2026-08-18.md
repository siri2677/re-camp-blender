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
- 실제 새 보정 루프 T4 실행: 도구 commit `296495f`로 실행 PASS

## 최신 T4 후보 보정·평가 실행 결과

2026-08-19에 최신 원격 branch `feature/ch101-free-ai3d-autobuild`를 T4 runtime에서
실행했다. 실행 중 발견된 Blender 인자 처리 누락과 `sys` import 누락은 각각
`78e45b2`, `296495f`로 수정·push한 뒤 같은 runtime에서 보정·평가 셀을 재실행했다.

- 참조 준비: PASS (`REFERENCE_VIEWS_READY`), art commit
  `b6c9b3128358e061eee6184230929413eba84101`
- Stable Fast 3D: gated model 접근 실패로 fallback
- TripoSR: 3회 생성 PASS (`attempts/01`~`03`), API credit 소비 0
- Blender 후보 보정: 3개 모두 PASS (`refinement-report.json`, refined GLB,
  normalized `.blend` 생성)
- Blender 평가·렌더: 3개 모두 PASS (`evaluation-report.json`, 5방향 PNG 생성)
- 점수 리포트: 3개 모두 PASS
- 각 후보 점수: overall `0.455933`, silhouette `0.415698`, appearance `0.342917`,
  color `0.153408`, face detail `0.382290`, technical `1.0`
- 자동 판정: 3개 모두 `REGENERATE_REQUIRED`; 최고 후보도 overall 최소 기준 `0.5`
  미달
- Review Asset: 선택 후보가 없어 생성하지 않음
- archive: `/content/re-camp-CH101-ai3d-review-NOT-PRODUCTION.zip` (약 26 MB)
- 최종 Gate: `sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`,
  `gateB=PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`,
  `productionPromotionAllowed=false`

이번 실행은 무료 AI 후보 생성·Blender 보정·평가 파이프라인이 실제 T4에서
끝까지 동작한다는 것을 확인했지만, 시각 품질 기준을 통과한 Alpha Review 후보를
확보한 것은 아니다. 다음 단계는 새 무료 후보 생성 또는 참조·Provider 개선이며,
Gate B와 Unity 연결은 계속 차단한다.

## 다음 무료 후보 다양화 보정

동일한 TripoSR 입력은 세 번 모두 같은 SHA와 점수를 만들었다. 다음 실행부터는
권위 art reference와 manifest hash는 고정한 채 TripoSR의 공식
`--foreground-ratio` 입력만 시도별 `0.75`, `0.85`, `0.95`로 변경한다. 이 값은
전경 크기 전처리만 바꾸며, 후보 manifest의 `providerParameters`에 기록한다.
이는 품질 통과를 보장하지 않으며, 세 번 모두 기준 미달이면 계속
`REGENERATE_REQUIRED`로 유지한다.

## Foreground ratio 변형 실제 실행 결과

2026-08-19에 최신 도구 commit `3dd36fd`를 원격 branch에서 Colab T4로 반영한 뒤,
노트북 화면에 남아 있던 이전 셀 코드는 재사용하지 않고 동일 Provider 실행기를
시도별 인자와 함께 직접 실행했다. 권위 art reference와 reference manifest hash는
그대로 유지했고 TripoSR 생성·Blender 보정·5방향 렌더·점수화를 모두 완료했다.

| 시도 | foreground ratio | 후보 SHA256 | overall | 판정 |
|---|---:|---|---:|---|
| 01 | 0.75 | `4f19519e60a3418dc34ee18eabc851be191f13e69ebad4f92e8f8cfecf0c37c5` | 0.439426 | `REGENERATE_REQUIRED` |
| 02 | 0.85 | `1c735d95df588e1aebcf30398f8d75df6e231ba6c231b05bc89284e1674d2a52` | 0.455933 | `REGENERATE_REQUIRED` |
| 03 | 0.95 | `dc5988cfdc9e49a54c57a23162fd88a6f915c03ec874c8fbaaf84755bfcce800` | 0.456930 | `REGENERATE_REQUIRED` |

최고 후보(03)의 세부 점수는 silhouette `0.418686`, appearance `0.339136`,
color `0.148622`, face detail `0.373681`, technical `1.0`이다. 세 후보 모두
Alpha Review 최소 overall `0.50`을 넘지 못했으므로 Review Asset을 선택 생성하지
않았고, 최종 상태는 `unityInputAllowed=false`, `productionPromotionAllowed=false`
로 유지한다. 산출물 archive는 `/content/re-camp-CH101-ai3d-review-NOT-PRODUCTION.zip`
이다.

## InstantMesh 무료 fallback bootstrap 결과

2026-08-19에 도구 commit `7cebf20`을 Colab T4에 반영하고 InstantMesh 공식 저장소를
commit `08822c52fdc399b93ea00e4fa9e596344ed52ccc`로 고정했다. Repository clone과
Python 의존성 설치는 완료했지만, 공식 실행 코드가 import하는 필수
`nvdiffrast.torch` 확장은 다음 두 방식 모두 후보 생성 전 단계에서 막혔다.

- 일반 PEP 517 설치: build requirements 단계 실패
- `--no-build-isolation`, `MAX_JOBS=2` 소스 빌드: wheel 생성이 완료되지 않아 취소

따라서 InstantMesh는 `BLOCKED_COLAB_NVDIFFRAST_BUILD`로 기록하고 품질 점수를 생성하지
않았다. 이 결과는 Provider 품질 실패가 아니라 현재 Colab 런타임의 CUDA 확장 설치
차단이며, TripoSR의 마지막 통과 가능한 무료 fallback 결과와 분리한다.
