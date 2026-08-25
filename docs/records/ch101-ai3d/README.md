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
