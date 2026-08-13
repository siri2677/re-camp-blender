# CH101 Production Roadmap

이 문서는 `re-camp`의 잠긴 CH101 아트 시트를 Blender·Unity 작업으로 연결하는 전체 계획이다. 현재 기준 아트는 `re-camp`의 `art/current-roster-gate-a-ch102` 브랜치와 커밋 `418ef96`이다.

## 현재 판정

상태: `PRODUCTION MODELING REFINEMENT V004 COMPLETE / GATE B PENDING`

완료된 증거:

- Public 도구 저장소: `siri2677/re-camp-blender`
- Google Drive 없이 Colab 실행 가능
- `xvfb-run`을 이용한 headless Blender 실행
- CH101 v004 front/side/back 렌더
- `.blend`와 `.fbx` export
- JSON 구조 검증 `PASS`
- 메시 80개 이상, 소켓 8개, 누락 0개

현재 결과는 최종 캐릭터 모델이 아니다. 실제 topology, UV, rig, animation, Unity Import, Android 성능 증거가 아직 없다.

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

상태: `COMPLETE — v004`

목표는 Blockout을 실제 제작에 사용할 수 있는 형태로 정리하는 것이다.

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

v004 적용 항목:

- 얼굴·눈·눈썹·입 가독성 cue
- 재킷 포켓·뒷면 시안 스트라이프
- 쇼츠 벨트와 허벅지 스트랩 버클
- 긴 포니테일 가닥과 시안 연결 가닥
- 세이버 그립 밴드와 리본 끝단 링크

### Phase 4 — Technical Asset Preparation

상태: `PENDING`

- 적용 가능한 topology 정리
- normals와 smoothing 확인
- UV 전개
- material slot 정리
- 텍스처 슬롯과 파일 경로 규칙 확정
- LOD 또는 모바일용 단순화 기준 추가
- FBX 재수출 및 파일 크기 확인

완료 기준: Unity에서 재현 가능한 material slot·transform·파일 구조가 존재한다.

### Phase 5 — Rig and Motion Preparation

상태: `PENDING`

- humanoid 기준 bone 구조 설계
- 팔·다리·손·헤어·리본의 변형 범위 정의
- 기본 A-pose/T-pose와 관절 충돌 확인
- 최소 idle/run/attack 테스트 모션

완료 기준: Blender에서 pose 검증이 가능하고, 내보낸 리그가 Unity Humanoid 기준을 만족한다.

### Phase 6 — Unity Import Proof

상태: `BLOCKED UNTIL UNITY ENVIRONMENT`

- FBX Import Settings 기록
- material과 texture 재연결
- socket 위치 확인
- Animator/Humanoid mapping 확인
- prefab 생성 및 씬 배치
- 콘솔 오류와 경고 기록

완료 기준: Unity Editor 화면, Import 설정, prefab, 실행 캡처가 증거로 남는다.

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

현재 바로 진행할 작업은 Phase 4의 `Technical Asset Preparation`이다. Unity와 Android 단계는 해당 실행 환경이 준비되기 전까지 계획·검증 기준만 유지한다.
