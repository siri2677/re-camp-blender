# CH101 Kaggle GPU workstream

## 목적

Colab GPU quota가 차단된 동안에도 동일한 CH101 v005 파이프라인을 Kaggle
Notebook의 무료 GPU에서 재개할 수 있도록 실행 경로를 준비한다. 이 경로는
Colab의 모델·계약·Gate 규칙을 바꾸지 않고 런타임 경로와 Secret·산출물 보관
방식만 교체한다.

## 현재 구현

`notebooks/05_ch101_ai3d_free_autobuild.ipynb`는 다음 런타임을 자동 감지한다.

| 런타임 | 기본 작업 경로 | Secret 조회 | 산출물 처리 |
|---|---|---|---|
| Colab | `/content` | 환경변수 → Colab userdata | ZIP 브라우저 다운로드 |
| Kaggle | `/kaggle/working` | 환경변수 → `kaggle_secrets` | Kaggle output panel에서 다운로드 |

수동 경로가 필요하면 `RE_CAMP_RUNTIME`과 `RE_CAMP_CONTENT_ROOT`로 런타임과
작업 루트를 고정할 수 있다. `TRIPO_API_KEY`와 `HF_TOKEN`은 기록하지 않으며,
무료 Provider 경로에서는 Tripo API를 호출하지 않는다.

Kaggle 첫 실행의 대기 시간을 줄이기 위해 tools/art 저장소는 기본적으로
`--depth 1`로 clone하고, `RE_CAMP_GIT_CLONE_DEPTH`로 조정할 수 있다. 각 외부
명령은 즉시 `RUN:`을 출력하므로 clone·preflight·Blender 설치 중 어느 단계가
지연되는지 확인할 수 있다.

## Kaggle 실행 전제

Kaggle 공식 문서 기준 Notebook에는 무료 NVIDIA GPU accelerator를 붙일 수
있고, 기본적인 무료 GPU는 Tesla P100이다. GPU quota는 주 단위이며 수요에
따라 달라질 수 있다. 세션은 최대 12시간이고, 외부 저장소 clone과 Provider
설치에는 Notebook Internet을 켜야 한다.

실행 전에 다음을 확인한다.

1. Kaggle Notebook에서 Accelerator를 GPU로 설정한다.
2. Notebook Internet을 켠다.
3. `nvidia-smi`와 `torch.cuda.is_available()`가 모두 정상인지 확인한다.
4. GitHub의 `feature/ch101-free-ai3d-autobuild` 브랜치에서 Notebook 05를
   업로드하거나 복사한다.
5. `RE_CAMP_BLENDER_TOOLS_COMMIT`을 지정하면 도구 commit을 고정한다.
6. 출력 ZIP은 `/kaggle/working` 아래에 남기고 세션 종료 전에 Kaggle output
   panel로 다운로드한다.

## 실행 순서

1. 런타임 preflight
2. tools/art commit checkout
3. CH101 reference crop·auxiliary reference SHA256 검증
4. v005 `CH101_V005_IDENTITY_RECOVERY` 전략 적용
5. Stable Fast 3D → InstantMesh → TripoSR fallback
6. Blender refine → evaluate → score → rank
7. 기준 미달이면 `REGENERATE_REQUIRED`
8. 기준을 통과해도 사람 Gate B 대기

P100에서 VRAM·dependency·provider compatibility 문제가 발생하면 실패 원인을
기록하고 Unity 단계로 우회하지 않는다. 기존 후보·reference manifest가 유효한
경우에는 재사용 Gate를 먼저 적용한다.

## Gate 고정

```text
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

Kaggle 실행 성공은 후보 생성 성공을 의미하지 않는다. 실제 후보 파일과
평가 리포트가 생성되고, 자동 점수와 보조 시각 검토를 통과해야 Alpha Review
후보가 된다. 사람 Gate B 승인 전에는 FBX/GLB와 Unity Import를 생성하지 않는다.

## 외부 참고

- Kaggle Notebook과 accelerator: <https://www.kaggle.com/docs/notebooks>
- Kaggle GPU quota: <https://www.kaggle.com/docs/efficient-gpu-usage>
