# CH101 넓은 겨드랑이 지지 곡선과 제한 조건 검토

2026-10-19, `feature/ch101-free-ai3d-autobuild`.

## 완료한 범위

[겨드랑이 독립 disk 교체](ch101-underarm-disks-2026-10-19.md) 이후의 설계 단계다.
단일 정점 star 제거를 반복하지 않고, 겨드랑이 영역 전체를 가로지르는 세 course
구간에 대해 넓은 지지 곡선을 제안했다. **이번에는 메시 면을 교체하지 않았다.**
기존 cap·5개 disk·원본 메시/UV/재질/가중치·기존 가이드와 표시 상태를 보존한다.
따라서 기존 2,699정점/5,040삼각형, 보호 edge 907개와 전역 최대 꺾임
134.755862도도 그대로다. 새 전신 점수나 SPAR3D/Kaggle 추론은 없다.

새 Blend에는 편집 가능한 `UNDERARM_SUPPORT_{0,1,2}_{source,bounded,target}`
POLY 곡선 9개를 기본 숨김으로 저장한다. 황색은 기존 course, 청록색은 제한 내
후보, 적색은 **거부된 강한 완화 비교안**이다. 적색이 승인된 외형 목표라는 뜻은 아니다.
기본 표시 조립본과 전신 rounded-hem 기준본을 대체하지 않는다.

## provenance와 설계 방법

기존 harmonic level 0.25/0.5/0.75의 겨드랑이 sector를 추출한다. 물리적인 길이
비율이나 해부학적 높이로 해석하지 않는다. 원본 layout → cap → disk 정점 map을
합성해 최신 메시의 64/60/52정점, 합 173 edge를 대응하고 좌표/연결을 확인한다.
원본 44-edge 주름망과의 위상적 교점은 각각 1/2/4개다.

각 전체 구간을 호 길이 기준 129점으로 재표본화하고 양 끝의 기존 종방향 seam
교점을 고정한다. `||Q-P||² + weight ||D²Q||²`를 푼다. weight는 선언한 129점
격자에 의존하는 무차원 조절값이며 물리적인 천의 강성/장력은 아니다.
0부터 2,097,152까지 고정된 15개 weight를 각각 검사해 총 45개 판단을 저장했다.
통과 후보 중 이산 곡률 제곱 적분이 가장 작은 안을 선택한다. 연속 최적화나 모든
가능한 디자인에 대한 최적성/불가능성 증명은 아니다.

다음 네 가지 **유한 표본** 최대 차이를 모두 1.5 mm 이내로 요구한다.

1. 후보 중심선 → 원본 branch chart.
2. 후보 중심선 → 해당 course 양옆의 최신 설계 영역.
3. 기존 course 구간 → 후보 선분.
4. 후보 중심선 → 기존 course 선분.

표본 간격은 최대 0.25 mm이며 점→선분 거리는 선분 전체에 대해 계산한다.
3/4번은 주름망의 다른 sheet로 건너가는 것을 억제하는 **추가 보수적 guide corridor**다.
이 guard의 실패를 원본 표면 1.5 mm 조건의 실패와 혼동하지 않는다.
곡선→표면 검사는 새 메시의 양방향 surface QA가 아니다. 곡선 bevel 두께도 의상
두께나 body clearance의 증거가 아니다.

## 실제 수치

| harmonic course | 선택 weight | 후보 길이 | 원본 표면 최대 차이 | 기존 구간→후보 최대 차이 |
| --- | --- | --- | --- | --- |
| 0.25 | 2 | 188.725 mm | 1.290640 mm | 1.268506 mm |
| 0.50 | 2 | 200.524 mm | 0.662065 mm | 1.233247 mm |
| 0.75 | 8 | 172.282 mm | 0.721417 mm | 1.120472 mm |

끝점 이동은 모두 0이다. 같은 영역까지의 최대 차이는 각각
0.273541/0.662059/0.721483 mm다. 후보→기존 구간은 0.808109/0.784790/0.774770 mm다.
이것은 **곡선** 수치이며 기존 연구면의 1.442278/1.480045 mm 양방향 표면 수치를
새로운 값으로 대체하지 않는다. 면 형상이 같으므로 이전 표면 QA는 출처를 달아 상속한다.

선택 weight보다 더 강한 첫 비교안 8/8/32는 원본 표면까지는 모두 1.5 mm 이내이나,
기존 course→후보가 1.544596/1.543257/1.556219 mm여서 추가 corridor guard에 거부된다.
반면 가장 강한 비교안은 원본 표면에서 22.451580/22.525949/13.002930 mm 벗어나
원본 조건 자체를 넘는다. 이를 적용하거나 한도를 확대하지 않았다.
이는 **해당 비교안**의 실패이며, 넓은 주름 재설계에 반드시 그만큼의 변위가 필요하다거나
다른 설계가 전부 불가능하다는 뜻은 아니다.

청록색 세 중심선 사이 최소 거리 하한은 6.839080/43.784638/15.193768 mm다.
점→다른 POLY 선분 최소 거리에서 표본 간격 절반을 빼는 1-Lipschitz 하한이다.
각 곡선의 비인접 선분 접촉도 따로 검사한다(1e-8 m 수치 허용오차).
이 검사는 중심선에 한정되며 봉제·의상/몸체 간격 승인은 아니다.

## 시각 검토와 검증

기존/제한 내/강한 비교안 각각 4방향, 총 12장 반투명 진단을 직접 확인했다.
청록색은 작은 꺾임을 완화하지만 여전히 큰 굴곡을 따른다. 적색은 넓게 펴지지만
표면에서 크게 떨어진다. 배경 면은 바뀌지 않았다. 전신 외형 승인으로 세지 않는다.
반투명 복사본은 render-only이며 새 Blend에 남기지 않는다.

Blender CPU 검사 범위: 45개 판단 재현, 전체 구간 provenance, 끝점 고정,
표면/영역/corridor 조건 분리, 정점 map·기록/NaN·곡선 좌표 변조 거부,
중심선 간 교차 및 자체 교차 거부, 모든 이전 메시·UV·재질·가중치·가이드/표시 보존,
파일/12장 렌더 해시, Gate 잠금, 입력 해시와 출력 덮어쓰기 방지다.
Blender 5.2.0 LTS CPU 검사 **11개 통과**(40.072초), 공유 utility 검사 **2개 통과**.
AI3D/Colab validator도 통과했다(10 notebooks / 57 Blender scripts / 36 utilities).
공유 ZIP과 17개 실제 파일을 새 경로로 다운로드해 모든 SHA256을 확인했다.
다운로드한 Blend에서도 11개 검사를 다시 실행해 통과했다(65.757초).

## 배포 기록

- [연구용 사전 Release](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-underarm-support-curves-v001).
- [복원 pointer](../artifacts/CH101-latest-underarm-support-curves.json).
- tools commit: `7b9166aafa0d990174c8caef5d884285be79b0fa`.
- Blend SHA256: `ef10dda26d6d54770b8a3f45d2919f96a39782825ad9121d93053024bc0d0930`.
- ZIP: 26,907,768 bytes; SHA256 `5618811430c0a18aa74d51f94ec142cc6511be385f0633f5118b3b49902b9df7`.
- manifest SHA256: `a83f5fd6074d38773fc17d4eaa7ad658a8a890274c692886472a3c691744dc78`.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-underarm-support-curves.json --output-dir artifacts/restored-underarm-support-curves
```

저장·복원 통과는 의상이나 Gate B 승인이 아니다. 이전 pointer들을 바꾸지 않았다.

## 재현 입력

- [underarm pointer](../artifacts/CH101-latest-underarm-disks.json): 실제 Blend와 report.
- [cap pointer](../artifacts/CH101-latest-cap-replacement.json): `cap-replacement-report.json` map.
- [layout pointer](../artifacts/CH101-latest-shoulder-deformation-layout.json): `deformation-layout-report.json` provenance.
- source Blend SHA256: `153bdb0528548ca587c0276d5a99eb49b823d36ed823145a2173eb0c7016a8bb`.
- source report SHA256: `74a762ba537fb6f1b2ee7d22cffd130ea36d427b8c689cfff431f9d8a712fa6a`.
- art commit: `b6c9b3128358e061eee6184230929413eba84101`.

```text
blender --background --python-exit-code 1 --python scripts/blender/design_ch101_underarm_support_curves.py -- --source <underarm>/extracted/CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION_v001.blend --cap-report <cap>/extracted/cap-replacement-report.json --layout-report <layout>/extracted/deformation-layout-report.json --art-root <re-camp> --output <new-directory>
blender --background --python-exit-code 1 --python tests/blender/test_underarm_support_curves.py -- --source <underarm>/extracted/CH101_DomainLockedUnderarmDisks_NOT_PRODUCTION_v001.blend --cap-report <cap>/extracted/cap-replacement-report.json --layout-report <layout>/extracted/deformation-layout-report.json --artifact <output>/CH101_BroadUnderarmSupportCurves_NOT_PRODUCTION_v001.blend
```

## 이어서 할 순서

1. 제한 내 곡선을 이용할 **넓은 multi-face replacement patch 구획/경계**를 설계한다.
   기존 cap와 5개 disk, 외곽/seam 및 영역 대응을 명시한다. 곡선 통과를 면 통과로
   바꾸어 쓰지 않고 실제 메시에서 원본 양방향 누적 1.5 mm·토폴로지·교차를 다시 검사한다.
   기존 907 edge 잠금을 조용히 해제하거나 원본 course를 덮어쓰지 않는다.
   새 course 경계로의 이동이 필요하면 변경 범위/대응을 먼저 별도 proposal로 남긴다.
2. 불가능한 패치를 통과시키기 위해 상한을 늘리지 않는다. 기존 보호 경계나 허용 오차를
   바꿔야 하는 경우 현재 허용 범위의 결과와 변경이 필요한 선택을 분리해 승인을 요청한다.
3. 임시 torso clip→실제 접합 경계, 보류한 18 crease edge 재판정.
4. 공유 소매 접합·두께·교차/벽 두께/몸체·장비 clearance → UV/장식/베이크 → 전신 정리.
5. rig/weight/실제 변형 증거 → 기술 인테이크·사람 Gate B → Unity/Android.

`geometryShapeChanged=false`, `fullUnderarmRebuilt=false`, `majorFoldShapeRedesigned=false`,
`garmentStaticQA=false`, `deformationValidated=false`, `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`이다.
몸체 누적 최대 2.999919 mm / 상한 3 mm를 초기화하지 않았다. Gate B pending,
Unity/production 금지를 유지한다.
