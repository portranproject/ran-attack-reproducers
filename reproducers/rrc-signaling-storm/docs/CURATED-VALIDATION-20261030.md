# Curated 패치 p5 검증 기록 — 2026-10-30

이 문서는 OAI `2026.w38` UE에 공식 PUCCH 수정과
`patch/rss-ue-curated.patch`를 적용한 뒤, OCUDU 26.10 분리형 CU/DU·Open5GS·ZMQ
가상 RF 테스트베드에서 수행한 검증 결과를 기록한다. 모든 공격 실행은 팀 소유의
격리 테스트베드에서만 수행했고 gNB 소스는 수정하지 않았다.

> 아래 p5 실측 뒤 현재 patch에는 UICC 가입자 로그와 direct Milenage 인증 dump 9개를
> 제거하는 보안 hunk가 추가됐다. 이 hunk는 clean w38 apply-check와 로컬 회귀만
> 통과했고, 현재 patch 그대로의 p5 rebuild·정상 attach는 아직 재검증 전이다.

## 결론

- clean OAI `2026.w38` worktree에 공식 PUCCH 수정과 curated 패치를 적용해
  `nr-uesoftmodem`, `oai_zmqdevif`, `zmq_radio_static`을 실제 빌드했다.
- 공격을 끈 단일 UE는 attach, Registration Accept, PDU Session Accept와 gateway
  ping에 성공했고 `msg4_ack_withheld`는 0건이었다.
- `MSG4_ACK=1/0`을 같은 단일 UE·2초 간격 조건에서 번갈아 3회씩 반복했다.
  ACK 허용군은 매번 ACK 64~65건·max-retransmission 폐기 0건이었고, 억제군은
  매번 ACK 0건·DTX 456~477건·max-retransmission 폐기 38~40건이었다.
- 따라서 **ZMQ 단일 공격 UE에서 Msg4 ACK 억제 훅이 재전송 경로까지 동작한다**는
  것과 이 결과의 3회 반복 재현성은 확인했다.
- 별도 프로세스 일반 witness의 attach→Registration→PDU→ping 경로도 성립했다.
  그러나 유효 공격군 두 런의 서비스 결과가 실패/성공으로 갈렸으므로 정상 사용자
  DoS의 결정적 재현성, OTA 상호운용과 대응 효과는 아직 입증하지 않았다.

## 빌드와 정상 회귀

기존의 변경된 `/root/OAI`는 건드리지 않고 clean `2026.w38` worktree를 별도로
만들었다. 공식 PUCCH 수정과 curated 패치는 충돌 없이 적용됐고 세 빌드 타깃과
바이너리 노브 검사를 통과했다.

공격 off 기준선은 `-e 0 -u 1 -p 1 -A 0 -d 40`으로 실행했다. `-A 0`을 줘도
공격이 꺼져 있으면 ACK 억제 훅이 비활성임을 함께 확인하려는 조건이다.

| 항목 | 결과 |
|---|---:|
| attach 시간 | 26.242초 |
| `RRCSetupComplete` | 1 |
| Registration Accept | 1 |
| PDU Session Accept | 1 |
| ping | 291 송신 / 287 수신, 손실 1.37% |
| ping 평균 RTT | 15.156 ms |
| `msg4_ack_withheld` | 0 |
| crash marker | 0 |

이 결과는 curated 빌드의 attack-off 경로와 `-A 0` 우회가 정상 접속을 깨뜨리지
않았다는 증거다. OTA와 장시간 안정성의 증거는 아니다.

## 혼합 probe에서 발견한 두 결함

첫 혼합 런은 `-e 1 -u 2 -p 1 -A 0` 조건에서
`nr_ra_procedures.c`의 `current_UL_BWP` null 역참조로 종료됐다. 조사 결과 서로
독립인 두 문제가 있었다.

1. 실행기가 `RSS_SHARE_NUE=NUM_UES-PROBE_UES`로 잡아 연결된 probe를 공유 무선
   flush에서 제외했다. probe도 PHY 샘플을 쓰므로 부분 uplink flush가 발생했고,
   타임스탬프 역행과 대량 channel timeout을 만들었다.
2. 연결을 잃은 probe의 재시도 경로가 MAC BWP 재구성 전에 `handle_t300_expiry`를
   호출할 수 있었다.

다음과 같이 수정했다.

- `rss-run`은 이제 `RSS_SHARE_NUE == NUM_UES`만 허용하고 부분 공유 배치를 거부한다.
- probe 재시도는 MAC과 `current_UL_BWP`가 존재하고 RA가 진행 중이 아닐 때만
  시작한다.

수정 뒤 혼합 런은 crash 없이 probe의 PDU 수락과 ping에 성공했다. 그러나
channel timeout 157,990건과 약 10.5%의 out-of-order 공유 TX가 남았다. 따라서
**같은 프로세스·같은 ZMQ 무선의 mixed probe는 진단 신호일 뿐, 독립 정상 UE의
서비스 보존 증거로 쓰지 않는다.** 정상 UE witness는 별도 프로세스와 RF 경로 또는
차폐 OTA에서 측정해야 한다.

## Msg4 ACK-on/off 비교와 재전송 훅

초기 구현은 첫 Msg4의 `ra_pucch`만 억제했다. `MSG4_ACK=0`에서도 OCUDU가 Msg4를
재전송하면 OAI의 일반 `get_downlink_ack()` 경로가 뒤늦게 ACK를 보냈다. DU 슬롯
로그에서 첫 PUCCH는 DTX였지만 뒤의 일반 HARQ ACK로 contention resolution이
완료되는 것을 확인했다.

이에 일반 재전송 경로의 one-bit common PUCCH에도 같은 공격 UE 판정을 적용했다.
probe와 attack-off UE는 계속 ACK한다. 수정 뒤 동일한 1 UE·2초 간격·10회 시도
조건에서 `MSG4_ACK=1`과 `0`을 번갈아 3회씩 비교했다.

| 반복 | 조건 | 시도 | Msg5 생략 | 억제 이벤트 | ACK | DTX | max-retx | crash |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `MSG4_ACK=1` | 10 | 10 | 0 | 64 | 19 | 0 | 0 |
| 1 | `MSG4_ACK=0` | 10 | 50 | 240 | 0 | 477 | 40 | 0 |
| 2 | `MSG4_ACK=1` | 10 | 10 | 0 | 64 | 20 | 0 | 0 |
| 2 | `MSG4_ACK=0` | 10 | 50 | 240 | 0 | 475 | 40 | 0 |
| 3 | `MSG4_ACK=1` | 10 | 10 | 0 | 65 | 18 | 0 | 0 |
| 3 | `MSG4_ACK=0` | 10 | 50 | 230 | 0 | 456 | 38 | 0 |

모든 런에서 NACK과 실제 Msg5는 0건이었다. `ConRes CE ACKed` 문자열은 모든 런에서
조건과 무관하게 10건이었고, channel timeout은 0~11건이었다. 세 번째 억제 런의
억제 이벤트와 max-retx가 각각 230건·38건인 것은 마지막 관측 창이 닫힐 때 진행
중이던 재전송 두 건이 소진 전이었기 때문이다. ACK 0건이라는 판정은 동일하다.

Msg5 생략과 ACK 억제 이벤트가 시도 수보다 많은 것은 재전송된 Msg4를 같은 시도에서
여러 번 수신했기 때문이다. 이 런은 ACK 억제 자체와 OCUDU의 재전송 소진을
입증하지만, 스케줄러 압력이나 정상 UE 서비스 저하를 정량화하지는 않는다.

## `ConRes CE ACKed`는 ACK 증거가 아니다

위 여섯 런 모두 OCUDU 로그에 `ConRes CE ACKed`가 10건 나타났다. ACK 억제군은 DU의
실제 HARQ ACK가 0건이고 재전송이 소진됐으므로 이 문자열로 두 조건을 구별할 수
없다. OCUDU의 `cell_event_manager.cpp`를 확인하면
pending contention-resolution CE가 있고 DL HARQ가 비었을 때 ACK status 확인 없이
해당 handler를 호출할 수 있다. 재전송 소진 뒤에도 이 문자열이 기록되는 이유다.

따라서 판정에는 다음 증거를 사용한다.

- DU FAPI 로그의 `HARQ: harq_ack=ack|dtx|nack`
- DL HARQ max-retransmission 폐기
- UE의 `msg4_ack_withheld`
- UE/CU의 `RRCSetupComplete`와 Msg5 관측

`ConRes CE ACKed` 문자열은 구현 이벤트 참고값일 뿐 실제 ACK의 증거로 집계하지
않는다. 혼합 트래픽에서 FAPI HARQ 카운터는 다른 UE의 ACK도 포함할 수 있으므로,
ACK 훅 검증은 단일 공격 UE의 ACK-on/off 런으로 판정한다.

## RSS 옵션 초기화와 broker 실행기 결함 수정

초기 broker 실행은 5 UE가 모두 `unknown option: --rss.*` 뒤 종료됐고 teardown의
`zmq_write()`에서 TX channel 0 assertion이 이어졌다. assertion이 원인이 아니라,
RSS 설정을 첫 RRC 호출 때만 lazy 등록해 OAI의 unknown-option 검사가 먼저 실행된
것이 원인이었다. curated 패치에 `nr_rss_config_init()`를 추가하고
`get_common_options()` 직후 호출해 radio 시작 전에 RSS prefix를 소비하도록 고쳤다.

실행기도 다음과 같이 수정했다.

- OAI endpoint 5개를 먼저 열고 GNU Radio broker를 뒤에 시작한다.
- 전역 `pkill nr-uesoftmodem`을 제거하고 실행기가 만든 PID/프로세스 그룹만 정리한다.
- gNB restart가 flock FD 9를 상속하던 문제를 모든 장기 자식 경계의 `9>&-`로 막았다.
  control 직후 attack 실행이 Linux에서 lock을 다시 획득하는 것으로 확인했다.
- control load UE와 실제 공격 UE의 카운터를 `load_ue_*`/`attacker_*`로 분리했다.

## 독립 일반 witness control/attack 비교

공식 srsRAN GNU Radio flowgraph를 5 UE로 확장해 네 load/attack UE와 한 일반 witness를
각각 별도 OAI 프로세스로 실행했다. 조건은 DU `nof_cell_sr_res: 1`(부팅 로그상 12 UE
상한), PRACH 64, CU `max_nof_ues: 200`인 **통제된 saturation profile**이며 기본
설정이 아니다.

| 런 | 판정 | sync | RRCSetupComplete 미전송형 시도 | witness attach | Registration/PDU | ping | service |
|---|---|---:|---:|---:|---|---|---|
| r8 control | 구 판정기 오판, 진단용 | 5/5 | 0 | 39 s | 성공 | 102/102, 0% loss | 성공 |
| r21 control | 유효 | 5/5 | 0 | 6 s | 성공 | 40/264, 84.8485% loss | 성공 |
| r2 attack | 유효 | 5/5 | 8, Msg5 0 | 실패 | 실패 | 없음 | 실패 |
| r3 attack | 유효 | 5/5 | 294, Msg5 0 | 50 s | 성공 | 51/52, 1.92308% loss | 성공 |

r8은 load UE의 정상 Msg5를 공격 Msg5로 오인하던 이전 validator 때문에
`valid=false`였지만 5/5 sync·crash 0과 전체 서비스 성공은 원자료에 남아 있다.

공격군 두 유효 런이 서로 반대 결과를 냈고, 공격 시도량이 훨씬 큰 r3에서도 witness가
서비스에 성공했다. 따라서 이 실험은 **독립 일반 witness 경로와 서비스 측정 도구의
성립**을 입증하지만, RRCSetupComplete 미전송형이 정상 서비스를 결정적으로 거부한다는 증거는 아니다.

5 UE broker는 실행별 `sync=0` 시작 경합이 자주 발생했다. r21/r3 관측 종료 중 보였던
SIGSEGV는 후속 kernel journal에서 OAI UE `UL__actor`의 `init_RA()`로 특정됐다. OAI
w38은 첫 INT를 deregistration 요청으로 쓰기 때문에 UE마다 INT를 두 번 보내고 최대
5초 기다리도록 고쳤다. 실행기는 raw UE/broker 종료 상태와 종료 신호 전
`crash_markers` 동결을 함께 기록하고, 인프라 sync timeout만 새 run id로 제한
재시도한다.

후속으로 **사전 고정한 control 15회**를 sync timeout 60초·관측 60초로 실행했다.
30초 이내 5/5 sync는 5회, 31~60초의 늦은 sync는 0회, clean timeout은 10회였다.
sync 성공 5회 중 유효 control은 3회, 의미적 무효는 2회였고, 15회 모두 clean
teardown·SIGSEGV 0이었다. 유효 3회의 attach는 1~36초, ping 손실은
0.833333%~93.5484%로 크게 흔들렸다. 60초까지 늘려도 늦은 성공을 얻지 못했으므로
운영상 fail-fast 기본값은 30초로 유지하지만, N=15로 percentile이나 성공률 보장을
주장하지 않는다. 이 control-only 캠페인은 broker가 안정 서비스 증거로 부적합함을
강화할 뿐 공격 효과나 정상 사용자 DoS의 근거가 아니다. 이 ZMQ 결과를 OTA RF 성능으로
일반화하지 않는다.

## 남은 검증 게이트

1. 실제 SDR 모델/serial·clock·gain 상한·감쇠/배선·누설 기준과 서로 다른 두 가입자
   profile을 확정한 뒤, 정상 UE 1대→2대 순으로 차폐 OTA attach·PDU·ping을 검증한다.
2. broker는 디버그·경로 확인에만 쓰고 안정 서비스 또는 공격/DoS 증거로 쓰지 않는다.
   N=15 control에서 late sync 0회였으므로 30초 제한은 운영상 유지하되 percentile
   보장으로 해석하지 않는다.
3. 실제 조치가 RRCSetupComplete 미전송형 미완료 컨텍스트에 닿는지 확인하고, 조치 뒤 미완료
   컨텍스트 감소와 정상 UE 보존을 함께 측정한다.

이 항목들 전에는 “정상 사용자 DoS”나 “탐지→대응 폐루프 성공”을 주장하지 않는다.

빌드 해시와 원격 원문 파일의 SHA-256 목록은
[`artifacts/curated-verify-20261030/`](../../../artifacts/curated-verify-20261030/)에
별도로 남겼다. 식별자와 가입 절차 자료가 포함될 수 있는 원문 로그 자체는 저장소로
복사하지 않았다. 독립 witness 요약과 원격 원문 해시는
[`artifacts/broker-witness-20261030/`](../../../artifacts/broker-witness-20261030/)에 있다.
종료 원인·2단계 종료·제한 재시도의 후속 검증은
[`artifacts/broker-stability-20261030/`](../../../artifacts/broker-stability-20261030/)에 있다.
15회 고정 control 캠페인의 결과·해시는
[`artifacts/broker-sync-sampling-20261030/`](../../../artifacts/broker-sync-sampling-20261030/)에
있다.
