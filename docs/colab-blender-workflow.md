# Re:Camp Colab Blender Workflow

이 저장소는 Blender 자동화 도구와 Colab 실행 Notebook을 보관한다. 원본 아트와 승인 상태는 [re-camp](https://github.com/siri2677/re-camp) 저장소에서 관리한다.

## 저장소 역할

- `re-camp`: 아트 원본, 프로젝트 문서, 승인 기준
- `re-camp-blender`: Colab Notebook, Blender Python, 검증 코드
- Colab `/content`: 세션 중 생성되는 임시 파일

Notebook은 다음 원본 브랜치와 커밋을 기준으로 CH101 소스를 읽는다.

`art/current-roster-gate-a-ch102` / `418ef96`

## Drive가 차단된 경우

`notebooks/00_colab_blender_nodrive_test.ipynb`를 연다. 이 Notebook은 Google Drive를 mount하지 않는다.

1. `re-camp` 원본 저장소를 `/content/re-camp`에 clone한다.
2. 이 저장소를 `/content/re-camp-blender`에 clone한다.
3. Colab runtime에 Blender를 설치한다.
4. 화면 장치가 없는 runtime에서는 `xvfb-run`을 자동으로 사용한다.
5. front/side/back 렌더, `.blend`, `.fbx`, JSON 검증 리포트를 생성한다.
6. `/content/re-camp-CH101-blockout.zip`을 브라우저로 다운로드한다.

Colab 세션이 끝나면 `/content`의 파일은 삭제되므로 ZIP을 세션 종료 전에 다운로드해야 한다.

## 판정 경계

현재 자동화 결과는 문서용 중립 Blockout이다. 최종 캐릭터 모델, Unity Import, Android 성능, Gate B 승인을 의미하지 않는다.

## 검증

```text
python scripts/validate_colab_package.py
```

`.blend`와 `.fbx`가 커지면 일반 Git 커밋보다 GitHub Release 또는 Git LFS를 사용한다.
