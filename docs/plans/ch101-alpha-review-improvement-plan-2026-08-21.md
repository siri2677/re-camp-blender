# CH101 Alpha Review 개선 계획

## 현재 판정

2026-08-21 Kaggle P100 실행에서 `03-CH101-TRIPOSR-001`이 overall `0.523413`으로
자동 Alpha Review 라우팅 기준을 통과했다. 이 결과는 후보 검토를 진행할 수 있다는 뜻이며,
사람 Gate B 승인이나 Production Mesh 승격을 의미하지 않는다.

```text
Alpha Review: 진행
sourceStatus: AI_GENERATED_CANDIDATE_NOT_PRODUCTION
gateB: PENDING_HUMAN_REVIEW
unityInputAllowed: false
productionPromotionAllowed: false
```

## Contact Sheet에서 확인된 개선 우선순위

1. 얼굴·헤어: 얼굴 정체성과 포니테일 구조를 승인 이미지에 맞춘다.
2. 의상: 재킷·쇼츠·스트랩·부츠의 분리와 비율을 보정한다.
3. 장비: 세이버·시스·리본·파우치의 실제 형상과 위치를 복원한다.
4. 색상·Material: 후보의 어두운 회색 표현을 승인 이미지의 색상 블록과 비교해 보정한다.
5. 형태·비율: 정면·측면·후면의 팔, 다리, 신발, 상체 비율을 재검토한다.

## 다음 실행 순서

1. 후보 03을 Alpha Review 기준 베이스로 보관한다.
2. 위 우선순위를 반영한 새 후보 또는 Blender 보정본을 만든다.
3. 동일한 refine → evaluate → score → rank 절차를 다시 실행한다.
4. 자동 점수 통과 후에도 Contact Sheet를 다시 만들어 사람 Gate B 검토를 받는다.
5. Gate B 승인 전에는 FBX/GLB Unity package, Production Mesh 승격, Unity Import을 실행하지 않는다.

현재 3회 TripoSR 후보가 이미 생성되었으므로, 다음 품질 개선은 추가적인 단순 재실행보다
참조 기반 보정 또는 다른 무료 멀티뷰 Provider 검토가 우선이다. 이 문서는 자동 생성 후보의
개선 방향을 고정하는 기록이며, 시각 승인을 대신하지 않는다.

## 강화된 자동 판정

단순 overall 점수만으로는 어두운 회색의 일반형 메시가 기술 기준을 통과할 수 있으므로,
`candidateAcceptance.visualReviewPolicy`를 별도로 적용한다. 현재 기준은 overall `0.60`,
silhouette `0.50`, appearance `0.55`, color `0.38`, face evidence `0.25`, technical
`0.90`이다. `scripts/ai3d/build_assisted_visual_review.py`가 이 기준으로 후보별
reason code를 생성하며, 하나라도 미달하면 `REJECT`와 `REGENERATE_REQUIRED`로 판정한다.

현재 EEVEE 후보는 overall `0.529061`, silhouette `0.452165`, appearance `0.540615`,
color `0.300492`이므로 강화 기준에서 자동 거절된다. 이 판정은 사용자의 반복 확인을
기다리지 않고 다음 후보 생성 여부를 결정하는 내부 QA 판정이며, 통과 후보도 사람 Gate B를
자동 승인하지 않는다.
