# 상시 셀 + 공격 슬롯 설계 (2026-11-24)

목표: **셀(CU·DU·broker)과 정상 UE 5대를 상시 유지하고, 공격만 그 위에서 켜고 끈다.**
공격마다 정상 UE 5대를 초기화하지 않는다.

## 왜 지금은 cold-start인가

p5의 ZMQ 가상 RF는 **샘플 위치(positional)** 로만 시간을 맞춘다. GNU Radio broker는
DU 하향을 복제하고 UE 상향을 요청/응답 lockstep으로 합산한다
(`workloads/normal-ue/tools/same_cell_broker.py:61-120`). 전송 계층에는 여러 프로세스가
공유하는 무선 timestamp가 없다. OAI ZMQ radio의 `rx_stream`/`tx_stream` 카운터는 각
프로세스가 시작할 때 0(정확히는 1 tick)에서 시작한다
(`radio/zmq/zmq_radio.cpp`의 `zmq_start`, `radio/zmq/zmq_imported.cpp`의 `start(init_time)`).

따라서 실행 중 새 UE 프로세스를 넣으면 그 UE의 sample cursor는 0부터인데 DU는 이미 T
샘플을 처리 중이다. broker는 새 UE의 상향 블록을 **현재 출력 위치**에 합산하므로, UE가
slot T+n용으로 만든 상향이 DU의 slot n 위치에 들어간다. PRACH/PUSCH의 slot 번호와
RA-RNTI가 어긋나 RAR 복호가 0이 된다. 이것이 2026-11-13에 관측된 실패의 원인이다.

실측 근거:

- 프로세스 교체: 정상 UE 5/5로 시작했으나 대기 UE를 새 프로세스로 바꾼 뒤 정상 UE가
  0/5가 되고 120초 안에 회복하지 못했다. REQ source를 재생성해도 기존 RF 시간축과
  합쳐지지 않았다. `workloads/normal-ue/docs/SAME-CELL-HOT-SWAP-20261113.md:29-45`
- flowgraph 재배선: `lock()/unlock()`만으로도 정상 UE가 재접속 상태로 내려갔다. 같은 문서
  `:37-43`
- 정적 selector + DL warmup: `Initial sync`·SIB1까지는 갔으나 `RAR-Msg2 decoded=0`,
  `Registration Accept=0`. 정상 UE도 5/5→0/5로 무너졌다. 같은 문서 `:42-50`
- 독립 victim·attacker ZMQ 프로세스의 상향 시간축 불일치로 victim Registration 0:
  `reproducers/blind-dos/artifacts/p5-same-cell-limit-20261116/README.md`

즉 cold-start는 상태 오염 회피가 아니라 **샘플 시간축을 0부터 함께 시작시키기 위한
필수 조건**이다. 공식 hot-plug 기능도 없다. srsRAN 다중 UE broker도 lockstep이고,
OAI ZMQ radio는 공유 timestamp를 전달하지 않는다.

## 채택안: 예약 슬롯 선기동(pre-started attack slot)

새 UE를 나중에 넣는 대신, **공격 UE 프로세스를 셀 시작 전에 미리 띄워 슬롯에 고정**하고
공격은 이득 gate로 켠다. 이 방식은 이미 `same-cell-run`의 persistent attack slot으로
구현돼 있다(`workloads/normal-ue/bin/same-cell-run:473-500`, broker의
`NORMAL_UE_BROKER_PERSISTENT_ATTACK=1`).

```
cell up  : broker(예약 슬롯 K개) + 정상 UE 5 + [모듈별 공격 UE/runner 선기동] + DU
attack run <module> : 해당 슬롯 gate 0→1, 라벨 기록, 종료 뒤 1→0
cell down: 슬롯 UE·broker·DU 종료 (CU·코어는 유지)
```

- 정상 UE 5대와 DU·broker는 `cell up`~`cell down` 동안 유지된다.
- 공격 UE는 셀 시작 전에 시작해 sample clock을 DU와 맞춘다. 프로세스는 상시 살아 있고
  **공격 동작만** gate로 켜고 끈다.
- 모듈 전환은 "새 UE 삽입"이 아니라 "다른 예약 슬롯의 gate 열기"다. 한 세션에서 여러
  모듈을 돌리려면 그 모듈들의 슬롯을 `cell up` 때 함께 선기동한다.

### 슬롯 예산

broker endpoint 상한은 15개다(`same_cell_broker.py`의 endpoint 상한). 정상 UE 5대를 빼면 공격
슬롯은 최대 10개다.

| 모듈 | 필요 슬롯 | 비고 |
|---|---:|---|
| L3-06 NAS counter 비동기화 | 1 | 단일 UE |
| L3-24 하향 IMSI | 1 | 단일 UE |
| L3-14 UE capability | 1 | 단일 UE |
| L3-21 상향 credential flood | 1 | 단일 UE가 10개 실패 연결 생성 |
| L3-20 Blind DoS | 2 | victim+attacker |
| L3-01-O 인증 미응답 | 10 | 2프로세스×5 UE |
| L3-01-V RRC storm | 12 | 6프로세스×2 UE — 슬롯 상한 초과 |

L3-01-V는 현재 토폴로지로는 한 셀 예약 슬롯에 들어가지 않는다. 슬롯 상한을 늘리려면
broker를 다중 프로세스로 나누거나 RSS UE 수를 줄이는 별도 결정이 필요하다.

## 현재 구현 상태

- `./ctl.sh cell up|down|status --profile p5`: broker·DU·정상 UE 5대 상시 유지. 구현됨.
- `./ctl.sh attack run <module>`: 예약 슬롯 선기동 배선 전. 현재는 fail-closed로
  거부하고 `cell up --modules` 설계를 안내한다.
- `same-cell run|campaign`: 옛 cold-start 운영 경로. `docs/BOUNDARY.md`에 따라 운영
  도구로 분류하며, 새 공격 도구의 기본 진입점이 아니다.

## 남은 일

1. `cell up --modules <m1,m2,...>`가 모듈별 runner를 예약 슬롯에 선기동하도록
   `same-cell-run`의 `start` 경로를 확장한다.
2. 각 runner에 슬롯 번호·gate 파일을 주입하고, `attack run`이 해당 슬롯만 0→1로 바꾼다.
3. 정상 UE 5/5를 공격 전·중·후로 기록하고, 탐지 경보는 운영 도구가 별도로 관측한다.
4. L3-01-V는 슬롯 예산을 넘으므로 UE 수를 줄인 변형을 별도 승인받는다.
