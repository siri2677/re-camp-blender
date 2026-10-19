# CH101 설계 경계 보존 겨드랑이 독립 패치

2026-10-19, `feature/ch101-free-ai3d-autobuild`.

## 이번에 완료한 범위

이전 cap 교체본을 보존한 채 겨드랑이의 독립 disk 5곳을 실제로 교체했다.
영역 6/7 안의 46삼각형을 36삼각형으로 바꾸고 내부 정점 5개를 제거했다.
새 연구면은 2,699정점/5,040삼각형이며, 열린 외곽·course·재질 영역 경계
907 edge와 유지 정점 좌표는 그대로다. 이전 cap 패치도 변경하지 않는다.

44-edge 주름망의 원본 정점 45개를 cap의 vertex map과 이전 설계도 provenance로
대응시킨다. 하나의 재질 구역 안에서 내부 정점 하나와 그 주변 삼각형으로
이뤄진 단순 disk만 후보로 삼는다. 경계 차수·방향·Euler를 검사하고 원본의
course/영역 경계에 닿는 내부 정점은 제거하지 않는다.
이는 **국소 disk 분할 및 면 교체**이며 넓은 cloth 지지 곡선의 전체 재설계는 아니다.

## 선택과 거부 절차

cap에서 검증한 경계 이웃 법선 조건 동적 계획법을 사용한다.
새 disk 및 접합부가 55도 초과 꺾임을 만들거나 예측 굴곡이 감소하지 않으면 거부한다.
예측 이득 순으로 검사하되 기존 선택 disk와 면을 공유하거나 한 면 이내로
인접한 후보는 건너뛴다. 따라서 서로의 고정 외부 법선을 바꾸지 않는다.
각 후보를 누적 적용한 임시 메시에서 원본 branch chart까지의 양방향 표본,
실제 렌더 굴곡, 자체 교차·면 방향·토폴로지를 다시 검사하고 통과한 것만 채택한다.

45개 후보 정점 중 27개는 사전 거부(보호 정점 2, 안전한 삼각분할 없음 20,
예측 굴곡 감소 없음 5), 10개는 전체 오차 QA 거부, 3개는 이웃 중복으로 제외했다.
최종 채택은 5개다. 각 판단과 수치는 report 및 `selection-review.json`에 보존한다.

예를 들어 seed 713은 국소 굴곡/55도 조건과 자체 교차 검사가 통과해도
원본 chart 차이가 2.353153 mm라 거부한다. seed 1076의 역방향 차이는
3.037412 mm다. 이를 통과시키려고 1.5 mm 상한을 확대하거나 기준을 직전 단계로
초기화하지 않는다. 국소 낮은 굴곡만으로는 모델을 승인하지 않는다.

## 실제 교체 구역과 수치

seed 번호는 **직전 cap 입력 메시 기준**이다. 새 메시 번호는 report의
`keptSourceVertices`로 대응한다.

| seed | 영역 | 삼각형 | patch 및 접합부 최대 꺾임 |
| --- | --- | --- | --- |
| 900 | 7 | 14 → 12 | 83.465 → 45.591도 |
| 757 | 6 | 4 → 2 | 57.111 → 45.599도 |
| 1014 | 6 | 4 → 2 | 65.836 → 37.818도 |
| 1030 | 6 | 12 → 10 | 58.155 → 51.279도 |
| 914 | 7 | 12 → 10 | 56.410 → 52.264도 |

5개 구역의 55도 초과 edge 합은 10 → 0이다. 국소 굴곡 합은
0.1282802087 → 0.0905136374 rad²·m (29.4407% 감소),
**전체 연구면** 굴곡 합은 1.5940189477 → 1.5562523711 (2.3693% 감소)다.
전역 최대 꺾임 134.755862도는 다른 큰 겨드랑이 주름에 그대로 남는다.
이는 전신 점수나 캐릭터 외형 개선율이 아니다.

| 검증 | 결과 |
| --- | --- |
| 원본 branch chart 정/역방향 최대 표본 차이 | 1.442278 / 1.480045 mm, 기존 1.5 mm 상한 이내 |
| 정/역방향 표본 수 | 15,478 / 1,129 |
| 새 패치→직전 cap 연구면 / 제거 구간→새 연구면 표본 차이 | 1.227855 / 1.616557 mm |
| 유지 정점 / 원본 몸체 이동 | 0 / 0 |
| 보호된 외곽·course·영역 edge | 907 |
| 자체 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 연결 성분 / 열린 경계 / Euler | 1 / 2 / 0 |

1.5 mm는 **원본 branch chart**에 대한 누적 기준이다. 직전 연구면과의 역방향
차이 1.616557 mm는 별도로 공개하며, 이것을 1.5 mm 이내라고 주장하지 않는다.
선행 단계 자체가 원본과 차이가 있어 두 값의 의미가 다르다.
모든 오차는 유한 표본이며 연속 최대 오차 증명이 아니다. 자체 교차 검사는
정점을 공유하는 삼각형 쌍을 제외한다. 몸체 누적 최대 2.999919 mm / 상한 3 mm도 유지한다.

## 검토와 검증

전후 넓은 8장·반투명 구역 표시 4장·확대 와이어 전후 4장, 총 16장을 직접 확인했다.
작은 꺾임과 내부 연결은 달라지지만 큰 주름, 좁은 삼각형과 임시 몸통 clip 경계는 남는다.
반투명 복사본은 숨겨진 패치 위치를 보여주는 render-only 진단이고 저장하지 않는다.
**외형 기준본 미채택**이며 이전 upper-interface 조립본을 기본 표시한다.

원본 메시·UV·재질·가중치와 기존 12개 설계 가이드, 이전 cap 패치를 보존했다.
새 패치 외곽의 편집 가능한 곡선 5개(`UNDERARM_DISK_GUIDE_*`)를 따로 저장한다.
새 연구면과 곡선은 기본 숨김이다. 새 연구면의 UV/두께/봉제·몸체 clearance·리깅을
작성하거나 승인하지 않는다.

Blender 5.2.0 LTS CPU 검사 **12개 통과**. 실제 5개 패치 제작/원본 보존, seed·정책
provenance, 보호 정점·무변화·겹치는 disk 거부, 국소 개선만 통과한 오차 초과 후보
거부, face/vertex map·선택 이력/NaN·영역/정점/곡선 변조 거부, source 해시·잠금·
출력 덮어쓰기 방지, 이전 cap 및 기존 가이드 회귀, 저장 후 재개방/표시/UV·재질·
가중치·곡선과 16장 렌더 해시를 확인했다.
공유 utility 2개와 AI3D/Colab validator
(10 notebooks / 56 Blender scripts / 36 utilities)도 통과했다.

## 재현과 공유

[cap 입력 pointer](../artifacts/CH101-latest-cap-replacement.json)와
[이전 설계도 metadata pointer](../artifacts/CH101-latest-shoulder-deformation-layout.json)를
각각 복원해야 한다. 후자는 기존 설계 영역과 seed provenance를 확인하는 JSON 입력이다.

- cap Blend SHA256: `7ece194c1fd5d7ea3f02c46f54cf38aeaf9538403af3ebd945b676afa4331cd0`
- cap report SHA256: `47df4f246311d2eea4166216787e110d9365c8fb26677b98b182fc670f162415`
- layout report SHA256: `ed9f9e3b5e0451a190401868e230f7c0258561c4a860acc7fd5af5633527d3ea`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과: `CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION_v001.blend`
- Blend SHA256: `153bdb0528548ca587c0276d5a99eb49b823d36ed823145a2173eb0c7016a8bb`

```text
blender --background --python-exit-code 1 --python scripts/blender/rebuild_ch101_underarm_disks.py -- --source <restored-cap>/extracted/CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION_v001.blend --layout-report <restored-layout>/extracted/deformation-layout-report.json --art-root <re-camp> --output <new-directory>
blender --background --python-exit-code 1 --python tests/blender/test_underarm_disks.py -- --source <restored-cap>/extracted/CH101_BoundaryLockedCapReplacement_NOT_PRODUCTION_v001.blend --layout-report <restored-layout>/extracted/deformation-layout-report.json --artifact <new-directory>/CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION_v001.blend
```

공유 완료: [연구용 Release](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-underarm-disks-v001),
[복원 pointer](../artifacts/CH101-latest-underarm-disks.json).
Blend·16장 렌더·report·read-me·시각 검토·선택/거부 기록 **21개 payload**를 새 경로로
다운로드해 ZIP과 모든 파일 SHA256을 검증했다. 저장·복원 검증은 의상/외형/변형
승인과 다르며 이전 pointer·전신 기준본을 대체하지 않는다.

- tools commit: `a4be0f5a1016dea25fb957875fab8d7887413d61`
- ZIP: 28,672,931 bytes
- ZIP SHA256: `db9ef5c53e11a1d47b557f23e655da3b9b522d98271c51dcfcf98b5a9c3184a0`

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-underarm-disks.json --output-dir artifacts/restored-underarm-disks
```

## 이어서 할 순서

1. 남은 큰 주름과 course/영역 경계가 충돌하는 구간의 넓은 지지 곡선을 설계한다.
   단일 정점 disk 제거를 계속 반복해 전체 재제작 완료로 세지 않는다.
   원본 1.5 mm 조건 안에서의 가능 범위를 먼저 검증하고, 필요 변경이 이를 넘으면
   임의로 한도를 늘리지 않고 필요한 선택/승인 범위를 분리한다.
2. 임시 몸통 clip을 실제 접합 경계로 교체하고 보류한 18 crease edge를 재판정한다.
3. 소매 공유 접합·두께 셸과 자체/몸체/장비 교차·간격·벽 두께·다방향 외형 QA.
4. 새 UV/장식/베이크 → 전신 정리 → rig/weight/실제 변형 증거.
5. 기술 인테이크·사람 Gate B 이후에만 Unity/Android 및 CH102–105 확장.

`fullUnderarmRebuilt=false`, `majorFoldShapeRedesigned=false`,
`garmentStaticQA=false`, `deformationValidated=false`, `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`이다.
Gate B pending·Unity/production 금지, 전신 rounded-hem 기준본을 유지한다.
새 SPAR3D/Kaggle 추론은 실행하지 않았다.
