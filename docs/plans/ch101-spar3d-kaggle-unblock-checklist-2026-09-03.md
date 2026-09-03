# CH101 SPAR3D Kaggle 차단 해소 체크리스트

## 현재 판정

2026-09-03 Kaggle T4 15GB×2에서 GPU·CUDA·PyTorch kernel과 세 Secret 연결은
준비됐지만, SPAR3D import preflight에서 차단됐다.

- `HF_TOKEN`이 Kaggle Secret으로 연결됨
- `RE_CAMP_SPAR3D_ACCESS_ACK=1`이 Kaggle Secret으로 연결됨
- `RE_CAMP_SPAR3D_LICENSE_ACK=1`이 Kaggle Secret으로 연결됨

현재 상태는 모델 품질 미달이나 token 누락이 아니라 provider 의존성 import
차단이다. 후보 mesh, score, Alpha Review 승인으로 해석하지 않는다.

## Secret 연결 후 첫 재개 결과

2026-09-03 Secret 연결 후 메인 Kaggle Notebook을 재실행한 결과, Secret 3개와
T4 15GB×2 GPU는 정상 인식되어 SPAR3D preflight는 `READY_GPU_VISIBLE`이 됐다.
그러나 첫 실행에서는 pinned SPAR3D `requirements.txt`의 `AlphaCLIP` git
패키지가 최신 pip의 격리 빌드 환경에서 실패해 `SPAR3D_SETUP_FAILED`
(`returnCode: 1`)로 종료됐다. 설치 경로를 `--no-build-isolation`로 고친 뒤
재실행에서는 AlphaCLIP·texture_baker·uv_unwrapper 설치가 완료됐지만,
`run_spar3d_candidate.py`의 import-only preflight가
`SPAR3D_DEPENDENCIES_IMPORT_FAILED`로 중단됐다. 따라서 실제 `run.py` 추론,
mesh, candidate manifest는 아직 생성되지 않았다.

첫 오류의 원인은 모델 접근 권한이나 GPU가 아니라 `AlphaCLIP`의 pinned
`setup.py`와 격리 build environment의 호환성 문제였다. Notebook 기본 설치 경로는
이제 `setuptools==69.5.1`·`wheel`을 먼저 runtime에 설치한 뒤
`--no-build-isolation -r requirements.txt`로 설치하도록 보강했으며, 각 설치
단계의 반환 코드와 실패 단계만 기록한다. 두 번째 오류의 원인을 확인하기
위해 import를 모듈별로 검사하고 `module:errorType`만 기록하도록 보강한다.
원본 stderr, 파일 경로, Secret 값은 기록하지 않는다.

두 번째 오류의 실제 원인은 `transparent-background==1.3.3`이 import 시 legacy
GUI 모듈을 함께 읽으면서 `FilePickerResultEvent`를 요구하는데, Kaggle의 최신
`flet`에는 해당 심볼이 없었던 것이다. 따라서 Notebook 07의 기본 설치 경로는
공식 requirements를 유지하면서 `flet==0.23.1`을 추가로 고정한다. 이 호환성
pin이 import preflight를 통과시키는지 Kaggle에서 재검증하며, 통과 전에는
GPU 추론을 시작하지 않는다. 참고: [transparent-background 공식 문서](https://github.com/plemeri/transparent-background),
[동일 import 오류 이슈](https://github.com/plemeri/transparent-background/issues/104).

호환성 pin을 반영한 재실행에서는 import preflight가 `READY_IMPORTS`로 통과했고
SPAR3D `run.py`까지 시작됐지만, provider가 `returnCode: 1`을 반환해
`SPAR3D_EXECUTION_FAILED`로 종료됐다. 이 첫 실행 래퍼는 provider stdout/stderr를
완전히 버렸기 때문에 현재 기록만으로는 CUDA·모델 다운로드·provider 런타임 중
어느 단계인지 구분할 수 없다. 다음 실행부터는 원문을 저장하지 않고 오류 유형·짧은
메시지·경로·token을 마스킹한 `executionFailureDetail`만 기록해 원인별로 분기한다.

## T4 원인 분석 및 수정

고정된 SPAR3D `run.py`를 소스 대조한 결과, CUDA 경로가
`torch.autocast(..., dtype=torch.bfloat16)`을 무조건 선택한다. Kaggle의 Tesla T4는
Compute Capability 7.5(sm_75)이고 CUDA BF16 연산은 Compute Capability 8.0 이상이
필요하므로, T4에서는 provider가 추론 초기에 종료할 수 있다. 이는 token·모델 접근
승인·VRAM preflight와 별개의 하드웨어 정밀도 호환성 문제다.

이를 해결하기 위해 `scripts/ai3d/patch_spar3d_t4_compat.py`와 wrapper 연결을
추가했다. Kaggle의 detached provider checkout에서만 다음 규칙을 적용한다.

- `torch.cuda.is_bf16_supported()`가 true면 기존 BF16 유지
- false인 CUDA 장치(T4 포함)는 FP16 autocast로 전환
- provider HEAD가 pinned commit과 다르면 패치·실행 중단
- 원본/패치 SHA256과 patch ID만 report에 기록하고 upstream commit은 변경하지 않음

현재 이 수정은 로컬 118개 unittest, Python compile, AI3D validator, Colab
validator를 통과했다. 새 Kaggle 진단 세션은 런타임 할당이 `Session is starting...`
에서 멈춰 중지했으므로, FP16 전환 후 실제 `run.py`가 mesh를 쓰는지는 호환 GPU가
할당되는 즉시 진단 Notebook 08에서 한 번 확인한다.

재검증 중 Notebook 08의 GitHub raw 다운로드가 PNG 대신 132바이트 Git LFS
pointer를 받아 `PIL.UnidentifiedImageError`를 냈다. 아트 파일은 LFS binary를
제공하는 `media.githubusercontent.com` URL로 받도록 바꾸고, 다운로드 직후
Pillow `verify()`를 통과하지 않으면 provider 설치·추론으로 진행하지 않는다.

이를 실행할 전용 Notebook
`08_ch101_spar3d_diagnostic.ipynb`도 추가했다. 이 Notebook은 Kaggle Secret과
GPU preflight가 모두 통과할 때만 동일한 공식 `run.py`를 `--diagnostic-only`로
한 번 실행한다. 결과 mesh가 생겨도 후보 등록·`.blend` 생성·Unity 입력은 하지
않으며, 실패 시에는 마스킹된 진단 문자열만 남긴다.

## 사용자가 한 번 수행할 준비

1. [SPAR3D 공식 모델 카드](https://huggingface.co/stabilityai/stable-point-aware-3d)에서
   접근 조건과 라이선스를 직접 확인하고 필요한 접근 승인을 완료한다.
2. Hugging Face에서 읽기 전용 token을 발급한다.
3. Kaggle Notebook의 Secrets에 다음 이름으로 저장한다. 값은 Notebook cell에
   직접 입력하지 않는다.

   - `HF_TOKEN`
   - `RE_CAMP_SPAR3D_ACCESS_ACK` 값 `1`
   - `RE_CAMP_SPAR3D_LICENSE_ACK` 값 `1`

Notebook 07은 Kaggle `UserSecretsClient`로 이 값을 실행 중 메모리 환경변수에만
전달한다. token 값은 출력·report·archive·Git에 기록하지 않으며, 기록되는 것은
token 존재 여부와 acknowledgement 여부뿐이다.

## 재개 절차

1. `feature/ch101-free-ai3d-autobuild`의 최신 Notebook 07을 연다.
2. GPU가 T4/L4/A10 등으로 표시되는지 확인한다.
3. `Run All`을 실행한다.
4. preflight가 다음을 모두 표시하는지 확인한다.

   ```text
   status: READY_GPU_VISIBLE
   torchKernelSupportsDevice: true
   vramSufficient: true
   heavyweightInstallAllowed: true
   ```

5. 조건이 충족될 때만 pinned SPAR3D checkout, setup command, `run.py
   --low-vram-mode`, GLB 확인이 이어진다.
6. mesh가 생성되면 Blender refine → evaluate → score → strict visual QA를
   수행한다.

## 계속 잠기는 조건

- Secret 이름 오타 또는 Secret 미연결
- Hugging Face 접근 승인 미완료
- license acknowledgement 누락
- 8GB 미만 GPU 또는 CUDA kernel 미지원
- 공식 `requirements.txt` 기본 설치가 실패하거나, 별도 설치가 필요한 경우의
  `RE_CAMP_SPAR3D_SETUP_COMMAND` override 오류
- pinned commit·mesh hash·reference hash 불일치

조건이 하나라도 빠지면 `BLOCKED_PROVIDER_PREFLIGHT` 또는 구체적인 실패 상태로
중단하며, 동일 전략을 임의로 반복하지 않는다. 후보가 생성돼도 다음 Gate는
계속 잠긴다.

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## 2026-09-03 재현 결과: CLI 기본값 오류

FP16 호환성 패치를 적용한 새 Kaggle T4 진단은 다음 단계까지 정상적으로
진입했다.

- GPU: `2x Tesla T4 15360MB`
- GPU preflight: `READY_GPU_VISIBLE`
- PyTorch kernel: `torchKernelSupportsDevice: true`
- Secret: `HF_TOKEN`, access acknowledgement, license acknowledgement 모두
  존재 여부만 확인됨
- reference image: Git LFS binary 다운로드 및 Pillow 검증 통과
- dependency import: `READY_IMPORTS`
- T4 runtime patch: 적용됨

그 뒤 pinned SPAR3D `run.py`가 다음 오류로 종료됐다.

```text
AttributeError: 'Namespace' object has no attribute 'reduction_count_type'
```

원인은 pinned `run.py`가 `gpytoolbox` 또는
`pynanoinstantmeshes` 중 하나가 설치된 경우에만
`--reduction_count_type`와 `--target_count`를 argparse에 추가하지만,
remesh backend가 모두 없는 일반 Kaggle 설치에서도 두 값을 무조건 읽기
때문이다. 기본 remesh 옵션은 `none`이므로 optional remesh 패키지를 강제로
설치할 필요는 없다.

`SPAR3D_T4_BF16_CLI_DEFAULTS_V002` 패치를 추가했다. 이 패치는 다음을
detached pinned checkout에만 적용한다.

- `reduction_count_type=keep` 기본값을 항상 정의
- `target_count=2000` 기본값을 항상 정의
- 기존 T4 BF16→FP16 자동 선택 유지
- provider commit 불일치 또는 패치 누락이면 실행 중단

패치 대상은 Kaggle 임시 checkout이며 upstream commit은 변경하지 않는다.
이번 진단은 `SPAR3D_DIAGNOSTIC_FAILED`, mesh 0개, candidate 미등록으로
종료됐고, 다음 재실행은 새 패치 커밋을 사용한다. 성공 여부를 확인하기
전까지 Production·Gate B·Unity 입력은 계속 잠근다.
