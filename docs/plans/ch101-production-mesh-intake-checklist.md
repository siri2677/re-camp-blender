# CH101 production mesh intake checklist

이 체크리스트는 실제 고해상도 CH101 production .blend를 Colab에서 기술 검증하고
Unity 전달 후보로 정리할 때 사용한다. 자동 검증 PASS는 시각 품질 승인이나 Gate B
승인을 의미하지 않는다.

## 파일을 준비하는 방법

1. Blender Desktop을 설치한다. Blender는 무료이며, 최종 모델링은 Colab보다 Desktop
   viewport에서 진행하는 것이 적합하다. Colab은 설치·배치 검증·렌더·압축에 사용한다.
2. 최신 CH101 승인 시트를 기본 디자인 입력으로 열고, references/CH101_A_FaceBustRotation_WIP_v012.png를
   얼굴·헤어·상체 비율 보조 기준으로 사용한다.
3. MPFB 바디나 기존 blockout을 사용한다면 기술 시작점으로만 사용한다. 얼굴·헤어·의상·장비를
   실제 표면에 맞춘 고해상도 production mesh로 직접 제작해야 한다.
4. 바디, 재킷·쇼츠·스트랩·부츠, 헤어·포니테일, 세이버·시스·리본·파우치를 각각 정리한다.
5. CH101 armature, UV, material, socket, weight를 정리한 뒤 기술 조건을 확인한다.
6. 파일을 CH101_A_HighRes_Production_v001.blend로 저장한다.

현재 자동화 스크립트가 만드는 primitive/styled/MPFB 결과는 이 파일을 대신하지 않는다.
그 결과를 이름만 바꾸거나 status만 수정해 production mesh로 처리하면 안 된다.

## 0. 입력 준비

- [ ] 파일 이름이 CH101_A_HighRes_Production_v001.blend인가
- [ ] 바디·의상·헤어·장비가 실제 표면에 맞춘 production mesh인가
- [ ] 현재 기술 WIP, primitive blockout, MPFB 단독 베이스를 입력으로 사용하지 않았는가
- [ ] 작업 기준 이미지와 제작 버전이 기록되어 있는가
- [ ] .blend 파일을 업로드할 수 있는가

## 1. Colab 실행

- [ ] 03_ch101_production_mesh_intake.ipynb를 연다
- [ ] 도구 저장소가 pinned commit c2f8247ec4fd9b29877ff38b92af64eca18f56aa로 checkout되는지 확인한다
- [ ] Blender와 xvfb-run 설치 셀을 실행한다
- [ ] production .blend 하나만 업로드한다
- [ ] Blender headless 검증 셀을 끝까지 실행한다

## 2. 기술 인테이크 PASS 기준

- [ ] MODEL_HIGH_BODY 컬렉션에 바디 메시가 있다
- [ ] MODEL_CLOTH_OUTFIT 컬렉션에 의상 메시가 있다
- [ ] MODEL_HAIR 컬렉션에 헤어 메시가 있다
- [ ] MODEL_EQUIPMENT 컬렉션에 장비 메시가 있다
- [ ] Socket_Equipment_Primary, Socket_VFXCenter, Socket_CameraFocus 공용 Socket이 있다
- [ ] 캐릭터별 상세 Socket과 Unity runtime alias가 모두 있다
- [ ] alias Socket은 원본 상세 Socket과 같은 Transform을 가리킨다
- [ ] CH101 armature와 Armature modifier가 있다
- [ ] 필수 socket 6개가 있다
- [ ] 모든 인테이크 메시의 UV가 있다
- [ ] 바디 triangle 수가 18,000 이하이다
- [ ] 장비 triangle 수가 2,000 이하이다
- [ ] material 수가 6개 이하이다 (`CHARACTER_3D_SPEC.md`와 Validator 공식 기준)
- [ ] scene status에 WIP 또는 NOT APPROVED가 없다
- [ ] ch101-mesh-intake-report.json의 status가 PASS이다

하나라도 실패하면 Unity에 전달하지 않고 production mesh를 수정한 뒤 다시 인테이크한다.

## 3. 산출물 보관

- [ ] ch101-mesh-intake-report.json을 보관한다
- [ ] production-mesh-handoff.json을 보관한다
- [ ] handoff의 sourceStatus가 PRODUCTION_MESH_READY인가
- [ ] handoff의 gateB가 PENDING_HUMAN_REVIEW인가
- [ ] .blend SHA256을 기록한다
- [ ] ZIP과 .sha256 파일을 다운로드한다
- [ ] 파일을 Git 일반 커밋 대신 Release, Drive, 또는 LFS 정책에 맞게 보관한다
- [ ] CH101~CH105 handoff 5개가 모두 준비되면 통합 manifest 병합 검증을 실행한다
- [ ] 병합 manifest의 unityInputAllowed가 false인지 확인한다

## 4. 사람 검토와 Unity 전달

- [ ] 정면·3/4·측면·후면에서 얼굴·헤어·의상·장비 실루엣을 검토한다
- [ ] 기준 이미지와 비율·색·디테일을 비교한다
- [ ] A-pose·idle·run·attack 변형을 검토한다
- [ ] 사람이 Gate A/B 승인 여부를 기록한다
- [ ] 승인 전에는 unityInputAllowed를 true로 바꾸지 않는다
- [ ] 승인 후에만 Unity Import, LODGroup, Prefab, Animator 검증을 시작한다

## 현재 상태

현재 저장소에는 실행 경로와 기술 검증기가 준비되어 있지만, 실제 고해상도 production
.blend가 없어 0단계와 1단계 실행 전 상태다. 현재 MPFB·primitive·styled 산출물은
검증용 WIP이며 이 체크리스트의 PASS 입력으로 사용할 수 없다. 공용 Socket 계약과
handoff 병합 도구는 준비됐지만, 실제 Unity Import는 사람 Gate B 승인과 production
FBX/GLB handoff 이후에만 허용된다.
