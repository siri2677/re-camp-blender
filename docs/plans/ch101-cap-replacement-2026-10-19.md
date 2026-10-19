# CH101 경계 고정 cap 패치 실제 교체

2026-10-19, `feature/ch101-free-ai3d-autobuild`.

## 이번에 완료한 범위

10월 5일 설계도에서 제거 후보였던 cap 미세 꺾임(group 1874)을 실제 삼각형
패치로 교체했다. 이 영역의 20삼각형/내부 3정점을 제거하고, 고정 외곽 16점을
사용하는 14삼각형을 작성했다. 전체 새 연구면은 2,704정점/5,050삼각형이다.
외곽·course·영역 경계 edge 907개와 교체 영역 밖의 면 연결/재질 구분은 유지한다.

유지된 정점은 이동 0이지만 면의 연결과 그 내부 표면은 실제로 달라졌다.
이를 단순 ‘정점 이동 0’으로 품질 통과시키지 않고 원본 branch chart까지의
누적 양방향 표본 차이, 자체 교차, 면 방향과 실제 굴곡을 다시 검사한다.
경계 고정 최적화의 국소 결과이며 **전체 cap/겨드랑이 재제작 완료가 아니다**.

## 교체 방법과 거부한 시험

경계를 최소제곱 평면에 투영해 유효한 내부 대각선 후보를 검사한다.
동적 계획법의 상태에 root triangle의 법선을 남겨 자식 삼각형과의 실제
dihedral 비용을 계산하고, 외곽에는 고정된 이웃 면의 법선을 사용한다.
55도 초과 꺾임을 만드는 후보를 거부하며, 굴곡 합에 작은 삼각형 형상
tie-break 비용을 더한다. 평면 투영은 후보 연결 검사에만 쓰고 정점을 평면으로
이동시키거나 원본 몸체를 평탄화하지 않는다.

첫 면 형상 비용 전용 시험은 참조 오차·교차가 통과해도 패치 최대 꺾임이
63.3931 → 76.3788도로 커졌고 국소 굴곡 합이 0.00795953 → 0.01447274로
악화되어 거부했다. 이 실패를 회귀 검사와 artifact 진단 JSON에 보존한다.

## 수치와 시각 검토

| 항목 | 이전 설계도 → 새 교체본 |
| --- | --- |
| 해당 disk 삼각형 / 내부 정점 | 20 → 14 / 3 → 0 |
| 고정 patch 외곽 / 설계 경계 | 16정점 / 907 edge 보존 |
| 유지 정점 / 원본 몸체 이동 | 0 / 0 |
| patch 및 접합부 최대 꺾임 | 63.393076 → 34.954569도 |
| 같은 영역 55도 초과 edge | 2 → 0 |
| 국소 렌더 굴곡 합 | 0.0079595325 → 0.0055625264 rad²·m, 30.1149% 감소 |
| 전체 연구면 굴곡 합 | 1.5964159489 → 1.5940189477 rad²·m, 0.150149% 감소 |
| 전역 최대 주요 꺾임 | 134.755862도, 겨드랑이 쪽에 그대로 남음 |
| 원본 branch chart 정/역방향 최대 표본 차이 | 1.442278 / 1.480045 mm, 기존 1.5 mm 상한 유지 |
| 새 cap→직전 연구면 / 제거 구간→새 cap 표본 차이 | 0.052532 / 0.083915 mm |
| 비인접 자체 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 연결 성분 / 열린 경계 / Euler | 1 / 2 / 0 |

30.1%는 이 작은 patch와 접합부의 굴곡 수치이며 전체 캐릭터 점수나 외형 개선율이 아니다.
삼각형 면 중심·edge 중점·정점의 유한 표본이며 연속 최대 오차 증명이 아니다.
교차 검사에서 정점을 공유하는 삼각형 쌍은 제외한다. 몸체 누적 최대 이동은
기존 2.999919 mm / 상한 3 mm로 유지하며 새 예산으로 초기화하지 않는다.

전후 넓은 8장, 확대 shaded 2장과 확대 wire 2장, 총 12장을 직접 검토했다.
확대 와이어에서 실제 면 연결 변경과 3개 접합점 제거를 확인했다.
일반 시점의 외형 변화는 작고 주변의 긴 좁은 면·큰 주름·각진 임시 몸통 경계는 남는다.
**외형 기준본 미채택**이며 기존 upper-interface 조립본을 기본 표시한다.
새 `CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION` 연구면은 기본 숨김이다.

원본 메시·UV·재질·가중치와 이전 설계 가이드는 바꾸지 않았다.
새 연구면의 UV/두께/봉제·몸체 clearance·리깅/변형 QA는 작성하지 않았다.

## 겨드랑이 후속 범위 확인

44-edge 주름망의 정점 주변 면을 한꺼번에 고르면 318면/261정점이 잡힌다.
외곽 206 edge는 203/3개의 두 연결 묶음으로 갈리고, 한 외곽 정점의 차수가 4여서
단순 disk가 아니다. 기존 course 정점 75개와 앞/겨드랑이 두 원본 영역을 함께
건드린다. 따라서 cap 교체 알고리즘을 이 영역 전체에 그대로 적용하지 않는다.
읽기 전용 진단은 `probe_underarm_disk`로 재현하며 원본을 수정하지 않는다.

## 검증

Blender 5.2.0 LTS CPU 검사 **10개 통과**: 실제 패치/원본 보존, 오목 다각형
연결 및 맞지 않는 주변 법선 거부, 잘못된 정책/disk/연결 기록/정점/외부 재질
변조 거부, 면 형상 전용 실패 검출, 잘못된 겨드랑이 자동 채움 거부, 해시/잠금/
기존 출력 덮어쓰기 거부, 저장 후 재개방/표시/UV·재질·가중치·렌더 해시 보존.
공유 utility 검사 2개와 AI3D/Colab validator
(10 notebooks / 55 Blender scripts / 36 utilities)도 통과했다.
공유 검사 기본 TEMP 접근 오류는 workspace 내부 TEMP/TMP 경로로 실행해 해결했다.

## 재현과 공유

원본은 [이전 설계도 pointer](../artifacts/CH101-latest-shoulder-deformation-layout.json)로 복원한다.

- source Blend SHA256: `2eec54b4e8b0a829c94304f7ed54fb93b42eb84b469d4470353d38af39370540`
- source report SHA256: `ed9f9e3b5e0451a190401868e230f7c0258561c4a860acc7fd5af5633527d3ea`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과: `CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION_v001.blend`
- Blend SHA256: `7ece194c1fd5d7ea3f02c46f54cf38aeaf9538403af3ebd945b676afa4331cd0`

```text
blender --background --python-exit-code 1 --python scripts/blender/rebuild_ch101_cap_patch.py -- --source <restored-layout.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_cap_replacement.py -- --source <restored-layout.blend> --artifact <new-output-directory>/CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION_v001.blend
```

공유 완료: [연구용 Release](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-cap-replacement-v001),
[복원 pointer](../artifacts/CH101-latest-cap-replacement.json).
Blend·12장 렌더·report·read-me·시각 검토·거부 시험/겨드랑이 진단 **17개 payload**를
새 경로로 재다운로드해 ZIP 및 모든 파일 SHA256을 검증했다.
저장·복원 검증은 최종 의상·외형·변형 승인과 다르며 이전 pointer와 전신 기준본을 유지한다.

- tools commit: `6e953c25a1cec297c69bc91949c44575f7093e1d`
- ZIP: 26,652,278 bytes
- ZIP SHA256: `d00a40ec0afa2bad1f45bbf55e5f61b463075ce96f0d98258b82118260dc8fb5`

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-cap-replacement.json --output-dir artifacts/restored-cap-replacement
```

## 이어서 할 순서

1. 겨드랑이를 16개 설계 구역 및 course/영역 경계를 지키는 단순 disk로 나눈다.
   분기/구멍을 먼저 해소하고 넓은 지지 곡선과 실제 replacement patch를 작성한다.
   cap 미세 꺾임 제거를 전체 어깨/겨드랑이 완료로 세지 않는다.
2. 임시 몸통 clip을 실제 접합 경계로 교체하고 보류한 18 crease edge를 재판정한다.
3. 소매 공유 접합·두께 셸, 자체/몸체/장비 교차·간격·벽 두께·다방향 외형 QA.
4. 새 패널 UV/장식/베이크 → 전신 정리 → rig/weight/실제 변형 증거.
5. 기술 인테이크·사람 Gate B 이후 Unity/Android 및 CH102–105 확장.

`capMicroCreaseRemoved=true`지만 `fullUnderarmRebuilt=false`,
`majorFoldShapeRedesigned=false`, `garmentStaticQA=false`,
`deformationValidated=false`, `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`이다.
Gate B pending·Unity/production 금지를 유지한다. 새 SPAR3D/Kaggle 추론은 하지 않았다.
