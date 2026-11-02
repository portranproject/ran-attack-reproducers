# 공식 srsRAN GNU Radio 브로커로 다중 UE 재현 (2026-10-29)

## 결론

srsRAN이 제공하는 GNU Radio 다중 UE flowgraph를 확장한 broker가 우리 OCUDU gNB +
OAI UE 조합에서 3~5개 별도 UE 프로세스를 연결할 수 있음은 확인했다. 다만 이는
OAI에 대한 공식 지원이 아니며, 5 UE에서는 실행별 `sync=0` 시작 경합과 대조군 서비스
품질 변동이 남는다. 과거 teardown SIGSEGV는 OAI UE 종료 경합으로 특정해 2단계 종료로
해소했다. 커스텀 C broker는 폐기하고 이 flowgraph만 실험 자산으로 유지한다.

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

현재 5 UE 실행은 직접 명령보다 `bin/rss-broker-witness`를 사용한다. OAI endpoint를
먼저 열고 broker를 뒤에 시작하며, p5에서 Xvfb `:99`/xcb 실패가 있었으므로
`QT_QPA_PLATFORM=offscreen`을 쓴다. `sync_ues != 5`인 런은 공격 효과가 아니라
인프라 무효로 판정한다. 현재 실행기는 `BROKER_SYNC_TIMEOUT_S`(기본 30초) 안에 5/5가
되지 않으면 요청한 관측 창을 시작하지 않고 `startup.sync_timeout: true`로 정리한다.
직접 새 run id로 다시 실행하거나 `bin/rss-broker-witness-retry`를 사용한다. wrapper는
이 깨끗한 sync timeout만 `BASE-tryNN`의 새 run id로 제한 재시도하며 유효한 서비스
실패·의미적 무효·손상된 결과·teardown 이상은 재시도하지 않는다.

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

## 2026-10-29: 독립 프로세스 RA-only admission probe의 CU 거부 관측 (CU 10)

- 공격 2대 + 증인 1대(ra_only, 1초 간격)를 **각각 별도 프로세스**로 브로커에 연결.
- 3대 모두 동기(재시도 2회째). 공격 179회/60초.
- 증인: `probe_attempt` 12회, **`rrc_reject` 14회**, `msg4_rx` 2회.
  거부는 air_ms 1.95초~7.63초 구간에 몰려 있었다.
- 이는 **독립 프로세스 RA-only admission probe가 CU로부터 RRCReject를 받은 첫 관측**이다.
  probe는 Msg5를 생략하므로 정상 UE나 서비스 witness가 아니다. 또한 이 런의 공격량이 179회로 낮아
  CU 포화가 약했으며, (c) 계측 구간이 짧다. 수치를 그대로 주장에 쓰기엔 부족하다.
- 개선: 공격 UE를 3~5대로 늘리고(플로우그래프 확장), 증인을 일반 Msg5 모드로
  바꿔 전체 60초 구간의 거부율을 측정해야 한다.

## 2026-10-29: 독립 프로세스 RA-only admission probe 전체 구간 측정 (CU 10)

- 구성: 공격 2대 + 증인 1대(ra_only, 1초 간격), 각각 별도 프로세스, 공식 브로커.
- 공격: 825회/60초.
- 증인: 시도 49회, `msg4_rx` 12회, **`rrc_reject` 63회**.
  거부는 air_ms 1,940~30,870 구간 전체에 걸쳐 발생.
- CU admission limit 로그: 최근 구간 약 202회.
- 해석: RA-only probe의 셋업 요청 중 약 84%가 CU admission에서 거부됐다.
- 한계: probe가 `ra_only`(Msg5 생략)라 정상 UE의 PDU 서비스 실패가 아니다. 84%이므로
  "항상 불가"는 아니고 "대부분 거부"다. 5 UE 브로커 확장은 GNU Radio add 블록이
  2입력 전용이라 실패(어댑터 체인으로 재구현 필요).

## 2026-10-29: 브로커 5 UE 확장 성공

- 공식 플로우그래프를 5 UE로 확장했다: UE4 2400/2401, UE5 2500/2501.
  `blocks.add_vcc(1)`는 2입력 전용이 아니라 다중 입력 연결을 받는다(초기 시도에서
  인자를 잘못 줘 실패했던 것). `add_vcc(1)`로 두고 연결만 추가하면 된다.
- 확장 파일: `reproducers/rrc-signaling-storm/tools/multi_ue_5ue.py` (5 UE 스모크에서 5대 모두
  동기·SIB1·RRCSetupComplete 확인).
- 4공격+1증인 실패: 두 번의 시도 모두 동기 실패(브로커/DU 시작 경합). 5 UE로
  늘리면서 경합이 더 자주 발생하는 것으로 보인다. 재시도 횟수를 늘려 재측정 필요.

## 2026-10-29: 5 UE 브로커에서 RA-only 요청 97% 거부 (CU 10)

- 구성: 공격 4대 + 증인 1대(ra_only 1초 간격), 각각 별도 프로세스, 5 UE 공식 브로커.
- 4번째 시도에서 전원 동기.
- 공격: **1,290회/60초**.
- 증인: 시도 52회, `msg4_rx` 3회, **`rrc_reject` 96회 → 97% 거부**.
  거부는 air_ms 1,640~23,220 구간 전체에 걸쳐 발생.
- CU admission limit 로그: 최근 구간 **628회**.
- 해석: CU 부하 상태에서 같은 셀 RA-only admission probe의 RRC 셋업 요청이
  97% 거부됐다. 정상 UE 서비스 거부율로 읽지 않는다.
- 남은 한계: probe가 `ra_only`(Msg5 생략)라 PDU까지의 완전 접속 실패는 아니다.
  3%는 수락되므로 문자 그대로 "항상 불가"는 아니다.

## 2026-10-29: 6 UE 확장 시도 — 동기만 되고 SIB1 미달

- 6 UE(공격 5 + 증인 1)로 확장해 시도했다(포트 2600/2601 추가, `add_vcc(1)`에 6번째 연결).
- 2번째 시도에서 6대 모두 `Initial sync`까지 갔으나, **SIB1 디코드/RRC 셋업이 진행되지
  않았다.** 증인 로그에는 `setup_req_prebuilt`만 쌓이고 `attempt_start`가 없었다.
- 즉 6 UE에서는 DL 분배가 SIB1 단계를 넘기지 못한다. 5 UE는 기능상 확인된 상한이지
  안정 상한은 아니다.
- 결론: 5 UE 구성의 **RA-only 요청 97% 거부(공격 1,290회/60초)**가 당시 최고 관측이다.

## 2026-10-29: 97% 결과 재현 (5 UE 브로커, CU 10, 4공격+1증인)

| 런 | 공격 시도/60초 | 증인 시도 | Msg4 | Reject | 거부율 |
|---|---|---|---|---|---|
| 라운드 46 | 1,290 | 52 | 3 | 96 | 97% |
| 라운드 48 | 372 | 21 | 4 | 27 | 87% |

- 두 런 모두 5대 동기(재시도 4회째), 거부는 런 전 구간에 걸쳐 발생.
- 거부율은 공격 시도량을 따라간다(1,290회→97%, 372회→87%). 즉 공격이 셀을 오래
  점유할수록 정상 UE의 셋업 성공률이 떨어진다.
- 결론: CU 부하 시 같은 셀 독립 RA-only probe의 RRC 셋업 요청이 **87~97% 거부**됐다.
- 한계: probe는 `ra_only`(Msg5 생략)다. 정상 UE의 Registration/PDU 서비스 거부를
  입증하지 않으며 문자 그대로 "항상 불가"도 아니다.

## 2026-10-29: CU guard 4초 실험 — 개선 없음 (92%)

- CU의 미완료 UE 유지 시간(`rrc_procedure_guard_time_ms`, 기본 1,000 ms)을 4,000 ms로
  늘려 슬롯이 비는 빈도를 줄여 보았다.
- 결과: 공격 1,264회/60초, 증인 시도 51, msg4 7, **reject 77 → 92%**.
  guard 1초(97%)와 유의한 차이가 없다. 오히려 무작위 변동 범위다.
- 해석: CU admission은 "요청이 도착한 순간 슬롯이 비어 있으면 수락"한다. 유지 시간을
  늘려도 증인의 1초 간격 시도가 빈 순간에 걸릴 확률은 남는다. 공격량을 더 늘리지 않는
  한 100%는 구조적으로 어렵다.
- 실험 후 CU 설정은 원복했다(guard 제거, max_nof_ues 10 유지).

## 2026-10-30: curated 일반 witness 서비스 attack-on/off 비교

RSS 옵션을 첫 RRC 호출에서 lazy 등록하던 결함 때문에 broker 지연 시 OAI가
`--rss.*` 36개를 unknown으로 판정하고 종료하는 문제가 있었다. curated 패치에서
`nr_rss_config_init()`를 radio 시작 전에 호출하도록 고친 뒤 5개 별도 OAI 프로세스가
60초 관측 창을 생존했다. 뒤따르던 `zmq_write()` channel-0 assertion은 종료 경로의
2차 증상이었다.

조건은 DU `nof_cell_sr_res: 1`(부팅 로그상 12 UE 상한), PRACH 64, CU cap 200인
통제된 saturation profile이다.

| 런 | 모드 | sync | 공격 시도 | 일반 witness 서비스 |
|---|---|---:|---:|---|
| r21 | control | 5/5 | 0 | attach 6 s, Registration/PDU 성공, ping 40/264 |
| r2 | attack | 5/5 | 8, Msg5 0 | Registration/PDU/tunnel/ping 실패 |
| r3 | attack | 5/5 | 294, Msg5 0 | attach 50 s, Registration/PDU 성공, ping 51/52 |

r8 control도 attach 39초, Registration/PDU, ping 102/102에 성공했지만 이전 validator가
load UE의 정상 Msg5를 공격 Msg5로 오인해 진단용으로만 남겼다.

일반 Msg5 witness의 결과는 공격군에서 실패/성공으로 갈렸다. 공격량이 더 큰 r3에서도
서비스가 성립했으므로, 앞의 87~97% 결과는 **ra_only admission 계측**으로만 유지하며
일반 UE의 지속 DoS로 확대 해석하지 않는다. 현재 입증된 것은 별도 프로세스 일반
witness 경로와 서비스 측정 도구의 성립, 그리고 서비스 영향의 비결정성이다.

5/5 sync 미달 조기 종료와 종료 상태 출처 기록을 실행기에 추가했다. 결과의
`teardown.ue_exit_statuses`/`broker_exit_status`는 관측 경계에서 동결한
`crash_markers`와 분리된 진단값이다. 과거 r21/r3의 kernel journal은 충돌 주체가
broker가 아니라 OAI UE `UL__actor`였음을 보였고, 주소 `0x53737a`는 curated 바이너리의
`nr_ra_procedures.c:789 init_RA()`로 매핑됐다. OAI w38의 첫 INT는 NAS deregistration
요청이라 UE마다 INT를 0.2초 간격으로 두 번 보내고 최대 5초 기다리도록 고쳤다.
후속 사전 고정 control 15회는 sync timeout 60초·관측 60초로 실행했다. 30초 이내
5/5 sync는 5회, 31~60초의 늦은 sync는 0회, clean timeout은 10회였다. sync 성공
5회 중 유효 control은 3회, 의미적 무효는 2회였다. 15회 모두 UE와 broker가 clean
teardown했고 SIGSEGV는 0회였다. 유효 3회의 attach는 1~36초, ping 손실은
0.833333%~93.5484%였다. 60초가 추가 성공을 만들지 않았으므로 운영상 30초 기본값은
유지하지만 N=15로 percentile이나 성공률을 보장하지 않는다. fail-fast와 제한 재시도는
시작 경합이나 control 품질 변동을 해결하지 않는다. 따라서 broker는 디버그·경로
확인용이며 안정 서비스, 공격 효과 또는 정상 사용자 DoS의 증거로 사용하지 않는다.
과거 control/attack 원문 해시는
[`artifacts/broker-witness-20261030/`](../../../artifacts/broker-witness-20261030/)에,
종료 원인·수정·재시도 검증은
[`artifacts/broker-stability-20261030/`](../../../artifacts/broker-stability-20261030/)에,
15회 고정 control 캠페인은
[`artifacts/broker-sync-sampling-20261030/`](../../../artifacts/broker-sync-sampling-20261030/)에
있다.
