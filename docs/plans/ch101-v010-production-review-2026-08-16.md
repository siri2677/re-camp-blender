# CH101 v010 Production-Skinning Review — 2026-08-16

## 목적

v007의 rigid blockout weight를 Blender에서 실제 포즈 검토가 가능한 정규화된
2-bone influence로 교체하고, v009 LOD 패키지와 material budget을 하나의
Unity handoff 후보로 고정한다. 이 문서는 최종 모델·Gate B 승인 문서가 아니다.

## 입력 잠금

- Source repository: `siri2677/re-camp`
- Source branch: `art/current-roster-gate-a`
- Source commit: `183b0f0983969937d779f70b2ac51e53fc976203`
- Reference sheet: `art_refs/characters/rin/concept/CH101_Rin_CharacterSheet_APPROVED_v001.png`

## 실행

```powershell
blender --background --python scripts/blender/build_blockout.py -- `
  --character CH101 `
  --source-asset <locked-sheet> `
  --source-commit 183b0f0983969937d779f70b2ac51e53fc976203 `
  --output-dir artifacts/CH101_v010_production_run1 `
  --render --export-fbx --optimize-budget --generate-lods `
  --production-skinning-review
```

```powershell
blender --background --python scripts/blender/validate_asset.py -- `
  --blend artifacts/CH101_v010_production_run1/CH101_Blockout_REVIEW_v010.blend `
  --report artifacts/CH101_v010_production_run1/reports/CH101_Blockout_validation_v010.json
```

## 결과

| 항목 | 결과 |
|---|---|
| Blender revision | `v010` |
| LOD mesh counts | LOD0 89 / LOD1 89 / LOD2 89 |
| LOD triangles | 19,090 / 10,383 / 5,704 |
| Combined review budget | `PASS` (20,000 max for LOD0) |
| Material budget | `PASS` (6 named materials) |
| Skinning | `PASS`, 89 LOD0 meshes, max 2 influences/vertex |
| Rig | `PASS`, 22 bones, 8 socket parents |
| Motion clips | `PASS`, Idle / Run / Attack / A-Pose Check |
| Pose renders | `PASS`, 4 review renders |
| Unity proof | `BLOCKED`, licensed Editor unavailable |
| Gate B | `PENDING`, human approval required |

## 산출물

- `artifacts/CH101_v010_production_run1/CH101_Blockout_REVIEW_v010.blend`
- `artifacts/CH101_v010_production_run1/CH101_Blockout_REVIEW_v010.fbx`
- `artifacts/CH101_v010_production_run1/reports/CH101_Blockout_validation_v010.json`
- `artifacts/CH101-Blockout-v010-production-run1.zip`

## 다음 단계

Blender 기술 스캐폴드는 v010에서 완료 상태다. 시각 제작 모델은 완료되지 않았고,
현재 결과를 최종 캐릭터나 Gate B 후보로 사용할 수 없다. 다음은 얼굴·헤어·의상·재질을
실제 5~6등신 일본 서브컬처 품질로 제작한 뒤, Unity licensed Editor에서 Import/
Humanoid/socket/material/LODGroup/prefab을 확인하고 Android 실기기 성능 증거를
남기는 단계다. Unity에서 최종 셰이더·Animator·Prefab을 확인하기 전에는
`APPROVED`로 표시하지 않는다.
