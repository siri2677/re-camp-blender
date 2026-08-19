# Re:Camp Colab Blender Workflow

이 저장소는 Blender 자동화 도구와 Colab 실행 Notebook을 보관한다. 원본 아트와 승인 상태는 [re-camp](https://github.com/siri2677/re-camp) 저장소에서 관리한다.

## 저장소 역할

- `re-camp`: 아트 원본, 프로젝트 문서, 승인 기준
- `re-camp-blender`: Colab Notebook, Blender Python, 검증 코드
- Colab `/content`: 세션 중 생성되는 임시 파일

Notebook은 다음 원본 브랜치와 커밋을 기준으로 CH101 소스를 읽는다.

`current/art-roster-gate-a-ch102` / `b6c9b3128358e061eee6184230929413eba84101`

Notebook은 브랜치 tip을 그대로 신뢰하지 않고 이 커밋을 `fetch`한 뒤
detached checkout한다. 이후 승인 시트 파일이 실제로 존재하지 않으면 즉시
실패한다.

## Drive가 차단된 경우

`notebooks/00_colab_blender_nodrive_test.ipynb`를 연다. 이 Notebook은 Google Drive를 mount하지 않는다.

1. `re-camp` 원본 저장소를 `/content/re-camp`에 clone한다.
2. 이 저장소를 `/content/re-camp-blender`에 clone한다.
3. Colab runtime에 Blender를 설치한다.
4. 화면 장치가 없는 runtime에서는 `xvfb-run`을 자동으로 사용한다.
5. front/side/back 렌더, `.blend`, `.fbx`, JSON 검증 리포트를 생성한다.
6. `/content/re-camp-CH101-blockout-v010.zip`을 브라우저로 다운로드한다.

Colab 세션이 끝나면 `/content`의 파일은 삭제되므로 ZIP을 세션 종료 전에 다운로드해야 한다.

## 판정 경계

현재 자동화 결과는 v009 LOD 패키지 위에 정규화된 2-bone production-review weight, 6개 material budget, Armature modifier, idle/run/attack/A-pose 변형 렌더를 추가한 v010이다. 최종 모델, Unity Import, Android 성능, Gate B 승인을 의미하지 않는다.

전체 제작 단계와 다음 Phase 6 작업은 [CH101 Production Roadmap](plans/ch101-production-roadmap.md)에서 관리한다.

## 검증

```text
python scripts/validate_colab_package.py
```

## CH101 production mesh intake

실제 고해상도 생산 모델이 준비되면 notebooks/03_ch101_production_mesh_intake.ipynb를 실행한다. 이 Notebook은 도구 저장소를 최신 확인 커밋 c2f8247ec4fd9b29877ff38b92af64eca18f56aa에 detached checkout한다.

1. CH101_A_HighRes_Production_v001.blend를 업로드한다.
2. Blender를 headless + xvfb-run으로 실행한다.
3. validate_ch101_mesh_intake.py가 컬렉션, 메시, 리그, UV, 소켓, 머티리얼, triangle budget을 검사한다.
4. PASS일 때만 production-mesh-handoff.json을 만들고 sourceStatus=PRODUCTION_MESH_READY로 기록한다.
5. gateB는 자동 승인되지 않고 PENDING_HUMAN_REVIEW로 남는다.
6. 검증 리포트, handoff JSON, 원본 .blend를 ZIP과 SHA256 파일로 다운로드한다.

이 Notebook은 최종 모델링이나 시각 품질 승인을 대신하지 않는다. 현재 저장소의 MPFB/primitive/styled 결과는 기술 WIP로만 취급하며, 실제 고해상도 생산 .blend가 없으면 Gate B와 Unity 입력은 계속 차단된다.

## CH101~CH105 공용 인테이크

CH102~CH105 파일이 준비되면 04_current_roster_production_mesh_intake.ipynb를 사용한다.
셀의 CHARACTER_CODE를 CH101, CH102, CH103, CH104, CH105 중 하나로 설정하고 해당
캐릭터의 production .blend 하나를 업로드한다. 공용 검증기는 캐릭터별 장비·소켓 계약과
공통 컬렉션·UV·Armature·triangle·material·status 조건을 검사한다.

검증기는 각 캐릭터의 기술 결과만 PASS/FAIL로 판정한다. 모든 캐릭터의 Gate B 승인이나
Unity roster 교체를 자동으로 수행하지 않으며, 각 캐릭터의 사람 시각 검토가 별도로 필요하다.

공용 계약 파일은 contracts/current_roster_socket_contract_v001.json이다. 이 파일은 공용
Runtime Socket과 캐릭터별 상세 Socket, Unity alias 관계, production 파일명, 승인 시트
경로를 고정한다. 5개 handoff가 모두 준비되면 scripts/merge_current_roster_handoffs.py로
통합 manifest를 만들 수 있지만, 결과의 unityInputAllowed는 계속 false로 남는다.

## CH101 무료 AI 3D 후보 자동 제작

수동 모델링을 수행할 사람이 없는 경우
`notebooks/05_ch101_ai3d_free_autobuild.ipynb`를 사용한다. Notebook은 승인
Character Sheet를 권위 기준으로 잠그고 Turnaround에서 front/right/back 입력을
분리한 뒤 다음 순서로 진행한다.

실행 재현성이 필요한 경우 Colab 환경변수
`RE_CAMP_BLENDER_TOOLS_COMMIT`에 전체 도구 commit SHA를 지정한다. 값을 비워두면
`RE_CAMP_BLENDER_TOOLS_REF`의 최신 branch tip을 checkout하고, 실제 checkout된
SHA를 런타임 manifest에 기록한다. 최신 로컬 변경을 실행하려면 먼저 해당 변경이
원격 branch에 반영되어 있어야 한다.

1. Stable Fast 3D를 기본 무료 Provider로 사용한다. API 키나 Tripo 크레딧은 필요하지 않다.
2. Stable Fast 3D 모델 접근 또는 GPU 실행이 실패하면 Notebook이 오류를 기록하고
   자동으로 TripoSR로 전환한다.
3. TripoSR fallback은 시도별 foreground ratio `0.75`·`0.85`·`0.95`를 적용해
   후보 다양성을 확보하고 적용값을 manifest에 기록한다. Tripo API는 다중 시점
   비교가 필요할 때만 선택적으로 사용한다.
4. 최대 3회 생성한 후보를 Blender에서 1.68m로 정규화하고, 중복 정점·법선·UV·Review Material을 보정한다.
5. 보정된 후보마다 4방향과 3/4 렌더를 만들고 실루엣·외형·색상·얼굴 디테일·기술 점수를 계산한다.
6. 기준을 통과한 후보에만 LOD0/1/2, 22본 Review Rig, 자동 Weight, 공용·CH101 상세 Socket을 만든다.

Stable Fast 3D를 사용할 경우 Hugging Face 접근 토큰과 GPU runtime이 필요할 수 있다.
Tripo를 선택할 경우에만 키를 Colab Secret의 `TRIPO_API_KEY`로 전달한다. 어떤 경로도
사람 Gate B를 자동 승인하거나 Unity package를 export하지 않으며 결과는 항상
`unityInputAllowed=false`다.

2026-08-19 기준 Colab T4에서 TripoSR 생성·Blender 평가·점수 계산까지 실제 실행을
확인했다. 최신 NumPy 호환을 위해 `trimesh>=4.4.0`, rembg 초기화를 위해
`onnxruntime-gpu`를 자동 설치한다. 생성 후보는 품질 게이트를 통과하지 못하면
`REGENERATE_REQUIRED`로 남는다. `foreground-ratio` `0.75`·`0.85`·`0.95` 변형을
실행해도 최고 overall `0.456930`으로 기준 `0.50`에 미달했으며, 세션이 끝나면
`/content` 산출물은 삭제될 수 있다.

후보 보정 스크립트는 `scripts/blender/refine_ai3d_candidate.py`이며, 결과는
`REFINED_REVIEW_CANDIDATE`로 표시된다. 이 결과는 기술·Review 보정본일 뿐이고,
얼굴 BlendShape와 장비 Socket은 각각 차단·추정 상태로 남는다.

로컬 dry-run과 Blender smoke 검증 근거는
[실행 기록](plans/ch101-free-ai3d-local-verification-2026-08-18.md), 전체 규칙은
[자동 제작 계획](plans/ch101-free-ai3d-autobuild-plan.md)에서 확인한다.

`.blend`와 `.fbx`가 커지면 일반 Git 커밋보다 GitHub Release 또는 Git LFS를 사용한다.
