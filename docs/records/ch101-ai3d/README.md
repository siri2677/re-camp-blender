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

`.blend`, `.glb`, 렌더 PNG, ZIP은 기본적으로 `.gitignore` 대상이다. 세션이 끝난 뒤에도
바이너리를 보관해야 할 때는 GitHub Release 또는 Git LFS를 사용하고, 해당 파일의
SHA256과 다운로드 위치를 이 디렉터리의 실행 기록에 추가한다. 기록 파일에는 API key,
Hugging Face token, Colab secret을 저장하지 않는다.
