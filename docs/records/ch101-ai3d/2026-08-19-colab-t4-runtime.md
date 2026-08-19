# CH101 Colab T4 실행 기록

실행일: 2026-08-19  
플랫폼: Google Colab  
가속기: Tesla T4

## 실행 순서

1. `05_ch101_ai3d_free_autobuild.ipynb`를 feature 브랜치에서 열고 T4 런타임을
   연결했다.
2. art commit `b6c9b3128358e061eee6184230929413eba84101`에서 정면·우측·후면
   reference view와 SHA256을 생성했다.
3. Stable Fast 3D 실행은 gated Hugging Face 모델 접근 오류로 fallback 되었다.
4. InstantMesh는 `nvdiffrast` 설치에서 중단되었다.
5. TripoSR 공식 requirements에서 누락된 `torchmcubes`를 확인하고
   `git+https://github.com/tatsy/torchmcubes.git`를 설치한 뒤 T4 추론을 완료했다.
6. front/right/back 입력과 foreground ratio `0.75/0.85/0.95`로 3개 후보를 만들고,
   Blender 보정·5방향 렌더·점수 계산을 모두 완료했다.

## 결과

| 시도 | 입력 | foreground ratio | overall | 판정 |
|---|---|---:|---:|---|
| 01 | front | 0.75 | 0.439426 | `REGENERATE_REQUIRED` |
| 02 | right | 0.85 | 0.443631 | `REGENERATE_REQUIRED` |
| 03 | back | 0.95 | 0.452043 | `REGENERATE_REQUIRED` |

최고 후보도 Alpha Review 기준 `overall >= 0.50`에 미달했다. 따라서 ranking manifest의
선택 후보는 없고 Review Asset·Gate B·Unity 입력은 생성하지 않았다.

Colab 세션 산출물:

- `/content/re-camp-ai3d/CH101/ranking-manifest-t4-2026-08-19.json`
- `/content/re-camp-CH101-ai3d-t4-run-NOT-PRODUCTION.zip`

이번 실행은 실제 GPU 추론 경로와 의존성 누락을 확인한 기술 검증이다. 최종 상태는
`AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`,
`unityInputAllowed=false`로 유지한다.
