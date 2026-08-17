# CH101-A 메시 인테이크 검증기 WIP — 2026-08-16

상태: `READY FOR FIRST REAL HIGH-RES MESH / GATE B BLOCKED`

## 검증기

- 스크립트: `scripts/blender/validate_ch101_mesh_intake.py`
- 대상: 실제 CH101-A production `.blend`
- 검사: 바디·의상·헤어·장비 컬렉션, UV, 삼각형 예산, 재질 수, CH101 armature,
  소켓, Armature modifier, WIP/승인 상태

## 현재 씬에 대한 기준 실행

모델링 가이드 run3에 실행한 결과는 의도대로 `FAIL / Gate B BLOCKED`다. 가이드 씬은
참조 이미지·기준점만 포함하고 생산 컬렉션과 메시가 비어 있기 때문이다.

- 리포트: `artifacts/CH101_modeling_guide_run3/reports/CH101_mesh_intake_expected_block.json`
- 실패 이유: body/outfit/hair/equipment 메시 없음, CH101 armature 없음, WIP 상태

실제 고해상도 메시가 도착하면 같은 명령으로 재검증하고, 이 검사가 PASS한 뒤에만
웨이트·포즈·LOD·Unity Gate B 증거를 수집한다. 이 검증기는 사람의 시각 승인(Gate A)을
대체하지 않는다.
