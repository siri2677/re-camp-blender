# CH101 어깨 경계 고정 국소 주름 정리

2026-10-05, `feature/ch101-free-ai3d-autobuild`.

## 이번에 완료한 범위

공유 사각 작업망을 복사해 경계 사이의 작은 굴곡을 실제로 보정했다.
열린 외곽, 88개 영역 공유 경계, 55도 초과 주요 주름 64개와 그 이웃을 고정한다.
703개 고정 정점은 이동 0이고, 나머지 중 1,547개 정점이 이동했다.
2,258정점/2,079quad와 영역 구분은 유지하며 원본 몸체·기존 연구본은 바꾸지 않는다.

목적함수는 렌더 삼각형 사이 각도의 제곱에 공유 edge 길이를 곱한 합이다.
quad 내부 대각선도 포함해 비평면 quad의 작은 음영 조각을 누락하지 않는다.
정점별 유한 차분 하강, 최대 0.35 mm 제안, 국소 최단 edge의 10% 제한,
backtracking과 원본 대비 총 1.45 mm 이동 상한을 적용한다. 교차/면 방향 실패가
생기면 해당 정점과 이웃을 고정하고 **원본 위치에서** 재시도한다.
이번 최종 실행은 첫 시도에서 교차 및 방향 실패 없이 통과했다.

이는 **국소 굴곡 감소**이지 전체 외형 점수, 주름 설계 완료, 변형용 재토폴로지
또는 완성 어깨가 아니다. 주요 주름과 높은/낮은 valence 접합점은 그대로다.

## 측정과 시각 검토

| 항목 | 결과 |
| --- | --- |
| 렌더 삼각형 굴곡 합 | 2.2651480605 → 1.6724863824 rad²·m, 26.1644% 감소 |
| 측정 interior triangle edges | 6,058개, quad 대각선 포함 |
| 최대 정점 이동 / 고정 정점 이동 | 1.450030 mm / 0 |
| 최대 정방향 / 역방향 표본 차이 | 1.433973 / 1.450014 mm, 상한 1.5 mm |
| 표면 차이 표본 수 | 10,753 / 1,129 |
| 비인접 면 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 원본 quad 대비 최소 face normal dot | 0.894303 |
| 최대 주요 꺾임 | 134.755862도, 변경 없음 |
| 몸체 이동 / topology 변경 | 0 / 없음 |

이동 측정의 약 0.000030 mm 초과분은 Blender float 저장 허용오차
0.0001 mm 이내다. 참조 차이는 처음 quad가 아니라 원본 branch chart에 대한
양방향 검사라서 선행 작업의 표면 차이까지 포함한다. 유한 표본이며 연속
최대 오차 증명은 아니다. 교차 검사에서 정점을 공유하는 삼각형 쌍은 제외한다.
몸체 누적 이동은 기존 2.999919 mm / 상한 3 mm를 유지하고 초기화하지 않는다.

정면·측면·후면·사선의 전후 8장을 직접 검토했다. 작은 음영은 바뀌지만 큰 주름,
각진 임시 몸통 절단선, 겨드랑이의 불규칙함이 남는다. 최종 외형 기준본으로
**미채택**한다. 이전 조립본이 기본 표시되고 새 연구 메시만 숨긴다.

초기 quad 평균 normal 목적함수 시험은 굴곡 지표가 24.99% 줄어도 작은
삼각형/별 모양 음영이 늘었다. 이를 거부하고 실제 렌더 대각선까지 측정하도록
수정했다. 실패 이유와 수치는 `rejected-quad-average-trial.json`에 남기며,
비평면 단일 quad 회귀 검사로 이 측정 누락을 검출한다.

Blender 5.2.0 LTS CPU 회귀 검사 7개 통과: 실제 보정/원본 보존, 작은 돌출면의
경계·이동 한도, 비평면 quad 대각선 측정, 변화 없는 결과 거부, 경계/정점 변조
거부, 해시/잠금 거부, 저장 후 재개방/표시/UV·재질·가중치/렌더 해시 보존.
AI3D/Colab validator 통과 (10 notebooks / 52 Blender scripts / 36 utilities).

## 재현과 공유

원본은 [공유 quad pointer](../artifacts/CH101-latest-shoulder-quad-cage.json)로 복원한다.

- source Blend SHA256: `075374b9849adb29a4162d4f020382da4a2eb929ffe4c8db71b3ff4d6afdc01a`
- source report SHA256: `7019af8733ec5591fee3711b9a583ca27d4c8377b503f88db9aff932e9f5bed8`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과: `CH101_CreaseAwareShoulderFairing_NOT_PRODUCTION_v001.blend`
- 결과 SHA256: `fda96bec01f2ddbab72c559effb7f61e8471340e9730cd34870d31847199908b`
- 새 연구 메시: `CH101_CreaseAwareShoulderFairing_NOT_PRODUCTION` (기본 숨김)

```text
blender --background --python-exit-code 1 --python scripts/blender/fair_ch101_shoulder_panels.py -- --source <restored-quad.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_crease_fairing.py -- --source <restored-quad.blend> --artifact <new-output-directory>/CH101_CreaseAwareShoulderFairing_NOT_PRODUCTION_v001.blend
```

실제 Blend·8장 렌더·report·read-me·visual review·거부 시험 요약을 버전별
GitHub prerelease로 공유한다. 배포 후 ZIP 및 payload 재다운로드 검증 결과를
이 절과 새 복원 pointer에 추가한다. 기존 pointer와 전신 rounded-hem 기준본은 유지한다.

## 이어서 할 순서

1. 큰 주름의 유지/단순화 위치와 변형용 edge flow를 명시적으로 설계한다.
   경계 고정 smoothing 반복이나 quad 변환만으로 B 완료를 대신하지 않는다.
2. 임시 clip 외곽을 실제 몸통 봉제 경계로 만들고 소매 상단과 연결 관계를 확정한다.
3. 두께 셸·공유 접합을 작성한 뒤 자체/몸체/장비 교차, 두께, 간격 및 다방향 외형 QA.
4. 이후 UV/장식/베이크 → 전신 정리 → rig/변형 → 사람 Gate B → Unity/Android.

현재 열린 무두께 연구면은 `garmentStaticQA=false`다. 몸체 clearance, 두께,
봉제, 애니메이션 승인을 주장하지 않는다. `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`,
Gate B pending, Unity/production 금지를 유지한다. 새 SPAR3D 추론은 실행하지 않았다.
