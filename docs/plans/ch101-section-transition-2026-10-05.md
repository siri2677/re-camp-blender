# CH101 단면 기반 12 mm 팔 쪽 접합 전이

작성: 2026-10-05. 브랜치: `feature/ch101-free-ai3d-autobuild`.

## 결과와 범위

기존 소매 상단에서 12 mm만 연장한 연결 셸의 정적 QA를 통과했다.
이는 10월 4일 실패한 전체 어깨 패널과 **다른 제한된 범위**이며, 전체 어깨의
1,166 자체 교차가 모두 해결됐다는 의미가 아니다. 실패한 원본과 모든 이전
메시는 그대로 보존했다. 새 SPAR3D 추론이 아닌 로컬 Blender CPU 제작이다.

비교/단독 렌더 9장에는 돌출된 턱, 각진 상단, 몸통에 연결되지 않은 끝면이 남는다.
**외형 기준본으로 채택하지 않는다.** 저장 파일은 이전 upper-interface 조립본을
표시하고 새 연구 메시를 숨긴다. 전체 기준본 rounded-hem 및 기존 pointer는 유지한다.

## 구현

- 원본 절단 chart의 삼각형과 단면 평면 교차를 공유 원본 edge ID로 연결한다.
  좌표 반올림으로 경로를 연결하지 않는다.
- 32개 단면 각각에서 닫힌 팔 루프 1개와 열린 몸통 경로 1개를 구분한다.
  몸통 경로는 제외하고 각도 128개 모두 유일하게 대응되는 팔 루프만 선택한다.
- 기존 q=0.036 seam부터 q=0.048까지 12 mm, 단면 간격 0.375 mm다.
  시험에서 +14 mm부터 유일한 대응을 잃어 16 mm 확장은 실패로 거부했다.
- 기존 소매 2,176정점은 그대로 유지한다. 새 복사본에서만 기존 상단 cap을
  제거하고 안/밖 각각 128개 seam edge를 공유한다. 원본 몸체 topology에
  봉제/병합한 것은 아니다.
- 새 표면은 단면 안의 방향으로 2.0→3.5 mm clearance를 처음 2 mm에서
  smoothstep 전이하고 0.8 mm 외벽을 만든다. 전체 몸체를 향해 ray를 발사하지 않는다.
- 비평면 skin quad 8,192개의 두 대각선을 몸체 교차 수, 중심/대각선 중점 간격으로
  비교해 실제 삼각형을 명시한다. 선택 수는 4,413 / 3,779다.
  충돌이나 간격 실패를 숨긴 것이 아니라 실제 면 구성을 바꾸고 같은 QA를 반복했다.

처음 같은 국소 범위의 2 mm 일정 clearance는 몸체 교차 52쌍이었다.
추가 clearance와 대각선 선택 후 느린 6 mm 전이는 최소 표본 간격 약 0.185 mm로
여전히 실패했다. 최종 2 mm 전이는 아래 수치로 통과하며, 회귀 검사에 실패안을 남겼다.

## 검증 결과

| 항목 | 측정값 |
| --- | --- |
| 정점 / 면 / 삼각형 | 10,368 / 18,752 / 20,736 |
| 연결 성분 / 비다양체 / 면 방향 불연속 / 영면적 | 1 / 0 / 0 / 0 |
| 비인접 자체 교차 / 몸체·검사 장비 교차 | 0 / 전부 0 |
| 몸체 최소 표본 간격 | 0.210349754 mm, 60,224 표본 |
| 새 구간 표본 벽 두께 | 0.313923432–0.800050679 mm, 24,832 표본 |
| 공유 seam edge (안/밖) | 128 / 128 |
| 원본 몸체 / 기존 소매 정점 이동 | 0 / 0 |
| 새 참조 offset 최댓값 / 상한 | 4.300030 mm / 6 mm |
| 단면 평면 오차 최댓값 | 0.000170768 mm |
| 참조 재구성 오차 / 제약 실패 | 0 / 0 |

자체 교차 검사는 정점을 공유하는 삼각형 쌍을 제외한다. 간격과 두께는 유한 정적
표본이며 연속 표면 전체 또는 변형 안전성 증명이 아니다. 최소 간격은 고정 기준
0.2 mm보다 약 **0.01035 mm** 클 뿐이다. 기존 몸체 누적 최대 이동
2.999919 mm / 상한 3 mm를 초기화하지 않았다. 런타임 최적화도 하지 않았다.

- Blender 6개 테스트 통과: 단면 출처, 원본·seam 보존, 간격 미달 거부,
  모호한 확장 거부, 입력/승격 잠금, 저장 후 재개방 QA와 렌더 해시.
- Python 테스트 132개 실행: 131 통과, 선택 테스트 1개 skip.
- AI3D/Colab 패키지 validator 통과: notebook 10, Blender script 49, utility 36.
- Blender 5.2.0 LTS (`fbe6228777e7`), CPU. 테스트 fixture는 GPU 추론 증거가 아니다.

## 재현과 공유

원본은 `CH101-latest-connected-shoulder-diagnostic.json`으로 복원한다.

- 원본 Blend SHA256: `4436c48177612dd0de663eb3d5b1522211848b5265de55b873a7ab186b1f019e`
- 원본 report SHA256: `c5a908aca8c0739160093e2b00072d056497483772029b9b1475a4c059397461`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 새 Blend: `CH101_SectionGuidedShoulderEntry_NOT_PRODUCTION_v001.blend`
- 새 Blend SHA256: `0d89a0bf4f842c2debb15f896f4fb6a641c0ac7e35befe43cd1b2db5b8aced84`
- 연구 메시: `CH101_SectionGuidedShoulderEntry_NOT_PRODUCTION` (기본 숨김)

저장소 루트에서 source/art-root/output을 로컬 복원 경로로 지정한다.

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_section_transition.py -- --source <source.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_section_transition.py -- --source <source.blend> --artifact <new-output-directory>/CH101_SectionGuidedShoulderEntry_NOT_PRODUCTION_v001.blend
```

전체 단면 좌표/출처와 QA는 `section-transition-report.json`, 수동 이미지 검토
판정은 `visual-review.json`에 구분해 저장한다. 생성 시 report의
`PENDING_VISUAL_REVIEW` 상태는 자동 생성 시점 기록이며 후속 검토는 미채택이다.

## 다음 작업

공유 완료: [연구용 프리릴리즈](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-section-transition-study-v001),
복원 pointer [CH101-latest-section-transition.json](../artifacts/CH101-latest-section-transition.json).
실제 Blend·9개 렌더·report·read-me·visual review 총 13개 payload를 새 경로로
재다운로드해 ZIP 및 각 파일 SHA256을 모두 검증했다. 저장 검증은 외형 승인이 아니다.

- tools commit: `f7bb8071afb011162d2b6d61f0c6aad888c71e43`
- ZIP 크기: 27,111,771 bytes
- ZIP SHA256: `0fb40ed789e2168e4605119b630a6b9fdf133ccb8cf3549c0a93ae61061d68fe`

### 이어서 실행할 순서

1. 새 상단 링과 참조 시트에서 앞·뒤·겨드랑이–몸통 분기 제어 경계를 명시한다.
   +14 mm 이후의 모호한 원형 단면을 자동 연장하거나 미세 offset 반복으로 대체하지 않는다.
2. 돌출된 턱을 포함한 전체 어깨 패널 면 흐름과 몸통 접합 topology를 설계한다.
   기존 원본 보존, 새 영역 예산, 교차·두께 기준은 유지해 재검사한다.
3. 다방향 외형 검토 후 UV/장식/베이크, 전신 정리, rig/변형, 사람 Gate B 순으로 진행한다.

`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`adoptionAllowed=false`, `completeShoulderPanel=false`, `rigBound=false`,
`fullCharacterScore=null`, Unity/production 금지를 유지한다. 전신 0.6 통과가 아니다.
