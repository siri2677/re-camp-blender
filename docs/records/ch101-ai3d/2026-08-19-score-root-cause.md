# CH101 AI 3D 점수 미달 원인과 개선 기록

## 확인된 원인

2026-08-19 T4 실행에서 세 후보의 점수는 다음과 같았다.

| 항목 | 최고값 | 해석 |
|---|---:|---|
| overall | 0.452043 | `0.50` 기준 미달 |
| silhouette | 0.413896 | 단일 이미지 모델이 다른 방향의 몸·헤어·장비를 추정하면서 형태 불일치 |
| appearance | 0.360276 | 세부 edge와 색상 정보가 약함 |
| color | 0.146237 | 생성 GLB에 재질·텍스처가 없고 Review 렌더도 중립색을 사용 |
| face detail | 0.473074 | 얼굴은 후보 중 상대적으로 높지만 BlendShape/정밀 랜드마크는 없음 |

이 결과는 기준이 과도하게 높아서만 발생한 것이 아니다. TripoSR은 한 장의 입력으로
전체 캐릭터를 추정하므로 정면 입력에서 후면과 측면을 정확하게 복원하지 못한다.
또한 기존 Review 파이프라인에는 다음 두 가지 표시 문제가 있었다.

1. GLB가 재질을 포함하지 않으면 `preserve` 모드도 실제 색을 복원할 수 없었다.
2. Blender Workbench `MATERIAL` 모드는 Principled BSDF의 Base Color가 아니라
   `Material.diffuse_color`를 읽으므로, imported material이 노드 색만 가지고 있으면
   색이 회색으로 렌더될 수 있었다.

## 적용한 개선

- 평가 전에 Principled BSDF Base Color를 Workbench `diffuse_color`로 동기화한다.
- imported material이 없는 AI 후보에는 CH101 승인 팔레트의 흰색·그래파이트·금색·시안·피부·헤어를
  높이와 면 방향 기반의 거친 Review 근사색으로 적용한다.
- 근사색은 최종 Texture/Material로 승격하지 않으며, report에
  `paletteFallbackUsed=true`와 경고를 남긴다.
- `unityInputAllowed=false`, `productionPromotionAllowed=false` 및 Gate B 대기는 그대로 유지한다.

## T4 색상 렌더 재검증 결과

최신 코드 `e6d9c19`를 Colab T4에 반영해 기존 세 후보를 Eevee로 다시 렌더링했다.
색상 파이프라인은 개선됐지만, 형상 점수가 기준을 넘지 않아 전체 후보는 계속
`REGENERATE_REQUIRED`다.

| 시도 | overall 전→후 | color 전→후 | 판정 |
|---|---:|---:|---|
| 1 | 0.439426 → 0.452120 | 0.153887 → 0.250803 | 미달 |
| 2 | 0.443631 → 0.451603 | 0.151301 → 0.219866 | 미달 |
| 3 | 0.452043 → 0.463577 | 0.146237 → 0.261198 | 미달 |

최고 후보의 색상 점수는 `+0.114961`, overall은 `+0.011534` 상승했다. 따라서
반복된 미달의 주원인은 이제 색상 표시가 아니라 단일 뷰에서 생성된 형상과 승인
turnaround의 불일치다. 다음 개선은 다중 참조 입력 또는 reference-conditioned
형상 재구성이고, 현재 후보를 Production Mesh로 승격할 근거는 없다.

## 다음 검증

재검증은 완료됐다. 기록은
`2026-08-19-color-render-rerun.json`에서 확인할 수 있다. 다음 실행에서는 다음을 비교한다.

- Eevee 색상 렌더의 안정성
- 다중 참조/조건부 생성 후 `silhouetteScore`와 `overallScore`
- 3개 후보 모두에 대해 동일한 SHA256·art commit·Gate 검증

이 개선은 색상 표시와 Review 가독성을 높이는 보정이다. 단일 이미지 3D 모델의
측면·후면 형태 추정 한계와 얼굴 BlendShape 부재를 해결하지 않으므로, 점수가 올라가도
Production Mesh 또는 Unity 입력으로 자동 승격하지 않는다.
