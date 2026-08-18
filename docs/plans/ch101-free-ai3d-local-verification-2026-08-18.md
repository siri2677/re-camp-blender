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

GitHub `feature/ch101-free-ai3d-autobuild` 브랜치의 Notebook을 Colab T4
runtime에서 실행했다.

- 도구 commit: `f7b1481ae072013b74329b406b3a11c428d47d24`
- 승인 참조 준비: PASS (`REFERENCE_VIEWS_READY`)
- Tripo 후보 계획: 4개
- `TRIPO_API_KEY`: 없음
- 실제 외부 생성 호출 및 credit 소비: 없음
- 다운로드 후보: 0개
- ranking: 후보가 없어 실행하지 않음
- 산출 ZIP: `/content/re-camp-CH101-ai3d-review-NOT-PRODUCTION.zip`
- 실행 결과: PASS (dry-run 완료)

초기 실행에서 짧은 Git SHA fetch가 실패했으며, Notebook을 전체 도구 commit SHA로
고정한 뒤 재실행해 통과했다. 이후부터는 Colab이 `feature/` 브랜치의 정확한 도구
commit을 checkout한다.

## 남은 외부 차단

실제 AI 후보 생성에는 다음 중 하나가 필요하다.

- Tripo API 무료 체험이 활성화된 `TRIPO_API_KEY`
- GPU가 배정된 Colab과 Stable Fast 3D 모델 접근 권한
- 위 경로 실패 시 GPU가 배정된 Colab의 TripoSR 실행 환경

실제 후보를 확보하면 같은 Notebook이 평가·선택·Review Asset 단계로 이어진다. 결과가
자동 기준을 통과해도 사람 Gate B 승인, 얼굴 BlendShape 보정, Unity 검증 전까지
Production 또는 Unity 입력 상태로 승격하지 않는다.
