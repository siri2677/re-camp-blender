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

## 다음 검증

최신 코드를 Colab T4에서 다시 실행해 다음을 비교한다.

- Workbench 색 동기화 전후 `colorScore`
- 팔레트 fallback 전후 `appearanceScore`와 `overallScore`
- 3개 후보 모두에 대해 동일한 SHA256·art commit·Gate 검증

이 개선은 색상 표시와 Review 가독성을 높이는 보정이다. 단일 이미지 3D 모델의
측면·후면 형태 추정 한계와 얼굴 BlendShape 부재를 해결하지 않으므로, 점수가 올라가도
Production Mesh 또는 Unity 입력으로 자동 승격하지 않는다.
