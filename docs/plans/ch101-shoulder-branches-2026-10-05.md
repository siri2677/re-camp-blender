# CH101 어깨–몸통 분기 경계 설계

2026-10-05. 브랜치 `feature/ch101-free-ai3d-autobuild`.

## 완료 범위

이전 12 mm 접합 구간의 상단 높이에서 원본 chart를 정확히 절단하고,
앞·뒤·어깨 바깥·겨드랑이의 경계 경로 4개로 면 영역 4개를 만들었다.
**원본 표면 위의 열린 설계 가설이지 새로운 의상 셸이나 몸통 봉제 결과가 아니다.**
단면을 반복 연장하지 않고 면 연결 관계를 따라 영역별 제작 기준을 마련했다.

- 원본 chart의 공유 edge ID와 보간 비율로 절단 정점을 만든다.
- 하단 루프의 방향별 극값을 시작점으로, 몸통 앞/뒤·어깨 상단·겨드랑이의
  명시적 목표 좌표에 가까운 외곽점을 끝점으로 선택한다. 좌표는 참조 시트에
  따른 설계 가설이며 정확한 재봉선 복원 또는 사람 승인 결과가 아니다.
- 원본 edge 길이와 직선 가이드 이탈을 비용으로 경로를 찾는다.
  다른 경로/경계 정점을 통과하지 못하게 하고 순서를 검토해 4개 분리 영역을 확보한다.
- 색상은 진단 영역 표시일 뿐 최종 재질이 아니다. 같은 이름의 경계 곡선과
  이전 소매 상단 링/대응선도 Blend에 저장했다.

## 검증 및 검토

| 항목 | 결과 |
| --- | --- |
| 새 참조 chart | 436정점, 693삼각형, 연결 성분 1, 경계 루프 2 |
| 서로 정점을 공유하지 않는 경로 | 4개; 앞/겨드랑이 각 11점, 뒤/어깨 각 13점 |
| 분할 영역 면 수 | 151 / 221 / 162 / 159 (전체 693면, 중복/누락 없음) |
| 원본 표면 보간 오차 / 원본 몸체 이동 | 0 / 0 |
| 비인접 참조 면 자체 교차 | 0 |
| 이전 소매 상단의 가까운 정점과 4개 anchor 간격 | 3.148315–4.004707 mm |
| Blender 회귀 검사 | 6개 통과, 저장 후 재개방 포함 |
| Python / 패키지 검사 | 132개 중 131통과·1skip; AI3D/Colab 통과 (10 notebooks / 50 Blender scripts / 36 utilities) |

Blender 5.2.0 LTS CPU에서 실행했다. Python 테스트 내 Provider 로그는 fixture이며
새 SPAR3D 추론 증거가 아니다. 원본 정점·UV·재질·가중치·이전 연구본을 보존한다.
몸체 기존 누적 2.999919 mm / 상한 3 mm는 그대로이며 예산을 초기화하지 않는다.

4장(정면·측면·후면·사선)을 직접 검토했다. 색상별 영역과 분기 경계는 확인되지만,
거친 원본 주름, 각진 경로, 떠 있는 흰 링이 남는다. 외곽은 기존 절단 envelope이며
최종 재킷 봉제 경계가 아니다. 원본 표면과 겹치는 참조 면이므로 몸체 clearance/벽두께
검사를 통과한 의상으로 취급하지 않는다. `garmentStaticQA=false`다.
자체 교차 검사는 정점을 공유하는 삼각형 쌍을 제외한다.

기존 조립본을 기본 표시하며 `CH101_ShoulderBranchChart_NOT_PRODUCTION`과
`BRANCH_GUIDE_*`는 숨긴다. 연구본을 보려면 이 객체들을 함께 표시한다.
전신 기준본, Gate B, Unity/production 금지, `rigBound=false`, `fullCharacterScore=null`,
`adoptionAllowed=false`, `completeShoulderPanel=false`를 유지한다.

## 재현

- 원본 pointer: [section-transition](../artifacts/CH101-latest-section-transition.json)
- 원본 Blend SHA256: `0d89a0bf4f842c2debb15f896f4fb6a641c0ac7e35befe43cd1b2db5b8aced84`
- 원본 report SHA256: `98540d2638a5579542ebbbdd1056eacfe7bb2825cff38bb55680a10815ca44fc`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과 Blend SHA256: `341074e648341a27c51290e0a29650b1297604506eb2defeec9f5010bf04577e`

```text
blender --background --python-exit-code 1 --python scripts/blender/design_ch101_shoulder_branches.py -- --source <restored-section-transition.blend> --art-root <re-camp> --output <new-output-directory>
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_branches.py -- --source <restored-section-transition.blend> --artifact <new-output-directory>/CH101_ShoulderBranchBoundaries_NOT_PRODUCTION_v001.blend
```

## 다음 실행

공유: [연구용 릴리즈](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-shoulder-branch-boundaries-v001),
[복원 pointer](../artifacts/CH101-latest-shoulder-branches.json).
실제 Blend·4렌더·report·read-me·visual review 총 8개 파일과 ZIP의 SHA256을
재다운로드 후 검증했다. 파일 무결성 검증이지 의상 승인이 아니다.

- tools commit: `eb02025f6b7002a8297e36c128f5a27da6b65512`
- ZIP: 21,016,432 bytes
- ZIP SHA256: `9e20782c1b820ef9f4ac60f27a9716ceb2b96d337e2f5f31f3a25bab56f82ca2`

### 제작 순서

1. 4개 face-region별로 제한된 면 재제작을 진행한다. 공유 경계 곡선을 함께 정리하되
   기존 chart 대비 위치 오차와 영역 간 경계 일치를 기록한다. 단순 색상 변경으로 완료 처리하지 않는다.
2. 임시 clip 외곽을 실제 몸통 부착 경계로 수정하고, coarse-edge 경로를 최종 주름/봉제선으로 확정한다.
3. 새 표면의 두께와 기존 소매 공유 topology를 작성한 후 같은 교차·간격·두께 QA를 실행한다.
   4개 anchor의 가까운 정점 대응을 그대로 자동 weld하지 않는다.
4. 다방향 외형 검토가 끝난 뒤 UV/장식/베이크로 넘어간다. 아직 0.6 전신 점수 통과가 아니다.
