# CH101 어깨 연결 topology와 실패 진단 — 2026-10-04

## 결과

통합 후속 계획을 완료/잔여/다음 단계로 갱신하고, 중단된 연결 패널 코드를 실제
실행했다. 기존 소매 상단에 새 어깨 패널이 정점을 공유하도록 작성했으나,
**교차·두께 기준 미달로 미채택**이다. 이 문서는 완성 모델이나 0.6 통과 기록이 아니다.

- 새 연결 메시: 10,368정점, 10,560면, 20,736삼각형, 한 연결 영역, Euler 0.
- 기존 소매 2,176정점 이동 0. 새 복사본의 상단 끝면 128개만 제거하고,
  안/바깥면 각각 128개 기존 경계를 공유하는 32행 패널과 상단 끝면을 연결했다.
- 비다양체/불연속 방향 edge/면적 0인 면은 0이며, 두 skin 모두 seam edge마다
  두 면이 연결된다. **이 연결성만으로 관통 없는 옷이 되지는 않는다.**
- 모든 기존 메시·UV·재질·가중치는 보존한다. 기본 화면은 이전 upper-interface
  조립본이고 새 시험 객체는 숨김이다. rounded-hem 전신 기준 pointer도 유지한다.

## 입력과 수정한 원인

입력은 10월 3일 `CH101_ClippedShoulderSeam_NOT_PRODUCTION_v001.blend`다.
SHA256 `b50dc04b7d4568a71d71da9b8840a0b5383a78083cb676cd1054cbb746bd83ca`.
동봉 report SHA256도 `03c0907d85b4cac9ccfc6740fab4adc4a42cfa36d2f628dec894bc34e72cc904`로
고정한다. art commit은 `b6c9b3128358e061eee6184230929413eba84101`이며 승인 Character/
Equipment Sheet와 Turnaround REVIEW 해시를 확인했다. Blender 5.2.0 LTS CPU 실행이다.

1. 최초 반지름 비 2의 harmonic annulus에서 730개 삼각형 중 88개 방향이 뒤집혀
   생성이 중단됐다. 무차원 parameter 바깥 반지름을 20으로 설계하고 모든 삼각형의
   방향을 검사한다. 최소 절대 parameter 면적 0.0007646776이며 물리적 모델 크기나
   이동 예산을 20배로 늘린 것이 아니다. 반지름 2 실패는 회귀 테스트로 유지한다.
2. 원 위에서 각도를 다시 보간하면 실제 원본 edge의 대응점이 달라진다. 기존
   seam map의 edge와 보간값을 parameter 공간으로 옮겨 사용하도록 수정했다.
   128개 새 grid 하단점의 원본 seam 최대 오차는 약 **0.0001202 mm**다.
3. 거친 면의 nearest-face 법선은 offset 방향을 불연속적으로 만든다. 보간한
   연속 법선과 독립 grid를 사용했지만, 곡률·접합 전이가 큰 영역에서 문제가 남았다.
   새 형상의 예산 부족을 숨기지 않고 각각의 행/열/원인을 report에 기록한다.
4. body 누적 이동 상한 3 mm(기존 최대 2.999919 mm)는 초기화하지 않는다.
   이번 body 이동은 0이다. 새 별도 패널의 source-chart 대비 범위는 **6 mm**이며
   벽 0.8 mm를 포함한다. 내부면 이동은 약 1.500–5.200 mm로 제한했다.
   예산에 걸린 점은 미충족으로 기록하고 반드시 eligibility를 false로 유지한다.

## 남은 실패와 시각 검토

| 검사 | 결과 | 판정 |
| --- | --- | --- |
| 비인접 자체 삼각형 교차 | 1,166쌍 | 실패 |
| 몸체 교차 | 4쌍 | 실패 |
| 손·세이버·부속 12객체 및 기존 rounded binding 교차 | 0쌍 | 검사 범위 내 통과 |
| 몸체 최소 표본 간격 | 0.054115 mm / 기준 >0.2 mm | 실패 |
| 새 패널 양면 표본 두께 | 0.000995–1.444823 mm / 기준 >0.2 및 <1.2 mm | 실패 |
| 점 제약 실패 기록 | 35건: 예산 부족 16, 방향 문제 2, 간격 미충족 17 | 실패; 같은 점의 여러 사유 포함 |

몸체 간격은 정점·edge 중점·삼각형 중심 52,032개 표본, 벽 두께는 양면 정점·
삼각형 중심 24,832개 표본이다. 연속 표면의 안전이나 애니메이션을 보장하지 않는다.
자체 교차에서는 정점을 하나라도 공유하는 삼각형 쌍을 제외하므로 검사 범위를
과장하지 않는다. 충돌 pair의 인덱스는 polygon이 아닌 **loop triangle** 인덱스다.

앞/옆/뒤 전후 6장, 단독 1장, 충돌 강조 1장(총 8장)을 확인했다. 흰 패널은 상단
경계를 인위적으로 자른 조각처럼 보이고, 하단 연결 주변에 접힘·주름·핀칭이 남는다.
원본 스트랩 무늬는 새 패널에 전달되지 않아 가려진다. **형상 진단용 흰 표면**으로만
취급하며 장식이나 실제 의상 패턴 완성으로 세지 않는다. 분홍 표시는 검출된 교차
삼각형의 면이며, 가려진 내부 교차도 있어 이미지에서 보이는 분홍 면만 세면 안 된다.

## 검증 결과

- Blender 회귀 5개 통과: parameter fold 거부, 정확한 seam 보간, 실제 공유 경계,
  이동 예산·원본 보존, 잘못된 source/report/frame/Gate/중복/output 거부,
  교차 실패 거부, 메타데이터가 0이어도 실제 원본 정점 이동 감지, 열린 면 감지,
  저장 후 잠금·숨김·실패 재검사와 렌더 해시 확인.
- **테스트 통과 = 실패 검출 로직 검증**, 정적 모델 QA는 `eligible=false`다.
- Python 132개 실행(131개 통과, 선택적 1개 skipped).
- AI3D/Colab validator 통과: 48 Blender scripts, 36 utilities, 10 notebooks.
- 기본 명령은 QA 실패 시 출력 전에 중단한다. 아래 명시적 진단 저장 옵션으로만
  거부 모델을 저장하며, 이 경우에도 CLI 종료 코드는 **1**이다.

## 재현·복원

```text
blender --background --python-exit-code 1 --python scripts/blender/author_ch101_connected_shoulder.py -- --source PATH/CH101_ClippedShoulderSeam_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-diagnostic --save-rejected-diagnostic
blender --background --python-exit-code 1 --python tests/blender/test_connected_shoulder.py -- --source PATH/CH101_ClippedShoulderSeam_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --artifact PATH/CH101_ConnectedShoulder_REJECTED_DIAGNOSTIC_v001.blend
```

진단 Blend SHA256: `4436c48177612dd0de663eb3d5b1522211848b5265de55b873a7ab186b1f019e`.
생성 report에 모든 source-grid 보간값, 제약 위반, 교차 pair, 행별 위치를 보관한다.
코드·계획·작은 기록은 Git, Blend·렌더·전체 report는 별도 진단 prerelease로 공유한다.

## 바로 다음 작업

1. 교차가 집중된 새 패널 0–9행의 접합 전이를 별도 설계한다. 기존 seam의 방향,
   두께, 접선과 새 패널의 면 흐름을 함께 제어한다. 단순 정점 공유와 일반 offset은
   봉제 형태를 보장하지 않는다는 것이 이번 시험에서 확인됐다.
2. 원본 절단 상자를 최종 패턴으로 쓰지 말고, 승인 참조를 기준으로 앞/뒤/겨드랑이
   경계 곡선을 나눈다. 23–32행의 외곽 주름 교차도 독립적으로 정리한다.
   report 행 집계는 여러 행에 걸친 삼각형을 중복 집계하므로 합계를 교차 수로 쓰지 않는다.
3. 새 제어 곡선으로 패널을 재작성하고 동일한 교차·두께·원본 보존·다방향 검사를
   재실행한다. 이 단계가 통과하기 전에는 UV·스트랩·리깅으로 완료 처리를 넘기지 않는다.

`adoptionAllowed=false`, `diagnosticOnly=true`, `rigBound=false`, `fullCharacterScore=null`.
`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `gateB=PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`.
