# CH101 AI 후보 원본 재질 보존 검증

검증일: 2026-08-19  
도구 commit: `5db8c9b`

## 목적

AI 후보 보정 단계가 원본 재질을 중립 회색으로 바꾸면서 색상 점수를 낮추는지
분리 확인했다. 보정 스크립트에 `--material-mode preserve`를 추가했고, 이 모드에서는
입력 GLB의 material slot과 vertex color를 유지한다. 입력에 재질이 없을 때만
`AI_REVIEW_NEUTRAL_AUTO`를 fallback으로 사용한다.

## 실행 대상

- Provider: TripoSR
- 후보: 03번 `back`, foreground ratio `0.95`
- 원본 후보: `/content/re-camp-ai3d/CH101/attempts/03/candidates/triposr/CH101_triposr_cand_001.glb`
- 출력 영역: `/content/re-camp-ai3d/CH101/evaluation-preserve/03-CH101-TRIPOSR-001`
- Gate: `AI_GENERATED_CANDIDATE_NOT_PRODUCTION`, `PENDING_HUMAN_REVIEW`, `unityInputAllowed=false`

## 결과

| material mode | imported material | overall | silhouette | appearance | color | face detail | 판정 |
|---|---|---:|---:|---:|---:|---:|---|
| `preserve` | 없음 → neutral fallback | 0.452043 | 0.413896 | 0.332043 | 0.146237 | 0.391916 | `REGENERATE_REQUIRED` |

TripoSR 출력 GLB에는 보존할 imported material slot이 없어서 기존 중립 재질이
그대로 사용되었고 점수 변화도 없었다. 따라서 이번 후보의 병목은 보정 단계의
재질 덮어쓰기가 아니라, Provider 출력 자체의 텍스처·재질 부재와 낮은 시각 일치도다.

## 다음 판단

이 변경은 파이프라인에 보존 경로를 추가했지만 Alpha Review 기준 `overall >= 0.50`을
충족시키지 못했다. 텍스처가 포함된 무료 Provider 출력 또는 별도 텍스처·재질 제작이
확보되기 전에는 CH101을 Gate B, Production Mesh, Unity 입력으로 승격하지 않는다.
