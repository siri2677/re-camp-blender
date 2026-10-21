# CH101~CH105 품질 통과 및 Unity·Android 연결 계획

## 현재 판정

CH101의 이전 `SEMANTIC_PROXY_REFERENCE_FITTED_V001`은 overall `0.505845`와
geometry hard gate 실패로 `REGENERATE_REQUIRED`였다. 이 기록은
`quality_progress_gate.py`에 입력되어 동일 전략을 다시 실행하지 않는다.

모든 자동 후보는 다음 상태를 유지한다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## 자동 전환 순서

`notebooks/07_ch101_hybrid_quality_strategies.ipynb`는 한 번에 한 전략만
선택한다.

1. GPU·CUDA kernel·24 GB 이상 VRAM·약관 확인을 모두 통과하면
   `TRELLIS_SINGLE_VIEW_V001`을 한 번만 선택한다.
2. TRELLIS가 preflight를 통과했어도 entrypoint가 검증되지 않거나 mesh를 만들지
   못하면, 아직 실행하지 않은 semantic 경로로 한 번만 fallback한다.
3. V001 거절 이력이 있으면 `UNIFIED_SEMANTIC_AUTHORING_V002`를 선택한다.
   V002는 Blender CPU 환경에서도 실행되며, 실제 연결형 primary shell을 만들고
   body/face·hair·outfit·equipment semantic label을 보존한다.
4. 같은 `strategyId`의 거절 결과는 자동 재실행하지 않는다. 기준을 낮추거나
   실패한 전략을 반복하지 않고 새 Provider 또는 사람의 semantic authoring으로
   전환한다.

V002는 Blender object를 단순히 join하는 데서 멈추지 않는다. 겹치는 authoring
volume을 voxel remesh해 실제 연결 component를 만들며, remesh operator가 없는
Blender에서는 성공으로 기록하지 않는다. 얼굴 BlendShape와 장비·리본 Socket은
자동 추정/placeholder로만 기록하고 승인 대상으로 사용하지 않는다.

## 공통 평가 경로

모든 후보는 다음 순서를 통과해야 한다.

```text
candidate registration → Blender refine → evaluate → score
→ geometry hard gate → strict visual QA → ranking
```

자동 defer 조건은 overall `0.60`, silhouette `0.50`, appearance `0.55`, color
`0.38`, face detail `0.25`, technical `0.90`, geometry hard gate PASS 및 네
semantic component 확인을 모두 요구한다. 통과해도 결과는 사람 Gate B 검토
대기이며 Production Mesh나 Unity 입력이 아니다.

## Gate B 이후

CH101의 정면·측면·후면·3/4, 얼굴·헤어 close-up, 의상·장비 경계, A-pose,
Socket 캡처와 hash를 사람이 승인한 뒤에만 CH102~CH105를 같은 계약으로 확장한다.
5개 handoff가 모두 승인되면 Unity `6000.5.3f1`에서 Import·Prefab·LOD·Rig·Physics·
Face Driver·Play Mode를 검증한다. Android Build Support와 실제 기기가 준비된
뒤에만 설치·실행·FPS·Draw Call·Triangle·Texture Memory·CPU/GPU·발열을 측정한다.

## 실행 기록 및 차단

실행 보고서는 tools/art/provider/reference/mesh SHA256을 기록하되 API key와
Colab secret은 기록하지 않는다. 대용량 Kaggle 산출물은 Git에 저장하지 않고
보관 경로와 hash만 저장한다.

현재 로컬 자동화 완료 범위는 V002 계약·Blender builder·orchestrator fallback·
Notebook 연결·후보 metadata 보존·테스트다. 실제 후보 생성은 호환 GPU 또는
Blender 런타임이 필요하며, Unity·Android는 각각 Editor/SDK/기기가 없으면
`Blocked`로 유지한다.
