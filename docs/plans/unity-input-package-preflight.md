# Unity 입력 패키지 사전검증 계획

`re-camp-blender`는 Blender나 Unity Editor가 없는 환경에서도 Unity 연결 직전의
계약을 검사할 수 있도록 `scripts/validate_unity_input_package.py`를 제공한다.

## 현재 가능한 검증

다음 명령은 Gate가 잠긴 production handoff manifest를 검사한다.

```text
python scripts/validate_unity_input_package.py \
  --manifest /path/to/current-roster-unity-import-manifest.json \
  --expected-tools-commit <handoff를 만든 tools commit>
```

검증 대상은 다음과 같다.

- manifest 버전과 `current-roster-socket-contract-v001` 일치
- `source_lock.json`의 승인 art commit 및 tools commit 형식/일치
- CH101~CH105의 순서·파일명·source reference·blend SHA256
- 공용 Socket, 캐릭터별 상세 Socket, runtime alias의 누락·중복
- `PRODUCTION_MESH_READY` 상태와 Gate 값
- `productionPromotionAllowed=false` 및 Unity 입력 잠금

AI 후보, WIP, technical scaffold는 `sourceStatus`만 바꾸어 통과할 수 없다.

## 실제 Unity 패키지 확보 후

Gate B 승인과 최종 package가 준비되면 다음처럼 파일 해시까지 확인한다.

```text
python scripts/validate_unity_input_package.py \
  --manifest /path/to/current-roster-unity-import-manifest.json \
  --package /path/to/re-camp-unity-input-v001.zip \
  --expected-tools-commit <handoff를 만든 tools commit> \
  --require-unity-input
```

`--require-unity-input`은 `gateB=APPROVED`,
`unityInputAllowed=true`, finalized `packageName`, manifest의
`packageSha256`, 실제 package SHA256을 모두 요구한다. validator는 Gate 값을
변경하거나 Prefab·Unity asset을 생성하지 않는다.

실제 `.blend`/FBX/GLB, Unity `6000.5.3f1`, 유효한 Editor license가 없으면
이 검증은 Unity 실행을 대신하지 않으며, Import·Prefab·Play Mode 증거는 계속
`Blocked` 상태다.
