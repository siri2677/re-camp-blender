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
