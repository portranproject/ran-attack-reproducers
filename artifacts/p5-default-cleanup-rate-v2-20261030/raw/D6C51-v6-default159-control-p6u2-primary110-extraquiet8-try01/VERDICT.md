# D6C51 exact 8-endpoint matched control 판정

## 결론

**공격군과 endpoint 수까지 맞춘 8-endpoint control은 합격이다.** 기본 DU cleanup/RLF와
CU `max_nof_ues: 200` 계보를 유지하고, 6개 load 프로세스(논리 UE 12개)와 추가 endpoint 1개를
관측창 내내 quiet로 둔 상태에서 primary UE 7이 한 번의 접속으로
`RRCSetupComplete` → Registration Accept → PDU Session Establishment Accept에 도달했다.
ping은 303/303(손실 0%, 평균 RTT 103.696 ms)이었다. 조기 종료, crash, 강제 종료는 없었다.

이 결과는 D6F45·D6F46·D6F48 공격군의 8-endpoint prelaunch/sync 자체가 primary 서비스를
항상 실패시키는 confound를 제거한다. 공격군의 3회 service-off/recovery-on과 결합할 matched
attack-off 대조군이지, 이 control 단독으로 공격 인과나 기지국 전체 마비를 입증하지는 않는다.

## 왜 8번째 quiet endpoint가 필요한가

앞선 D6C49는 load 6 + primary 1의 7 endpoints였고, 공격군은 load 6 + primary 1 + recovery 1의
8 endpoints였다. D6C51은 endpoint 8을 시작부터 실행해 8/8 sync시키되 접속 시도를 런 밖으로
미뤘다. 이 endpoint의 `attempt_start`, Msg3, Msg5는 모두 0건이다. 따라서 아래가 정확히 맞는다.

| 항목 | D6C51 control | D6F45/46/48 attack |
|---|---:|---:|
| 전체 프로세스 endpoint | 8 | 8 |
| load/attacker 프로세스 | 6 | 6 |
| 논리 load/attacker UE | 12 | 12 |
| primary endpoint | 1 | 1 |
| 선기동 추가 endpoint | 1 quiet | 1 recovery |

## 시간 정렬

- runner 설정: primary delay 110,000 ms
- primary `attempt_start`: `2026-10-30T18:15:31.078194Z`
- run 시작 대비: 114.078194초
- 비교 공격 스케줄(UE launch 기준): 90.000초 시작, 마지막 공격자 150.685초 종료
  (`90 + 5×0.137 + 60`)
- primary의 110초 시도는 비교 공격창 안이다.

`result.json`의 `attach_s=100`은 run 시작이 아니라 sync 뒤 observation gate 기준이다.
절대 UE JSONL 시각과 혼용하지 않는다.

## 정상 서비스와 quiet 증거

| 항목 | 결과 |
|---|---:|
| endpoint sync | 8/8 |
| quiet load UE 1–6 attempt / Msg3 / Msg5 | 0 / 0 / 0 |
| extra quiet UE 8 attempt / Msg3 / Msg5 | 0 / 0 / 0 |
| primary UE 7 attempt / Msg3 / Msg4 / Msg5 | 1 / 1 / 1 / 1 |
| RRCSetupComplete / Registration / PDU | 1 / 1 / 1 |
| RRCReject | 0 |
| ping | 303/303, 0% loss |
| UE/broker exit status | 전부 0 |
| SIGSEGV / forced kill | 0 / 0 |

DU 원문은 primary RNTI `0x4601`의 `UE Create` 성공,
`InitialULRRCMessageTransfer`, Msg4 HARQ ACK, 후속 UL RRC 전달을 기록한다. UE 원문은 같은
RNTI에 대해 RRCSetupComplete, Registration Accept, PDU Session Establishment Accept와 TUN
구성을 기록한다.

## 설정·실행물 검증

- `du-config.yaml` SHA-256:
  `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`
- DU rendered config: PRACH index 159, preamble 64,
  `max_consecutive_kos: 100`, `t310: 1000`
- 같은 연속 p5 캠페인에서 직전 D6C49가 보존한 CU config SHA-256:
  `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`,
  `max_nof_ues: 200`
- 실제 실행 runner SHA-256:
  `39a0d968f957f7a301303d8dd9b965384c8d56f4dfe0b3213b079a875ed5a94f`
- 8-endpoint broker SHA-256:
  `75c8aab23c151caf46198066d70f4f2db294cae2149eed2b8de2e3e9f1b95dfc`

D6C51 디렉터리에는 CU config 자체가 다시 반출되지 않았다. 따라서 CU 해시는 직전 D6C49의
보존본과 캠페인 운영 기록을 참조하며, D6C51 원문만으로 독립 재검산한 값이라고 쓰지 않는다.
이 control은 quiet 상태라 DU의 유효 capacity 96도 다시 부하 측정하지 않았다.

## 판정 범위

D6C51은 **8 endpoints 자체·broker·ZMQ·DU/CU/core가 primary 정상 접속을 막지 않았다**는
대조다. 공격군과 endpoint 수가 달랐던 D6C49의 confound는 제거됐다.

다음은 여전히 이 결과로 주장하지 않는다.

- 30초 CU/DU context 포화
- 30초 동안 여러 fresh 정상 UE의 반복 거부
- 동일 witness의 attack-on 실패 후 attack-off 회복
- canonical A의 서비스 거부
- 기지국 전체 마비, 차폐 OTA 또는 상용 장비 효과

## 원문 무결성

`stats.json`은 `run.json`, `result.json`, UE 1–8 JSONL/로그, `witness_ping.txt`,
`odu.log.gz`에서 재검산했다. `SHA256SUMS`는 자신을 제외한 run 디렉터리 파일을 봉인한다.
