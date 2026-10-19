# CH101 경계 고정 다중 내부 정점 겨드랑이 패치

2026-10-19, `feature/ch101-free-ai3d-autobuild`.

## 완료 범위와 남은 한계

[지지 곡선 검토](ch101-underarm-support-curves-2026-10-19.md) 후, 영역 7의 약
42.346 mm 구역에서 **실제 면 21개를 17개로 교체**했다. 원래 내부 정점 3개를
제거하고 원본 오차를 지키는 내부 지지점 1개를 새로 작성한다. 새 전체 연구면은
2,697정점/5,036삼각형이다. 단일 정점 star 제거 반복이나 곡선만 저장한 단계가 아니다.

그러나 이 구역 하나가 17–20 cm 겨드랑이 전체의 재설계 완료를 뜻하지 않는다.
전역 최대 꺾임 134.755862도, 좁은 삼각형, 임시 torso clip과 미봉제 경계는 남는다.
원본 메시/UV/재질/가중치, 이전 cap·5개 disk의 50개 면, course/영역/외곽 907 edge,
기존 곡선과 기본 표시 조립본을 보존했다. 새 연구면과 새 경계 곡선은 기본 숨김이다.
외형 기준본 미채택, 전신 rounded-hem 기준본 유지. 새 UV·장식·두께·리깅은 작성하지 않았다.

## 패치 구획과 선택

이전 원본 crease group 193을 layout→cap→disk 정점 map으로 대응시킨 40개 잔여
정점을 출발점으로 사용한다. 선택 지지 곡선 35 mm 이내에서 같은 재질 영역의
면 인접 graph를 1–4 ring 확장한다. 이전 cap/disk와 보호 경계를 넘지 않는다.
중복 면 집합은 한 번만 계산한다. 경계가 단순한 내부 disk이고 내부 정점 ≥3,
면 ≥20, 최대 점간 거리 ≥25 mm일 때만 multi-interior panel 후보로 센다.
동적 계획법의 선언한 경계 예산은 32정점이다. 이 탐색은 모든 가능한 재설계의
가능성/불가능성을 증명하지 않는다.

구획을 통과한 68개 중 7개가 실제 3D 법선과 경계 밖 이웃을 고려하는 55도 제한
삼각분할을 통과한다. 하지만 내부 점을 모두 제거한 7개는 원본 누적 표면 검사에서
모두 탈락한다. 가장 가까운 seed 910의 역방향 오차도 1.579210 mm다.

오차를 초과한 역방향 원본 표본의 최근접 패치 위치에 내부 지지점 하나를 삽입하는
별도 설계를 시험한다. 기준점/선분이 외곽이면 거부하며 기존 경계 정점은 움직이지 않는다.
원본 표본까지의 목표 거리는 1.45/1.35/1.20 mm의 고정된 세 경우만 검사한다.
전체 16개 실제 면 안 중 두 개가 전체·추가 국소 표본 조건을 통과하며 같은 구역의
다른 지지점 배치다. 그중 전체 렌더 삼각형 굴곡이 더 낮은 하나만 채택한다.

선택: **최신 disk 입력 메시 기준 seed 910, 영역 7, face ring 2, 목표 1.45 mm**.
경계 17정점은 그대로다. 생성 지지점은 점 없는 임시 패치에서 0.129216 mm 떨어진
곳에 있으며 원본 branch chart 표본 160을 출처로 가진다. 이는 몸체 정점 이동이 아니다.
각 map, 원본 면/삼각형, 삽입 전 최근접점, barycentric 좌표, 새 좌표를 report에 남긴다.

낮은 표면 오차만으로도 채택하지 않는다. 예를 들어 seed 1071은 지지점 추가 후
표면 조건을 만족해도 국소 최대 88.856도라 거부한다. seed 1101은 꺾임이 55도
이내이고 표면 조건도 통과하지만 굴곡 합이 증가해 거부한다.

## 실제 수치

| 검증 | 결과 |
| --- | --- |
| 선택 구역 / 내부 정점 | 21→17삼각형 / 기존 3개 제거·새 지지점 1개 |
| 국소 patch + 접합부 최대 꺾임 | 74.747534→37.232130도 |
| 국소 55도 초과 edge | 2→0 |
| 국소 굴곡 합 | 0.0372458657→0.0158840721 rad²·m, 57.3535% 감소 |
| 전체 연구면 굴곡 합 | 1.5562523711→1.5348905732, 추가 1.37264% 감소 |
| 원본 chart 정/역방향 최대 표본 차이 | 1.442278 / 1.480045 mm |
| 기본 정/역방향 표본 | 15,466 / 1,129 |
| 추가 새 패치→원본 / 배정 원본→패치 최대 차이 | 1.085629 / 1.449994 mm |
| 추가 정/역방향 표본 | 1,547 / 221 |
| 유지 정점 / 원본 몸체 이동 | 0 / 0 |
| 자체 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 연결 성분 / 열린 경계 / Euler | 1 / 2 / 0 |

오차 상한은 직전 면이 아니라 **원본 branch chart에 대한 누적 1.5 mm**를 유지한다.
추가 표본은 12분할 barycentric grid이며, 역방향은 원본 표본의 기존 연구면 최근접
삼각형이 제거 구역에 속하는 경우로 배정한다. 연속 최대 오차 증명이 아니다.
자체 교차는 정점을 공유하는 삼각형 쌍을 제외한다. 몸체 누적 2.999919 mm / 3 mm도
초기화하지 않는다. 위 굴곡 수치는 전신 외형 점수나 캐릭터 품질 개선율이 아니다.

## 실제 이미지와 저장

실제 Blender 메시를 렌더한다. AI 합성 이미지가 아니다.
전후 넓은 8장, 위치 진단 4장, 확대 와이어 전후 4장, 좌우 비교 1장을 제작한다.
`panel_before_after.png`는 왼쪽 원본 21삼각형과 오른쪽 교체 17삼각형을 같은 재질·
조명·시점에서 보여주는 **구역 분리 진단**이다. 전신 완성본이나 봉제 완료 이미지가 아니다.
넓은 시점 차이는 작다. 큰 주름이 해결되었다거나 전신 외형 기준본을 교체했다고 세지 않는다.
비교용 복사본/와이어/글자는 render-only이며 저장본에 남기지 않는다.
저장된 Blend 해시와 QA를 먼저 재검증한 뒤 `--rerender-comparison`으로 좌우 비교와
확대 반투명 와이어 4장을 다시 렌더할 수도 있다. 이 옵션은 Blend를 다시 저장하거나
형상을 수정하지 않고 해당 PNG/report 해시만 갱신한다.

출력: `CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend`,
`underarm-panels-report.json`, read-me, 17장 실제 렌더와 시각/선택 검토 기록.
17장을 직접 확인했다. Blender 5.2.0 LTS CPU **14개 검사 통과**(75.624초),
공유 utility **2개 검사 통과**, AI3D/Colab validator 통과
(10 notebooks / 58 Blender scripts / 36 utilities).
전체 68개 구획·16개 면 안의 선택을 재현하고, 실제 면/지지점/경계/이전 패치 보존,
오차·꺾임·굴곡 조건의 독립적인 실패, provenance/map/NaN/곡선 변조 거부,
모든 원본 메시·UV·재질·가중치·곡선·표시 상태, 저장 후 재개방·렌더 해시·Gate 잠금과
입력 해시/덮어쓰기 방지를 확인했다. 공유 해시는 배포 검증 후 덧붙인다.

## 재현

- [지지 곡선 pointer](../artifacts/CH101-latest-underarm-support-curves.json): Blend와 curve report.
- [disk pointer](../artifacts/CH101-latest-underarm-disks.json), [cap pointer](../artifacts/CH101-latest-cap-replacement.json),
  [layout pointer](../artifacts/CH101-latest-shoulder-deformation-layout.json): provenance report.
- source Blend SHA256: `ef10dda26d6d54770b8a3f45d2919f96a39782825ad9121d93053024bc0d0930`.
- curve report SHA256: `9fabffce970e35917ff320751fa219c27f83108e9b3f1180aa48fe0f3a13b689`.
- art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/rebuild_ch101_underarm_panels.py -- --source <support>/extracted/CH101_BroadUnderarmSupportCurves_NOT_PRODUCTION_v001.blend --disk-report <disks>/extracted/underarm-disks-report.json --cap-report <cap>/extracted/cap-replacement-report.json --layout-report <layout>/extracted/deformation-layout-report.json --art-root <re-camp> --output <new-directory>
blender --background --python-exit-code 1 --python tests/blender/test_underarm_panels.py -- --source <support>/extracted/CH101_BroadUnderarmSupportCurves_NOT_PRODUCTION_v001.blend --disk-report <disks>/extracted/underarm-disks-report.json --cap-report <cap>/extracted/cap-replacement-report.json --layout-report <layout>/extracted/deformation-layout-report.json --artifact <output>/CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend
```

## 이어서 할 순서

1. 남은 큰 주름의 다중 면 구획을 **내부 지지점 포함 설계**로 확장한다.
   원래의 55도·굴곡 감소·원본 누적 1.5 mm를 함께 검증하고, 이번 한 구역이나
   단일 star 제거 반복을 겨드랑이 전체 재제작 완료로 세지 않는다.
2. 기존 보호 course를 바꾸는 별도 proposal이 필요하면 위치/영역 대응과 필요한
   선택을 먼저 분리한다. 907 edge 잠금이나 허용 오차를 조용히 바꾸지 않는다.
3. 임시 torso clip→실제 접합 경계, 보류한 18 crease edge 재판정.
4. 소매 공유 접합·두께·자체/몸체/장비 교차·벽 두께/간격·다방향 외형 QA.
5. UV/장식/베이크 → 전신 정리 → rig/weight/실제 변형 → 기술 인테이크·사람 Gate B → Unity/Android.

`fullUnderarmRebuilt=false`, `majorFoldShapeRedesigned=false`, `garmentStaticQA=false`,
`deformationValidated=false`, `adoptionAllowed=false`, `completeShoulderPanel=false`,
`rigBound=false`, `fullCharacterScore=null`이다. Gate B pending·Unity/production 금지 유지.
새 SPAR3D/Kaggle 추론을 실행하지 않았다.
