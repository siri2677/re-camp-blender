# CH101-A 모델링 가이드 씬 WIP — 2026-08-16

상태: `WIP / MODELING GUIDE / NOT APPROVED`

## 산출물

- 스크립트: `scripts/blender/build_ch101_modeling_guide_wip.py`
- Blender 씬: `artifacts/CH101_modeling_guide_run3/CH101_A_ModelingGuide_WIP_v001.blend`
- 리포트: `artifacts/CH101_modeling_guide_run3/reports/CH101_A_ModelingGuide_WIP_v001.json`
- 기준 이미지: Re:Camp `CH101_A_Canonical_Turnaround_WIP_v005.png`

## 포함 내용

- CH101-A 턴어라운드·표정·장비·포즈 기준 이미지 참조 오브젝트
- 머리·목·어깨·흉부·허리·골반·무릎·발목 제작 기준점
- 세이버·리본·파우치·포니테일 소켓 기준점
- 고해상도 바디·의상·헤어·장비·Export 컬렉션
- 컬렉션별 목적과 Gate 상태 메타데이터

생산 컬렉션은 의도적으로 비워 두었다. 기존 레고형 프리미티브를 다시 넣지 않고,
실제 연결 메시가 제작된 뒤에만 채운다. 이 씬은 모델링 착수용이며 완성 모델·리그·FBX·
Unity Prefab·Gate B 증거가 아니다.

## 검증

- `python -m py_compile scripts/blender/build_ch101_modeling_guide_wip.py` 통과
- Blender 4.5 백그라운드 저장 통과
- run3에서 v005~v009 참조 이미지 연결 확인
- 상태: Gate A 대기 / Gate B 차단 / Unity 차단
