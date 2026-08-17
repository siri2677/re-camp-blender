# CH101 Production Roadmap

이 문서는 `re-camp`의 잠긴 CH101 아트 시트를 Blender·Unity 작업으로 연결하는 전체 계획이다. 현재 기준 아트는 `re-camp`의 `current/art-roster-gate-a-ch102` 브랜치와 커밋 `b6c9b3128358e061eee6184230929413eba84101`이다.

## 현재 판정

상태: `TECHNICAL SCAFFOLD V010 COMPLETE / VISUAL PRODUCTION MODEL NOT STARTED / GATE B BLOCKED`

완료된 증거:

- Public 도구 저장소: `siri2677/re-camp-blender`
- Google Drive 없이 Colab 실행 가능
- `xvfb-run`을 이용한 headless Blender 실행
- CH101 v005 front/side/back 렌더 자동화
- `.blend`와 `.fbx` export
- UV·material slot·triangle·LOD metadata 검증 자동화
- Colab validation `PASS`: 메시 89개, 삼각형 26,584개, 소켓 8개
- UV 누락 0개, material slot 누락 0개
- `LOD0 ONLY / LOD PENDING` 상태 기록
- `/content/re-camp-output/CH101_v005/` 산출물과 `/content/re-camp-CH101-blockout-v005.zip` 생성
- CH101 v006 Colab 검증 `PASS`: 메시 89개, 삼각형 26,584개, 소켓 8개
- 22본 armature, motion clip 4개, socket bone mismatch 0개
- `/content/re-camp-output/CH101_v006/` 산출물과 `/content/re-camp-CH101-blockout-v006.zip` 생성
- CH101 v007 Colab 검증 `PASS`: weighted mesh 89개, skinning 오류 0개
- A-pose·idle·run·attack pose review render 4개 생성
- `/content/re-camp-output/CH101_v007/` 산출물과 `/content/re-camp-CH101-blockout-v007.zip` 생성
- 2026-08-16 locked source commit `183b0f0983969937d779f70b2ac51e53fc976203` 기준 로컬 v007 재생성·FBX export·validation `PASS`
- 로컬 산출물: `artifacts/CH101_v007_run1/` (blend, FBX, 3면 렌더, pose 렌더, JSON report)
- Unity review budget 주의: 측정 삼각형 26,584개이며 LOD0 본체 18,000 + 장비 2,000 기준을 아직 분리 충족하지 않음
- 2026-08-16 v008 budget-review variant: deterministic LOD0 simplification으로 19,090 tris, combined review budget `PASS`; LOD1/LOD2는 계속 대기
- 2026-08-16 v009 LOD review: LOD0/LOD1/LOD2가 각각 19,090/10,383/5,704 tris로 생성되고 구조 검증 `PASS`; Unity `LODGroup` 연결은 Phase 6에서 수행
- 2026-08-16 v010 production-skinning review: LOD0/LOD1/LOD2 동일 예산을 유지하면서 89개 LOD0 파츠에 정규화된 최대 2-bone influence를 적용하고, 6개 material slot budget을 `PASS`

현재 결과는 최종 캐릭터 모델이 아니다. v010은 프리미티브 기반 Blender 기술 스캐폴드이며, 사용자가 요구한 원신·니케·젠레스 존 제로 계열의 매력적인 일본 서브컬처 캐릭터 품질을 충족하지 않는다. Unity Import 이전에 고품질 3D 제작 모델 단계가 새로 필요하다.

## 단계별 계획

### Phase 0 — 아트 기준 고정

상태: `COMPLETE`

- CH101 Production Sheet 승인 이미지 확인
- 원본 저장소와 기준 브랜치 고정
- 모든 생성 리포트에 source commit 기록

완료 기준: 모델·렌더·리포트가 동일한 source commit을 가리킨다.

### Phase 1 — 재현 가능한 Blender 환경

상태: `COMPLETE`

- `re-camp-blender` Public 저장소 구성
- Drive 경로와 no-Drive 경로 분리
- Blender 설치·headless 실행·ZIP 다운로드 자동화
- Notebook JSON과 Python 패키지 검증

완료 기준: 새 Colab 세션에서 Notebook을 위에서부터 실행해 산출물을 재생성할 수 있다.

### Phase 2 — 아트 방향 Blockout

상태: `COMPLETE — v003`

- 크롭 스포츠 재킷, 쇼츠, 허벅지 스트랩
- 포니테일과 시안 포인트
- 부츠, 세이버, 시스, 신호 리본
- 재질 토큰, 조명, front/side/back 카메라
- Gate B 소켓 8개

완료 기준: 구조 검증 `PASS`, 렌더 3장, `.blend`, `.fbx`, JSON 리포트가 생성된다.

### Phase 3 — Production Modeling Refinement

상태: `REOPENED — VISUAL QUALITY NOT ACCEPTED`

기존 v004는 파츠 분리와 기술 이름 정리만 완료했으며, 사용자가 확인할 수 있는 최종 시각 품질은 충족하지 못했다. 목표는 프리미티브 블록아웃을 참고용으로 보존한 뒤, 실제 5~6등신 스타일라이즈드 일본 서브컬처 캐릭터 모델로 교체하는 것이다.

필수 품질 기준:

- 얼굴은 평면 구체가 아니라 눈·눈썹·코·입·턱선이 분리된 애니메이션 얼굴 구조여야 한다.
- 머리카락은 덩어리 구체가 아니라 앞머리·옆머리·포니테일의 곡면 락 구조와 시안 포인트를 가져야 한다.
- 재킷·쇼츠·허벅지 노출·장비는 실제 패턴과 두께가 보이고, 쿼터뷰에서도 여성 실루엣과 캐릭터 훅이 읽혀야 한다.
- 평면 색상만으로 끝내지 않고 피부·천·가죽·금속·발광 재질과 셀 셰이딩을 분리해야 한다.
- 128px 얼굴·전신 실루엣·저채도 비교에서 CH101이 다른 4인과 구분되어야 한다.

- 얼굴·눈·앞머리·포니테일 실루엣 정밀화
- 재킷 패널, 후드, 소매, 쇼츠, 스트랩 분리
- 부츠와 세이버의 비율·두께·손잡이 방향 수정
- 신호 리본의 시작점·끝점·충돌 영역 정리
- 파츠별 이름·parent·socket 관계 고정
- front/side/back 렌더에서 실루엣 비교

완료 기준:

- 각 주요 파츠가 별도 오브젝트로 식별된다.
- 카메라 3면에서 큰 형태 충돌이 없다.
- 리본·세이버·부츠가 기준 시트의 기능적 위치와 일치한다.
- 변경 전후 렌더와 변경 리포트가 남는다.

시각 품질 완료 기준: 사람이 정면·측면·후면·쿼터뷰를 보고 레고/회색 박스가
아닌 프리미엄 서브컬처 캐릭터로 판정하고 Gate A를 통과한다.

v004 적용 항목:

- 얼굴·눈·눈썹·입 가독성 cue
- 재킷 포켓·뒷면 시안 스트라이프
- 쇼츠 벨트와 허벅지 스트랩 버클
- 긴 포니테일 가닥과 시안 연결 가닥
- 세이버 그립 밴드와 리본 끝단 링크

### Phase 4 — Technical Asset Preparation

상태: `COMPLETE — v005`

- procedural curve 오브젝트를 mesh로 변환
- bevel 등 modifier 적용 및 scale transform 적용
- UV가 없는 메시의 smart projection 생성
- material slot 누락 검사와 triangle 수 기록
- `LOD0 ONLY / LOD PENDING` 메타데이터 기록
- v005 `.blend`와 `.fbx` 재수출

완료 기준: Colab에서 UV·material slot 검증 `PASS`, triangle 수와 LOD 상태가 JSON에 기록되고 v005 산출물이 재생성된다. 충족됨.

### Phase 5 — Rig and Motion Preparation

상태: `TECHNICAL COMPLETE — V010 SCAFFOLD / VISUAL MODEL REQUIRED`

- Unity Humanoid 역할명에 맞춘 22-bone armature prototype
- 8개 socket을 hand/chest/hips/head bone에 연결
- `CH101_A_Pose_Check` review action 추가
- `CH101_Idle`, `CH101_Run`, `CH101_Attack` review action 추가
- v007~v009 rigid blockout/LOD 비교본 보존
- v010에서 각 LOD0 메시 파츠에 정규화된 2-bone production-review weight와 Armature modifier 적용
- v010에서 6개 material slot budget과 max 2 influences/vertex를 검증
- LOD0 예산 최적화와 LOD1/LOD2 review mesh 생성
- A-pose·idle·run·attack 변형 preview render 생성
- weighted mesh 수와 skinning 오류를 JSON으로 검증

완료 기준: 로컬/Colab에서 bone·socket·motion clip·weight·pose render·LOD·material budget 검증 `PASS`를 확인한다. 충족됨. Unity Humanoid 최종 매핑, LODGroup, prefab, Android 성능은 Phase 6~7에서 별도 확인한다.

### Phase 6 — Unity Import Proof

상태: `IN PROGRESS — PREFLIGHT CONTRACT / UNITY LICENSE BLOCKED`

- FBX Import Settings 기록
- material과 texture 재연결
- socket 위치 확인
- Animator/Humanoid mapping 확인
- prefab 생성 및 씬 배치
- 콘솔 오류와 경고 기록

완료 기준: Unity Editor 화면, Import 설정, prefab, 실행 캡처가 증거로 남는다. 현재 Unity
`6000.5.3f1` batch editor는 유효 라이선스가 없어 import proof 실행 전 단계에서 종료된다.

### Phase 7 — Android Performance Proof

상태: `BLOCKED UNTIL DEVICE/BUILD ENVIRONMENT`

- target Android build 생성
- draw call, triangles, texture memory 기록
- GPU/CPU frame time 측정
- thermal/battery 영향 확인
- 저사양 기준과 현재 결과 비교

완료 기준: 동일한 빌드·기기·씬 조건의 측정 리포트가 존재한다.

### Phase 8 — Gate B Review

상태: `PENDING`

- 최종 turnaround 일관성
- 장비 구조와 socket evidence
- material slot과 simplification table
- blockout 또는 final asset proof
- Unity Import proof
- Android performance proof
- 사람 승인 기록

완료 기준: 모든 필수 증거가 연결되고, 사람이 Gate B를 명시적으로 승인한다.

## 캐릭터 확장 순서

CH101을 Phase 3까지 정리한 뒤 같은 규격으로 다른 캐릭터를 확장한다. 캐릭터별 아트 시트와 source commit은 독립적으로 고정하며, 공통으로 유지할 항목은 socket 이름·material slot 규칙·export 규칙이다.

## 저장 규칙

- 코드·Notebook·문서는 `re-camp-blender`에 저장한다.
- 아트 원본과 승인 문서는 `re-camp`에 저장한다.
- `.blend`·`.fbx` 생성물은 기본적으로 ZIP 다운로드로 보관한다.
- 영구 대용량 보관이 필요하면 GitHub Release 또는 Git LFS를 사용한다.
- 토큰·개인정보·Colab 인증정보는 저장소에 넣지 않는다.

## 다음 실행 항목

현재 바로 진행할 작업은 CH101을 프리미티브 스캐폴드에서 고품질 3D 제작 모델로 교체하는 시각 제작 단계다. 공통 베이스 run3/4, 연결 Skin run2, voxel body run1을 실행했지만 모두 레고·토이형 표면으로 반려되었으므로 Gate B 후보로 승격하지 않는다. 실제 고해상도 수동/스컬프 베이스 메시와 의상 패턴이 `CH101_A_HighRes_Production_v001.blend`로 확보된 뒤에만 Unity 라이선스가 활성화된 Editor에서 v010 기술 계약을 새 모델에 적용하고 Import/LODGroup/Prefab/Animator/AndroidPlayer 증거를 수집한다.
