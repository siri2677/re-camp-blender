# CH101 AI 3D 실행 기록

이 디렉터리는 Colab에서 생성된 대용량 모델 파일을 저장하지 않고, 이후 실행과
판정을 재현하는 데 필요한 메타데이터만 Git으로 추적한다.

기록에 포함하는 항목:

- 고정된 art/tools commit
- Provider, 시도 번호, 입력 방향, foreground ratio
- 후보 SHA256과 평가 점수
- Blender 보정 mode와 material fallback 여부
- `sourceStatus`, `gateB`, `unityInputAllowed`, `productionPromotionAllowed`
- Colab 세션 산출물의 임시 경로와 보관 방식

실제 T4 실행 순서와 결과는
`2026-08-19-colab-t4-runtime.md`에, 기계 판독용 요약은 JSON 실행 기록에 보관한다.
점수 미달 원인과 이번 보정 내용은 `2026-08-19-score-root-cause.md`에 보관한다.

2026-09-02에는 기존 Wonder3D·semantic V001~V003 전략의 반복을 막고 다음 무료
Provider를 준비하기 위해 공식 Microsoft TRELLIS.2 경로를 추가했다. 24 GB 이상
NVIDIA GPU, CUDA kernel, Linux 및 별도 약관 확인이 모두 필요하므로 현재 실행은
`BLOCKED_PROVIDER_PREFLIGHT`이며, 실제 추론·mesh·점수는 아직 생성하지 않았다.
고정 commit·공식 Python API·설정 명령·게이트 상태는
`2026-09-02-trellis2-preflight-pivot-v001.json`과
`docs/plans/ch101-trellis2-quality-pivot-2026-09-02.md`에 보관한다.

TRELLIS.2는 필수가 아니므로 16 GB-class 런타임을 위한 별도 원본 TRELLIS
fallback도 준비했다. `TRELLIS_SINGLE_VIEW_16GB_V002`는 공식
`TrellisImageTo3DPipeline` API와 고정 commit을 사용하고, 단일 GPU의 실제
VRAM이 16384 MB 이상이며 `RE_CAMP_TRELLIS16_LICENSE_ACK=1`과 명시적인
`RE_CAMP_TRELLIS16_SETUP_COMMAND`가 있을 때만 one-shot 실행한다. 현재 로컬은
GPU가 없으므로 이 경로도 실행되지 않았고, 후보·점수·Alpha Review 통과를 주장하지
않는다. 상세 계획은 `docs/plans/ch101-trellis16-fallback-plan-2026-09-02.md`에
보관한다.
Workbench→Eevee 색상 렌더 재검증 결과는 `2026-08-19-color-render-rerun.json`에 보관한다.
새 Colab T4에서 Provider fallback부터 3회 후보 생성·평가까지 자동 실행한 결과는
`2026-08-19-colab-t4-automatic-run.json`에 보관한다.
최신 진단 재실행의 SF3D gated-model 오류, InstantMesh `huggingface_hub` 호환성 오류,
TripoSR 재평가 결과는 `2026-08-19-colab-t4-provider-diagnostics.json`에 보관한다.
InstantMesh 상한 버전 보정 전후의 smoke test와 provider 실행 결과는
`2026-08-19-colab-t4-provider-compatibility-rerun.json`에 보관한다.
최신 상한 버전 재실행에서 확인된 `diffusers==0.20.2`의 `cached_download` 오류와
격리 shim 보정 내용은 `2026-08-19-colab-t4-provider-compatibility-rerun-v002.json`에
보관한다.
JAX 레거시 심볼 보정까지 포함한 최신 T4 실행에서 InstantMesh가 실제 추론 단계에
진입했지만 15GB CUDA 할당 요청으로 OOM 되었고, TripoSR 세 후보가 다시
`0.452120`, `0.451603`, `0.463577`로 기준 미달한 결과는
`2026-08-19-colab-t4-provider-compatibility-rerun-v003.json`에 보관한다.
T4-safe base 프로파일과 4-view 설정으로 InstantMesh가 OOM 없이 front/right/back
세 후보를 생성했지만, 시도 번호 보존 결함을 수정한 재평가에서도 최고 점수
`0.461022`로 기준 미달한 결과와 원본 OBJ·manifest SHA256은
`2026-08-19-colab-t4-instantmesh-base-rerun-v001.json`에 보관한다.
현재 품질 병목을 해결하기 위한 무료 연구 후보 Wonder3D의 멀티뷰 구조·라이선스·
T4 실행 전제와 다음 검증 명령은
`2026-08-20-free-multiview-provider-feasibility-v001.json`에 보관한다.
실행 가능한 Colab Notebook과 Wonder3D 후보 등록/후처리 래퍼도 같은 기록의
`repositoryAutomation` 항목으로 고정한다.
GPU 사용 불가 상태에서 실행한 art 연결/CI 모드의 최신 정적 검증 결과는 각각
`2026-08-20-no-gpu-workstream-v001.json`과
`2026-08-20-no-gpu-ci-mode-v001.json`에 보관한다.
Provider별 GPU preflight와 Wonder3D repository/참조 해시/실행 명령 dry-run 결과는
`2026-08-20-no-gpu-preflight-wonder3d-dry-run-v001.json`에 보관한다.
No-GPU runner가 다섯 Provider preflight와 정적 검증을 통합 실행한 결과는
`2026-08-20-no-gpu-runner-provider-preflight-v001.json`에 보관한다.
art 저장소 연결 상태에서 reference crop, Tripo dry-run, Unity handoff까지 포함한
최신 전체 실행 결과는 `2026-08-20-no-gpu-runner-art-connected-v001.json`에 보관한다.
Wonder3D 6-view 재사용 gate, 강제 재생성 flag, hash/commit/file 검증과 28개 테스트
결과는 `2026-08-20-wonder3d-reuse-gate-validation-v001.json`에 보관한다.
최신 Colab GPU 연결 재시도에서 확인한 사용량 제한 차단과 CPU fallback 미선택 결과는
`2026-08-20-wonder3d-colab-gpu-retry-v001.json`에 보관한다.
다운로드된 전체 후보 6개의 상하 반전 원인 수정, Blender 5.2 재보정·30개 렌더 평가,
최종 순위, Review 전용 Blend의 LOD·Rig·Socket·가중치 감사, 시각 거절 권고는
`2026-08-20-complete-local-candidate-evaluation-v001.json`에 보관한다.
geometry Hard Gate를 적용해 오래된 자동 선택을 다시 검증하고, 상위 후보의 보조 시각
검토를 거절 전용 overlay로 적용한 최종 기계 판정은
`2026-08-20-final-hard-gated-candidate-evaluation-v002.json`에 보관한다. 최종 상태는
`REGENERATE_REQUIRED_AFTER_ASSISTED_VISUAL_REVIEW`이며 `selectedCandidate`는 `null`이다.
비교 이미지는 `assets/CH101_GateB_ContactSheet_NOT_APPROVED_v001.png`에 보관하며,
이는 사람 Gate B 승인서가 아니다.
2026-08-21 Kaggle P100 재평가에서는 TripoSR 기존 후보 3개를 재사용하고, CH101 후보 03을
EEVEE로 재평가해 overall `0.523413`으로 자동 기준을 통과시켰다. Gate B 검토 패키지와
아카이브를 생성했지만 사람 승인 전이므로 `GATE_B_REVIEW_PACKAGE_READY_NOT_APPROVED`와
모든 Unity·Production gate false를 유지한다. 상세 실행 기록은
`2026-08-21-kaggle-p100-triposr-eevee-gate-b-v015.json`에 보관한다.

같은 날 Wonder3D P100 재시도에서는 최신 attention·RGBA·checkout 보정까지 반영하고 GPU도
확인했지만, provider가 `/usr/local/bin/accelerate`에서 별도 Python 환경의
`huggingface_hub`를 읽어 `split_torch_state_dict_into_shards` import 단계에서 중단됐다.
6-view·mesh·Review 산출물은 만들지 않았으며, 실패 기록은
`2026-08-21-kaggle-wonder3d-p100-blocked-v018.json`에 보관한다. 이후 provider 실행을
Notebook의 동일 `sys.executable`로 고정한 `c5ea2ae`를 추가했으며, Kaggle 재실행 전까지
상태는 `BLOCKED_PROVIDER_INFERENCE_FAILED`로 유지한다.

2026-08-24 새 Kaggle 세션에서는 P100이 보였지만 PyTorch `2.10.0+cu128`의 커널 목록이
`sm_70` 이상이고 P100은 `sm_60`이라 실제 CUDA 커널을 실행할 수 없었다. 기존 preflight가
이를 GPU 준비 상태로 잘못 허용한 것을 확인해 `BLOCKED_GPU_UNSUPPORTED`로 분류하고 No-GPU
작업으로 자동 전환하도록 보강했다. 해당 관찰과 산출물 없음은
`2026-08-24-kaggle-p100-unsupported-torch-v019.json`에 보관한다.

같은 날 Kaggle T4 x2 호환 런타임에서는 preflight와 Wonder3D 실제 6-view 추론이
성공했다. `sm_75`, `torchKernelSupportsDevice=true`, reference SHA256 일치,
6개 azimuth 생성까지 확인했지만, NeuS는 Python 3.12·입력 디렉터리·Hub/Transformers·
onnxruntime·xformers 호환 문제를 단계적으로 통과한 뒤에도 학습/mesh validation이
세션 시간 안에 끝나지 않아 `BLOCKED_NEUS_RUNTIME_TOO_SLOW`로 기록했다. mesh·candidate·
Review Blend·Unity package는 생성하지 않았고 모든 gate는 false다. 상세 기록은
`2026-08-24-kaggle-t4-wonder3d-multiview-v020.json`에 보관한다.

재현을 위해 Notebook에는 T4 호환 dependency pin, Python 3.12 legacy Hub shim,
PyTorch attention fallback, NeuS flat-input staging, worker 제한과 `exp/neus/<case>`
mesh 수집을 반영했다.

같은 T4 세션에서 NeuS를 짧은 검증 프로파일로 재개해 실제 GLB mesh와 후보 manifest를
생성했다. Blender 정규화·4방향/3/4 평가 렌더·누락 `pos_y` 보정 렌더까지 완료했으며,
최종 overall `0.496221`로 `0.50` 기준에 미달했다. Appearance `0.054322`, color
`0.151526`, face detail `0.001466` 및 triangle budget 초과가 함께 확인되어 상태는
`REGENERATE_REQUIRED`다. 사람 Gate B, Production, Unity 입력은 계속 잠금이며 상세
기록은 `2026-08-24-kaggle-t4-wonder3d-neus-candidate-v021.json`에 보관한다.
Notebook은 `RE_CAMP_NEUS_END_ITER`, 저장/검증 주기 환경변수로 NeuS 재개 프로파일을
재현할 수 있도록 보강했다.

이전 `0.523413`과 현재 `0.496221`은 동일 후보의 하락이 아니다. 전자는 TripoSR 후보
03이고 후자는 Wonder3D NeuS 후보이며, 참조 manifest SHA256·도구 커밋·렌더 환경·얼굴/
재질 구성이 모두 다르다. 따라서 두 점수는 직접 비교하지 않고, 상세 provenance 비교는
`2026-08-24-score-comparison-audit-v022.json`에 보관한다.

같은 날 현재 art reference로 TripoSR를 다시 3회 평가했다. foreground ratio `0.85`,
`0.80`, `0.98`의 overall은 각각 `0.455933`, `0.493954`, `0.516883`이었고, 최고
후보도 color `0.147429`가 최소 `0.20`에 미달해 `REGENERATE_REQUIRED`다. 이번 실행은
T4·Blender Workbench였으며, 이전 `0.523413`은 P100·Blender EEVEE였으므로 단순한
모델 품질 하락으로 해석하지 않는다. 최고 후보의 EEVEE 통제 재평가는 Blender glTF
importer 오류로 리포트가 생성되지 않아 점수에 반영하지 않았다. 현재 참조·Provider·후보
SHA256과 세부 점수는 `2026-08-24-kaggle-t4-triposr-current-reference-v023.json`에
보관한다. 모든 Production·Gate B·Unity gate는 계속 잠금이다.

이후 동일한 normalized Blend를 재사용해 EEVEE로 통제 재평가했다. 같은 후보의 Workbench
점수 `0.516883`이 EEVEE에서 `0.529061`로 올라갔고, color `0.300492`와 appearance
`0.540615`도 최소 기준을 통과했다. 따라서 현재 CH101은 자동 `AUTO_REVIEW_CANDIDATE`
및 Gate B 검토 패키지 생성 단계까지 도달했지만, 이는 사람 승인이나 Production 승격이
아니다. 검토 패키지의 상태는 `GATE_B_REVIEW_PACKAGE_READY_NOT_APPROVED`이며, 사람
결정은 `PENDING_HUMAN_REVIEW`, Unity 입력은 false다. EEVEE 통제 결과·후보/패키지
SHA256은 `2026-08-24-kaggle-t4-triposr-eevee-controlled-v024.json`에 보관한다.

`.blend`, `.glb`, 렌더 PNG, ZIP은 기본적으로 `.gitignore` 대상이다. 세션이 끝난 뒤에도
바이너리를 보관해야 할 때는 GitHub Release 또는 Git LFS를 사용하고, 해당 파일의
SHA256과 다운로드 위치를 이 디렉터리의 실행 기록에 추가한다. 기록 파일에는 API key,
Hugging Face token, Colab secret을 저장하지 않는다.

Blender 3.0.1이 NeuS가 생성한 유효한 GLB를 가져오지 못하는 경우를 위해
`scripts/ai3d/convert_glb_to_obj.py`가 원본 GLB를 삭제하지 않고 삼각형 위치만
보존한 OBJ transport copy를 만든다. Notebook 06은 GLB가 없거나 Blender GLB
export가 실패해도 저장된 review Blend 또는 OBJ를 평가 입력으로 선택한다. 이
경로는 포맷 호환성만 보완하며 material·texture·rig·socket·face 품질을 개선하지
않고, `unityInputAllowed=false`와 `productionPromotionAllowed=false`를 유지한다.

v056와 v073의 차이를 비교한 결과, v056의 RGB foreground voxel fallback은
overall `0.758976`·appearance `0.563129`였지만 v072/v073은 NeuS가 완료됐다는
이유만으로 그 결과를 대체해 appearance `0.519240`에 머물렀다. 따라서 Notebook
06은 이제 NeuS 완료 여부를 품질 통과로 간주하지 않고 NeuS와 voxel fallback을
각각 `NEUS`·`VOXEL` 후보로 등록해 동일한 refine/evaluate/score/rank 경로에서
비교한다. 다음 실행 결과가 나오기 전까지 이 변경은 해결 경로 준비 상태이며,
사람 Gate B·Production·Unity gate는 계속 잠금이다.

같은 전략을 반복 실행해도 얼굴·헤어·의상·장비 의미론이 새로 생기지 않는 문제를
막기 위해 v075에서 `quality_progress_gate.py`를 추가했다. `WONDER3D_NEUS_VOXEL_COMPARE_V001`
전략의 거절 score/history가 발견되면 Provider 설치·추론 전에
`QUALITY_PLATEAU_SAME_STRATEGY`로 중단하고
`PIVOT_TO_SEMANTIC_RECONSTRUCTION_OR_NEW_PROVIDER`를 다음 작업으로 기록한다.
명시적인 `RE_CAMP_ALLOW_SAME_STRATEGY_RETRY=1`은 진단 목적의 override일 뿐이며,
어떤 경우에도 `unityInputAllowed`나 Production 승격을 허용하지 않는다.
CH101 semantic reconstruction에 넘길 입력·해시·Socket·컬렉션 체크리스트는
`2026-08-28-semantic-reconstruction-inputs-v001.json`에 기록한다. 이 파일은
실제 Mesh가 아니라 Blender authoring 전용 preflight이며, 입력이 준비되어도
Blender 작업과 사람 Gate B 없이는 다음 단계로 승격하지 않는다.

v076에서는 Wonder3D 반복을 중단하고 무료 hybrid pivot을 추가했다. 새로운
`TRELLIS_SINGLE_VIEW_V001`은 24576 MB VRAM·CUDA kernel·약관 확인을 통과할 때만
one-shot 실행되며, 조건이 부족하면 `BLOCKED_PROVIDER_PREFLIGHT`로 heavyweight
설치 없이 종료한다. `SEMANTIC_PROXY_REFERENCE_FITTED_V001`은 네 개의 승인 참조
해시를 확인하고 CPU Blender에서 body/face, hair, outfit, equipment를 분리한
review-only proxy를 만들 수 있다. 두 전략은 같은 refine/evaluate/score/strict
visual QA/rank 경로를 사용하고, 동일 strategy 재실행은 품질 Gate가 막는다.
구현과 고정 Gate는
`2026-08-28-hybrid-quality-strategy-v076.json`과
`docs/plans/ch101-hybrid-quality-improvement-plan-2026-08-28.md`에 기록한다.
실제 Blender 실행·후보 점수·Gate B 승인은 아직 외부 환경과 사람 검토가 필요하므로
모든 상태는 `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
Unity/Production false로 유지한다.

2026-08-24 EEVEE 후보 재검토에서는 단순 자동 점수 통과가 시각적 승인 수준을 의미하지
않는 문제가 확인됐다. 이후 `build_assisted_visual_review.py`가 strict visual identity
policy를 적용한다. 현재 후보는 color `0.300492`, silhouette `0.452165`, appearance
`0.540615`, overall `0.529061`로 강화 기준을 충족하지 못하므로 자동 `REJECT`와
`REGENERATE_REQUIRED`로 기록한다. 이 보조 판정은 Gate B 승인 권한을 갖지 않으며,
기준을 통과한 후보도 `DEFER_TO_HUMAN_REVIEW`로만 남긴다.
이 재판정의 메타데이터는 `2026-08-24-kaggle-t4-triposr-eevee-strict-review-v025.json`에
보관한다.

같은 날 T4 x2에서 InstantMesh가 3회 후보를 생성했고, Blender 3.0.1의 OBJ importer
호환성 보정 후 세 후보 모두 refine·evaluate·score를 완료했다. 세 후보 모두 overall
`0.445080`, silhouette `0.402714`, appearance `0.333264`, color `0.179879`로
strict 자동 QA에서 `REJECT_GATE_B_AND_REGENERATE` 판정을 받았으며, geometry hard gate도
실패했다. 실행 도구 커밋과 후보/GLB SHA256은
`2026-08-24-kaggle-t4-instantmesh-strict-review-v026.json`에 보관한다.

다음 재생성 전 로컬 보강으로 InstantMesh의 foreground ratio를 실제 단일 입력
이미지 정규화에 적용하도록 수정했다. 이전에는 Notebook에서 ratio를 전달해도
InstantMesh provider command가 이를 무시했으며, 이제 시도별 파생 입력 PNG와
원본·파생 SHA256, foreground bbox, 보조 이미지 병합 여부를 `candidate-manifest.json`
의 `providerInput`에 기록한다. 또한 Review Material 기본값을 CH101의 coarse palette
보조 모드로 설정했지만 이는 색상 블로킹 확인용일 뿐 최종 텍스처가 아니다. 다음 T4/L4
실행에서만 효과를 측정하며, strict visual QA·Gate B·Production·Unity 입력은 계속
잠금이다.
구현 상태와 정적 검증 결과는 `2026-08-25-instantmesh-input-normalization-v027.json`에
보관한다.

2026-08-25 Kaggle T4 x2 실행에서는 InstantMesh가 비정상 종료해 TripoSR fallback으로
전환되었고, foreground ratio `0.80`, `0.90`, `0.98`의 세 후보가 생성되었다. 첫 평가가
기본 `EVAL_ATTEMPT=01` 때문에 1번 후보만 처리한 것을 확인한 뒤 `EVAL_ATTEMPT=ALL`로
재실행해 세 후보 모두 Blender refine·evaluate·score·rank에 포함했다. overall은 각각
`0.454041`, `0.454932`, `0.480015`였고 최고 후보도 upside-down orientation, color
minimum, overall `0.50` 기준을 충족하지 못했다. 기술 점수는 모두 `1.0`이지만 시각 품질
기준은 모두 실패했으며, 자동 QA는 3개 모두 `REJECT_GATE_B_AND_REGENERATE`로 판정했다.
Gate B 패키지는 세 후보 순위로 갱신했지만 `GATE_B_REVIEW_PACKAGE_READY_NOT_APPROVED`,
`PENDING_HUMAN_REVIEW`, Unity 입력 false를 유지한다. 재발 방지를 위해 Notebook의
기본 평가 범위를 `ALL`로 변경했다. 실행 상세와 SHA256은
`2026-08-25-kaggle-t4-triposr-foreground-normalized-v028.json`에 보관한다.

같은 T4 세션에서 upside-down 자동 감지 후 수직 polarity 보정을 적용해 세 후보를
재평가했다. 보정 후 overall은 `0.497417`, `0.496654`, `0.519884`로 상승했고, 03번은
overall `0.50`을 넘었지만 color `0.136379`가 최소 `0.20`에 미달했다. 따라서 방향 문제는
해결됐으나 색상·재질 일치가 현재 병목이며 자동 QA는 3개 모두
`REJECT_GATE_B_AND_REGENERATE`로 남았다. Gate B 패키지는 `03 → 01 → 02` 순서로
갱신되었지만 `GATE_B_REVIEW_PACKAGE_READY_NOT_APPROVED`, `PENDING_HUMAN_REVIEW`,
Unity 입력 false를 유지한다. 다음 실행부터 수직 보정을 기본 적용하도록 Notebook을
변경했으며 상세 점수·보정 GLB SHA256은
`2026-08-25-kaggle-t4-triposr-vertical-correction-v029.json`에 보관한다.

다음 색상 보정 단계에서는 CH101 승인 시트의 피부 톤과 맞지 않던 기존 흰색 skin
review palette를 따뜻한 soft-matte 톤으로 교체했다. 이는 최종 텍스처가 아니라 색상
히스토그램 개선을 위한 검토용 보정이며, 다음 T4 실행에서 color score 변화를 측정한다.

2026-08-25 최신 `83f0438` 도구 커밋으로 Kaggle T4를 재실행했다. Wonder3D는 T4
preflight와 pinned checkout까지 통과했지만 six-view inference subprocess가 exit code 1로
종료되어 mesh를 만들지 못했고, TripoSR fallback이 foreground ratio `0.80`, `0.90`,
`0.98` 세 후보를 생성했다. Blender 전용 NumPy 경로를 복구한 뒤 warm skin palette와
수직 polarity correction을 적용해 세 후보를 모두 refine·evaluate·score·rank했다.
점수는 각각 overall `0.497417`, `0.496654`, `0.519884`, color `0.137409`, `0.132872`,
`0.136379`로 이전 v029와 동일했으며, palette 변경만으로 color 병목은 해결되지 않았다.
보조 시각 판정은 세 후보 모두 `REJECT_GATE_B_AND_REGENERATE`였고, Gate B 패키지는
생성하지 않았다. 실행 해시와 상세 provenance는
`2026-08-25-kaggle-t4-triposr-palette-v030.json`에 보관한다. 모든 Production·Gate B·
Unity gate는 계속 잠금이다.

v030에서 피부색 단일 변경만으로 color score가 움직이지 않은 원인을 보강하기 위해,
CH101 리뷰 팔레트를 전역 bounds·좌우 위치·전면 법선 기반의 색상 블로킹으로 변경했다.
검은 상·하의/헤어, 흰 재킷·부츠, 피부 영역, 제한된 청록·금색 포인트를 분리하고
객체별 재질 배정 통계를 리포트에 기록한다. 이는 텍스처 생성이나 의미론적 얼굴·의상
분할이 아니며, 평가 기준과 Gate는 변경하지 않았다. 로컬 정적 검증은 통과했지만 실제
점수는 아직 T4에서 재측정하지 않았으므로 현재 판정은 계속
`REGENERATE_REQUIRED_UNTIL_T4_REMEASUREMENT`이며 상세 구현 기록은
`2026-08-25-ch101-palette-blocking-v031.json`에 보관한다.

같은 날 최신 v031을 T4에서 재측정하려 했으나, Kaggle 작업공간이 재연결되며 이전
TripoSR 후보 파일이 사라진 상태였다. T4·PyTorch `sm_75` 호환성은 PASS였고 tools/art/
Provider 재clone과 참조 준비까지는 완료했지만, 의존성 설치 중 세션 상태가 끊겨 실제
TripoSR 추론·후보·점수는 생성되지 않았다. 따라서 v030 점수를 새 결과로 덮어쓰지 않고,
실행 기록은 `2026-08-25-kaggle-t4-session-reset-v032.json`에 보관한다. 다음 실행은
설치·참조·3회 후보 생성·평가를 별도 checkpoint 셀로 나누며, 후보 manifest 3개가
확인되기 전에는 refine/score를 실행하지 않는다.

2026-08-26 T4 실행에서는 TripoSR 3개, Stable Fast 3D 1개 시도, InstantMesh 3개를
비교했다. TripoSR 최고 후보는 색상 복원 후 overall `0.514884`, color `0.210645`까지
올랐지만 strict visual identity policy의 overall `0.60`, silhouette `0.50`, appearance
`0.55`, color `0.38`을 충족하지 못해 자동 시각 QA에서 거절됐다. InstantMesh의
`0.98` 후보는 texture 보존 평가에서 overall `0.508256`, appearance `0.557187`,
color `0.385785`였지만 geometry hard gate의
`LARGEST_CONNECTED_COMPONENT_BELOW_MINIMUM`으로 거절됐다. Stable Fast 3D는
Hugging Face gated model 인증 요구로 후보를 만들지 못했다. 전체 비교·원본 SHA256·
provider commit은 `2026-08-26-kaggle-t4-provider-comparison-v040.json`에 보관한다.
Alpha Review, Gate B, Production Mesh, Unity 입력은 모두 잠금 상태다.

2026-08-26 현재 렌더 조건으로 재기준선을 다시 맞춘 뒤 review-only 보정을 비교했다.
v048 기준선은 overall `0.529923`, v049 coarse palette는 color `0.221981`, v050
palette+surface bridge는 overall `0.535797`, appearance `0.401226`, color `0.221873`,
technical `1.0`, triangle `28,728`, largest component ratio `0.97760467`로 기본
candidate failure 없이 통과했다. 그러나 strict assisted visual QA의 overall `0.60`,
appearance `0.55`, color `0.38` 기준에는 미달해 `REJECT_GATE_B_AND_REGENERATE`로
판정했다. 전면 reference projection v051도 v050보다 낮아 선택하지 않았다. 따라서
v050을 현재 기술상 최선의 review candidate로만 보관하고 Alpha Review·Gate B·Production·
Unity 입력은 잠근다. 상세 SHA256과 비교 결과는
`2026-08-26-kaggle-t4-review-remediation-v053.json`에 보관한다.

같은 실행에서 전면 reference projection의 좌우 반전 변형도 측정했지만 v051과 동일한
overall `0.533393`, appearance `0.39161`, color `0.204233`으로 개선되지 않았다.
projection 계열은 중단하고, 다음 품질 상승은 다면 reference/provider 또는 실제 Blender
조형 입력이 준비될 때 재개한다. 상세 결과는
`2026-08-26-kaggle-t4-reference-projection-flip-v054.json`에 보관한다.

같은 T4 세션에서 최신 Diffusers가 Wonder3D checkpoint의 provider-local custom UNet을
원격 코드로 찾지 못하는 원인을 확인하고, local UNet + checkpoint VAE/CLIP/scheduler를
조립하는 manual loader로 실제 6-view RGB/normal 생성을 완료했다. 공식 NeuS mesh
추출은 1000·200·20 iteration 최소 프로파일 모두 현재 Kaggle 런타임에서 완료되지 않아
중단했으며, mesh·candidate manifest·Review Blend는 생성하지 않았다. 동일 세션의
완료된 TripoSR 후보는 overall `0.512628`이지만 color `0.170125`로 최소 `0.20`에
미달해 `REGENERATE_REQUIRED`다. 상세 provenance와 Wonder3D 차단 상태는
`2026-08-26-kaggle-t4-wonder3d-manual-loader-v055.json`에 보관한다.

이후 같은 T4 세션에서 Wonder3D 6-view RGB/normal을 재생성하고, NeuS가 계속
`BLOCKED_NEUS_RUNTIME_TOO_SLOW`인 경우를 위한 deterministic voxel-surface fallback을
실행했다. 96-grid 표면은 10,063개 정점·20,136개 삼각형으로 생성되었고, Wonder3D
RGB를 정면·후면·측면 review texture로 투영한 뒤 Subdivision level 1을 적용했다.
최종 review-only 후보는 overall `0.758976`, silhouette `0.797221`, appearance
`0.563129`, color `0.863743`, face `0.524969`, technical `1.0`으로 기본 후보 기준과
strict visual identity policy를 모두 통과했다. Assisted visual QA는
`DEFER_TO_HUMAN_GATE_B_REVIEW`로 판정했으며, 얼굴 metric은 의미론적 얼굴 일치 증명이
아니므로 반드시 사람 검토가 필요하다. `2026-08-26-kaggle-t4-wonder3d-voxel-textured-alpha-review-v056.json`
에 점수·해시·6개 view 해시를 기록한다. Gate B·Production·Unity 입력은 계속 잠금이다.

2026-08-27 Kaggle T4 재실행에서는 Wonder3D 실제 6-view 추론이 성공했지만, normal
alpha가 front/front-right/back/front-left에서 crop-sized rectangle로 나온 원인을
확인했다. RGB 전경 마스크를 사용하면 사람 형태 실루엣은 복구되지만, visual-hull
fallback은 여전히 면이 거칠고 얼굴·헤어·의상·장비 디테일이 부족했다. EEVEE 기준
최고 기본 점수는 v064 overall `0.533389`였으나 strict visual policy의 overall
`0.60`, silhouette `0.50`, appearance `0.55`, color `0.38`을 충족하지 못해
`REJECT_GATE_B_AND_REGENERATE`로 판정한다. normal-alpha를 사용한 v058/v065의 높은
점수는 box-like geometry가 실루엣 지표를 부풀린 결과라 품질 개선으로 인정하지 않는다.
`build_wonder3d_voxel_surface.py`에 `--mask-source rgb-foreground`를 추가했고,
Notebook 06은 NeuS 실패/시간 초과 시 이 review-only fallback으로 전환하도록 연결했다.
상세 provenance·점수·해시는
`2026-08-27-kaggle-t4-wonder3d-mask-recovery-v065.json`에 기록한다. 이 실행의 Kaggle
binary와 render는 세션 임시 산출물이며 Git에 저장된 것으로 주장하지 않는다. Gate B,
Production, Unity 입력은 계속 잠금이다.

같은 Notebook 06을 최신 `e9486f2` 브랜치에서 재실행했다. 사전 검사 후 최신
reference manifest의 SHA256이 이전 report와 달라 안전하게 6-view를 재생성했고,
`READY_GPU_VISIBLE`·T4 2장·Wonder3D pinned commit을 확인했다. NeuS는 120초에서
timeout되어 `BLOCKED_FALLBACK_USED`로 전환되었고, RGB foreground mask 기반 fallback은
32,762개 정점·65,520개 삼각형을 만들었다. 그러나 최종 후보는 overall `0.432967`,
appearance `0.050563`, color `0.049172`, face `0.046689`, technical `0.85`로
`REGENERATE_REQUIRED`다. 따라서 `selectedCandidate`는 `null`이며,
`REJECT_GATE_B_AND_REGENERATE`로 판단한다. 최신 Notebook 실행 결과와 해시는
`2026-08-27-kaggle-t4-wonder3d-notebook-fallback-v066.json`에 기록한다. 이 결과도
review-only이며 Gate B·Production·Unity 입력은 잠금 상태다.

이후 `2735aed`에서 Python 3.12 `pyhocon/imp` shim, NeuS tensor shape 보정, timeout
process-group 정리를 적용하고 기존 6-view를 재사용해 NeuS partial mesh를 평가했다.
NeuS는 120초 내 전체 종료하지 않았지만 intermediate GLB를 보존했고, fallback 대신
이를 평가한 결과 overall `0.474892`, appearance `0.235407`, color `0.194787`, face
detail `0.412924`, technical `1.0`이었다. overall·appearance·color 기준 미달로
`REGENERATE_REQUIRED`이며, `selectedCandidate`는 `null`이다. 실행 기록은
`2026-08-27-kaggle-t4-wonder3d-neus-partial-v067.json`에 보관한다. 이 결과도
review-only이고 Gate B·Production·Unity 입력은 잠금 상태다.

이후 같은 6-view를 사용한 EEVEE review texture 보정 v071은 승인 reference의
front/back/right를 모두 투영해 overall `0.612213`, silhouette `0.601561`, color
`0.805709`, face `0.369580`, technical `1.0`까지 올렸지만 appearance가
`0.484794`로 strict minimum `0.55`에 미달했다. 화면상 메시도 outfit·hair·equipment
경계가 보존되지 않은 추상 표면이므로 assisted visual QA는
`REJECT_GATE_B_AND_REGENERATE`로 판정했다. 이어서 3,000 iteration NeuS v072가
GLB를 생성했으나 Blender 3.0.1 GLTF importer 오류로 refine 전에 중단되어 점수와
후보로 인정하지 않았다. 두 시도의 provenance·점수·source mesh hash는
`2026-08-27-kaggle-t4-wonder3d-neus-quality-v071-v072.json`에 보관한다. 품질 상승을
위해서는 더 강한 reconstruction provider 또는 실제 Blender semantic reconstruction이
필요하며, 임계값을 낮추거나 추상 표면을 Alpha Review로 승인하지 않는다. Gate B,
Production, Unity 입력은 계속 잠금이다.

GLB importer 오류를 우회하기 위해 v072 메시를 순수 GLB parser로 OBJ로 변환한 뒤,
OBJ 직접 평가 → 정규화 Blend → 승인 reference texture 투영을 실행한 v073도 확인했다.
이 결과는 overall `0.622415`, appearance `0.519240`, color `0.888452`, face
`0.416412`, technical `1.0`으로 직전보다 나아졌지만 appearance minimum `0.55`에
미달했다. Contact sheet에서도 표면이 slab-like abstract shape로 남아 strict visual QA는
동일하게 `REJECT_GATE_B_AND_REGENERATE`다. 따라서 이 후보도 Alpha Review·Gate B·Unity
입력으로 승격하지 않으며, v071~v073 기록은
`2026-08-27-kaggle-t4-wonder3d-neus-quality-v071-v072.json`에 갱신했다.

이후 Kaggle hybrid Notebook에서 `TRELLIS_SINGLE_VIEW_V001`과
`SEMANTIC_PROXY_REFERENCE_FITTED_V001`을 각각 한 번의 정책으로 처리했다. 현재 런타임은
GPU가 노출되지 않아 TRELLIS는 `BLOCKED_PROVIDER_PREFLIGHT`로 기록됐고, CPU Blender
semantic proxy는 OBJ transport까지 생성되어 refine·evaluate·score·strict visual QA를
완주했다. 후보 점수는 overall `0.505845`, silhouette `0.484222`, appearance `0.364404`,
color `0.201315`, face `0.449624`, technical `1.0`이며, strict 기준 미달과 함께
연결 성분 60개·유의미 성분 35개·최대 성분 비율 `0.05831217`로 geometry hard gate도
실패했다. 따라서 `REGENERATE_REQUIRED` 및 `REJECT_GATE_B_AND_REGENERATE`이며,
동일 semantic 전략은 반복하지 않는다. 실행 아티팩트 해시와 Kaggle 경로는
`2026-08-28-kaggle-hybrid-semantic-proxy-v077.json`에 보관한다. Gate B, Production,
Unity 입력은 계속 잠금이다.

2026-08-28 품질 정체 후속 구현에서는 `UNIFIED_SEMANTIC_AUTHORING_V002`를 추가했다.
V001 거절 이력을 확인하면 이 새 전략만 선택하며, compatible GPU가 먼저 준비되면
TRELLIS를 우선 실행하고 실제 mesh가 없을 때 남은 semantic 경로로 한 번만 fallback한다.
V002 builder는 V001의 60개 분리 primitive 문제를 해결하기 위해 semantic authoring
volume을 하나의 primary shell로 join한 뒤 voxel remesh로 실제 연결성을 확인한다.
body/face·hair·outfit·equipment label, LOD, rig, Socket 및 face placeholder는
리포트에 남기지만 자동 결과는 여전히 review-only다. Notebook, candidate metadata,
quality-progress gate, strict QA 연결과 83개 unittest·Colab/AI3D validator 검증을
완료했다. 실제 Blender/Kaggle 실행 결과가 나오기 전까지 점수나 Alpha Review 통과를
주장하지 않으며, Gate B·Production·Unity 입력은 계속 잠금이다. 계획과 차단 조건은
`docs/plans/ch101-quality-unity-android-plan-2026-08-28.md`에 고정한다.

2026-08-29 로컬 Blender 4.5.10에서 V002를 실제 생성해 remesh·UV·LOD·weight·socket과
GLB export를 확인했다. 평가기는 review floor와 중복 LOD를 캐릭터 topology에서 제외해
geometry hard gate를 PASS로 판정했지만, appearance `0.346415`와 color `0.138373`이
strict visual QA 기준에 미달해 `REJECT_GATE_B_AND_REGENERATE`로 남겼다. 이 실행은
검토용 임시 산출물이며 Gate B·Production·Unity 입력을 해제하지 않는다. 상세 hash와
점수는 `2026-08-29-local-blender-v002-review-v001.json`에 보관한다.

동일 V002 전략은 quality-progress gate에서 `QUALITY_PLATEAU_SAME_STRATEGY`로 잠갔다.
최고 overall `0.608431`은 appearance·color 기준을 충족하지 못하므로 같은 전략을
반복하지 않고, 다음 실행은 실제 semantic face/hair/outfit 재구성 또는 새로운 Provider로
전환한다. 판정은 `2026-08-29-quality-progress-gate-v002.json`에 보관한다.

V002 정체 이후의 다음 semantic pivot인 `SEMANTIC_DETAIL_AUTHORING_V003`도 로컬
Blender 4.5.10에서 실제 생성·평가했다. body shell remesh는 PASS하고 face detail,
hair, outfit, equipment를 별도 semantic group으로 보존했지만, transport 기준
geometry hard gate는 연결 성분 192개·유의미 성분 70개로 실패했다. 점수는 overall
`0.479447`, silhouette `0.441747`, appearance `0.369244`, color `0.182749`,
face `0.514200`, technical `1.0`이며 strict visual QA는
`REJECT_GATE_B_AND_REGENERATE`다. 이 결과는 Kaggle 실행 결과가 아닌 로컬
CPU fallback 검증이며, 다음 Kaggle 세션에서 동일 전략을 반복하지 않도록
V002 plateau 기록을 orchestrator history로 연결했다. 상세 결과는
`2026-08-29-local-blender-v003-review-v001.json`에 보관한다.

2026-08-31 Kaggle T4 x2 세션에서는 Provider를 재실행하지 않고 MPFB 기반 Blender-only
의상·실루엣 보정 후보를 한 번 추가했다. aggregate overall은 `0.682993`까지 상승했지만,
appearance `0.373505`, face `0.000000`, technical `0.8`과 연결 성분 194개·유의미
성분 35개로 strict visual/geometry gate를 통과하지 못해 `REGENERATE_REQUIRED`로
판정했다. 기록과 검토 패키지 SHA256은
`2026-08-31-kaggle-semantic-authoring-v002-review.json`에 보관하며, Gate B·Production·
Unity 입력은 계속 잠금이다.
