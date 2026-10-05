# CH101 주요 경계 고정 사각 면 연결 정리

2026-10-05, `feature/ch101-free-ai3d-autobuild`.

## 이번에 완료한 범위

이전 국소 보정본에서 실제 quad 연결을 276회 바꾸고 520개 면을 재구성했다.
두 quad의 공통 edge를 다른 대각 연결로 회전하되 동일한 방향의 6-edge 외곽,
재질 영역, 열린 외곽과 공유 분기 경계 88개를 유지한다. 주요 주름 edge 64개,
인접 면 121개와 표면 오차가 발생했던 두 면 164/421은 잠근다.
두 면 번호는 고정 source 해시에 종속된 보호 장치이며 일반 모델에 재사용하지 않는다.

연결 변경만으로는 음영이 악화될 수 있어 실제 Blender 렌더 삼각분할을 사용한
50회 제한 보정을 함께 실행했다. quad가 움직이며 대각선이 바뀔 수 있으므로
각 반복에서 삼각분할을 갱신한다. 709개 고정 정점은 이동 0이며 연구 정점
1,533개가 이동했다. 기존 몸체·메시·UV·재질·가중치는 바꾸지 않는다.

제한은 이전 보정본에서 추가 1.2 mm, 최초 quad cage에서 누적 1.48 mm,
원본 branch chart에 대한 양방향 표본 차이 1.5 mm다. 단계별 예산을 초기화하지 않는다.
몸체의 기존 누적 2.999919 mm / 상한 3 mm도 그대로다.
이는 **국소 연결 정리와 굴곡 보정**이며 주요 주름 재설계나 변형용 최종 면 흐름은 아니다.

## 측정과 시각 검토

| 항목 | 이전 보정본 → 이번 결과 |
| --- | --- |
| 정점 / quad | 2,258 / 2,079 유지 |
| 내부 4방향 접합점 | 950 → 974 (내부 정점 1,900개) |
| 불규칙 내부 접합점 | 950 → 926 |
| valence 4 대비 제곱 오차 합 | 2,501 → 1,662, 33.55% 감소 |
| 실제 렌더 삼각형 굴곡 합 | 1.6724863824 → 1.5962370764 rad²·m, 추가 4.5590% 감소 |
| 최대 주요 꺾임 | 134.755862도, 변경 없음 |
| 추가 이동 / 최초 cage 대비 누적 이동 | 1.200000 / 1.480056 mm |
| 고정 정점 / 원본 몸체 이동 | 0 / 0 |
| 정방향 / 역방향 참조 표본 차이 | 1.442278 / 1.480045 mm |
| 자체 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 연결 성분 / 열린 경계 / Euler | 1 / 2 / 0 |

이동 수치의 float 초과분은 0.0001 mm 저장 허용오차 이내다.
굴곡은 quad 내부 대각선 포함 6,058개 내부 삼각형 edge를 측정한다.
참조 표본은 10,753 / 1,129개로 선행 단계 오차를 포함하지만 연속 최대 오차 증명은 아니다.
교차 검사에서는 정점을 공유하는 삼각형 쌍을 제외한다.
열린 무두께 면이라 몸체 clearance·두께·봉제 QA를 통과했다는 뜻은 아니다.

정면·측면·후면·사선의 전후 8장 및 와이어 4장을 직접 확인했다.
초기 연결 시험의 심한 작은 조각/별 모양 음영은 줄었지만 큰 주름, 겨드랑이의
불규칙 접합, 잔여 faceting과 각진 임시 몸통 절단선은 남는다.
**외형 기준본 미채택**이며 이전 upper-interface 조립본을 기본 표시하고 새 메시를 숨긴다.
절반에 가까운 내부 정점이 아직 불규칙해 최종 변형용 재토폴로지로 승인하지 않는다.

초기 무보정 348회 연결은 4방향 접합점이 1,035개로 늘어도 굴곡이
1.672486 → 3.007942로 악화되어 거부했다. 별도 tessellation 대체 방법도
2,079 quad 중 1,011개만 Blender 렌더와 일치해 사용하지 않는다.
최종 레시피는 국소 굴곡 증가를 0.002 rad²·m로 제한하고 독립 최종 QA를 적용한다.
실패 요약을 `rejected-reconnection-trials.json`에 저장한다. 회전마다 굴곡 감소를 주장하지 않는다.

Blender 5.2.0 LTS CPU 검사 **16개 통과**: 신규 9개와 이전 fairing 회귀 7개.
실제 제작/원본 보존, 방향 있는 외곽 유지, 모든 source quad의 실제 삼각분할 일치,
무변화 및 무보정 악화 거부, 연결 기록/valence 변조·잠금/이동/해시 변조 거부,
저장 후 복원/표시/UV·재질·가중치와 12장 렌더 해시를 검사했다.
AI3D/Colab validator 통과: 10 notebooks / 53 Blender scripts / 36 utilities.

## 재현과 공유

원본은 [이전 보정 pointer](../artifacts/CH101-latest-shoulder-crease-fairing.json)로 복원한다.

- source Blend SHA256: `fda96bec01f2ddbab72c559effb7f61e8471340e9730cd34870d31847199908b`
- source report SHA256: `7c44b13a16966a04c4cebc9ccead1b02ee31aced1cee28fe0b96eedb9e52f715`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과: `CH101_FeatureLockedShoulderEdgeFlow_NOT_PRODUCTION_v001.blend`
- 결과 SHA256: `4710695635be734c20d469d8c60f3bb6c94ffae6fb8fe51e9818cb8b86a2da55`
- 새 메시: `CH101_FeatureLockedShoulderEdgeFlow_NOT_PRODUCTION` (기본 숨김)

```text
blender --background --python-exit-code 1 --python scripts/blender/author_ch101_shoulder_edge_flow.py -- --source <restored-fairing.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_edge_flow.py -- --source <restored-fairing.blend> --artifact <new-output-directory>/CH101_FeatureLockedShoulderEdgeFlow_NOT_PRODUCTION_v001.blend
```

실제 Blend·12장 렌더·QA report·read-me·visual review·거부 시험 요약을
별도 연구용 Release로 공유한다. 공개 후 새 경로 다운로드와 ZIP/개별 SHA256
검증 결과를 여기에 기록한다. 이전 pointer와 전신 rounded-hem 기준본을 대체하지 않는다.

## 이어서 할 순서

1. 고정된 큰 주름의 유지/단순화 범위를 설계하고 겨드랑이·어깨의 변형 방향에
   맞는 경로를 작성한다. valence 수치나 smoothing 반복만으로 B를 완료하지 않는다.
2. 임시 clip 외곽을 실제 몸통 접합 경계로 교체하고 소매 상단과의 연결 관계를 확정한다.
3. 공유 경계와 두께 셸 제작 후 자체/몸체/장비 교차·간격·벽 두께·다방향 외형 QA.
4. 새 패널 UV/장식/베이크 → 반대 팔/몸통/얼굴/헤어 전신 정리 → rig/변형 증거.
5. 전체 기술 인테이크와 별도 사람 Gate B 후에만 Unity/Android 및 CH102–105 확장.

`garmentStaticQA=false`, `majorFoldShapeRedesigned=false`,
`deformationValidated=false`, `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`이다.
Gate B pending, Unity/production 금지를 유지한다. 새 SPAR3D/Kaggle 추론은 하지 않았다.
