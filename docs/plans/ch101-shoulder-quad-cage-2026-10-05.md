# CH101 어깨 공유 사각 작업망

2026-10-05, `feature/ch101-free-ai3d-autobuild`.

## 완료한 내용

앞/뒤/어깨/겨드랑이 경계가 나눈 원본 4영역을 하나의 사각 작업망으로 재구성했다.
각 원본 삼각형에 edge midpoint와 face center를 추가해 같은 평면의 사각 면
3개를 만든다. 같은 원본 edge ID는 전체에서 하나의 midpoint만 가지므로
영역별 복사본 사이의 틈이 없다. 원본 정점과 주름 경계를 보존한다.

이 단계는 열린 면 topology의 제작이다. 원본 면을 세분한 구조이므로 새 외형,
주름 단순화, 규칙적인 변형용 edge flow를 완료한 것으로 세지 않는다.
많은 3-valence/고-valence 접합점이 남는다. 비교 shaded 렌더는 원본과 거의 같은
형상을 보이며 wire 렌더에서 새 사각 면과 복잡한 접합점을 확인했다.

## 거부한 균일 격자와 원인

4영역을 볼록한 원형 펼침 좌표로 만든 뒤 규칙적인 quad grid를 대응시켰다.
좌표의 삼각형·격자는 모두 양의 면적이었지만, 3D 면이 거친 원본 주름을
건너뛰면서 자체 교차와 큰 표면 차이를 만들었다.

| 영역당 격자 | 자체 교차 | 정방향 최대 표본 차이 | 역방향 최대 표본 차이 |
| --- | --- | --- | --- |
| 24×40 | 220쌍 | 3.430038 mm | 5.916744 mm |
| 48×80 | 780쌍 | 1.685731 mm | 3.026390 mm |

두 시험은 1.5 mm 표면 오차와 자체 교차 0 기준 미달로 거부했다.
단순한 밀도 증가는 해결책으로 채택하지 않는다. 실패 좌표/측정 기록은
`rejected-grid-trials.json`에 남기고 기본 24×40 사례를 회귀 검사에 포함했다.
`--structured-trial`은 실패를 재현하는 경로이며 정상 공유 결과로 저장하지 않는다.

## 통과한 작업망 검사

| 항목 | 결과 |
| --- | --- |
| 정점 / quad / 렌더 삼각형 | 2,258 / 2,079 / 4,158 |
| 영역별 quad | 453 / 663 / 486 / 477 |
| 영역 사이 공유 경계 | 88개, 각각 두 영역 면이 같은 edge를 사용 |
| 연결 성분 / 열린 경계 루프 / Euler | 1 / 2 / 0 |
| 자체 교차 / 내부 면 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 정점 출처 재구성 오차 | 0 |
| 최대 정방향 / 역방향 표본 차이 | 0.016213409 / 0.000120137 mm |
| 표면 검사 표본 수 | 10,753 / 1,129 |
| 원본 몸체 이동 | 0 |

각 사각 면이 자신의 원본 삼각형 평면에 남고, 원본 693삼각형이 정확히
3개씩 대응되는지 검사한다. 원본 정점·UV·재질·가중치와 이전 연구본을 보존한다.
기존 body 누적 2.999919 mm / 상한 3 mm는 유지한다.

자체 교차 검사는 정점을 공유하는 삼각형 쌍을 제외한다. 표면 차이는 유한 표본이며
연속 오차 상한 증명이 아니다. 몸체 표면을 따라 만든 열린 작업망이므로
`garmentStaticQA=false`이고 몸체 clearance·벽두께·봉제 통과를 주장하지 않는다.

Blender 5.2.0 LTS CPU, 신규 회귀 검사 6개 통과: 출처·공유 경계·원본 보존,
잘못된 영역/정점/경계 거부, 균일 격자 실패 거부, 저장 후 재개방·잠금·렌더 해시.
AI3D/Colab validator 통과 (10 notebooks / 51 Blender scripts / 36 utilities).
12장 before/after/wire의 정면·측면·후면·사선을 직접 검토했다.

## 재현과 이어서 쓸 파일

원본은 [shoulder branches pointer](../artifacts/CH101-latest-shoulder-branches.json)로 복원한다.

- 원본 Blend SHA256: `341074e648341a27c51290e0a29650b1297604506eb2defeec9f5010bf04577e`
- 원본 report SHA256: `487c101ee45d6884d9d959e431fcbf02334191fba65ceccb3bb3bc357110698f`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과 Blend: `CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION_v001.blend`
- 결과 SHA256: `075374b9849adb29a4162d4f020382da4a2eb929ffe4c8db71b3ff4d6afdc01a`
- 연구 메시: `CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION` (기본 숨김)

```text
blender --background --python-exit-code 1 --python scripts/blender/retopologize_ch101_shoulder_regions.py -- --source <restored-branch.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_quad_cage.py -- --source <restored-branch.blend> --artifact <new-output-directory>/CH101_FeaturePreservingShoulderQuadCage_NOT_PRODUCTION_v001.blend
```

## 남은 작업

공유 완료: [연구용 릴리즈](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-shoulder-quad-cage-v001),
[복원 pointer](../artifacts/CH101-latest-shoulder-quad-cage.json).
Blend·12장 렌더·report·read-me·visual review·실패 격자 기록 총 17개 파일을
새 경로로 재다운로드해 ZIP 및 각 payload의 SHA256을 검증했다.

- tools commit: `15568a509b606e485adb220b57b7d580b145cf23`
- ZIP: 25,820,712 bytes
- ZIP SHA256: `43877d19a3ffc029c6153cce162fb089178054fb7323487321abea99e2b23cf8`

### 이어서 제작할 순서

1. 네 영역의 주요 주름과 봉제선만 남기는 crease-aware 형상·edge flow를 설계한다.
   단순 triangle→quad 변환이나 균일 밀도 증가를 추가 품질 개선으로 세지 않는다.
   영역 사이 공유 경계와 참조 대비 이동·오차를 함께 검사한다.
2. 임시 clip 외곽을 실제 몸통 접합 경계로 설계하고 하단 소매 상단과 대응시킨다.
3. 두께 셸과 공유 접합 topology를 만든 뒤 교차·두께·간격 및 다방향 실루엣 QA를 진행한다.
4. 이후 UV/장식/베이크 → 전신 정리 → rig/변형 → 사람 Gate B 순서를 따른다.

기존 조립본과 전신 기준본을 유지한다. `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`,
Gate B pending, Unity/production 금지를 유지한다.
