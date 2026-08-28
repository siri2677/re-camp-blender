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

1. GPU가 복구되면 CH101 Wonder3D 6-view 재사용 검사를 먼저 실행한다.
2. 재사용 가능한 결과가 없을 때만 pinned Wonder3D 설치·추론·NeuS mesh extraction을 실행한다.
3. NeuS가 완료되어도 품질 통과로 간주하지 않고, RGB foreground voxel fallback을 별도
   후보로 생성해 두 결과를 Blender refine → pre-export geometry audit → render
   evaluation → score 순서로 동일하게 비교한다.
4. 실행 전에 `quality_progress_gate.py`가 이전 score/history를 확인한다. 동일한
   `WONDER3D_NEUS_VOXEL_COMPARE_V001` 전략에서 이미 거절된 결과가 있으면 GPU 설치와
   추론을 반복하지 않고 `QUALITY_PLATEAU_SAME_STRATEGY`로 중단한다.
   다음 작업은 `PIVOT_TO_SEMANTIC_RECONSTRUCTION_OR_NEW_PROVIDER`이며, 동일 전략
   재시도는 명시적인 진단용 override가 있을 때만 허용한다.
5. `build_assisted_visual_review.py`의 rejection-only 검토를 거친 뒤에만 rank한다.
   점수 또는 Hard Gate 미달이면 `REGENERATE_REQUIRED`로 종료한다.
6. 기술 기준 통과 후보도 비교 시트에서 시각 검토하고, 보조 검토는 거절·보류만 기록한다.
7. 사람이 Gate B를 승인한 경우에만 Production Mesh 인테이크와 Unity handoff 준비로 이동한다.
8. CH101 절차가 검증되면 같은 계약으로 CH102~CH105 후보 생성을 순서대로 실행한다.
9. 실제 5인 Production Mesh handoff와 사람 승인 5개가 모인 뒤 통합 manifest를 만들고 Unity Import를 시작한다.

## 품질 정체 이후의 1회성 hybrid pivot

Wonder3D `WONDER3D_NEUS_VOXEL_COMPARE_V001`의 거절 이력이 있으므로 같은 전략을
반복하지 않는다. 새 Notebook
`notebooks/07_ch101_hybrid_quality_strategies.ipynb`는 다음 두 전략을 각각 한
번만 평가한다.

1. `TRELLIS_SINGLE_VIEW_V001`: 24576 MB 이상 VRAM, CUDA kernel, 약관 확인을
   포함한 provider preflight가 모두 PASS일 때만 실행한다.
2. `SEMANTIC_PROXY_REFERENCE_FITTED_V001`: CPU Blender에서도 실행 가능한
   reference-fitted semantic proxy를 만들고 body/face, hair, outfit,
   equipment를 별도 구조로 검사한다.

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

이 저장소에서 자동화 가능한 pre-Unity 준비는 완료됐다. 전체 프로젝트 완료는 다음 외부 결과가 모두 있을 때만 선언한다.

- CH101~CH105 각각 승인 가능한 고품질 후보 또는 Production Mesh
- 사람 Gate B 승인 기록 5개
- Production handoff 5개와 통합 manifest hash 검증
- Unity `6000.5.3f1` Import·Prefab·Play Mode PASS
- Android 실기기 설치·실행·성능 측정 PASS

현재는 위 외부 결과가 없으므로 Unity·Android 완료로 승격하지 않는다.
