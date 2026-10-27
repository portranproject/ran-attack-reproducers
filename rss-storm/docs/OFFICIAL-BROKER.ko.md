# 공식 srsRAN GNU Radio 브로커로 다중 UE 재현 (2026-10-29)

## 결론

srsRAN/OCUDU가 문서로 제공하는 **공식 다중 UE 브로커**(GNU Radio 플로우그래프)가
우리 OCUDU gNB + OAI UE 조합에서도 **그대로 동작**한다. 커스텀 브로커를 만들 필요가
없었다. UE 3대가 동시에 `Initial sync` → `SIB1` → `RRCSetupComplete`까지 도달했다.

## 왜 되는가

- OCUDU의 ZMQ 장치는 `ZMQ_REP`(TX)/`ZMQ_REQ`(RX)를 쓴다(`lib/radio/zmq`).
- 공식 브로커 플로우그래프도 `zeromq_rep_sink`/`zeromq_req_source` = REQ/REP다.
- OAI UE의 `oai_zmqdevif`는 OCUDU-ZMQ 상호운용 패치로 같은 프로토콜을 말한다.
  그래서 브로커를 사이에 넣어도 양쪽이 그대로 연결된다.

## 구성

- gNB(`du.yaml`): `tx_port=tcp://127.0.0.1:2000,rx_port=tcp://127.0.0.1:2001`
- 브로커(GNU Radio):
  - DL: `req_source` → gNB 2000, `rep_sink` → UE 2100/2200/2300
  - UL: `req_source` ← UE 2101/2201/2301, `rep_sink` → gNB 2001
- UE i 포트: `tx = 21xx1`, `rx = 21xx0` (UE1 2101/2100, UE2 2201/2200, UE3 2301/2300)

## 절차

```
# DU 호스트
apt-get install -y gnuradio xvfb
curl -sL https://docs.srsran.com/projects/project/en/latest/_downloads/0e089ea8fa3a22bf1eec673ab3dffd94/multi_ue_scenario.grc -o /root/multi_ue.grc
grcc /root/multi_ue.grc                     # -> ~/multi_ue_scenario.py
sed -i "s/11520000/23040000/" ~/multi_ue_scenario.py   # 우리 셀 srate

# 1) CU(코어/RIC/CU) 먼저, 2) DU 새로 시작, 3) UE 3개, 4) 플로우그래프
./ctl.sh start
timeout 75 nr-uesoftmodem ... --zmq.[0].tx_channels tcp://127.0.0.1:2101 --zmq.[0].rx_channels tcp://127.0.0.1:2100 &
timeout 75 nr-uesoftmodem ... --zmq.[0].tx_channels tcp://127.0.0.1:2201 --zmq.[0].rx_channels tcp://127.0.0.1:2200 &
timeout 75 nr-uesoftmodem ... --zmq.[0].tx_channels tcp://127.0.0.1:2301 --zmq.[0].rx_channels tcp://127.0.0.1:2300 &
sleep 3
xvfb-run -a timeout 60 python3 ~/multi_ue_scenario.py
```

## 실측 (CU cap 30)

- 정상 UE 3대(스톰 없음): 3대 모두 `Initial sync`, `SIB1 decoded`, `RRCSetupComplete`.
  (같은 IMSI 3개라 NAS 등록은 경합해 해제됨.)
- 공격 2대 + 증인 1대: 3대 모두 동기. 증인(정상 Msg5 경로)은 **28회 시도, 접속 0회**.
  단 `attempt_end`가 전부 `no_msg4`였다. 즉 이번 실패는 CU 거부가 아니라 **RA 단계
  실패**다. 공격 UE의 PRACH 부하로 증인의 RA가 먼저 무너진 것이다.

## 다음 단계

1. 공격 UE를 1대로 줄이고(RA 경합 완화) CU 포화는 유지되는지 확인. CU 30에서 1대
   ~16회/s면 점유 42로 포화가 유지된다.
2. `cell_cfg.prach`에 `total_nof_ra_preambles: 64`, `nof_ssb_per_ro: 1`,
   `nof_cb_preambles_per_ssb: 64`를 넣어 PRACH 경합을 완화(공식 문서 권장).
3. 그 상태에서 증인의 `actual_reach`가 `rrc_reject`로 바뀌는지 확인. 그것이 목표
   (CU 과부하로 정상 UE 연결 불가)의 직접 증거다.

## 참고

- 공식 문서: https://docs.srsran.com/projects/project/en/latest/tutorials/source/srsUE/source/index.html
- 플로우그래프 다운로드: `.../_downloads/0e089ea8fa3a22bf1eec673ab3dffd94/multi_ue_scenario.grc`

## 2026-10-29 추가 실측: RA 단계에서 막힘

- 공격 1대 + 증인 1대 + 유휴 UE 1대(총 3)로 CU 30에서 60초 실행.
- 3대 모두 `Initial sync`까지 성공. 그러나 **유휴 UE까지 포함해 전원이
  `RRCSetupComplete`에 도달하지 못했다.** 증인은 19회 시도, 전부 `no_msg4`.
- 공격 UE도 3~5회 시도에 그쳤다. 즉 공격 강도 이전에, 브로커를 경유한 상태에서
  RA(Msg3/Msg4)가 안정적으로 성립하지 않는다.
- 같은 구성의 초기 스모크 테스트(정상 UE 3대)에서는 3대 모두 `RRCSetupComplete`가
  나왔다. 즉 **간헐적으로 성립하지만 안정적이지 않다.**

### 원인 후보

- 플로우그래프의 `blocks_throttle`+`slow_down_ratio`(기본 4)가 샘플을 1/4 속도로
  흘린다. srsUE는 이에 맞춰 설계됐지만, OAI UE의 PHY/타이밍은 실시간 샘플을
  전제로 해서 UL 타이밍이 어긋날 수 있다.
- 다음 시도: `slow_down_ratio`를 1로 두고(스로틀 제거 효과) 같은 실험을 반복한다.

### 다음 단계

1. `slow_down_ratio=1`로 변경해 RA 성립 여부 확인.
2. 성립하면 공격 1대 + 증인 1대로 CU 거부(`actual_reach=rrc_reject`) 확인.
3. 계속 불안정하면 공식 브로커는 srsUE 전제임을 인정하고, 좁은 증거로 마무리.

## 2026-10-29: slow_down_ratio=1 실측

- 플로우그래프의 `slow_down_ratio`를 4→1로 낮추자 정상 UE 3대가 안정적으로
  `Initial sync` → `SIB1` → `RRCSetupComplete`(1대는 `Registration Accept`까지)에
  도달했다. 스로틀이 RA 불안정의 한 원인이었음이 확인됐다.
- 같은 조건에서 공격 1 + 증인 1 + 유휴 1(CU 30): 공격 696회/60초, 유휴 UE 접속,
  증인은 3회 시도 후 **1회 접속**했다. CU 30에서는 1스톰으로 포화가 확실하지 않았다.
- CU 20으로 낮춰 재시도: 이번에는 3대 모두 동기 실패(브로커 시작 경합).
  같은 구성이 어떤 실행에서는 되고 어떤 실행에서는 안 되는 **시작 경합**이 남았다.

### 현재 상태

- 공식 브로커 경유로 (a) 정상 UE 3대 동시 접속, (b) 공격 UE 696회/60초 가동까지는
  확인됐다.
- 목표 증거(증인의 CU 거부, `actual_reach=rrc_reject`)는 아직 못 잡았다.
  남은 변수는 브로커 시작 순서/타이밍의 안정화다.

## 2026-10-29: PRACH 프리앰블 확장 후 (CU 10~20)

- `du.yaml`의 `cell_cfg`에 공식 문서 권장값을 넣었다.
  `prach: { total_nof_ra_preambles: 64, nof_ssb_per_ro: 1, nof_cb_preambles_per_ssb: 64 }`
- 효과: 브로커 경유 3 UE 스모크에서 3대 모두 접속. 공격 실행에서도 유휴 정상 UE가
  정상 접속했다(이전에는 RA 실패).
- CU 10, 공격 2 + 증인 1: 동기 3/3, 공격 시도 839회/60초, CU admission 거부 약 150회.
  그러나 증인은 **첫 시도에 접속**했다. CU admission 카운터가 해제/재점유로 진동해
  단일 시도가 빈틈에 들어가는 패턴이 반복됐다.

### 결론

- 공식 브로커 + PRACH 설정으로 "독립 프로세스의 정상 UE"가 같은 셀에 붙는 환경은
  갖춰졌다.
- 다만 정상 UE의 **첫 시도가 매번 수락**되어, "완전 연결 불가의 지속"은 재현되지
  않는다. CU는 설계대로 초과분을 거부하고, 남는 틈으로 정상 UE를 받아들인다.
- 가능한 남은 선택지: (a) 증인을 ra_only(상시 재시도)로 두어 거부율을 측정(이미 확보한
  63%·56% 증거와 같은 성격), (b) 4 UE 이상 브로커로 공격을 더 키워 틈을 없애기,
  (c) 현재 증거로 확정.
