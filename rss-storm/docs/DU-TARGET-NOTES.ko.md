# DU 포화 목표 — 진행 기록 (2026-10-29)

목표: DU UE context cap 96(기본설정 가정), CU 96 이상에서 DU RRC storm 폭주 재현,
정상 UE 연결 불가.

## 확인된 사실

1. **DU의 96 상수는 코드에 없다.** OCUDU DU의 하드 한도는
   `MAX_NOF_DU_UES_PER_CELL = 2048`(include/ocudu/ran/du_types.h)이고, 실제 셀 한도는
   `min(PUCCH/SRS 자원 수, 2048)`로 계산된다(du_ran_resource_manager_impl.cpp:188).
   "기본 96"이 무엇을 가리키는지는 소스에서 확인하지 못했다. 실측이 필요하다.
2. **한 프로세스 다중 UE 한도 ≈ 10.**
   - N=8: 정상(동기 74, 시도 188)
   - N=10: 정상(동기 47, 시도 234)
   - N=12: 12 UE가 shared RX에 조인한 뒤 `Error, channel timeout`
   - N=20/60/101: RSS 배너 없이 초기화 단계에서 정지
   - 원인 후보: 공유 TX lockstep이 모든 UE의 write를 기다리는 구조에서 UE가 늘면
     정지. `RSS_SHARE_NUE=5`로 바꿔도 N=20은 실패.
3. CU는 `max_nof_ues: 200`으로 설정(≥96), DU ZMQ 직접 포트(4556/4557) 복원.
4. 브로커 경로(프로세스당 1 UE)는 정상. 5 UE까지 검증됨.

## 다음 단계 후보

- A: 10 엔드포인트 브로커 × 프로세스당 10 UE = 100 UE로 DU 포화 시도.
  플로우그래프 확장은 `add_vcc(1)`에 연결 추가로 가능(5 UE까지 검증).
- B: 공유 TX lockstep을 N>10에서도 동작하도록 수정(코드 변경, 리스크 큼).
- C: DU 실제 컨텍스트 한도를 먼저 실측(브로커 5×10=50 UE로 어디서 막히는지 확인).
