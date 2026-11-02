# RRCSetupComplete 미전송형 대응 경로 감사 — 2026-10-30

## 결론

OCUDU 26.10의 기존 E2 제어와 코어 제어는 `RRCSetupComplete`를 보내기 전의 미완료
UE 컨텍스트에 닿지 않는다. 이번에 감사한 OCUDU 내장 경로 중, 소스 수정 없이 자연 타임아웃보다 먼저
context를 정리할 가능성이 확인된 후보는 **DU의 CSI-DTX → radio link failure(RLF)
→ F1 UE Context Release** 경로다. p5 ZMQ의 단일 UE 직렬 런에서 threshold 20으로
각 단계 집계가 20건씩 일치해 F1 release와 CU Setup 취소 전체 경로에 부합했다. 다만
외부 탐지기가 호출하는 대응 API가 아니라 DU 시작 시 적용하는
**정적·셀 전체 hardening**이다.

## 왜 기존 경로가 막히는가

RRCSetupComplete 미전송형은 Msg4를 ACK한 뒤 UE가 DU의 CellGroup을 적용하고 Msg5를 만드는 경로를 생략한다.
이 시점에는 DU/CU UE context·C-RNTI·F1AP ID·SRB1은 있지만 AMF/NGAP UE context,
DRB, PDU session과 확정 S-NSSAI는 없다. OCUDU도 SetupComplete 뒤에야
`InitialUEMessage`를 보낸다.

| 후보 | RRCSetupComplete 미전송형 도달성 | 판정 |
|---|---|---|
| E2 DU slice PRB quota | matching DRB/S-NSSAI가 필요 | 도달 불가 |
| E2 CU handover | AMF UE NGAP ID와 GUAMI가 필요 | 도달 불가 |
| Open5GS/AMF per-UE 제어 | `InitialUEMessage` 전이라 대상 UE가 없음 | 도달 불가 |
| `release <PCI> <RNTI>` | no-NG UE release 자체는 가능 | 같은 UE의 진행 중 Setup FIFO 뒤에 서므로 자연 타임아웃보다 늦음 |
| F1/SCTP eBPF drop | 메시지 drop이 조기 정리로 이어지지 않음 | 텔레메트리 전용으로 유지 |
| `cell_lock`·DU/RF 정지 | 모든 정상 UE도 끊김 | 비상 containment·positive control 전용 |
| `cell_bar` | 기존 context를 정리하지 못하고 비표준 공격 UE가 무시 가능 | 신규 정상 접속도 막는 셀 전체 수단 |
| CU hold-time 단축 | 정적으로는 가능 | 모든 정상 attach deadline을 줄이는 fallback, reactive 대응 아님 |

`cell_lock`/`cell_bar` WebSocket은 기본 비활성·loopback이고 인증 계층을 소스에서
확인하지 못했다. 필요하더라도 격리 랩의 loopback/SSH 경로 밖으로 노출하지 않는다.

## CSI-DTX RLF 경로

DU는 Msg3 단계에서 MAC UE와 PUCCH/CSI 자원을 먼저 만든다. MAC RLF detector는
CSI가 연속으로 decode되지 않은 횟수가 `pucch.max_consecutive_kos`에 닿으면 RLF를
한 번 알린다. 이후 t310이 끝나면 DU가 F1 UE Context Release Request를 보낸다.
CU의 DU-initiated handler는 release를 FIFO에 넣기 전에 pending RRC transaction을
취소하므로 진행 중 Setup을 실제로 깨울 수 있다.

기본 추정은 `100 × CSI 20 ms + t310 1000 ms ≈ 3 s`라 현재 CU hold 약 2초보다
늦다. `max_consecutive_kos=20`, t310=1000 ms면 명목상 약 1.4초다. MAC은
스케줄러가 CSI를 기대했다는 사실만으로 세지 않고 PHY가 `csi_part1_info`를 포함한
invalid UCI를 전달할 때만 센다. p5의 현재 OCUDU/ZMQ 경로에서는 RRCSetupComplete 미전송형 시도 20건과
그 조건의 RLF 로그 20건이 일치했다. 차폐 OTA와 다른 PHY·채널 조건은 여전히
미검증이다.

RRCSetup HARQ-ACK 억제형(과거 시나리오 값 `A_no_ack`)은 이 상태까지 도달하지 않을 수 있으므로 이 시험에는
`MSG4_ACK=1`인 DU ACK 확인 RRCSetupComplete 미전송형 후보만 쓴다. 임계치 0은 비교 조건상 발화하지 않고,
1은 CU F1 ID가 생기기 전 one-shot RLF가 소실될 수 있어 쓰지 않는다.

## threshold 100/20 최소 비교

1. 실행 전 DU 설정·바이너리·로그 원문의 SHA-256을 봉인한다.
2. 단일 저속 RRCSetupComplete 미전송형, `MSG4_ACK=1`, 기존 `max_consecutive_kos=100`으로 baseline을
   측정한다.
3. 다른 조건은 그대로 두고 `max_consecutive_kos=20`만 적용해 DU를 재시작한다.
4. 시도별로 다음 순서를 확인한다.
   `RLF detected` → t310 expiry → F1 Release Request → CU Setup cancelled →
   Release Command/Complete → context 제거.
5. 사전 판정 기준은 context lifetime <2초, Msg5·InitialUEMessage 0 유지,
   20회 중 18회 이상 DU-RLF 경로다. 단순 `no_reply`는 성공으로 세지 않는다.
6. 공격 실행 전후 정상 UE attach/PDU/ping 반복에서 unintended RLF 0을 확인한다.
7. 설정을 원복하고 DU를 재시작해 hash와 정상 UE를 다시 확인한다.

RLF가 안 생기면 threshold나 t310을 더 낮추지 말고 먼저 PHY invalid-CSI indication과
실제 CSI 주기를 확인한다. 정상 UE false release가 한 번이라도 나오면 이 후보를
폐루프 대응으로 승격하지 않는다.

## p5 ZMQ 실측

단일 UE·2초 시도 간격·`MSG4_ACK=1`로 비교했다. 기본 threshold 100에서는 10개
시도 모두 CSI RLF를 기록했지만, t310까지 기다리기 전에 기존 Setup 타임아웃이
context를 정리해 F1 release request는 0이었다.

threshold 20의 단일 UE 직렬 런에서는 다음 전체 경로의 각 단계 집계가 모두 20건으로
일치했다.

`CSI RLF` → `RLF timer expiry` → `F1 Release Request` → `CU Setup cancelled` →
`F1 Release Command` → `F1 Release Complete`

이는 20개 시도의 전체 경로와 부합하지만 시도별 F1/CU ID 조인 증거는 아니다.
Msg5·InitialUEMessage는 0이었다. 같은 threshold 20의 정상 UE 회귀 한 번에서는
Registration/PDU 성공, ping 20/20, unintended RLF 0이었다. DU 설정은 원본
SHA-256으로 원복했다. 원문 해시와 집계는
[실기 증거](../../../artifacts/label-v1-rlf20-20261030/README.md)에 있다.

ZMQ radio의 air time이 wall time보다 빠르므로 이 런의 wall-clock context 수명을
OTA 수명으로 일반화하지 않는다. 정상 회귀도 한 번뿐이라 장기·열악 채널의 false
release 위험을 제거하지 못했다.

사전 기준 가운데 각 단계 20건·Msg5/InitialUEMessage 0·설정 원복은 확인했다.
그러나 `<2초` 수명은 ZMQ 시간 왜곡 때문에 채점하지 않았고, 공격 전후 반복 정상 회귀와
원복 뒤 정상 UE 재검증은 수행하지 않았다. 따라서 §5의 안전 게이트 전체를 통과한 것은
아니다.

## 주장 경계

현재 성립하는 주장은 "정적 DU hardening으로 ZMQ RRCSetupComplete 미전송형 context를 조기 정리했다"까지다.
탐지기 판단 뒤 외부 인터페이스로 개별 UE에 적용한 것이 아니므로
**near-RT RIC 탐지→대응 폐루프**로 부르지 않는다. 폐루프 주장은 RRCSetupComplete 미전송형 시점에 닿는
실제 actuator와 독립 정상 UE 보존을 별도로 입증한 뒤에만 한다.

## 소스 근거

- [RRC setup procedure — SetupComplete 뒤 InitialUEMessage](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/rrc/ue/procedures/rrc_setup_procedure.cpp)
- [MAC RLF detector](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/mac/mac_sched/rlf_detector.h)
- [DU UE controller — t310 뒤 release](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/du/du_high/du_manager/du_ue/du_ue_controller_impl.cpp)
- [CU DU-initiated release — pending transaction 취소](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/cu_cp/du_processor/du_processor_impl.cpp)
- [E2 DU control executor](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/e2/e2sm/e2sm_rc/e2sm_rc_control_action_du_executor.cpp)
- [DU RIC configuration validation](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/du/du_high/du_manager/procedures/du_ue_ric_configuration_procedure.cpp)
- [E2 CU control executor](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/lib/e2/e2sm/e2sm_rc/e2sm_rc_control_action_cu_executor.cpp)
- [per-UE FIFO scheduler](https://gitlab.com/ocudu/ocudu/-/blob/e0db566a/include/ocudu/support/async/fifo_async_task_scheduler.h)
