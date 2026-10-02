# CH101 어깨 절단 경계와 소매 대응 — 2026-10-03

## 결과와 적용 범위

다른 환경의 새 커밋 10개를 fast-forward로 반영했다. 시작 커밋은 `bbe4805`이며,
최신 shoulder-domain 릴리즈의 ZIP과 14개 payload를 복원·검증했다.
최신 계획의 명시적 절단 경계와 공통 seam parameter 단계를 구현했다.

원본 삼각형 전체를 centroid로 선택하던 톱니형 경계를, 원본 삼각형과
명시적인 절단면의 교차로 바꿨다. 4개 UV 레이어와 재질·점 속성을 원본
삼각형의 barycentric 좌표로 보간하고 각 면의 출처를 기록한다.
새 메시의 하단 34점 경계를 기존 소매 상단 128개 지점과 같은 hand angle로
대응시켰다. 128개 각도 모두 단일 교차점과 유일한 소매 정점을 가진다.

이 결과는 **원본 표면 위에 놓인 열린 참조 패널**이다. 새 옷의 두께나
붙인 접합부는 아직 없다. 기본 표시에는 이전 upper-interface 조립본을
유지하며 참조 패널은 숨겨서 저장한다. 전후 단독 이미지에서 톱니형 외곽은
줄었지만 원본의 거친 주름과 투영 무늬는 남아 있다.

## 입력과 구성

- 입력 `CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION_v001.blend` SHA256:
  `e8faa8b846b838bfb24164ee6d19b89384dedc05371346e213bd160da001ad67`.
- art commit `b6c9b3128358e061eee6184230929413eba84101`, 승인 Character Sheet와
  Equipment/Turnaround REVIEW 참조 해시 검증. 로컬 Blender 5.2.0 LTS CPU 실행.
- 클립 영역(m): X [-.265,-.085], Y [-.115,.115], Z [1.09,1.31].
  이는 **작업용 경계 가설**이며 승인된 재봉 패턴이나 semantic 분할이 아니다.
  이전 탐색 필터의 하단 Z=1.11 대신 1.09를 사용해 q=.036 소매 단면 전체를 포함한다.
- 하단 절단면: `handHeight - .245 - .15 * handU = .036` m.
  기존 upper-interface의 마지막 행과 동일한 signed plane이다.
- 450정점, 644면, 730삼각형; 한 연결 영역, Euler 0, 경계 루프 2개(136점/34점).
  열린 chart이므로 경계 edge가 존재하며 닫힌 solid 조건을 적용하지 않는다.
- 위치 1µm 버킷으로 공유 clip 정점을 연결하되 원본 면 보간 좌표와의 실제 오차를
  1µm 미만으로 검증한다. 기존 몸체의 정점 이동 0, 숨긴 이전 패널·UV·재질·장비·
  가중치·이미지 보존. 원본 누적 변위 예산도 유지한다.

## 대응 간격 해석

공통 hand angle `k/128`에서 절단 폴리라인과 소매 바깥 행을 대응한다.
각도 순서와 signed plane이 어긋난 소매는 거부한다. 대응 지점 및 chart edge,
edge 보간값, 소매 vertex ID를 report에 저장한다.

간격은 **2.799907–2.800113 mm**다. 기존 소매 바깥면의 ray 방향 여유
2.0 mm와 벽 0.8 mm를 반영하는 값이다. 표면 법선 간격, 봉제 상태 또는
애니메이션 안정성을 증명하지 않는다. 이전 1.014–29.405 mm 값은 다른 경계와
nearest 대응으로 측정됐으므로 이번 수치와 직접적인 개선율을 비교하지 않는다.
`automaticWeldAllowed=false`, `sewnOrWelded=false`를 유지한다.

## 검증과 시각 판정

- 원본 삼각형 보간 좌표와 최대 차이 **0.0001204 mm**, UV corner 오차 **0**.
- 절단면 조건 위반 최대 **0.0000858 mm**, 하단 plane 오차 최대 **0.0000926 mm**.
- 면적 0인 면과 비인접 삼각형 자체 교차 **0**. 공유 정점 쌍은 교차 검사에서 제외한다.
- 새 chart는 원본 표면과 겹치는 참조 자료여서 몸체 clearance 검사를 의상 승인으로
  사용하지 않는다. 실제 옷 두께·몸체/장비 교차·변형 검증은 새 패널 제작 시 수행한다.
- Blender 5개 검사 통과: 평면 교차/보간, 원본 보존, UV·좌표 변조 거부,
  소매 parameter 변조 거부, 잘못된 hash/frame/Gate/output 거부, 저장 후 재검증.
- Python 132개 실행: 131개 통과, 선택적 1개 skipped. AI3D/Colab validator 통과
  (47 Blender scripts, 36 utilities, 10 notebooks). source-tree art 정적 검사도 통과.
- 단독 앞/옆/뒤 전후 6장과 외곽·seam 진단 2장, 총 8장 확인.
  청록선은 chart/source 경계, 금색선은 소매 바깥면, 분홍선은 16개 간격 표시다.
  곡선 표시의 굵기는 진단용이며 접합 메시가 아니다.

판정: `CLEANER_CLIP_BOUNDARY_AND_ORDERED_SEAM_MAP_USABLE_FOR_AUTHORING`.
실루엣 톱니 제거와 대응 기준 확보는 진전이지만 전체 의상 외형은 미통과다.
chart와 이전 두께 셸은 서로 다른 제작물이며 단독 이미지 비교를 두께 개선으로
해석하지 않는다. 스트랩은 원본 텍스처 무늬로 보존됐으며 별도 메시가 아니다.

## 재현과 다음 작업

```text
blender --background --python-exit-code 1 --python scripts/blender/clip_ch101_shoulder_seam.py -- --source PATH/CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp --output PATH/fresh-output
blender --background --python-exit-code 1 --python tests/blender/test_clipped_shoulder_seam.py -- --source PATH/CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_ClippedShoulderSeam_NOT_PRODUCTION_v001.blend
```

다음은 이 공통 parameter를 사용해 **새 연결 패널 topology**를 설계하는 단계다.
앞/뒤/겨드랑이 방향의 패널 곡선과 주름을 제어하고, 대응한 소매 루프에서
어깨 둘레로 분기시켜야 한다. chart를 그대로 다시 offset하거나 몸체/소매를
자동 weld하는 방식으로 연결 완료를 대신하지 않는다. 이후 새 패널의 실제
두께·교차·UV 전달을 검증하고 전후 외형을 판정한다.

`adoptionAllowed=false`, `rigBound=false`, `fullCharacterScore=null`.
`sourceStatus=AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `gateB=PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`, `productionPromotionAllowed=false`.

코드·계획·작은 기록은 Git, 실제 Blend·렌더·전체 correspondence report는
별도 prerelease에 보관한다. 이전 릴리즈와 전체 캐릭터 기준 포인터는 보존한다.

## 게시·복원 확인

[절단 경계와 소매 대응 v001 릴리즈](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-clipped-shoulder-seam-study-v001)
게시 완료. ZIP과 **12개 payload**를 새로 다운로드해 SHA256을 검증했다.

- Tools commit `f9183e3409460ba134b142ce52c29669368d9ca0`.
- 실제 Blend SHA256 `b50dc04b7d4568a71d71da9b8840a0b5383a78083cb676cd1054cbb746bd83ca`.
- ZIP 22,410,290 bytes, SHA256
  `58f220dfb30f94802f11300dcb5a0bf8dd2126c8629ef0495a77142a678e9977`.
- 복원 pointer `docs/artifacts/CH101-latest-clipped-shoulder-seam.json`.
- 원본과 rollback은 `CH101-latest-shoulder-domain.json`, 기본 표시 조립본은
  `CH101-latest-upper-interface.json`로 유지한다.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-clipped-shoulder-seam.json --output-dir artifacts/restored-clipped-shoulder-seam
```
