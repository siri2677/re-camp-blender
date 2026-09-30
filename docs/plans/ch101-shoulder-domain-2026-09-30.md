# CH101 어깨 면 연결·패널 경계 작업본 — 2026-09-30

## 판정

어깨·겨드랑이 영역을 실제 원본의 면 연결 그래프로 분리하고, 기존 UV와
재질을 유지한 별도 두께 있는 패널을 만들었다. **제작 범위와 경계 대응 자료는
확보했지만, 시각 품질 개선으로 채택하지 않는다.** 기본 화면에는 이전 fitted
upper sleeve interface와 원본 몸통만 표시한다. 새 패널은 숨긴 비교 객체다.

정면·측면·후면·전체 전후 및 패널 단독/경계 진단 렌더 10장을 직접 검토했다.
청록·금색 스트랩 무늬는 유지됐지만, 원본 삼각형의 톱니형 경계와 거친 주름이
남는다. 후면에서 별도 패널의 경계가 도드라진다. 이것은 완성된 어깨 패턴,
실제 봉제 연결, 매끈한 리토폴로지 또는 전체 캐릭터 품질 통과가 아니다.

`adoptionAllowed=false`, `fullCharacterScore=null`. 원본의 어두운 상단 전이를
마스크 확장으로 가리지 않았으며, 소매 연결이나 색 연결을 완료했다고 기록하지 않는다.

## 입력·보존

- 브랜치: `feature/ch101-free-ai3d-autobuild`; 시작 커밋
  `326499fb584ddee2247a0792ce4b66d162ccbc62`, 작업 트리 clean.
- 입력: `CH101_FittedUpperSleeveInterface_NOT_PRODUCTION_v001.blend`, SHA256
  `a4a9c424fc74005594321fa1d72135ecaa0fbd379452aa25e5b04b8dd9f27e24`.
- art commit: `b6c9b3128358e061eee6184230929413eba84101`.
  승인 Character Sheet와 Equipment/Turnaround REVIEW 참조 해시를 검증했다.
  Turnaround 정면·측면·후면을 직접 확인했다. REVIEW 이미지를 Production 승인으로
  승격하지 않는다.
- 실제 실행: 로컬 Blender **5.2.1 LTS**, build `9e2066aef7ef`, CPU.
  Kaggle/GPU 추론이나 유료 Provider를 사용하지 않았다.
- 원본 몸통·이전 패널·장비의 좌표/면/UV/재질/가중치 변경 0.
  기존 48-정점 스트립 및 9월 23일 기준 누적 변위 제한은 유지한다.
  새 패널 오프셋은 별도 형상이며 원본 변위 예산을 갱신하는 것이 아니다.

## 구현과 범위

`build_ch101_shoulder_domain.py`는 원형 ray extrusion을 +36 mm 위로 연장하지 않는다.
고정 world envelope와 signed hem >42 mm는 **탐색용 후보 필터**이고,
실제 face/edge adjacency로 하나의 연결된 영역과 단순 경계를 확인한다.
이는 참조에서 회수한 정확한 봉제선이나 semantic garment segmentation이 아니다.
기하가 달라지거나 분리/비다양체/잘못된 경계가 나오면 거부한다.

- 연결된 원본 506개 삼각형 / 297개 정점 / Euler 0.
- 경계: 소매 대응 루프 20개 정점, 어깨·앞뒤·겨드랑이 perimeter 68개 정점.
- 별도 안팎 면과 88개 끝벽을 생성한다: 594개 정점 / 1,100개 면 / 1,188개 삼각형.
- 원본의 UV 4개(`UVMap`, `StudyUV`, `SleeveTrimStudy`, `UpperPatchBakeUV`),
  point shader 속성과 재질 참조를 전달한다. UV corner 오차 0.
- 기존 스트랩은 **텍스처에 그려진 무늬**다. 별도 스트랩 메시를 복구한 것이 아니다.
  끝벽 UV는 미작성이며 새로운 bake를 수행하지 않는다.
- 두 겹의 대응 정점 간 이동 방향 오프셋: 내부 1.0 mm, 외부 1.8 mm.
  정점 쌍 거리 0.8 mm는 연속적인 법선 두께 보장이 아니다.
- 하단 경계에서 기존 소매 상단 128개 edge segment까지 nearest 대응을 기록한다.
  측정 gap **1.014088–29.405193 mm**. 일대일 봉제 대응이 아니고 큰 틈이 남는다.
  이 값이 연결 가능성을 증명하지 않으므로 자동 weld하지 않는다.

## 오류 원인 및 수정

`diagnosing-bugs` 절차로 실제 소스 테스트에서 self crossing **10 != 0**을 재현했다.
테스트 함수 실행은 약 0.25초였다. 두 삼각형만 남긴 작은 BVH에서도 실제
교차가 유지됐다. 위치는 매우 짧은 원본 모서리가 모인 하단/상단 두 영역이었다.

순서대로 세 가설을 세웠다: 짧은 면에서 서로 다른 miter 방향으로 인한 뒤집힘,
안팎 벽 오프셋 길이 문제, 끝벽의 삼각분할 문제. 2 mm 미만 연결 모서리의
정점 그룹에 동일 miter를 사용하는 한 변수 변경으로 교차가 0이 됐다.
원본 정점 삭제/병합이나 몸통 이동은 필요 없었다. 그룹 직경 4 mm 초과는 거부한다.

공유 miter를 그대로 두면 급한 주름에서 sampled wall 최대 2.059541 mm로
1.2 mm 상한을 넘었다. 두 번째 회귀 테스트를 먼저 실패시킨 뒤 방향을
정규화해 paired distance 0.8 mm를 유지했다. 샘플 결과는 아래 범위를 통과한다.
교차/벽/틈 기준을 낮추지 않았다. 임시 진단 스크립트는 제거했고 검사 이미지와
이전 실패/실험 산출물은 ignored artifacts에 보존했다.

## 검증

| 항목 | 결과 |
| --- | --- |
| 닫힌 연결 성분 / Euler | 1 / 0 |
| 비다양체 / winding / 면적 오류 | 0 / 0 / 0 |
| 비인접 self/body/equipment/기존 소매 교차 | 0 |
| 최소 sampled body gap | 0.320829 mm, 3,476 samples |
| sampled opposing wall | 0.225586–0.800079 mm, 1,606 samples |
| 대응 정점 UV corner 오차 | 0 |
| 원본 몸통 이동 / 삭제 | 0 / 0 |

기하 테스트는 shared-vertex self pair를 제외한 표면 교차와 유한 샘플이다.
연속 충돌, solid containment, cloth simulation, 동작 안전성을 증명하지 않는다.
이전 cuff가 원본과 분리된 상태도 변하지 않는다.

검증 명령:

```text
blender --background --python-exit-code 1 --python scripts/blender/build_ch101_shoulder_domain.py -- --source PATH/CH101_FittedUpperSleeveInterface_NOT_PRODUCTION_v001.blend --art-root PATH/re-camp-art --output PATH/fresh-shoulder-domain
blender --background --python-exit-code 1 --python tests/blender/test_shoulder_domain.py -- --source PATH/CH101_FittedUpperSleeveInterface_NOT_PRODUCTION_v001.blend --artifact PATH/CH101_ShoulderFaceGraphDomain_NOT_PRODUCTION_v001.blend
```

7개 Blender 테스트: 실제 교차, sampled gap/wall, 원본 보존·UV/material/속성 전달,
Gate/hash/frame/output/중복 거부, 열린 벽 거부, 몸통 관통 거부,
저장 후 원본/기본 표시/Gate/렌더 해시 검증.
Python unittest **132개 PASS**. AI3D/Colab validator **PASS**(10 notebooks,
46 Blender scripts, 36 utilities). Python compile 및 `git diff --check` PASS.
Optional source-tree 정적 검사는 환경변수 미설정으로 skipped이며,
실제 Blender 실행에서는 source/art/reference 해시를 별도로 검증했다.

최종 저장 파일 SHA256:
`e8faa8b846b838bfb24164ee6d19b89384dedc05371346e213bd160da001ad67`.

## 다음 단계 — 같은 추출/오프셋을 반복하지 않는다

1. 이 face graph는 **참조 표면과 경계 대응 자료**로만 사용한다. 기본 작업본은
   기존 upper-interface이다. 새 비교 패널로 전체 baseline을 덮어쓰지 않는다.
2. centroid selection의 톱니형 둘레 대신, 명시적인 clip/intersection 경계와
   앞/뒤/겨드랑이 패널 곡선을 설계한다. 20점 하단과 128점 소매 경계를
   직접 weld하지 말고 먼저 공통 seam parameter와 간격 조건을 확립한다.
3. 새 연결 panel topology를 작성하고 바깥쪽 주름을 제어한다. 원본 surface를
   그대로 offset하거나 같은 smoothing을 반복하는 것은 다음 전략이 아니다.
4. 새 geometry에서 장식 스트랩과 흰색 바탕의 경계를 실제로 분리하거나
   출처가 검증된 UV/material 전달로 유지한다. 마스크 확장으로 가리지 않는다.
5. 연결·실루엣·두께·교차 검증과 전후 시각 판정이 먼저다. 그 후에 UV/bake 및
   deformation을 별도 검증한다. 얼굴·헤어·남은 의상·production rig는 미완성이다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
rigBound: false
fullCharacterScore: null
```

사람 Gate B, CH102~CH105, Unity·Android는 자동 완료 처리하지 않는다.

## 결과 보관

산출물: 별도 숨긴 비교 패널을 포함한 Blend, 전후/단독/경계 진단 10장,
face IDs·UV·seam 대응·기하 검증 report. Git에는 코드·계획·작은 기록만 저장하고
모델·렌더는 GitHub prerelease에 보관한다. 게시 후 ZIP과 모든 payload를 새로
다운로드하여 SHA256을 검증한다. 기존 release와 rollback pointer는 보존한다.

## 게시·복원 검증 완료

[어깨 경계 자료 v001 prerelease](https://github.com/siri2677/re-camp-blender/releases/tag/ch101-shoulder-domain-study-v001)
게시 완료. 파일·전후 10장·report·read-me·판정 JSON을 포함한 ZIP과
**14개 payload 전체를 새로 다운로드하여 SHA256 PASS**를 확인했다.
단독 경계/후면/전체 preview도 별도 첨부했다. Release 제목과 notes에
`NOT ADOPTED / NOT PRODUCTION`을 명시했다.

- Tools commit: `6d2e3d89c5cc7987788f816597cc36637abffbe3`.
- ZIP: 25,938,705 bytes.
- ZIP SHA256: `95457321e8f590338560390ef6cc1a6daa0f12d38fa083c7cc03cba1987abb0b`.
- 복원 pointer: `docs/artifacts/CH101-latest-shoulder-domain.json`.

```text
python scripts/ai3d/review_artifact_release.py fetch --pointer docs/artifacts/CH101-latest-shoulder-domain.json --output-dir artifacts/restored-shoulder-domain
```
