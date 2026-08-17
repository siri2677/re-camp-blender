# CH101-A MPFB 베이스 소스 검토 — 2026-08-17

상태: `SOURCE ACCEPTED FOR WIP BASE / NOT APPROVED AS CH101 ART`

## 소스

- 저장소: `makehumancommunity/mpfb2`
- 커밋: `437dd513888a92399d1d3202d0e80859fae55abc`
- 파일: `src/mpfb/data/3dobjs/base.obj`
- 로컬 경로: `vendor/mpfb2/src/mpfb/data/3dobjs/base.obj`

공식 MPFB 라이선스 문서는 그래픽 자산(베이스 메시·프록시·타깃·텍스처·의상·리그)을
CC0 1.0 Universal로 설명하고, 소스 코드는 GPLv3로 분리한다. Re:Camp에는 소스 코드가
아닌 CC0 그래픽 베이스만 WIP 입력으로 사용한다.

## 실행 결과

- 원본 바디: 13,380 vertices / 18,486 faces 수준의 실제 인체 토폴로지
- 산출물: `artifacts/CH101_mpfb_base_run2/CH101_A_MPFBase_CC0_WIP_v001.blend`
- 리그 바인드: `artifacts/CH101_mpfb_bound_run2/CH101_A_MPFBody_RigBound_WIP_v001.blend`
- 바인드 검증: `scripts/blender/validate_ch101_bound_body.py`
- 검증 리포트: `artifacts/CH101_mpfb_bound_run2/reports/CH101_bound_body_validation.json`
- 자동 웨이트: 13,380 vertices weighted, Armature modifier `True`
- CH101 본 22개·소켓 7개 연결
- 바인드 전용 검증: `PASS`

타깃 델타를 적용한 별도 패스도 생성했다.

- 타깃 바디: `artifacts/CH101_targeted_obj_run2/CH101_A_TargetedObjBody_WIP_v001.blend`
- 타깃 바디 리그 바인드: `artifacts/CH101_targeted_bound_run1/CH101_A_TargetedBody_RigBound_WIP_v001.blend`
- 타깃 바디 바인드 검증: `artifacts/CH101_targeted_bound_run1/reports/CH101_targeted_bound_validation.json` (`PASS`)
- 적용 타깃: `head-oval`, 좌/우 눈 크기 증가, breast volume vertical up

## 품질 경계

MPFB 바디는 이전 레고형 프리미티브보다 실제 인체 표면/손/발/관절 토폴로지가 훨씬
낫지만, 일본 서브컬처 얼굴·헤어·CH101 의상·장비는 아직 적용되지 않았다. 따라서
`CH101_A_MPFBody_RigBound_WIP_v001.blend`는 기술 베이스일 뿐이며 Gate A/B·Unity
자산으로 승인하지 않는다.

MPFB 바디 표면에 자동 얼굴/헤어/의상 셸을 얹은 스타일링 run1~5도 렌더 검토했다.
실제 바디 토폴로지는 유효했지만 눈·헤어·의상 셸이 여전히 장난감형으로 읽혀 CH101
시각 기준을 통과하지 못했다. 따라서 스타일링 WIP는 시각 참고로만 남기고, 최종
스타일은 수동/고해상도 의상·헤어 제작으로 전환한다.

2026-08-17 후속 패스도 같은 경계를 재확인했다.

- `artifacts/CH101_mpfb_styled_run6/` — 로프트 의상 쉘·부츠·얼굴/헤어 비례 보정 시도.
- `artifacts/CH101_mpfb_styled_run7/` — torso jacket shell·알몬드 눈·가는 헤어 스트랜드 시도.
- `artifacts/CH101_mpfb_helpers_run1/` — MPFB helper hair/skirt/tights 좌표 정렬 검사.
- `artifacts/CH101_face_bust_run1/` — 얼굴·헤어·상체만 분리한 surface-patch 검증.
- 세 패스 모두 실제 인체 베이스 위에 붙는 제작 메시에 도달하지 못했다. run6/7은
  재킷이 부유한 판/튜브로 읽히며, helper run1은 MPFB helper 좌표·형상이 CH101
  의상 앵커와 직접 호환되지 않는다. 세 결과는 `WIP / NOT APPROVED`이며 Gate A/B
  후보로 승격하지 않는다.
- face-bust run1도 단순 캡/눈 오버레이와 상체 패치가 목표 품질에 못 미쳐 반려했다.
- Blender 4.x/5.x EEVEE 엔진 enum 차이를 스크립트에서 호환 처리했다.

3D 자동 스타일링을 더 누적하지 않고, Re:Camp 쪽에 v005/v010 기반 2D
`CH101_A_FaceBustStyleAnchor_WIP_v011.png`를 추가해 얼굴·헤어·상체 기준을 먼저
재정렬했다. v011은 사람 Gate A 검토용 앵커이며, 승인 전에는 Blender production
mesh 입력으로 고정하지 않는다.

v011을 실제 제작 입력으로 연결하기 위한 모델링 가이드도 만들었다.

- 씬: `artifacts/CH101_v011_modeling_guide_run1/CH101_A_V011_ModelingGuide_WIP_v001.blend`
- 리포트: `artifacts/CH101_v011_modeling_guide_run1/reports/CH101_A_V011_ModelingGuide_WIP_v001.json`
- 기준 이미지: `references/CH101_A_FaceBustStyleAnchor_WIP_v011.png`
- MPFB 바디는 `WIRE` 레퍼런스로만 표시하고, 얼굴·헤어·재킷 가이드 포인트와
  CH101 리그·소켓·액션 템플릿을 함께 배치했다. 생산 컬렉션은 의도적으로 비어 있다.

v012 회전 시트를 기준으로 같은 가이드를 다시 생성했다.

- 씬: `artifacts/CH101_v012_modeling_guide_run1/CH101_A_V012_ModelingGuide_WIP_v001.blend`
- 리포트: `artifacts/CH101_v012_modeling_guide_run1/reports/CH101_A_V012_ModelingGuide_WIP_v001.json`
- 기준 이미지: `references/CH101_A_FaceBustRotation_WIP_v012.png`
- v012는 정면·3/4·측면·후면의 얼굴/헤어/칼라/재킷 상체 일치를 위한 최신 제작 입력이다.

## 다음

1. 바디 표면 위에서 CH101 얼굴/헤어/의상/장비를 수동 또는 고해상도 스컬프로 제작한다.
   자동 패널/튜브 생성은 검증용으로만 유지한다.
2. 의상은 재킷·쇼츠·부츠를 각각 실제 표면에 맞춘 production mesh로 만들고,
   머리카락은 두피 캡 + 가닥/리본 파츠로 분리한 뒤 리그 변형을 확인한다.
3. v005~v010 시트와 4방향·포즈 렌더를 다시 검토한다.
4. 메시 인테이크 검증 PASS 후 Gate A/B 및 Unity Import로 이동한다.
