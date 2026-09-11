# Current roster AI3D pre-Unity 실행 계획

## 현재 결론

CH101의 로컬 후보 6개는 Blender 5.2 재평가와 geometry Hard Gate를 마쳤다. 자동 점수와 Hard Gate를 함께 통과한 후보는 TripoSR 2개지만, 얼굴·헤어·의상·장비·손 품질이 승인 시트에 미달해 보조 시각 검토에서 모두 거절됐다. 최종 상태는 `REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW`이며 `selectedCandidate`는 `null`이다.

CH102~CH105는 승인 이미지 lock, 3-view crop, 캐릭터별 계약, 공용·상세 Socket 설정과 No-GPU 실행 경로까지 준비됐다. 아직 실제 AI inference 후보나 Production Mesh는 없다.

모든 현재 결과의 고정 상태는 다음과 같다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## 완료된 범위

- CH101 후보 6개, 30개 방향 렌더, SHA256 재검증
- pre-export `.blend` 기반 connected-component/loose/non-manifold/degenerate Hard Gate
- 렌더 실루엣 분리 검증과 자동 점수 제한 명시
- 상위 3개 보조 시각 검토와 Gate B 비교 시트 생성
- 최종 후보 미선택 및 Review `.blend`/Unity package 생성 금지
- CH101~CH105 단일 roster AI3D 계약과 15개 reference view 생성
- CH102·CH105 No-GPU adaptive 스모크 PASS
- CH105 Blender review rig·LOD·공용/상세 Socket alias 스모크 PASS
- 단위 테스트, AI3D validator, Colab package validator 자동화

## GPU 자동 전환

다음 명령은 GPU 상태를 확인하고 실행 경로를 분리한다.

```text
python scripts/run_adaptive_workstream.py --provider sf3d --character CH101 --art-root ../re-camp-art --output artifacts/adaptive-ch101.json
```

- GPU가 보이면 provider Notebook 실행 허용 상태와 이어서 실행할 Notebook을 기록한다.
- GPU가 없으면 무거운 설치·추론을 하지 않고 validator, 테스트, CPU reference crop, provider dry-run, Unity handoff 정적 검증을 실행한다.
- `tripo`는 GPU가 필요 없지만 API key와 credit을 사용하는 선택 경로다. 기본 무료 경로에서는 실행하지 않는다.
- 어떤 경로도 사람 Gate B를 대신 승인하거나 Unity 입력을 활성화하지 않는다.

`--character`에는 `CH101`부터 `CH105`까지 지정할 수 있다. Colab Notebook 05에서는 환경 변수 `RE_CAMP_CHARACTER_CODE`로 같은 값을 선택한다.

## 다음 실행 순서

1. `notebooks/07_ch101_hybrid_quality_strategies.ipynb`를 최신
   `feature/ch101-free-ai3d-autobuild` 브랜치에서 실행한다.
2. 먼저 GPU 노출·CUDA kernel·VRAM 24 GB·TRELLIS 약관과 entrypoint를 확인한다.
   조건이 맞지 않으면 heavyweight 설치 없이 `BLOCKED_PROVIDER_PREFLIGHT`를 남긴다.
3. V001 거절 이력은 `quality_progress_gate.py`가 차단한다. Blender가 있으면
   `UNIFIED_SEMANTIC_AUTHORING_V002`를 한 번 실행하고, primary shell voxel remesh와
   semantic component audit를 기록한다.
4. TRELLIS가 preflight를 통과해도 실제 mesh를 만들지 못하면 아직 실행하지 않은
   V001 또는 V002 semantic fallback으로 한 번만 전환한다.
5. 후보가 있으면 Blender refine → evaluate → score → geometry hard gate → strict
   visual QA → rank를 수행한다. 점수·Hard Gate·semantic 구조 중 하나라도 미달이면
   `REGENERATE_REQUIRED`로 종료하며 같은 strategy를 반복하지 않는다.
6. 자동 기준을 통과한 후보도 `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`과
   `PENDING_HUMAN_REVIEW`를 유지한다. 사람이 Gate B를 승인한 경우에만 Production
   Mesh 인테이크와 Unity handoff로 이동한다.
7. CH101 기술 검증과 사람 Gate B가 모두 끝난 뒤 동일 계약으로 CH102~CH105를 순서대로
   진행하고, 5개 승인 handoff가 모인 뒤 통합 manifest와 Unity Import을 시작한다.

## 품질 정체 이후의 1회성 hybrid pivot

Wonder3D와 V001 semantic proxy의 거절 이력이 있으므로 해당 전략을 반복하지 않는다.
새 Notebook `notebooks/07_ch101_hybrid_quality_strategies.ipynb`는 다음 경로를
quality gate에 따라 각각 최대 한 번만 평가한다.

1. `TRELLIS_SINGLE_VIEW_16GB_V002`: 원본 TRELLIS 공식 API를 16384 MB 이상
   VRAM, CUDA kernel, 약관 확인을 통과할 때만 one-shot 실행한다. 24 GB 이상
   환경에서는 `TRELLIS2_SINGLE_VIEW_V001`을 우선 검토한다.
2. `TRELLIS_SINGLE_VIEW_V001`: 24576 MB 이상 VRAM, CUDA kernel, 약관 확인을
   포함한 provider preflight가 모두 PASS일 때만 실행한다.
3. `SEMANTIC_PROXY_REFERENCE_FITTED_V001`: 과거 경로로 기록만 유지하며 거절 이력이
   있으면 재실행하지 않는다.
4. `UNIFIED_SEMANTIC_AUTHORING_V002`: CPU Blender에서 연결형 primary shell,
   semantic labels, LOD, rig, Socket placeholder를 만들고 remesh 결과를 검사한다.

두 후보는 동일한 Blender refine → evaluate → score → strict visual QA → rank
경로를 사용한다. 기준 미달이면 `REGENERATE_REQUIRED`와 원인 코드를 남기며,
재실행은 품질 Gate가 차단한다. 상세 계약과 중단 조건은
`docs/plans/ch101-hybrid-quality-improvement-plan-2026-08-28.md`에 기록한다.

## 중단 조건

- GPU quota 또는 CUDA/dependency/NeuS 실패
- provider commit, art commit, reference SHA256 불일치
- 후보 파일 누락 또는 SHA256 불일치
- geometry Hard Gate 또는 점수 기준 미달
- 얼굴·헤어·의상·장비·손의 시각 품질 거절
- 동일 strategy ID의 거절 이력(`QUALITY_PLATEAU_SAME_STRATEGY`)
- `unityInputAllowed=true` 또는 `productionPromotionAllowed=true` 입력 발견
- 실제 Production Mesh, Unity Editor, Android 기기 부재

## 완료 기준

이 저장소에서 자동화 가능한 pre-Unity 준비(V002 fallback 포함)는 완료됐다. 전체 프로젝트 완료는 다음 외부 결과가 모두 있을 때만 선언한다.

- CH101~CH105 각각 승인 가능한 고품질 후보 또는 Production Mesh
- 사람 Gate B 승인 기록 5개
- Production handoff 5개와 통합 manifest hash 검증
- Unity `6000.5.3f1` Import·Prefab·Play Mode PASS
- Android 실기기 설치·실행·성능 측정 PASS

현재는 위 외부 결과가 없으므로 Unity·Android 완료로 승격하지 않는다.
