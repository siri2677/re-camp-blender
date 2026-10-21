# CH101 양방향 오차 기반 겨드랑이 지지 메시 — 2026-10-21

## 이번 결과

원격 `15ad64c2d391b2ddef99364be6154a98b44b6b19`까지 fast-forward한 뒤
10월 19일의 실제 최신 파일에서 이어갔다. 9월 30일 어깨 경계 추출을 반복하지 않았다.
기존 42 mm 패치를 보존하고 **다른 영역 5의 28.495 mm 구역**에서 실제 면을
32→24삼각형으로 교체했다. 내부 5정점을 제거하고 오차 보정 지지점 1개를 추가한다.
새 연구면은 2,693정점 / 5,028삼각형이다.

국소 최대 꺾임 88.753158→54.289260도, 국소 55도 초과 edge 4→0,
국소 굴곡 합 48.8816% 감소. 전체 연구면 굴곡 합은 추가 2.0421% 감소다.
이는 전신 품질 점수나 모델링 완료율이 아니다. 전역 최대 134.755862도 주름은 남는다.

17장 실제 Blender 렌더를 확인했다. 분리 패치/와이어에서는 정점 집중과 면 배치가
바뀌지만, 넓은 시점의 차이는 작다. 새 연구면·가이드는 숨긴 상태로 저장하고
기존 표시 조립본과 rounded-hem 전신 기준본을 유지한다. 외형 기준본 미채택이다.

## 원인 진단과 새 방법

`diagnosing-bugs` 스킬의 실제 소스 회귀 절차로 방향 누락을 분리했다.
최신 입력의 seed 887 / 영역 6 / ring 1에서 패치→원본 오차 1.851690 mm가
상한 1.5 mm를 넘는데, 원본→패치 오차는 1.480045 mm였다. 역방향 witness만
선택하면 구역 밖의 정상 표본을 선택해 `WITNESS_OUTSIDE_REPLACEMENT`로 중단한다.
선택된 한 구역만 실행하는 회귀 테스트에서 약 1.2초로 재현했다.

가설은 (1) 방향 누락, (2) 최신 source map/triangle index 오류,
(3) 보호 경계에 걸린 삽입 위치였다. 실제 패치의 forward witness를 추가하고
더 큰 위반 방향을 선택하는 한 변수 변경으로 해당 테스트가 통과했다.
기존 인덱스 map과 보호 경계를 바꾸지 않았고, 실제 interior edge를 분할한다.

새 방법은 지지점을 최대 4개까지 **순차적으로** 삽입할 수 있다. 원본 chart 대비
양방향 coarse 표본과 추가 12분할 barycentric 표본을 함께 사용한다.
coarse 통과 뒤 dense 오차가 남으면 그 위치도 다음 지지점의 출처로 쓴다.
보호 경계 이동, 기존 정점 이동, 오차 기준 완화는 하지 않는다.

예를 들어 seed 887은 지지점 3개 후 coarse 검사를 통과해도 dense에서 실패한다.
4번째 지지점을 넣은 뒤에도 실패하면 그대로 거부한다. 현재 유한 탐색을 모든
가능한 재설계에 대한 불가능성 증명으로 해석하지 않는다.

## 탐색·선택

- 최신 map으로 대응시킨 잔여 seed 39개, 중복 제거한 구획 61개.
- 목표 거리 1.45 / 1.35 / 1.20 mm, 각 경로 최대 지지점 4개.
- 실제 geometry/QA 측정 42회, checkpoint 기록 52개. 각 목표에서 공유하는
  무지지점 출발안을 중복 기록하므로 두 수는 다르다.
- 모든 조건을 통과한 3개는 **같은 구역의 서로 다른 지지점 위치**다.
  전체 굴곡 합이 가장 낮은 seed 713 / domain 5 / ring 1 / target 1.20 mm를 선택했다.
- 최종 채택된 국소 안은 지지점 **1개**다. 여러 지지점 탐색 지원을 여러 점이
  적용된 최종 패치, 여러 구역 교체 또는 겨드랑이 전체 재제작으로 부풀리지 않는다.

## 수치와 보존

| 항목 | 결과 |
| --- | --- |
| 실제 선택 구역 | 32→24삼각형, 내부 5개 제거·지지점 1개 추가 |
| 국소 최대 꺾임 / 55도 초과 edge | 88.753158→54.289260도 / 4→0 |
| 국소 굴곡 합 | 0.0641222912→0.0327783087 rad²·m |
| 전체 굴곡 합 | 1.5348905732→1.5035464423 rad²·m |
| 원본 chart 정/역 최대 표본 차이 | 1.442278 / 1.480045 mm |
| 기본 정/역 표본 수 | 15,442 / 1,129 |
| 추가 패치 정/역 최대 표본 차이 | 1.285122 / 1.288256 mm |
| 추가 표본 수 | 2,184 / 237 |
| 유지 정점 이동 / 원본 몸체 이동 | 0 / 0 |
| 보호 layout edge / 기존 패치 면 | 907 / 67 유지 |
| 자체 비인접 교차 / 방향 불연속 / 면적 오류 | 0 / 0 / 0 |
| 성분 / 열린 경계 / Euler | 1 / 2 / 0 |

이전 cap·5개 disk·42 mm 패치의 면 67개와 모든 원본 메시/UV/재질/가중치,
기존 가이드·표시 상태를 유지했다. 새 메시 UV는 아직 작성하지 않았다.
원본 몸체의 누적 2.999919 mm / 3 mm와 원본 branch chart 대비 누적 1.5 mm를
갱신하거나 초기화하지 않는다. 위 표본은 연속 오차·solid containment·변형 안전성
증명이 아니다. 이 연구면은 열린 unoffset 면이므로 몸체/장비 관통·의상 두께·봉제
전체 QA를 통과했다고 하지 않는다.

## 남은 주름의 실제 분류

저장된 파일의 SHA256·렌더·QA를 검증한 다음, Blend를 수정/재저장하지 않는
`--inspect-saved`로 `remaining-crease-report.json`을 만들었다.
55도 초과 edge는 63개이며, 그중 보호 설계 edge 8개·비보호 edge 55개다.
가장 큰 134.755862도 edge `[877,1389]`는 영역 6의 **비보호 edge**다.
따라서 모든 큰 주름이 907개 잠금 때문에 해결 불가능하다고 결론내리지 않는다.
이번 구획·DP·최대 4점 witness 삽입 방식이 해당 부분을 해결하지 못한 것이다.

## 다음 실행 순서

1. 이번에 검사한 구획/목표 조합을 같은 이름으로 다시 돌리지 않는다.
   영역 6의 최대 잔여 crease와 주변 비보호 연결망을 우선 대상으로 삼는다.
2. 현재의 ‘내부 점 모두 제거 후 witness로 복원’ 방식 대신, 필요한 내부 ridge와
   support 연결을 처음부터 남기는 **구조 보존 패널 재분할**을 설계한다.
   보호 course 이동이 필요하면 별도 proposal·대응 map으로 분리하고 원본을 보존한다.
3. 원본 1.5 mm·55도·굴곡 감소·교차·경계 보존 조건을 함께 검사한다. 제한된 탐색
   실패를 이유로 품질 기준을 낮추거나 전체 불가능으로 단정하지 않는다.
4. 임시 torso clip→실제 접합 경계, 보류된 torso crease 재판정,
   공유 소매 접합·두께·몸체/장비 교차 QA를 진행한다.
5. UV/장식/bake → 반대 팔·몸통·얼굴·헤어 전신 정리 → rig/weight/변형 →
   기술 인테이크·사람 Gate B → CH102~105 → Unity·Android 순서를 유지한다.

## 재현·검증·저장

런타임은 로컬 Blender **5.2.1 LTS**, build `9e2066aef7ef`, CPU다.
새 Kaggle/GPU/유료 Provider 추론을 실행하지 않았다.

입력은 [최신 패널 pointer](../artifacts/CH101-latest-underarm-panels.json)를 복원한
`CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend`이며 SHA256은
`48844f26a0182f6243081fbbfb036269c8436a8dd9ec79dc129addaf184ad362`다.
disk/cap/layout/support-curve/previous-panel report 5개의 정확한 SHA256,
art commit `b6c9b3128358e061eee6184230929413eba84101`, 참조 이미지 해시와 Gate를 검증한다.
5개 이전 Release는 새 폴더에 다운로드해 ZIP·payload 해시를 검증했다.

```text
blender --background --python-exit-code 1 --python scripts/blender/refine_ch101_underarm_support_mesh.py -- --source <panels>/CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend --disk-report <disks>/underarm-disks-report.json --cap-report <cap>/cap-replacement-report.json --layout-report <layout>/deformation-layout-report.json --curve-report <curves>/support-curves-report.json --art-root <art-repository> --output <fresh-output>
blender --background --python-exit-code 1 --python tests/blender/test_underarm_support_mesh.py -- --source <panels>/CH101_BoundaryLockedUnderarmPanels_NOT_PRODUCTION_v001.blend --disk-report <disks>/underarm-disks-report.json --cap-report <cap>/cap-replacement-report.json --layout-report <layout>/deformation-layout-report.json --curve-report <curves>/support-curves-report.json --artifact <output>/CH101_MultiKnotUnderarmSupportMesh_NOT_PRODUCTION_v001.blend
```

Blender 신규 검사 11개(전체 10개 + 읽기 전용 진단 검사), 이전 패널 회귀 검사 14개,
Python unittest 132개, AI3D/Colab validator(10 notebooks / 59 Blender scripts / 36 utilities),
compile/diff 검사를 모두 통과했다. optional source-tree 검사는 환경변수 미설정으로 skipped이고,
실제 실행에서는 input/art/reference 해시를 별도 검증했다.

산출물: Blend, 실제 전후/위치/와이어 렌더 17장, 전체 탐색·선택·QA report,
잔여 주름 분류, read-me 및 시각 검토 기록. 코드·계획·작은 기록은 feature 브랜치,
큰 결과물은 GitHub prerelease에 보관하고 새 다운로드로 전부 SHA256 검증한다.
최종 Blend SHA256: `9001b1849c09582f91819db9d9d657bc6d51cfa31722dabf593e6e7b0cbba6af`.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
adoptionAllowed: false
fullUnderarmRebuilt: false
garmentStaticQA: false
deformationValidated: false
rigBound: false
fullCharacterScore: null
```

## 배포·복원 검증

[연구용 prerelease](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-underarm-support-mesh-v001)에
Blend·렌더·report·잔여 주름 진단·read-me·시각 판정을 보관했다.
새 폴더로 ZIP과 **22개 payload 전체를 다운로드하여 SHA256 PASS**를 확인했다.
`panel_before_after.png`를 ZIP 밖에도 첨부했다. 배포 검증은 모델 품질 승인과 별개다.
다운로드한 Blend로 신규 **11개 검사 전체를 다시 실행해 통과**했다(47.517초).
별도 preview asset도 새 다운로드 후 해시가 ZIP 내부 payload와 일치함을 확인했다.

- Tools commit: `7647ebbc93405750f9bcdd7164df87b05a91e1a4`.
- ZIP: 30,245,368 bytes, SHA256
  `34ed55bc26815cc64a19cba8ca22a24a17058c371cca1dee8bc0433dfb3aff02`.
- manifest SHA256: `be734c7dbd8631551e5a6f2281eedfe8f59eb89c94ad69ff20d704af1ba310ea`.
- preview SHA256: `5e633859ea51dfaca7db3d5b4c15d2d5f1131f9188722f56a56c463e37e33358`.
- 복원 pointer: `docs/artifacts/CH101-latest-underarm-support-mesh.json`.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-underarm-support-mesh.json --output-dir artifacts/restored-underarm-support-mesh
```
