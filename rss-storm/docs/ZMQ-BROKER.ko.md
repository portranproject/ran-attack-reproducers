# ZMQ 브로커 (다중 UE 독립 접속) — 설계와 현재 상태

2026-10-28.

## 왜 필요한가

OAI의 ZMQ 무선 드라이버는 셀당 스트림 하나를 전제로 한다.

```
DU  TX: REP bind 4556     UE RX: REQ connect 4556
DU  RX: REQ connect 4557  UE TX: REP bind 4557
```

그래서 UE 프로세스 하나가 4557을 독점하고, 여러 UE는 한 프로세스 안에서 상향을 합쳐
쓰는 방식이었다. 이 방식에서는 정상 UE(증인)를 같은 셀에 독립적으로 둘 수 없다
(배치 포함 시 공격률 붕괴, 제외 시 증인 UL 미전달 — `docs/KNOWN-ISSUES.ko.md` §4).

브로커는 DU와 UE 사이에 들어가 DU에는 UE 하나처럼 보이고, 뒤에서 N개의 UE를
독립 프로세스로 연결한다. OAI 소스는 수정하지 않는다. UE는 CLI의 ZMQ 주소만
브로커 포트로 바꾼다.

## 포트 배치

| 방향 | DU 쪽 | 브로커 | UE i 쪽 |
|---|---|---|---|
| DL (DU→UE) | REP bind 4556 | REQ connect 4556 (수집), REP bind 4601+2i (배포) | REQ connect 4601+2i |
| UL (UE→DU) | REQ connect 4557 | REP bind 4557 (DU에 응답), REQ connect 4600+2i (UE에서 수집) | REP bind 4600+2i |

실행:

```
/root/zmq_broker <n_ue> [dl_du=4556] [ul_du=4557] [ue_ul_base=4600]
# UE i:  --zmq.[0].tx_channels tcp://127.0.0.1:$((4600+2i))
#        --zmq.[0].rx_channels tcp://127.0.0.1:$((4601+2i))
```

## 구현

- **DL 스레드**: DU에서 블록을 계속 당겨 FIFO(256)에 넣고, UE의 요청이 있으면 큐의
  가장 오래된 블록을 보낸다. 큐가 비면 마지막 블록을 다시 보낸다. 초기 구현은 최신
  블록만 보내서 UE가 몇 백 프레임마다 동기를 잃었다.
- **UL 스레드**: DU의 요청마다 UE 각각에서 블록을 하나씩 당겨 합산(포화 덧셈)하고
  한 번에 응답한다. UE가 아직 없으면 11520샘플 무음으로 응답하고, 이때만 실시간
  (0.5 ms/블록)으로 페이싱한다. 실제 UE 블록이 있으면 UE의 생산 속도가 곧 페이싱이다.

## 현재 상태 (2026-10-28)

- 빌드: `gcc -O2 -pthread -o /root/zmq_broker tools/zmq_broker.c -lzmq`
- DL 경로 동작 확인: UE가 브로커를 통해 `Initial sync successful, PCI: 1`을 얻고
  **`SIB1 decoded`까지 성공**했다. RF overflow 0, UL 페이싱 약 2,000블록/s.
- UE 로그로 확인한 배선: `TX socket ... bound to 4600`, `RX socket ... connected to 4601`.
- 막힌 곳: UE가 브로커로 상향 블록을 전혀 내보내지 않는다(`used_ue=0`, 5초 대기로도).
  그래서 `RA-Msg3 transmitted`가 0이고 접속으로 진행하지 못한다.
- 회귀 하나 기록: DL fetch를 소비자 속도로 조절하면 DU의 TX 큐가 넘쳐 RF overflow가
  386만 회 발생했다. DU는 계속 당겨야 하고, 버퍼(1024블록)로 흡수해야 한다.

### 2026-10-28 후반 갱신

- UL이 흐르기 시작했다. 원인은 REQ 소켓의 미결 요청 상태였다. 타임아웃 뒤 다시
  보내면 EFSM으로 실패하고 UE의 늦은 응답을 영원히 회수하지 못했다. UE별
  `ul_await` 상태로 요청/응답을 맞추자 `used_ue=1`이 되었다.
- UE는 11520샘플이 아니라 4슬롯(46080샘플)씩 보낸다. 그대로 DU에 넘기면 DU의
  샘플 시계가 4슬롯씩 점프해 정렬이 깨진다. 브로커가 11520샘플 단위로 잘라
  넘기도록 고쳤다(나머지는 UE별 버퍼에 보관).
- 진행: UE가 `SIB1 decoded` → `4-Step CBRA procedure` 시작까지 도달했다.
  아직 `RA-Msg3 transmitted`가 0이고 접속 전에 재동기한다.

### 2026-10-28 저녁: 단일 UE 완전 접속 성공

- UE별 미결 요청 상태와 11520샘플 절단에 더해, **첫 실제 상향 블록이 나올 때까지
  DU에 응답하지 않도록** 고쳤다. 무음을 먼저 보내면 샘플 축이 밀려 PRACH가 DU 창을
  벗어나던 문제다. 스트림이 시작된 뒤에는 슬롯마다 무음(0)을 더한다.
- 결과(1 UE): `Initial sync successful` → `RRCSetupComplete` → `Registration Accept`
  → `PDU Session Establishment Accept`, UE IPv4 10.45.1.2. RF overflow 0.
  브로커 경유로 정상 UE가 완전히 접속한 첫 사례다.
- 결과(2 UE): 두 UE 모두 동기 획득(sync=1)했고 상향도 흐르지만, Msg3 전에 두 프로세스가
  모두 SIGSEGV로 종료됐다. 원인 미확정. 다음 라운드에서 gdb로 백트레이스를 잡는다.

### 남은 문제 (추정)

- UL 스트림 정렬. UE가 첫 블록을 내기 전에 브로커가 무음을 넣으면, 그 무음이
  UE의 실제 샘플 축을 밀어 PRACH 위치가 DU의 탐색 창과 어긋난다. UE의 첫 블록이
  나올 때까지 DU 시계를 세우지 않고, 첫 블록부터 1:1로 흘리는 방식이 필요하다.

## 다음 진단

1. 브로커의 UE별 요청/응답 카운터를 찍어, UE의 `zmq_tx_channel`이 요청을 받고도
   응답하지 않는지(데이터 없음) 아니면 요청 자체가 전달되지 않는지 구분한다.
2. UE 쪽에서 RA 시작 여부(`Initialization of 4-Step CBRA procedure`)와 PRACH 송신을
   확인한다. SIB1 이후 RA가 시작되지 않으면 RRC idle 진입 문제를 본다.
3. UE의 REP가 "데이터가 있을 때만" 응답한다면, 브로커는 요청을 보낸 채 기다리는
   대신 UE가 실제로 송신하는 슬롯에만 요청하도록 바꾼다.

## 다음 단계

1. DL 배포 경로 수정(전용 스레드 + 큐)으로 단일 UE 접속 완료.
2. 2 UE(공격 1 + 증인 1)로 확장해 각 UE가 독립적으로 붙는지 확인.
3. CU `max_nof_ues` 90 이하에서 공격 5 UE + 증인 1 UE를 브로커로 실행해, 증인이
   지속적으로 거부되는지 측정. (이것이 목표 재현)
4. 성공 시 `rss-run`에 브로커 모드(`--broker`)를 넣어 재현 절차를 자동화.
