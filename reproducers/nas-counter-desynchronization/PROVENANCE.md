# 계보와 구현 기여

- 연구 원형: 5GReasoner의 Uplink NAS Counter Desynchronization. MITM이 invalid NAS SMC를
  반복 전송하고 UE의 reject를 차단해 UE·AMF 상향 NAS counter를 어긋나게 한다.
- 탐지 계약: 팀 L3-06은 선행 NAS SMC와 짝이 없는 상향 SecurityModeReject를 탐지한다.
  이는 원 논문의 전체 counter-wrap 공격보다 좁은 결과 신호다.
- 차용: 논문의 공격 흐름과 3GPP 메시지 의미만 참고했다. 외부 공격 코드는 복사하지 않았다.
- 자체 구현: OAI w38 UE one-shot 결과 패치(`patch/nas-counter-desync-result-w38.patch` 및
  `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`), control/emulation runner,
  TeleRAN·production detector·dashboard 종단 연결, 독립 차원 판정, 해시 봉인, matched
  campaign과 `p1q9-20261119` same-cell 6/6 검증을 구현·확인했다.
- 변경 경계: OAI UE만 수정한다. DU/CU·Open5GS·TeleRAN·detector 소스와 detector 임계값은
  수정하지 않는다.
- 주장 한계: 실제 invalid SMC 수신, MITM·reject drop, NAS counter wrap, 서비스 거부,
  OTA는 관측하지 않았다.
