# CH101-A 리그·소켓 템플릿 WIP — 2026-08-16

상태: `WIP / RIG TEMPLATE / NO MESH / NOT APPROVED`

## 산출물

- 스크립트: `scripts/blender/build_ch101_rig_template_wip.py`
- Blender: `artifacts/CH101_rig_template_run5/CH101_A_RigTemplate_WIP_v001.blend`
- 리포트: `artifacts/CH101_rig_template_run5/reports/CH101_A_RigTemplate_WIP_v001.json`
- 자동 검증: `scripts/blender/validate_ch101_rig_template.py`
- 검증 리포트: `artifacts/CH101_rig_template_run5/reports/CH101_A_RigTemplate_validation.json`

## 포함 내용

- Root/Hips/Spine/Chest/Neck/Head와 사지·손·발·발가락 본 계층
- `Socket_Weapon_R`, 리본 L/R, 파우치 L/R, 포니테일, 카메라 포커스 소켓
- Idle/Run/Attack/A-Pose 점검용 액션 슬롯 템플릿
- Gate B에서 실제 메시를 바인드할 기술 컬렉션과 상태 메타데이터

## 경계

이 파일은 리그 템플릿이며 메시·웨이트·변형·애니메이션 증거가 없다. 실제 고해상도
CH101-A 메시와 사람 Gate A 승인이 들어오기 전까지 Gate B 또는 Unity Import로 승격하지
않는다.

## 검증

- Python 구문 검사 통과
- Blender 4.5 백그라운드 저장 통과
- 본 22개·소켓 7개·액션 슬롯 4개 생성 확인
- 자동 템플릿 검증 `PASS`
