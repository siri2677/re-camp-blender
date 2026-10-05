# CH101 어깨 둘레 경로·주름 재설계 구역

2026-10-05, `feature/ch101-free-ai3d-autobuild`.

## 이번에 완료한 범위

국소 quad 연결 정리 다음 단계로 편집 가능한 둘레 경로 3개와 주름 정책 5묶음을
작성했다. 새 연구면에 둘레 경로를 따라 **실제 공유 edge**를 추가해, 기존
앞/뒤/어깨/겨드랑이 경로 4개와 함께 연결된 설계 구역 16개로 나눴다.
단순 표시선만 얹은 것은 아니지만 **최종 quad 재토폴로지나 주름 형상 수정은 아니다**.

보존된 입구 ring 76정점을 0, 임시 몸통 clip 282정점을 1로 고정한 양의 uniform
graph-Laplacian 좌표를 구한다. 0.25/0.5/0.75 등위선을 실제 Blender 렌더
삼각형과 교차시킨다. source edge/대각선 ID와 보간값을 공유 키로 사용해 균열
없이 삼각형을 분할한다. 곡선 3개는 각각 네 종방향 경로와 한 번씩 교차한다.
스칼라 값은 물리적 길이 비율·관절 각도·승인된 해부학적 루프가 아니다.

설계도는 2,707정점/5,056삼각형이며, 새 정점 449개는 기존 삼각형 edge 위
보간점이다. 이는 구역 경계를 명시하기 위한 보조 topology 증가이지 runtime
최적화나 새로운 겉옷 셸 제작이 아니다. 원본 메시·UV·재질·가중치를 바꾸지 않았다.

## 주요 주름 정책

참조 시트와 REVIEW turnaround의 넓은 흰 겉소매 형태를 보고, 기존 조밀한
겨드랑이 주름망을 그대로 최종 패널로 옮기지 않도록 다음 가설을 작성했다.
주름·봉제 대응이 승인 시트에서 정확히 복원됐다는 뜻은 아니다.

| 표시 | 범위 | 다음 제작 지시 |
| --- | --- | --- |
| 빨강 | 44 edge, 겨드랑이 주름망 (group 193) | 분기 많은 주름을 넓은 cloth 지지 경로와 별도 replacement patch로 재설계. 입구 ring·영역 경계 유지 |
| 주황 | 18 edge, clip에 닿는 3묶음 (141/611/932) | 실제 몸통 접합 경계를 정할 때까지 현재 위치 보존. clip을 봉제선으로 승인하지 않음 |
| 초록 | 2 edge, 길이 0.384221 mm의 cap 미세 꺾임 (1874) | 향후 넓은 cap 재제작에서 제외할 후보. 이번 파일에서 제거/평탄화하지 않음 |

64개 주요 crease edge 전체에 정책을 붙이고 ID/위치/길이/이웃 면을 report에 저장했다.
독립 편집 가능한 POLY 곡선 12개(종방향 4 + 둘레 3 + 주름 정책 5)를 Blend에 보존한다.
주름 검토 렌더는 내부 선이 보이도록 render-only 반투명 복사본을 쓴다.
그 복사본과 전용 재질은 최종 Blend에 남기지 않는다.

## 검증과 검토

| 항목 | 결과 |
| --- | --- |
| 실제 공유 둘레 edge 수 | 128 / 144 / 177 |
| 종방향 교차 | 12개, 각 course에 4개 |
| 설계 구역 | 16개 모두 비어 있지 않은 단일 연결 성분 |
| 보간 정점 오차 | 측정 0, 상한 1 μm |
| harmonic 잔차 | 2.109424e-15 |
| 전체 면적 상대 차이 | 2.221679e-9 |
| 원본 삼각형별 최대 상대 면적 차이 | 0.060032%, float 보간 검사 상한 0.1% |
| 비인접 자체 교차 / 방향 불연속 / 영면적 | 0 / 0 / 0 |
| 전체 성분 / 열린 경계 / Euler | 1 / 2 / 0 |
| 원본 몸체 이동 / 주름 형상 변경 | 0 / 없음 |

면적은 원본 삼각형마다도 검사해 전체 합만 일치하는 누락/중복을 방지한다.
교차 검사에서는 정점을 공유하는 삼각형 쌍을 제외한다. 보간 QA는 원본 렌더
삼각형에 대한 설계도 보존 검사이며, 두께·몸체 clearance·봉제·변형 QA가 아니다.
이전 quad/branch chart 대비 표면 오차를 초기화하거나 상한을 완화하지 않았다.
몸체 기존 누적 최대 이동 2.999919 mm / 상한 3 mm와 전신 rounded-hem 기준본을 유지한다.

원본·course·주름 정책의 정면/측면/후면/사선 12장을 직접 확인했다.
큰 주름, 거친 faceting, 불균등한 course 간격과 꺾인 제어 곡선이 그대로 남는다.
주름 정책 렌더는 가려졌던 안쪽 주름망을 보여주는 진단이며 형상 개선 렌더가 아니다.
**외형 기준본 미채택**이고 이전 upper-interface 조립본이 기본 표시된다.
새 chart와 `DEFORMATION_LAYOUT_*` 곡선은 기본 숨김이다.

Blender 5.2.0 LTS CPU 검사 **9개 통과**. 실제 구역 제작/원본 보존, 경계 역할과
harmonic 잔차, 잘못된 경로 거부, 좌표/NaN/경계 역할/정책/교차 기록 변조 거부,
면 영역/보간값/제어 곡선 위치·정책 변조 거부, 해시/잠금/기존 출력 덮어쓰기 거부,
저장 후 복원/표시/UV·재질·가중치/가이드/12장 렌더 해시를 확인했다.
AI3D/Colab validator: 10 notebooks / 54 Blender scripts / 36 utilities 통과.

## 재현과 공유

원본은 [국소 면 연결 pointer](../artifacts/CH101-latest-shoulder-edge-flow.json)로 복원한다.

- source Blend SHA256: `4710695635be734c20d469d8c60f3bb6c94ffae6fb8fe51e9818cb8b86a2da55`
- source report SHA256: `7b8efeac91bbf493a4fbcc5663e4425767a50ae9db119ccff0526d3618c1caac`
- art commit: `b6c9b3128358e061eee6184230929413eba84101`
- 결과: `CH101_ShoulderDeformationLayout_NOT_PRODUCTION_v001.blend`
- Blend SHA256: `2eec54b4e8b0a829c94304f7ed54fb93b42eb84b469d4470353d38af39370540`

```text
blender --background --python-exit-code 1 --python scripts/blender/design_ch101_shoulder_deformation_layout.py -- --source <restored-edge-flow.blend> --art-root <re-camp> --output <new-directory>
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_deformation_layout.py -- --source <restored-edge-flow.blend> --artifact <new-directory>/CH101_ShoulderDeformationLayout_NOT_PRODUCTION_v001.blend
```

Blend·12장 렌더·report·read-me·visual review·주름 정책을 별도 연구용 Release에
보존하고, 공개 후 새 경로 다운로드와 모든 SHA256 검증 결과를 기록한다.

## 이어서 할 순서

1. 16개 구역 중 겨드랑이/어깨 cap의 넓은 지지 경로와 실제 replacement patch를
   작성한다. 가이드/구역 분할만으로 주름 형상 재설계나 변형용 retopology 완료를 세지 않는다.
2. 임시 몸통 clip 대신 실제 접합 경계를 작성하고 보류한 18 edge를 다시 판정한다.
3. 새 경로를 사용한 공유 소매 접합·두께 셸, 자체/몸체/장비 교차·간격·벽 두께 QA.
4. 새 패널 UV/장식/베이크 → 전신 정리 → rig·weight·실제 변형 증거.
5. 기술 인테이크·사람 Gate B 이후에만 Unity/Android와 CH102–105 확장.

`majorFoldShapeRedesigned=false`, `geometryShapeChanged=false`,
`deformationValidated=false`, `garmentStaticQA=false`, `adoptionAllowed=false`,
`completeShoulderPanel=false`, `rigBound=false`, `fullCharacterScore=null`이다.
Gate B pending, Unity/production 금지를 유지한다. 새 SPAR3D/Kaggle 추론은 실행하지 않았다.
