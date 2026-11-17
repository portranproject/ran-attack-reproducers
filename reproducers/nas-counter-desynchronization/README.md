# 요청되지 않은 NAS SecurityModeReject 결과 (L3-06)

## 무엇을 재현하는가

5GReasoner의 원 공격은 MITM 기지국이 피해 UE에 무결성이 틀린 NAS
`SecurityModeCommand`를 반복 전송하고 UE의 `SecurityModeReject`를 정상 망에 전달하지 않아,
UE와 AMF의 상향 NAS counter를 어긋나게 만드는 공격이다.

현재 p5는 UE와 정상 gNB가 1:1로 연결된 ZMQ 환경이라 MITM·메시지 차단과 256회 counter
증가를 만들 수 없다. 따라서 이 모듈은 공격 원인이 아니라 탐지 문서 L3-06이 요구하는
**요청되지 않은 상향 `SecurityModeReject` 결과**를 실제 프로토콜 경로로 재현한다.

```text
control:   AuthenticationRequest → AuthenticationResponse → 정상 등록/PDU/ping
emulation: AuthenticationRequest → SecurityModeReject(1회) → UE→DU/CU→TeleRAN→detector
```

UE 패치만 사용한다. OCUDU DU/CU, Open5GS, TeleRAN, production detector의 소스와 임계값은
바꾸지 않는다. `observations.jsonl`은 TeleRAN 원문과 detector recorder의 SHA-256이 같아야
통과하며, 직접 생성한 `ue_evt`·`kpm2`를 detector에 주입하지 않는다.

## 성공 조건

- control: `SecurityModeReject=0`, L3-06 경보 0, Registration·PDU·ping 성공
- emulation: 실제 상향 `SecurityModeReject=1`, 그보다 앞선 NAS `SecurityModeCommand=0`,
  production L3-06 RAISE 1회, 대시보드 전송 성공
- 공통: 100 ms TeleRAN hello, seq 연속, gap 0, KPM 존재, UE crash 0
- 주장 고정: `live_protocol_path_observed=true`, `mitm_observed=false`,
  `invalid_smc_received_observed=false`, `nas_counter_wrap_observed=false`

서비스 거부는 합격 조건이 아니다. 원 공격 전체를 재현했다고도 주장하지 않는다.

## 실행

```bash
./ctl.sh setup l3-06 --profile p5
./ctl.sh run l3-06 control l3-06-control --profile p5
./ctl.sh run l3-06 emulation l3-06-emulation --profile p5 --enable
./ctl.sh campaign l3-06 l3-06-matched --profile p5 --enable
```

same-cell 진입점은 제공하지만 p5 자격은 미승인이다. 2026-11-17 정상 배경 5대+L3-06 UE
1대와 4대+1대 control 모두 broker 전환 뒤 정상 풀 health가 회복되지 않았다. direct 1셀
자격과 섞어 주장하지 않는다. 진단 실행은 다음과 같다.

```bash
./ctl.sh same-cell run nas-counter-desync -n l3-06-same-cell --count 5 -- \
  ./ctl.sh run l3-06 emulation l3-06-same-cell --enable
```

## 근거와 한계

- [5GReasoner](https://syed-rafiul-hussain.github.io/wp-content/uploads/2019/10/5GReasoner.pdf):
  Uplink NAS Counter Desynchronization의 MITM·invalid SMC·reject drop·counter divergence 원형
- [5G-SPECTOR](https://dev.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf):
  NAS/RRC 메시지 수준 관측으로 공격 흔적을 탐지하는 계보

실 SDR OTA, MITM relay, 잘못된 SMC의 실제 수신, 8-bit sequence wrap, 이후 정상 uplink NAS
폐기와 지속 DoS, 정상 UE same-cell 공존은 미검증이다. p5 direct 1셀 matched 결과는
[2026-11-17 자격 기록](artifacts/p5-live-result-20261117/)에 있다.
