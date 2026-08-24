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

`.blend`, `.glb`, 렌더 PNG, ZIP은 기본적으로 `.gitignore` 대상이다. 세션이 끝난 뒤에도
바이너리를 보관해야 할 때는 GitHub Release 또는 Git LFS를 사용하고, 해당 파일의
SHA256과 다운로드 위치를 이 디렉터리의 실행 기록에 추가한다. 기록 파일에는 API key,
Hugging Face token, Colab secret을 저장하지 않는다.
