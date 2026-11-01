# rss-storm — RRC 시그널링 스톰 재현기 (RRCSetupComplete 미전송형)

> English: **[README.en.md](README.en.md)**

> **2026-11-02 마감:** 구현·실측 범위를 동결하고 분석기 평가용으로 정리했다.
> 운영자는 [사용 가이드](docs/USAGE-GUIDE.ko.md)를 먼저 읽는다.
> 기본 cleanup에서 지속 기지국 마비는 입증되지 않았다.

**내가 소유한** 5G NR 기지국을 상대로 **RRC 시그널링 스톰**을 통제된 형태로
재현하는 도구다. 초기접속 시도를 반복하면서 **의도적으로 끝내지 않아**
gNB의 미완료 UE 컨텍스트 점유와 거절 로그를 관측한다. 아래 결과는 특정
OCUDU·ZMQ 테스트베드의 내부 실험 요약이다. 별도 프로세스 일반 UE로 서비스 영향을
측정했지만 성공/실패가 갈려 결정적인 정상 사용자 DoS는 입증되지 않았다.
D6 기본-cleanup 원문·집계·SHA-256은
[`artifacts/p5-default-cleanup-rate-v2-20261030/`](../../artifacts/p5-default-cleanup-rate-v2-20261030/)에
보존했으며, 그 범위를 넘어 OTA·상용망으로 일반화하지 않는다.

2026-10-30에는 clean OAI `2026.w38`에서 curated 패치를 실제 빌드하고 attack-off
attach/PDU/ping 회귀와 Msg4 ACK 억제 경로를 p5 ZMQ에서 검증했다. 단일 공격 UE의
느린 `MSG4_ACK=1/0` ACK-on/off 비교를 3회 반복했고, 억제군은 매번 DU HARQ ACK 0건·
DTX 456~477건·max-retx 폐기 38~40건, Msg5 0건이었다. 원인 분석과 남은 게이트는
[curated 검증 기록](docs/CURATED-VALIDATION-20261030.ko.md)에 있다.

같은 clean 계보의 최종 빌드로 label v1도 실기 검증했다. 첫 ACK-on 런에서
MAC/RRC 동시 JSONL 기록이 섞이는 결함을 exporter가 fail-closed로 잡았고, writer
전체를 mutex로 직렬화한 뒤 ACK-on/off 모두 `label_export=ok`, `valid=true`였다.
또 DU의 정적 `pucch.max_consecutive_kos=20` 설정은 단일 UE 직렬 RRCSetupComplete 미전송형 20회에서
RLF→F1 Release Request/Command/Complete 각 단계 집계 20건과 일치했고, 같은 설정의
attack-off 회귀는 ping 20/20·RLF 0이었다. 이는 시도별 ID 조인 증거가 아닌 셀 전체
정적 hardening이지 탐지기가 호출한 actuator는
아니다. 원문 해시와 주장 경계는 [label/RLF20 실측](../../artifacts/label-v1-rlf20-20261030/README.md)에 있다.

같은 날 GNU Radio 5 UE broker에서 별도 프로세스 일반 witness의
attach→Registration→PDU→ping 경로를 확인했다. 공격군 r2는 서비스 실패, r3은
294회 공격에도 서비스 성공했고, 후속 사전고정 control에서도 유효 런의 ping 손실이
0.833333%~93.5484%로 흔들렸다. broker
지연 때 RSS 옵션이 unknown으로 종료되던 lazy-config 결함은 `nr_rss_config_init()`의
eager 호출로 고쳤다. 이 결과는 독립 witness 경로의 성립과 서비스 영향의 비결정성까지
입증하며 OTA나 지속 DoS 증거는 아니다.

구현 형태는 **OpenAirInterface NR UE에 대한 패치**다. 기지국은 수정하지도,
패치하지도 않는다.

> **격리된 테스트베드 전용.** RF 차폐 박스 또는 가상 무선(ZMQ), 내가 소유한
> 장비에서만. `-e 1`을 넘기지 않으면 공격은 비활성 상태다.
> [NOTICE.md](NOTICE.md) 참고.

---

## 공격 시나리오

**RRCSetupComplete 미전송형 = 초기접속 미완료.** 랜덤 액세스부터 Msg4 수신까지는 정상 UE와 똑같이
수행하고, 마지막 한 장인 `RRCSetupComplete`만 보내지 않는다.

| 단계 | 정상 UE | 이 도구 |
|---|---|---|
| PRACH / Msg1-2 | 수행 | 수행 |
| `RRCSetupRequest` (Msg3) | 수행 | 수행 |
| `RRCSetup` (Msg4) 수신 + HARQ ACK | 수행 | 기본 수행. `MSG4_ACK=0` 변형은 공격 UE만 DTX |
| `RRCSetupComplete` (Msg5) | **전송** | **생략** |
| gNB 측 결과 | UE 접속 완료 | gNB의 가드 타이머가 만료될 때까지 컨텍스트 점유, 이후 해제 |

Msg5가 도착하지 않으므로 gNB는 코어로 `InitialUEMessage`를 보내지 않는다.
코어는 전혀 건드리지 않고 압박은 전부 기지국의 연결 상태에 걸린다.

`MSG4_WAIT=0`은 별도 변종인 **RRCSetupRequest 후 중단형**이다. MAC scheduler가 Msg3를 PHY에 실제로
넘긴 것을 `msg3_tx`로 기록한 뒤에만 현재 RA를 `GO_TO_IDLE_KEEP_CAMPED`로
초기화하므로 Msg4를 기다리거나 ACK하지 않는다. RRCSetupComplete 미전송형의 `canonical_a`와 섞지
않고 `canonical_msg3_only`로 판정한다.

**왜 이 시나리오인가**

- **탐지 신호가 깨끗하다.** 코어에 닿지 않으므로 압박 지점이 기지국의 연결
  상태에 있다. `rrcSetupComplete`와 `InitialUEMessage`가 관측되지 않은 것은
  시나리오와 일치하지만, 로그 0건만으로 이를 입증할 수는 없다.
- **기지국을 수정할 필요가 없다.** 표준 Uu 절차(PRACH/RRC)만 사용하므로 상대는
  소스 변경이 필요하지 않다. 상용 gNB와 실 SDR OTA의 동작은 검증하지 않았다.
- **점유 목표를 지정할 수 있다.** `-o`는 UE 측 기록과 보유시간 가정으로 계산한
  추정 점유를 사용한다. gNB의 실제 점유와 일치한다는 보장은 없다.

이 공격이 **왜** 통하는지 — 기지국이 어느 메시지에서 자원을 잡는지, 왜 망 쪽
타이머가 그것을 즉시 회수하지 않는지, 어떤 설정값이 결과를 좌우하는지 — 는
기지국 소스를 인용해 [docs/MECHANISM.ko.md](docs/MECHANISM.ko.md)에서 논증한다.

> 이 명칭은 3GPP의 공식 공격 분류가 아니라, 표준 RRC 메시지명으로 중단 지점을
> 설명한 이름이다. RRC 스톰은 여러 절차의 묶음이며 UE 재시작 반복형 같은 다른
> 변종은 별도 구현 대상이다.

기존 label v1과 봉인 증거의 기계값은 호환성을 위해 바꾸지 않는다.
`scenario="A"`와 `canonical_a*`는 RRCSetupComplete 미전송형,
`scenario="A_early"`와 `canonical_msg3*`는 RRCSetupRequest 후 중단형,
`scenario="A_no_ack"`는 RRCSetup HARQ-ACK 억제형을 뜻한다.

---

## 테스트베드 스펙

이 도구가 **가정하는** 환경이다. [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md)의
모든 측정값이 아래 구성에서 나왔다.

### 토폴로지

```
   CU 호스트 (c6i.xlarge)                 DU 호스트 (c6i.2xlarge)
 +----------------------+   F1 / IP    +--------------------------+
 |  OCUDU CU            |<------------>|  OCUDU DU                |
 |  Open5GS 코어        |   (VPC 사설) |  공격 UE (이 패키지)      |
 |  FlexRIC             |              |   ZMQ 가상 무선          |
 |  CU 로그 /tmp/ocu.log|              |   tcp://127.0.0.1:4556-7 |
 |  bin/rss-report      |              |                          |
 +----------------------+              +--------------------------+
        판정                                    공격 실행
```

- 공격 UE는 **DU와 같은 호스트**에서 돈다. ZMQ 가상 무선이 loopback이기 때문이다.
  현재 build·doctor·runner는 `oai_zmqdevif`만 지원한다. `DEVICE`만 바꾸면 OTA가
  되는 구조가 아니며 실행기가 이를 거부한다. 실 SDR OTA는 장비별 backend·인자와
  RF 안전 검사를 갖춘 별도 경로로 구현해야 한다.
- 판정은 **CU 호스트**에서 한다. 점유와 거절 카운터의 출처가 CU 로그다.
- CU/DU가 한 호스트에 있어도 동작에는 문제가 없다. 그 경우 두 단계를 같은 곳에서
  실행하면 된다.
- RRCSetupComplete 미전송형 시도는 코어(AMF)에 닿지 않는다. 그러나 **CU에 AMF와 CU-UP가 연결돼 있어야
  한다** — 연결이 없으면 OCUDU CU-CP가 모든 `RRCSetupRequest`를 거절해 실험이
  성립하지 않는다(전제 조건 참고).

### 소프트웨어

| 구성요소 | 버전 / 커밋 | 비고 |
|---|---|---|
| gNB | OCUDU `release_26_10` (`e0db566a`, srsRAN 파생) | **수정하지 않음.** 용량 12·보유 7초 진단 프로필에서 설정만 변경 |
| 공격 UE | OAI `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (태그 `2026.w38`) | 기본 빌드 패치 `patch/rss-ue-curated.patch`의 기준 커밋 |
| 무선 드라이버 | OAI `oai_zmqdevif` | 패치가 `radio/zmq/`를 함께 수정한다 |
| 코어 | Open5GS (Docker) — **연결 필수** | RRCSetupComplete 미전송형 시도는 NGAP에 닿지 않지만, AMF나 CU-UP가 하나도 연결돼 있지 않으면 OCUDU가 **모든** `RRCSetupRequest`를 거절한다 |
| RIC | FlexRIC | 이 도구와 무관한 테스트베드 구성 요소 |
| 분석 | `python3` 표준 라이브러리만 | 외부 패키지 설치 없음 |
| OS | Linux | 스크립트가 `bash`, `taskset`, `nproc`, `pgrep`, `timeout`을 쓴다 |

### 셀

| 항목 | 값 | conf 키 |
|---|---|---|
| 밴드 | n78 (TDD) | `BAND=78` |
| 하향 중심 주파수 | 3489.42 MHz (`dl_arfcn` 632628) | `DL_FREQ=3489420000` |
| SCS | 30 kHz (numerology 1) | `NUMEROLOGY=1` |
| 대역폭 | 51 PRB (20 MHz 채널) | `PRB=51` |
| ZMQ TX / RX | `tcp://127.0.0.1:4557` / `:4556` | `ZMQ_TX`, `ZMQ_RX` |

이 값들은 **gNB가 실제로 방송하는 셀과 일치해야 한다.** 틀리면 UE가 셀 탐색에서
멈추고 런은 시도 0으로 끝난다.

### gNB 설정과 용량

용량과 유지 시간이 결과를 결정하므로, 두 값을 설정에서 확인하고 로그에서 실측한다.

| | 기본 cleanup 프로필 | 용량 12·보유 7초 진단 프로필 | 설정 키 |
|---|---:|---:|---|
| 동시 UE 용량 | 96 | 12 | `cell_cfg.pucch.nof_cell_sr_res` 8 → 1 (DU) |
| `t300` | 1000 ms | 2000 ms | `cell_cfg.sib.t300` (DU, 3GPP 최대 2000) |
| RRC 절차 가드 | 1000 ms | 5000 ms | `cu_cp.rrc.rrc_procedure_guard_time_ms` (CU) |
| 컨텍스트 유지 **실측** | 약 1900 ms | 약 1460–1850 ms | CU 로그에서 측정 |
| 내부 기록의 시도율 | 33–38/s | 5.6–6.5/s | 집계 원본 미포함, 이벤트 정의·창 재확인 필요 |
| 내부 기록의 결과 | 용량 도달(버스트) | 거절 로그 반복 관측 | "점유와 거절 관측" 참고 |

- 용량은 `min(SR 자원, CSI 자원, ...)`로 결정되므로 `nof_cell_sr_res` 하나를
  내리면 같이 내려간다.
- **유지 시간은 설정값의 합이 아니다.** 용량 12·보유 7초 진단 프로필의 설정상 합은 7000 ms지만 DU가 먼저
  해제하는 경우가 있어 실측은 1.6초 근처였다. 반드시 로그에서 측정해서 `-H`에
  넣는다.
- 프로필 적용은 `bin/rss-gnb-profile`이 하고 **gNB 소스는 건드리지 않는다.**
  `.orig` 백업을 남기며 멱등적이다.

### 호스트

측정은 AWS EC2 인스턴스 두 대에서 수행했다. 아래 값은 박스에서 직접 읽었다.

| 역할 | 인스턴스 | vCPU | CPU | 메모리 | OS / 커널 |
|---|---|---:|---|---:|---|
| CU (OCUDU CU + 코어 + RIC + 판정) | `c6i.xlarge` | 4 | Intel Xeon Platinum 8375C @ 2.90 GHz (1 소켓) | 7.6 GiB | Ubuntu 24.04.5 LTS / `7.0.0-1014-aws` |
| DU + 공격 UE | `c6i.2xlarge` | 8 | Intel Xeon Platinum 8375C @ 2.90 GHz (1 소켓) | 15.3 GiB | Ubuntu 24.04.5 LTS / `7.0.0-1014-aws` |

**호스트 병목에 관한 내부 관측.** DU 박스 8 vCPU에서 관측했을 때 odu가
약 1.7 코어, 공격 UE가 약 0.3 코어를 썼고 **6 코어가 유휴**였다(별도 세션의
`top`·`loadavg` 관측이며 런 산출물로 보관돼 있지는 않다). 그 상태에서도
시도율은 36–38/s로 기록됐다. 이 기록만으로 호스트 병목을 배제하거나
일반적인 성능 상한을 확정할 수 없다. 당시 해석은 [docs/MECHANISM.ko.md](docs/MECHANISM.ko.md) §6.3–§6.4에 있다.
RF는 실 SDR이 아닌 ZMQ 가상 무선이므로 차폐 박스나 안테나는 쓰지 않았다.

**2026-10-20 p5 정상 접속 재시험.** CU의 코어·RIC·OCUDU와 DU의 OCUDU를
기동해 F1/E2 연결을 확인했다. 보존돼 있던 패치 전 UE의 첫 시도는
`RRCSetupComplete` 생성 후 SIGSEGV로 종료됐다. 커널의 충돌 주소와 역어셈블 결과,
공통 PUCCH 자원 포인터가 `NULL`인데 UE 스케줄러의 다중화 경로가 이를 역참조한
것이 원인이었다. [OAI의 해당 수정](https://github.com/openairinterface/openairinterface5g/commit/3d4b1923b424be974c1dadcc9c48eddbe8428ba0)을 적용했다.
그 전에 `bin/rss-bootstrap`으로 공식 OAI `2026.w38`을 새로 얕은 clone·빌드했고
(`--deps` 생략), 깨끗한 스톡 UE의 첫 정상 접속도 성공했다. 이 한 번의 성공으로
스톡 빌드의 간헐적 PUCCH 충돌 위험이 사라진 것은 아니다. 수정 후에는 DU·UE를
함께 재기동해 **정상 접속 10/10회**, 코어 게이트웨이 `10.45.1.1`로의 ping
**50/50회**에 성공했고 UE SIGSEGV가 재발하지 않았다. 이전의 변경된 OAI 소스와
RSS 패치 빌드는 삭제했다. 이어서 수정된 OAI 브랜치에서 `rss-build`로 UE·ZMQ·static
세 타깃을 빌드했고 노브 검사를 통과했다. 빌드 후 `rss-doctor`는 블로커 0건,
예상된 경고 2건이었다. `rss-run -e 0 -u 1 -d 30`에서는
`RRCSetupComplete`, PDU 수락과 `oaitun_ue1` 설정을 확인했고 외부 타임아웃으로
50초에 종료됐다. UE 로그에 `channel timeout` 15건이 있어 무선 안정성까지 입증한
것은 아니다. 같은 패치 빌드를 제어판으로 실행한 정상 접속에서는 게이트웨이 ping
**5/5회**에 성공했다. 시험 뒤 패치 소스·빌드를 제거하고 RSS 표식이 없는 정상 UE를
다시 빌드했다. 현재 p5 DU의 `/root/OAI`는 깨끗한 `codex/oai-pucch-null-fix`
브랜치(`6d6782b`)이며, 최종 정상 UE의 두 번째 DU·UE 동반 기동에서 접속과 ping
**5/5회**에 성공했다. 이후 커널 UE SIGSEGV는 없었다. 임시 스크립트를 지우고
EC2 두 대를 중지했다. 이 검증은 **ZMQ 정상 UE 경로**에 한정한다. `-e 1` 공격 실행,
실 SDR OTA, 게이트웨이 너머 데이터 경로와 수정에 따른 SR/CSI 억제 효과는 미검증이다.

**2026-10-30 curated 패치 검증.** 기존 변경 트리를 보존하고 별도 clean w38
worktree에서 공식 PUCCH 수정과 `patch/rss-ue-curated.patch`를 적용해 UE·ZMQ·static
세 타깃을 빌드했다. attack-off `-e 0 -A 0` 기준선은 attach, Registration Accept,
PDU Session Accept와 ping에 성공했고 `msg4_ack_withheld`는 0건이었다. 최초 구현은
첫 Msg4 PUCCH만 억제해 재전송의 일반 HARQ 경로가 ACK하는 결함이 있었고, 그 경로도
동일하게 억제하도록 수정했다. 동일한 단일 공격 UE·2초 간격·10회 시도 대조를
3회 반복한 결과 `MSG4_ACK=1`은 DU ACK 64~65건·max-retx 0건,
`MSG4_ACK=0`은 ACK 0건·DTX 456~477건·max-retx 38~40건이었다. 모든 런에서
Msg5와 crash는 0건이었다. 같은 프로세스의 mixed
probe는 PDU와 ping에 성공했지만 대량 channel timeout이 남아 독립 정상 UE 증거로는
기각했다. 자세한 수치와 판정 한계는
[검증 기록](docs/CURATED-VALIDATION-20261030.ko.md)에 있다. 별도 프로세스 broker
witness는 구현됐지만 서비스 결과와 baseline 품질이 불안정하다. 차폐 OTA와
탐지→대응 폐루프는 아직 남아 있다.

**2026-10-30 label v1·정적 RLF 검증.** 최종 curated 빌드의 공용 JSONL writer를
mutex로 직렬화해 MAC ACK event와 RRC event가 한 줄에 끼어들던 결함을 고쳤다.
ACK-on 10회는 UE 측 미전송 후보 10건·최종 라벨 `null` 10건, ACK-off 10회는 후보 0건·최종 라벨
`false` 10으로 export됐다. 이 보존 실측은 새 DU 조인 전 결과다. 현재 runner와
exporter는 선택적 `ODU_LOG`의 run-scoped slice에서 UE와 DU의 `(rnti, frame, slot)`
FAPI ACK를 정확히 조인한다. hold32 V4 계보 바이너리(`202934f7…`)의 p5 CU200에서는
세 공격 셀에서 `canonical_a=true`·`du_ack_state=ack`가 합계 176건 나왔고 모든
manifest가 검증됐다. aggregate ACK만으로는 승격하지 않는다. 별도
`max_consecutive_kos=20` 설정 전/후 비교에서는 단일
UE 직렬 RRCSetupComplete 미전송형 20회의 RLF와 F1 release 각 단계 집계가 20건씩 일치했고, 약 60초
attack-off 기준선은
Registration/PDU·ping 20/20, RLF 0이었다. DU 설정은 원본 SHA-256으로 원복했다.
차폐 OTA, 장기·열악 채널 정상 UE 안전성, 외부 탐지기가 호출하는 동적 actuator는
미검증이다. [원격 원문 SHA-256과 집계](../../artifacts/label-v1-rlf20-20261030/README.md)를
같이 본다.

**2026-10-30 CU 200 hold32 진단(성공 판정 아님).** CU의 `max_nof_ues: 200`과 셀별 DU capacity를
바꾸지 않고 세 공격 셀로 RRCSetupComplete 미전송형을 발생시켜 CU 점유가 정확히 200에 도달했고,
200 점유가 15.68초 연속 유지됐다. 별도 네 번째 셀의 정상 witness는 포화 뒤
16.31초 동안 17회 모두 `RRCReject`를 받았으며 Msg4·`RRCSetupComplete`·Registration·
PDU·channel timeout은 모두 0이었다. 부하 전 4셀 control은 모두
`RRCSetupComplete`에 성공했고 한 셀은 Registration/PDU/TUN까지 통과했다.
그러나 `bin/rss-cu200`은 기본 약 2초 정리시간을 32초로 늘리고 첫 context 만료 전에
끝냈다. 이는 DU ACK 확인 RRCSetupComplete 미전송형·CU 200 도달과 그 인공 hold 안의 거부를 보여 줄 뿐,
공격 유입률이 기본 해제율을 이긴 통제 가능한 서비스 거부 증거가 아니다. 설정·로그·
해시는 [CU200 진단](../../artifacts/p5-cu200-3cell-20261030/README.md)에 있다.

**2026-10-30 기본 cleanup rate-v2 재검증(실패).** rate-v2 패치 `4ef70618…`,
바이너리 `c2761193…`로 한 공격 프로세스의 6 UE와 별도 full-service witness를
120초 실행했다. F1 제공률 48.652/s는 정리율 39.407/s보다 높았지만 8.558/s가
컨텍스트 생성 전에 DU에서 거절됐다. 실제 RRC Setup 시작은 40.095/s였고 워밍업 뒤
생성 40.026/s 대 정리 39.922/s로 평형이었다. 점유 96 최장 구간은 0.885초였고
정상 witness는 첫 distinct 시도만 거절된 뒤 Registration·PDU와 ping 437/438에
성공했다. 따라서 공격 처리율 개선은 확인했지만 sustained denial과 공격자 통제성은
성립하지 않았다. [원문·계산·다중 셀 반증](../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md)을
같이 본다.

**2026-10-30 기본 cleanup D6 후속 판정.** exact ACK RNTI 보정을 포함한 v6 UE
바이너리 `6b4f254f…`와 6프로세스×2UE RRCSetupRequest 후 중단형으로 세 번 반복했다. D6F45·46·48은
모두 공격 중 primary 정상 UE 서비스 실패와 공격 stop 뒤 별도 prelaunched UE의
Registration·PDU·ping 회복을 보였다. D6F48은 Msg3 77.408/s와 DU provisional
73.338/s가 cleanup 34.209/s를 완전한 5초 창 12/12에서 넘었지만, 초과분 2,373건은
Setup admission 전에 즉시 거절돼 admitted Setup은 cleanup과 평형, 점유 피크는
95/96이었다. 같은 8-endpoint attack-off D6C51은 quiet endpoint 시도 0건과 primary
ping 303/303을 기록했다. 별도 D6F50 DU ACK 확인 RRCSetupComplete 미전송형 런은 exact DU ACK 149/205와 공격자
Msg5 0을 확인했지만 공격 중 정상 UE가 Registration·PDU·ping 194/195에 성공했다.
따라서 RRCSetupRequest 후 중단형의 좁은 서비스 on/off는 3/3 반복됐고 DU ACK 확인
RRCSetupComplete 미전송 기전도 확인됐지만, 30초 지속 포화·기지국 전체 마비는
입증되지 않았다. 원문과 제한은
[기본 cleanup artifact](../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md)를 따른다.

**2026-10-30 RRCSetupRequest 후 중단형 p5 검증.** `G2-msg3-0140`은 MAC-confirmed Msg3 10개를
current-run CU `RRCSetupRequest`와 TC-RNTI로 10/10 조인했다. 이후 확인 결과
`G4/G13/G14`의 DU 설정에는 `nof_cell_sr_res: 1`이 있어 실제 capacity가 12였다.
따라서 당시 probe 거부는 유효한 cap12 결과지만, 별도의 숨은 12-context pool이나
capacity-96 결과는 아니다.

지연 probe가 있는 최종 쌍에서 `valid=true`인 고속 `G13-pair-attack-valid`은 `msg3_tx=1029`,
공격자·probe Msg4 0, CU 요청 921·절차 시작 84·DU 거절 837이었다. probe TC-RNTI
10개는 CU 요청·거절과 10/10 일치했고 `InitialUEMessage`와 PDU 성공은 0이었다.
G13 뒤 DU를 clean restart한 `valid=true` 저부하 control
`G14-pair-recovery-control`은 probe 첫 시도에
Registration, PDU와 TUN까지 성공했고 CU도 RRC·PDU 성공을 기록했다. 다만 두 UE가 같은 OAI 프로세스와 ZMQ 무선을 공유하므로
통제된 진단 witness이지 독립 물리 UE DoS 증거는 아니다. 이 후행 control은 영구
장비·구성 고장을 배제하지만 재시작 없는 자연 회복을 입증하지 않는다.

실제 capacity-96 후속 검증에서는 기본 CSI-DTX RLF가 context를 약 2.86초 만에
해제해 정상 probe가 연결됐다. capacity 값은 그대로 두고 실험 관측창의 정리
경계만 뒤로 미룬 `max_consecutive_kos=2000`, `t300=2000`, CU guard 30000ms
hold32 진단 프로필에서 G34 정상 control이 Registration/PDU/TUN을 통과했다. 같은 설정의 G35는
probe 11회가 모두 CU까지 도달한 뒤 `DU is not able to serve`로 거부됐고,
10.13초 동안 Msg4·Msg5·연결이 0이었다. 상세 설정·반증 run·해시는
[capacity-96 artifact](../../artifacts/p5-msg3-cap96-20261030/README.md)에 있다.

### 전제 조건

- **OAI 소스 트리는 미리 준비하지 않아도 된다.** `bin/rss-bootstrap`이 공식
  저장소의 `2026.w38` 태그를 얕은 clone으로 받아 최초 빌드까지 한다(수십 분).
  이미 트리가 있으면 로컬 변경을 검사하고, 변경이 있으면 거부한다. 변경을 보존한
  뒤 별도의 깨끗한 OAI 경로를 사용한다. 기존 바이너리는 RSS 표식이 있으면 거부하며,
  표식이 없어 재사용하더라도 스톡 출처까지 증명하지는 않는다. **다른 커밋의 빌드가
  있는 트리도 거부한다.** 따라서 현재 p5 DU의 수정 브랜치에는 `rss-bootstrap`을
  다시 실행하지 않는다. `rss-build`는 이미 적용된 PUCCH 수정을 인식한다.
- `git`, `cmake`, C/C++ 툴체인, `python3`. OAI의 시스템 패키지는
  `bin/rss-bootstrap --deps`가 설치한다.
- OAI 트리와 런 산출물이 `/root` 아래라면 UE 호스트의 root 권한. CU 로그 읽기도
  마찬가지다.
- gNB와 UE 사이의 무선 경로: 현재 실행 가능 경로는 ZMQ 가상 무선뿐이다. 차폐 박스
  실 SDR OTA는 장비 inventory·driver·clock·gain·감쇠·누설 기준이 확정된 뒤 별도로
  구현·검증한다.
- OTA G0를 준비할 때는 `conf/ota-inventory.example.json`을 gitignore 대상인
  `conf/ota-inventory.json`으로 복사하고
  `python3 analysis/validate_ota_inventory.py conf/ota-inventory.json`을 먼저 통과시킨다.
  exit 0은 manifest 완결성일 뿐 실물 대조나 송신 승인이 아니다.
- **CU에 코어(AMF)와 CU-UP가 연결돼 있어야 한다.** RRCSetupComplete 미전송형 시도가 코어에 닿지는
  않지만, 연결이 없으면 OCUDU CU-CP가 모든 `RRCSetupRequest`를 거절해 실험 자체가
  성립하지 않는다.

---

## 사용 방법

이 저장소만 받으면 된다. OAI 소스를 미리 준비해 둘 필요는 없다 — 1단계가 받아서
빌드한다. gNB(OCUDU)는 이미 돌고 있다고 가정한다.

### 한눈에

```bash
git clone https://github.com/portranproject/ran-attack-reproducers.git
cd ran-attack-reproducers/reproducers/rrc-signaling-storm
bin/rss-bootstrap                        # 1. OAI 받아서 최초 빌드 (한 번만)
cp conf/rss.conf.example conf/rss.conf   # 2. 설정
$EDITOR conf/rss.conf
bin/rss-build                            # 3. PUCCH 수정·RSS 패치 적용 + UE 빌드
bin/rss-doctor                           # 4. 빌드 결과·전제 조건 진단
bin/rss-run -e 0 -u 1 -d 30              # 5. 정상 접속 회귀
bin/rss-run -e 1 -u 2 -d 120             # 6. 공격
bin/rss-report --since HH:MM:SS --until HH:MM:SS   # 9. 판정(CU 호스트)
```

**실행 위치**: 공격 UE를 돌릴 호스트(보통 DU와 같은 호스트)다. 판정 단계만 CU
호스트에서 한다. 기본 경로가 `/root` 아래이므로 **root로 실행**한다
(`sudo -i` 후 작업하거나 모든 명령에 `sudo`를 붙인다).

### 1단계 — OAI 트리 준비

```bash
bin/rss-bootstrap            # 기본: 받기 + 기준 커밋 체크아웃 + 최초 빌드
# 라이브러리가 부족해 실패했을 때만: bin/rss-bootstrap --deps
```

하는 일:

1. `$OAI`(기본 `/root/OAI`)에 트리가 없으면 공식 저장소의 `2026.w38` 태그를
   얕은 clone으로 받는다.
2. **기준 커밋 `1c2f4d3c…`(태그 `2026.w38`)로 체크아웃**한다. 이 패치는 이 커밋에
   맞춰 만들어졌다.
3. `--deps`를 주면 OAI의 `build_oai -I`로 시스템 패키지를 설치한다. 호스트를
   바꾸는 작업이라 **기본적으로 하지 않는다.** 빌드가 라이브러리 부족으로 실패하면
   한 번 주고 다시 돌린다.
4. 스톡 UE를 한 번 빌드한다: `build_oai --nrUE -w ZMQ`. `-w ZMQ`가 이 도구가
   패치하는 무선 드라이버(`oai_zmqdevif`)를 함께 만든다. gNB는 빌드하지 않는다.
5. `nr-uesoftmodem`과 `liboai_zmqdevif.so`가 생겼는지 확인한다.

**이 단계는 길다.** 찬 트리에서 빌드가 수십 분이다. 이미 트리가
있으면 로컬 변경이 없는 경우에만 재사용하고, 다른 커밋의 빌드가 있으면 거부한다.
기준 커밋의 기존 빌드가 있으면 RSS 표식을 검사한 뒤 그대로 쓴다. `--force`는
빌드를 다시 실행하지만 기존 산출물이 재사용될 수 있다. **빌드 산출물이 없는 깨끗한
기준 소스에서 처음 생성한 경우에만** 바이너리의 스톡 출처가 확인된다.
기준 커밋의 스톡 UE에는 위 PUCCH 충돌이 간헐적으로 발생할 수 있다. 다음 단계의
`rss-build`가 공식 수정을 적용하며, 공격을 끈 실행(`-e 0`)에도 수정이 포함된다.
현재 p5 DU의 수정 브랜치에서 이어갈 때는 이 단계를 건너뛰고 설정 뒤 `rss-build`로
진행한다.

### 2단계 — 설정

```bash
cp conf/rss.conf.example conf/rss.conf
$EDITOR conf/rss.conf
```

최소한 아래를 내 환경에 맞춘다. 나머지는 기본값으로 둬도 된다.

| 키 | 왜 필요한가 |
|---|---|
| `OAI` | OAI 소스 트리 경로. 빌드와 런이 모두 여기를 본다 |
| `UE_CFG` | OAI UE 설정 파일 경로 |
| `BAND` `DL_FREQ` `NUMEROLOGY` `PRB` | gNB가 방송하는 셀과 일치해야 한다 |
| `ZMQ_TX` `ZMQ_RX` | DU가 열어 둔 ZMQ 포트 쌍 |
| `GNB_RESTART_CMD` | **ZMQ 경로에서는 사실상 필수.** 아래 설명 참고 |
| `LOGDIR` | 런 산출물이 쌓이는 곳 |
| `ODU_LOG` | 선택적 단일-sector append-only OCUDU DU 로그. `log.fapi_level: debug`가 필요하며 이번 run의 FAPI HARQ ACK slice만 봉인해 최종 RRCSetupComplete 미전송 라벨 조인에 쓴다 |
| `ODU_SECTOR_ID` | `ODU_LOG`와 함께 쓰는 OCUDU `Sector#N`. 누락·다른 sector 로그는 조인을 실패시킨다 |
| `GNB_LOG` `CAPACITY` | CU 호스트에서 판정할 때 쓰는 값 |

- `ENABLE=0`을 **파일 기본값으로 유지한다.** 실수로 실행해도 정상 UE로 동작한다.
  공격은 `-e 1`을 명시적으로 넘길 때만 켜진다.
- 설정 파일을 다른 위치에 두려면 `RSS_CONF=/path/to/rss.conf`로 지정한다.
- **ZMQ 가상 무선에는 자체 클럭이 없다** — 샘플 교환 자체가 클럭이다. DU와 UE가
  같이 시작하지 않으면 두 스트림이 끝까지 정렬되지 않으므로, DU 재기동 명령을
  `GNB_RESTART_CMD`에 넣어 `rss-run`이 매 런마다 DU를 다시 띄우게 한다.
- **DU만 띄우는 명령을 넣는다.** 정상 UE까지 함께 띄우는 명령을 넣으면 그 UE가 ZMQ
  포트 쌍을 먼저 차지해 공격 UE가 붙지 못한다.
- 이 명령에 **파이프라인을 쓰지 않는다.** 파이프의 쓰기 끝이 열린 채 남아 EOF가
  오지 않아 영원히 멈출 수 있다. `bin/rss-doctor`가 이 실수를 잡아낸다.

### 3단계 — 빌드

```bash
bin/rss-build
```

하는 일:

1. **OAI 트리에 커밋되지 않은 변경이나 추적되지 않은 파일이 있으면 거부한다.**
   자동으로 변경을 되돌리지 않는다. 기존 변경을 직접 확인·보존·정리해야 한다.
   깨끗한 트리에서 `rss-ue-a-type` 브랜치를 만들거나 체크아웃한다.
2. [OAI 공식 PUCCH 충돌 수정](https://github.com/openairinterface/openairinterface5g/commit/3d4b1923b424be974c1dadcc9c48eddbe8428ba0)을
   아직 적용되지 않았을 때만 적용한 뒤 RSS UE 패치를 적용한다. 공격을 끈 모드도
   수정된 UE 바이너리로 실행한다.
3. `nr-uesoftmodem`, `oai_zmqdevif`, `zmq_radio_static` **세 타깃**을 빌드한다.
   무선 드라이버는 UE가 런타임에 로드하는 별도 공유 라이브러리(`liboai_zmqdevif.so`)라서,
   UE 바이너리만 빌드하면 `radio/zmq/` 수정이 런에 반영되지 않는다.
4. 빌드 산출물을 `strings`로 뒤져 노브(`target_occupancy`, `msg4_wait`,
   `RSS_SHARE_LOCKSTEP`, `RSS_ZMQ_TX_WAIT_US`)가 실제로 들어갔는지 확인한다.
   하나라도 없으면 **실패로 종료한다** — 빌드가 성공해도 노브가 없는 바이너리의
   런은 믿을 수 없기 때문이다.

기존 바이너리는 `.orig`로 백업된다. 이전 패치 적용도 커밋되지 않은 변경으로
남으므로, 재실행 시에는 그 변경을 먼저 직접 확인·보존·정리해야 한다.

### 4단계 — 진단

```bash
bin/rss-doctor
```

빌드 뒤에 실행한다. 스톡 바이너리는 RSS 노브가 없어 이 진단에서 `[FAIL]`로
판정된다. 진단은 읽기만 하며 호스트 명령, 설정 파일, OAI 트리와 커밋, 빌드 산출물,
**바이너리에 노브가 실제로 들어갔는지**, UE 설정 파일, 산출물 디렉토리 권한, ZMQ
포트 수신 여부, 재기동 훅, CU 로그 접근성을 차례로 본다.

```
== attacker UE binary
  [ok]   binary: /root/OAI/cmake_targets/ran_build/build/nr-uesoftmodem
  [ok]   knobs present (target_occupancy, msg4_wait, RSS_SHARE_LOCKSTEP)
```

`[FAIL]`이 하나라도 있으면 종료 코드가 1이고, 각 줄이 해결 명령을 함께 알려 준다.
`[warn]`은 상황에 따라 정상이다(예: DU가 아직 꺼져 있음, 이 호스트에 CU 로그가
없음). **블로커가 없을 때만 다음 단계로 간다.**

### 5단계 — 회귀 베이스라인부터

```bash
bin/rss-run -e 0 -u 1 -d 30
```

공격을 끈 상태로 정상 접속이 되는지 먼저 증명한다. **`-u 1`을 명시한다** — 설정
파일 기본값이 `NUM_UES=2`인데, 정상 UE 두 개를 한 무선·한 가입자 식별자로 동시에
붙이면 베이스라인으로서 의미가 없고 실제로 UE가 죽었다(이 테스트베드에서 rc=139). CU 로그에서
`rrcSetupComplete`는 RRC 단계 도달만 보여 준다. 정상 접속 성공은 UE의
`oaitun_ue1` 주소 할당과 코어 게이트웨이 통신까지 확인한다. p5에서 수정된 패치
빌드의 `rss-run -e 0`은 PDU 수락·터널 설정까지 통과했고, 같은 빌드의 별도 정상 UE
실행은 게이트웨이 ping 5/5회에 성공했다. 해당 `rss-run` 로그에는 `channel timeout`
15건이 있어 무선 안정성까지 확인한 것은 아니다.

이 단계를 건너뛰면, 공격 런에서 시도 0이 나왔을 때 **셀 설정 문제인지 공격 로직
문제인지 구분할 수 없다.** 30초는 한 번의 확인 창이며 첫 시도 성공을 보장하지 않는다.

### 6단계 — 공격 실행

```bash
bin/rss-run -e 1 -u 2 -d 120              # 기본 cleanup 프로필, 기본 gNB 설정
bin/rss-run -e 1 -u 2 -o 48 -H 1900 -d 0  # 추정 점유 목표 48
```

- `-u 2`가 권장값이다. 용량에 도달하는 가장 작은 UE 수이고 샘플 손실이 가장 적다
  ("NUM_UES 선택" 참고).
- 용량 12·보유 7초 진단 프로필의 기존 관측 결과는 "점유와 거절 관측"에 있다.
- `-o`는 추정 점유 목표다. 실제 부하 수준은 CU 로그에서 별도로 확인한다.
- `-d`는 킬 스위치다. UE 내부에서 공격 생성을 멈추고, 실행기가
  같은 시간에 OAI가 지원하는 2단계 SIGINT로 UE 프로세스를 종료한다.
  5초 안에 종료하지 않아 SIGKILL이 필요하면 런은 무효다.

### 7단계 — 중지

```bash
pkill -INT -x nr-uesoftmodem
```

`-d 0`으로 시간 제한 없이 돌린 경우 두 킬 스위치가 **의도적으로 해제**되므로
사람이 킬 스위치다. 위 명령으로 중지한다.

종료 코드는 그대로 보고된다. `130`은 SIGINT, `137`은 SIGKILL,
**`139`는 SIGSEGV이며 뒤의 두 경우는 런이 무효**다.

### 8단계 — 산출물과 자체 점검

런은 `$LOGDIR/<run_id>/`에 쌓인다. **같은 경로의 파일·디렉토리·심볼릭 링크가
이미 있으면 실행을 거부한다.** 기존 결과를 덮어쓰지 않는다. `run_id`는 ASCII
영문자·숫자로 시작하고 이후 영문자·숫자·`.`·`_`·`-`만 허용하며, 두 번째
문자 `O`는 기존 OAI 제약으로 허용하지 않는다.

| 파일 | 내용 |
|---|---|
| `run.json` | 스키마 버전, 시나리오, 모든 노브, 셀 파라미터, UE full commit, UE binary·RSS patch·runner/exporter·redactor·scanner SHA-256, 시작 시각·시계 증거 |
| `attempts.jsonl` | 불변 UE 정답 이벤트. 한 시도에 여러 이벤트가 속하며 **탐지기 입력으로 주지 않는다.** `-e 1` 런에서만 생성된다 |
| `ground_truth.jsonl` | `(run_id, ue, seq)`로 정규화한 시도당 정답. ACK가 불명확하면 RRCSetupComplete 미전송형을 확정하지 않는다 |
| `odu.log` | `ODU_LOG` 캡처 성공 시 이번 run에 append된 완전한 DU 로그 행만 담은 slice |
| `du_log_slice.json` | DU source inode·offset·시작/종료 미완결 byte·slice SHA-256 |
| `du_log_start.json` `du_log_capture.err` | 선택적 캡처 경계와 실패 진단 |
| `ue.log` | 가입자/auth 행을 제거한 UE 표준 출력. run 디렉터리 0700, 파일 0600 |
| `ue_redaction.json` `ue_redaction.err` | UE 로그 정제 상태·정제 행 수·출력 SHA-256과 실패 진단 |
| `sensitive_artifact_check.txt` | 봉인 직전 run 전체의 평문 credential 검사 성공 기록 |
| `gnb_boot.txt` | `GNB_RESTART_CMD`의 출력 |
| `run_stop.json` | 종료 상태·유효성·이유·DU ACK 조인 상태(`matched|no_match|capture_*|not_requested`)와 slice SHA-256·종료 시각 |
| `evidence_manifest.json` | 위 핵심 산출물의 run ID·크기·SHA-256을 종료 시 봉인한 manifest |

`rss-run`이 끝나면서 출력하는 자체 점검을 반드시 읽는다.

- **`[RSS]` 배너가 없으면 그 런은 무효다.** 노브가 파싱되지 않았다는 뜻이고,
  스크립트가 실패 코드로 종료한다.
- OAI source patch는 UICC 가입자 값과 direct Milenage 인증 벡터를 출력하지 않으며 runner도 UE 종료 직후 `ue.log`를 다시
  검사한다. 예상 밖 민감 행이 한 줄이라도 정제되면 재발로 보고 run을 무효화한다.
  봉인 직전 run 전체 검사에 실패하면 `evidence_manifest.json`을 만들지 않는다.
- `attempts`가 0이면 셀 탐색이나 랜덤 액세스에서 막힌 것이다. 공격 런에서는 실패
  코드로 종료한다. (`-e 0` 회귀 런에서는 공격 기록을 남기지 않으므로 0이 정상이다.)
- `RRCSetupComplete omission UE-side`는 UE scheduler가 ACK을 예약하고 Msg5를 생략한 후보 수다. `RRCSetupComplete omission final`은
  `ODU_LOG`가 설정되고 UE/DU 양쪽에서 유일한 exact FAPI ACK가 조인된 최종 수다.
  로그 캡처나 매칭이 없거나 모호하면 후보는 `RRCSetupComplete omission unknown`으로 남는다.
  `du_ack_join=no_match`는 slice만 정상 캡처됐다는 뜻이며 ACK 실패의 음성 정답이 아니다.
- `Msg3 UE-side`는 RRCSetupRequest 후 중단형의 MAC-confirmed 후보 수다. 최종
  `canonical_msg3_only=true`는 current-run CU slice에서 같은 TC-RNTI의 유일한
  `RRCSetupRequest`가 조인될 때만 별도 exporter 결과로 승격한다.
- `python3 analysis/evidence_manifest.py verify <run-dir>`로 산출물 hash와 run ID를
  확인한다. seal과 verify는 실행 중인 checkout의 현재 scanner로 run 디렉터리 전체도
  다시 검사하므로 그 checkout을 신뢰해야 한다. 최종 RRCSetupComplete 미전송 실증은 `--require-matched`까지 통과해야 한다.
- `--require-matched`는 봉인된 raw UE 이벤트와 DU 로그로 label을 재생성해 저장된
  `ground_truth.jsonl`과 정확히 일치하는지도 확인한다.
- `ch.timeout`(`Error, channel timeout`)이 많으면 샘플 손실이 크다는 신호다.
  `-u`를 줄인다.

### 9단계 — 판정 (CU 호스트에서)

```bash
bin/rss-report --since 2026-10-20T06:31:00 --until 2026-10-20T06:33:10 \
               --jsonl /root/rss-runs/<run_id>/attempts.jsonl
```

- **시간 창은 필수다.** 창 없이 읽으면 로그 전체 합계를 한 런의 수치로 착각하게
  된다(실제로 그런 사고가 있었다).
- 예시 날짜·시각은 실제 분석 구간으로 바꾼다. 구간은 **시작 포함, 끝 제외**다.
  시각과 시간대 표기는 **gNB 로그와 같게** 지정한다. `run.json`의 UTC 시각과 혼동하지 않는다.
- `HH:MM:SS`는 로그에서 날짜 구간이 하나로 정해질 때만 허용된다. 날짜가 모호하거나
  비어 있는 구간, 로그 범위 밖 구간은 거부한다. 전체 구간 지표에 필요한 시간 범위가
  로그에 없으면 분석을 중단한다.
- `--jsonl`은 선택이다. UE 호스트에서 CU 호스트로 복사해 오면 UE 쪽 시각도 함께
  나온다. **UE 요약은 전달한 JSONL 파일 전체**를 읽고 `--since`/`--until`은
  CU 로그에만 적용된다. 같은 기간인지 자동 확인하지 않으므로 서로 다른 기간의
  수치를 직접 비교하면 안 된다. 생략하면 CU 로그만 분석한다.
- 용량 12·보유 7초 진단 프로필에서는 `--capacity 12`를 함께 넘긴다. 기본값은 96이다.
- 출력 해석은 아래 "판정 읽기"에 있다. 판정은 공격자 쪽이 아니라 **gNB 자신의
  로그**에서 나온 관측값이며, 실제 사용자 서비스 거부를 직접 판정하지 않는다.

### 10단계 — 원복

```bash
bin/rss-gnb-profile --role du restore     # 용량 12·보유 7초 진단 프로필를 적용했다면
bin/rss-gnb-profile --role cu restore
# gNB 재기동으로 설정을 다시 읽게 한다
```

UE 바이너리의 기존 사본은 `bin/rss-build`가 남긴 `.orig`에 있다. OAI 소스의
변경은 직접 확인·보존한 뒤 처리해야 하며, 브랜치 전환만으로 원복되지는 않는다.

### 문제 해결

| 증상 | 원인과 조치 |
|---|---|
| `bin/rss-doctor`가 블로커를 냄 | 각 `[FAIL]` 줄이 해결 명령을 알려 준다. 그것부터 한다 |
| `[RSS]` 배너가 없다 | 패치가 빠진 바이너리. `bin/rss-build`를 다시 돌리고 노브 체크가 통과하는지 확인 |
| `unknown option: --rss.*` 뒤 종료 | RSS config eager-init이 빠진 옛 curated 빌드다. 최신 `rss-ue-curated.patch`를 clean w38에 다시 적용·빌드한다. 뒤따르는 ZMQ channel-0 assertion은 종료 경로의 2차 증상일 수 있다 |
| `RSS patch does not apply cleanly` | OAI 소스가 이 패치와 호환되지 않거나 이미 적용됐다. 기준 `2026.w38` 또는 검증된 수정 브랜치의 깨끗한 소스를 확인하고 강제 적용하지 않는다 |
| `OAI PUCCH crash fix does not apply cleanly` | 수정이 없거나 이미 적용된 것으로 판정할 수 없는 OAI 소스다. 원본 `2026.w38` 또는 검증된 수정 브랜치를 확인하고 강제 적용하지 않는다 |
| `no build dir ... build stock OAI once first` | `bin/rss-bootstrap`을 먼저 돌린다 |
| 빌드가 라이브러리 부족으로 실패 | `bin/rss-bootstrap --deps`를 한 번 돌린다 |
| 시도가 0, 셀 탐색 실패 | 셀 파라미터 불일치, 또는 DU가 떠 있지 않음. ZMQ면 `GNB_RESTART_CMD` 설정 |
| UE가 `Intializing UE Threads`에서 멈춘다 | DU와 UE의 ZMQ 스트림이 어긋났다. `GNB_RESTART_CMD`로 DU를 함께 재기동해야 한다 |
| `run_id ...: second character must not be 'O'` | OAI의 `-O` 파싱 버그(두 번째 글자가 `O`인 인자를 설정 파일 옵션으로 오인). 런 id를 바꾼다 |
| `Error, channel timeout`이 많다 | 샘플 손실. `-u`를 2 이하로 내린다 |
| `cannot read /tmp/ocu.log` | CU 로그가 없는 호스트이거나 권한 부족. `--log`로 경로를 주거나 sudo |
| gNB 재기동 명령이 끝나지 않는다 | `GNB_RESTART_CMD`에 파이프라인을 썼다. 단일 명령으로 바꾼다 |
| `gNB did not become ready` | `GNB_READY_CMD`가 제한 시간 안에 성공하지 않았다. `gnb_ready.txt`에서 DU/F1/ZMQ 준비 실패를 확인한다. 이 경우 UE는 실행되지 않는다 |
| `another broker witness run is active`가 실행 종료 뒤에도 남음 | gNB/broker 자식이 lock FD 9를 상속한 옛 실행기다. 최신 `bin/rss-broker-witness`는 모든 장기 자식 경계에서 `9>&-`로 닫는다 |
| broker 결과가 `sync_ues < 5` / `startup.sync_timeout: true` | 5 UE GNU Radio 시작 경합. 공격 효과가 아니라 인프라 무효다. 실행기는 기본 30초 뒤 관측 창을 시작하지 않고 정리한다. 수동으로 새 run id를 쓰거나 `bin/rss-broker-witness-retry`로 이 조건만 제한 재시도한다 |
| broker 결과의 `teardown.*`가 137/139 또는 `forced_kill_count > 0` | 각각 SIGKILL/SIGSEGV/강제 종료 진단값이다. 현재 2단계 UE 종료의 정상값은 UE 5개·broker exit 0, forced kill 0이다. 이상이 있으면 재시도 wrapper도 중단하며 원문과 kernel journal을 확인한다 |
| 점유가 올라가지 않는다 | 용량과 유지 시간을 먼저 실측한다. "점유와 거절 관측" 참고 |
| 모든 접속이 거절된다 | CU에 AMF나 CU-UP가 연결돼 있지 않다. OCUDU는 그 경우 모든 `RRCSetupRequest`를 거절한다 |

---

## 파라미터

세 가지 방식 모두 동작하고, 다음 순서로 덮어쓴다.
**명령행 > `conf/rss.conf` > 환경변수 > 내장 기본값.**

스크립트가 설정 파일을 먼저 읽어 들이므로, **설정 파일에 적힌 키는 같은 이름의
환경변수를 덮는다.** 환경변수로 넘기고 싶으면 그 키를 설정 파일에서 주석 처리한다.

### 공격 형태

| 옵션 | 환경변수 / conf | 기본값 | 의미 |
|---|---|---|---|
| `-e 0\|1` | `ENABLE` | 0 | 공격 off(정상 UE) / on |
| `-u N` | `NUM_UES` | 1 | 하나의 무선을 공유하는 공격 UE 인스턴스 수 |
| `-i MS` | `INTERVAL_MS` | 0 | 시도 사이 추가 지연. 0 = 무선이 허용하는 최대 속도 |
| — | `PHASE_MS` | 0 | non-probe UE의 매 재시도에 `UE ID × PHASE_MS`를 더하는 지속 stride(0..5000ms). probe와 attack-off에는 적용하지 않는다 |
| `-d SEC` | `MAX_DURATION_S` | 60 | 킬 스위치. **0 = 중지할 때까지 계속** |
| `-o N` | `TARGET_OCCUPANCY` | 0 | UE 측 추정 점유 목표. 실제 gNB 점유 보장은 없음. 0 = 목표 제한 없음 |
| `-H MS` | `HOLD_MS` | 2000 | 내 gNB의 유지 시간. 점유 제어기가 사용한다 |
| `-c PCT` | `COMPLETION_PCT` | 0 | **1회성 점검용.** 0보다 크면 시도 하나를 정상 완료시키고 **그 지점에서 런을 끝낸다.** 혼합 트래픽을 지속 생성하는 노브가 아니다 |
| `-r 0\|1` | `HONOR_REJECT` | 1 | `RRCReject`의 waitTime을 지킴 / 즉시 재시도 |
| `-g 0\|1` | `ACK_GATE` | 1 | Msg4 ACK가 대기 중이면 랜덤 액세스를 다시 시작하지 않음 |
| `-G 0\|1` | `RA_GATE` | 1 | 랜덤 액세스가 진행 중이면 다시 시작하지 않음 |
| `-M 0\|1` | `MSG4_WAIT` | 1 | 1 = Msg4 ACK 뒤 Msg5 생략(RRCSetupComplete 미전송형). 0 = MAC-confirmed Msg3 뒤 즉시 RA 초기화(RRCSetupRequest 후 중단형) |
| `-p N` | `PROBE_UES` | 0 | 인스턴스 0..N-1을 공격 대신 **정상 UE**로 돌린다. 연결·등록·PDU 세션까지 수행하며 "정상 UE가 여전히 붙을 수 있는가"를 재는 측정기다 |
| `-t MS` | `PROBE_DELAY_MS` | 0 | probe의 첫 접속 지연. 혼합 프로세스는 첫 non-probe MAC-confirmed Msg3부터, 전부 probe인 독립 프로세스는 프로세스 시작부터 잰다. SIB1의 자동 첫 RA도 그동안 막는다 |
| — | `PROBE_RA_ONLY` | 0 | 1이면 probe도 Msg5를 생략하고 RA만 반복한다. RRC admission 계측이며 정상 접속/PDU 증거가 아니다 |
| — | `PROBE_INTERVAL_MS` | 1000 | RA-only probe의 최소 재시도 간격. probe가 스스로 CU를 포화시키지 않게 한다 |
| `-A 0\|1` | `MSG4_ACK` | 1 | 0 = 공격 UE가 Msg4를 복호한 뒤 최초와 재전송 HARQ-ACK PUCCH를 DTX로 만든다. probe는 항상 ACK한다. p5 단일 공격 UE ACK-on/off 비교 3회에서 ACK 64~65→0, DTX 18~20→456~477, max-retx 0→38~40을 확인했다. 정상 UE 서비스 영향은 미검증이다. `-A 0`과 `-c > 0`은 함께 쓸 수 없다 |
| — | `GNB_SETTLE_S` | 4 | `GNB_STOP_CMD`과 `GNB_RESTART_CMD` 사이 대기. `pkill -9`는 F1-U 소켓 해제보다 먼저 반환하므로 즉시 재기동하면 2152 바인드가 실패하고 **죽은 셀을 상대로 런이 계속된다** |
| — | `GNB_READY_CMD` | 비움 | 0으로 끝날 때까지 폴링하는 배치별 읽기 전용 준비 검사. DU/F1/ZMQ가 실제 준비되었는지 확인하며, 실패하면 UE를 띄우지 않는다 |
| — | `GNB_READY_TIMEOUT_S` | 30 | readiness 전체 제한 시간(1~300초) |
| — | `GNB_READY_INTERVAL_S` / `GNB_READY_PROBE_TIMEOUT_S` | 1 / 5 | 검사 사이 대기 / 검사 한 번의 제한 시간 |
| — | `ODU_LOG` | 비움 | 선택적 local/mounted 단일-sector OCUDU DU 로그. `log.fapi_level: debug`가 필요하며 runner가 이번 run의 완전한 행만 봉인한다 |
| — | `ODU_SECTOR_ID` | 비움 | `ODU_LOG` 사용 시 필수인 0..65535 sector ID. run.json에 기록하고 모든 FAPI 후보 prefix와 대조한다 |
| — | `GATE_TIMEOUT_MS` | 500 | 게이트가 이만큼 붙잡고 있으면 재시도를 강제한다(0 = 강제 없음). 명령행 옵션은 없다 |
| `-n ID` | `RUN_ID` | 자동 | 런 식별자 |

**`TARGET_OCCUPANCY`는 UE 측 점유 추정값을 사용한다.** 최근 로컬 이벤트와
`HOLD_MS`의 고정 보유시간 가정에 의존하며, gNB의 실제 점유를 피드백받지 않는다.
조기 해제나 보유시간 변동으로 실제 점유와 달라질 수 있다. 과거에 목표 3·6·12와
CU 로그 수치가 일치했다는 내부 기록은 있지만 원본은 이 패키지에 없다.
이 추정값을 탐지 평가의 정답 라벨로 사용하지 말고 CU 로그 관측값과 구분한다.

### 무선 효율

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `RSS_ZMQ_TX_WAIT_US` | `-2` | ZMQ TX 스레드가 로컬 샘플을 기다리는 방식: `0` 업스트림의 블로킹 10 ms 폴, `>0` usleep(n), `-1` 스핀, `-2` 조건 변수 |
| `RSS_SHARE_LOCKSTEP` | `1` | UE별 하향 커서를 함께 묶어 둔다 |
| `RSS_SHARE_NUE` | `NUM_UES` | 공유 무선 배치의 PHY 인스턴스 수. `rss-run`은 부분 배치를 거부한다. 연결된 probe도 PHY 샘플을 쓰므로 제외하면 uplink가 부분 flush되어 타임스탬프 역행·채널 timeout·크래시가 발생한다. 독립 정상 UE 증거가 필요하면 별도 프로세스/RF 경로를 쓴다 |
| `RSS_SHARE_WR_MONOTONIC` | `0` | **0으로 유지.** "기각된 최적화" 참고 |

### 셀, 경로, 배치

`OAI`, `UE_BIN`, `UE_CFG`, `UECAP`, `LOGDIR`, `BAND`, `DL_FREQ`,
`NUMEROLOGY`, `PRB`, `DEVICE`, `ZMQ_TX`, `ZMQ_RX`, `UE_TASKSET`,
`GNB_TASKSET`, `UE_EXTRA`, `GNB_RESTART_CMD`, `GNB_STOP_CMD`, `GNB_READY_CMD`, `ODU_LOG`, `ODU_SECTOR_ID`,
`CLOCK_SYNC_METHOD`, `CLOCK_OFFSET_NS`, `CLOCK_UNCERTAINTY_NS`,
`CLOCK_EVIDENCE_SHA256`, `GNB_LOG`, `CAPACITY`. 모두 `conf/rss.conf.example`에
주석으로 문서화돼 있다.
현재 `DEVICE`는 `oai_zmqdevif`만 허용한다. `UE_EXTRA`는 로그·스레드 튜닝용이며
radio/cell/`--rss.*`/`-O`/`--num-ues`처럼 실행기가 소유한 옵션은 덮어쓸 수 없다.
시계 offset·uncertainty가 실측되지 않으면 기본값 `unmeasured`/`null`을 유지하며,
호스트 간 탐지·대응 지연은 점수화하지 않는다.

**ZMQ 테스트베드에서는 `GNB_RESTART_CMD`가 중요하다.** ZMQ 가상 무선은 자체
클럭이 없다 — 샘플 교환 자체가 클럭이다. 그래서 DU와 UE가 같이 시작하지 않으면
두 스트림이 끝까지 정렬되지 않는다. 여기에 DU 재기동 명령을 넣는다.

`GNB_RESTART_CMD`가 0으로 끝난 사실만으로 서비스 준비가 증명되지는 않는다.
배치에 맞는 `GNB_READY_CMD`를 두어 DU 프로세스, F1 association, ZMQ/SDR 준비 신호를
확인한다. 이 명령은 읽기 전용이고 빨리 반환해야 하며, 값 자체는 `run.json`에 기록하지
않는다(자격증명 유출 방지). 활성화 여부와 제한 시간만 기록한다.

### 독립 5 UE broker witness

`bin/rss-broker-witness`는 `BROKER_SYNC_TIMEOUT_S`(기본 30초) 안에 다섯 UE가 모두
`Initial sync successful`을 남겨야 요청한 관측 시간을 시작한다. 미달이면
`reason: infrastructure_failure`, `startup.sync_timeout: true`로 조기 종료한다. 이
제한값은 아직 percentile로 교정되지 않은 운영값이다. 후속 control 15회를 사전고정해
sync 제한 60초·관측 60초로 실행한 결과 5회는 30초 안에 5/5가 됐고, 31~60초의 늦은
sync는 0회, 나머지 10회는 60초까지 0/5인 clean timeout이었다. 즉 현재 관측은
fast-success/stuck-0/5 이봉형이므로 30초 운영값은 유지할 수 있지만 percentile 보장은
아니다. sync-ready 5회 중 유효 control은 3회, semantic invalid는 2회였다.

종료 뒤 `teardown.ue_exit_statuses`와 `teardown.broker_exit_status`를 기록한다.
과거 r21/r3의 종료 충돌은 broker가 아니라 OAI UE `UL__actor`의 `init_RA()`에서
발생했다. OAI w38은 첫 INT를 NAS deregistration 요청으로 쓰므로 실행기는 UE마다
INT를 두 번 보내고 최대 5초 기다린다. 실기 3회에서 UE 5개와 broker가 모두 exit 0,
`forced_kill_count: 0`, kernel SIGSEGV 0이었다. 후속 15회도 전부 clean teardown,
segfault 0이었다. 관측 경계에서 동결한
`crash_markers`와 종료 진단은 계속 분리한다.

시작 경합만 제한 재시도하려면 다음 wrapper를 쓴다. 각 시도는
`BASE-try01`…의 별도 불변 디렉토리에 남는다. 유효한 서비스 실패, 의미적 무효,
손상된 결과, 종료 이상은 재시도하지 않는다.

```bash
bin/rss-broker-witness-retry control -n bw-control-1030 -a 3 -d 60
bin/rss-broker-witness-retry attack  -n bw-attack-1030  -a 3 -d 60
```

fail-fast와 제한 재시도는 `sync=0` 시작 경합 자체나 대조군 ping 품질 변동을 해결하지
않는다. 종료 수정과 제한 재시도의 실기·회귀 근거는
[`artifacts/broker-stability-20261030/`](../../artifacts/broker-stability-20261030/)에 있다.
15회 캠페인의 유효 c04/c07/c13은 각각 attach 1/3/36초, ping 손실
93.3333%/93.5484%/0.833333%였다. 원문 해시와 분류는
[`artifacts/broker-sync-sampling-20261030/README.md`](../../artifacts/broker-sync-sampling-20261030/README.md)에
있다. 이 표본으로 안정적인 DoS나 서비스 보존을 주장하지 않는다.

---

## 점유와 거절 관측

점유는 정상상태에서 **컨텍스트 생성률 × 평균 보유시간**으로 근사할 수 있다.
요청 시도율·수락률·로그 발생률은 서로 다르며, 이 근사만으로 포화나 서비스
거부를 판정할 수 없다. 아래는 원본을 포함하지 않은 내부 실험 요약이다.

```
평균 점유의 근사  =  컨텍스트 생성률 × 평균 보유시간
```

### 기본 cleanup 프로필

내부 기록은 용량 96, 유지 약 2초, 시도율 33~38회/초를 보고했다.
**기록된 결과: 용량에는 버스트로 도달했다**
(`RRCReject`와 함께 피크 96). 다만 96에서의 최장 연속 평탄 구간은 0.93초였다.

기본 설정에서 *유지되는* 것: 점유 **48 이상이 120초 런의 99%, 연속 평탄 구간
55.41초** (2 UE). `-o`는 실제 점유가 아닌 추정 점유 목표다.

```bash
bin/rss-run -e 1 -u 2 -o 48 -H 1900 -d 0     # 추정 점유 목표 48, 시간 제한 없음
```

### 용량 12·보유 7초 진단 프로필

`bin/rss-gnb-profile`은 **설정만으로** 셀 용량을 낮춘다 — gNB 소스는 건드리지
않는다. `.orig` 백업을 남기고 멱등적으로 동작한다.

```bash
# 각 설정 파일을 가진 호스트에서 실행
bin/rss-gnb-profile --role du apply     # 용량 96 -> 12, t300 -> 2000 ms
bin/rss-gnb-profile --role du show      # 적용됐는지 확인(앵커 키가 없으면 apply가 실패한다)
bin/rss-gnb-profile --role cu apply     # 절차 가드 -> 5000 ms
bin/rss-gnb-profile --role cu show
# gNB를 재기동해 설정을 다시 읽게 한 뒤:
bin/rss-run -e 1 -u 2 -r 0 -H 1500 -d 0
...
bin/rss-gnb-profile --role du restore
bin/rss-gnb-profile --role cu restore
```

내부 기록은 용량 12 조건의 두 실행을 비교한다. 점유는 420초 런 중 **200초 구간**,
거절 카운터는 **123.2초 구간**으로 기록돼 있으며 정확한 경계와 원본 로그는 없다.
서로 다른 창의 비율을 결합하거나 고유 UE·메시지 수로 해석하면 안 된다.

| | `-r 1` (기록상 102초 창) | `-r 0` (점유: 기록상 200초 창) |
|---|---:|---:|
| 내부 기록의 시도/초 | 5.6 | 6.5 |
| 피크 점유 | 12 / 12 | 12 / 12 |
| `RRCReject` 포함 로그 행 | 388 | 7,551 (기록상 123.2초 창) |
| `DU is not able to serve the UE` 포함 로그 행 | 130 | 2,517 (기록상 123.2초 창) |
| 점유 >= 6 / 12 | — | 100%로 반올림, 최장 연속 199.8초 |
| 점유 >= 9 / 12 | — | 94%, 최장 연속 15.2초 |
| 점유 >= 12 / 12 | — | 33%, 최장 연속 0.87초 |
| 거절 로그 사이 최장 공백 | — | 0.45초 |
| `rrcSetupComplete` / `InitialUEMessage` 포함 로그 행 | 0 / 0 | 0 / 0 |

이 기록은 점유 변화와 거절 로그가 반복됐다는 내부 관측이다. 원본 로그와 집계
버전이 없어 수치·창·중복 여부를 재검증할 수 없다. 정상 UE 접속 실패는 측정하지
않았으므로 **지속적인 사용자 서비스 거부나 최대용량 유지의 증거가 아니다.**

> **장기 실행의 내부 기록:** 약 **36.5분** 런에서 점유 >= 6 / 12가
> **98%, 최장 연속 426.1초**로 보고됐다. 거절 로그 사이 최장 공백은 **2.53초**다.
> 2191초 창과 25.2초 ramp-up의 관계가 불명확해 전체 기간의 지속성을 확정할 수 없다.
> 그보다 긴 실행의 안정성도 미검증이다. [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) §8 참고.

`bin/rss-report`는 로그에서 재구성한 점유와 패턴 발생 횟수·간격을 보고한다.
거절 로그의 반복은 정상 사용자가 실제로 서비스를 받지 못했다는 측정과 구분한다.

### 시간 제한 없이 실행

```bash
bin/rss-run -e 1 -u 2 -r 0 -d 0       # 시간 제한 없음
pkill -INT -x nr-uesoftmodem          # 중지
```

`-d 0`에서는 두 킬 스위치가 의도적으로 해제되므로 **사람이** 킬 스위치다.
`-d N`이면 독립적인 두 개가 걸린다: 프로세스 내부 타이머와 `N+20`초의 외부
`timeout`.

---

## NUM_UES 선택

레퍼런스 테스트베드 실측 (OCUDU 26.10, gNB 기본 설정, 용량 96, 유지 2000 ms,
60초 런, 공유 ZMQ 무선 1개):

| UE | 시도/초 | 피크 점유 | `RRCReject` | `channel timeout`(샘플 손실) | 200 ms 이상 공백 |
|---:|---:|---:|---:|---:|---:|
| 1 | 33.8 | 90 / 96 | 0 | 0 | 0 |
| 2 | 38.6 | **96 / 96** | 33 | 5,136 | 3 (런의 5%) |
| 3 | 36.2 | 96 / 96 | 198 | 14,718 | 22 (39%) |
| 4 | 37.4 | 96 / 96 | 312 | 39,765 | 25 (45%) |

"UE가 많을수록 좋다"가 아니므로 주의해서 읽어야 한다.

- **시도 레이트는 2 UE를 넘으면 늘지 않는다.** 모든 인스턴스가 무선 하나와 DU
  MAC 하나를 공유하므로, 공유 계층이 36~38회/초에서 포화된다.
- **늘어나는 것은 샘플 손실이다.** 디바이스는 자신이 이미 지나친 타임스탬프의
  상향 write를 버리고, 인스턴스가 많아지면 그 비율이 올라간다.
- 손실은 **1초 단위 정지**로 나타나고, 그동안 점유가 빠진다. 4 UE에서는 런의
  45%가 그런 공백 안이고, 2 UE에서는 5%다.
- 따라서 **2 UE가 권장값**이다. 용량에 도달하는 가장 작은 수이면서 정지가 가장
  적다.

탐지기 학습용으로 손실 없는 깨끗한 시도 스트림이 필요하면 1 UE를 쓴다(샘플 손실
0, 다만 90/96에서 멈추고 거절이 발생하지 않는다). `RRCReject` 이벤트를 많이
만들고 싶고 처리량 수치는 상관없을 때만 3~4 UE를 쓴다.

---

## 판정 읽기

`bin/rss-report`는 세 블록을 출력한다.

**점유(Occupancy)** — gNB 로그에서 UE id로 짝지은 동시 미완료
`RRC Setup Procedure` 수와 각 수준에 머문 관측 시간이다. 현재 출력은
`observed occupancy`로 표시하고, 초기 점유가 불명확하거나 이벤트를 짝짓지
못하면 경고한다. 아래는 **독립 검증되지 않은 과거 출력 발췌**이며 현재
파서로 다시 계산한 결과가 아니다.

```
(과거 출력 발췌)
peak occupancy 96   at 06:31:24
sustained occupancy
  >=  48   56.4 s of 59 s ( 95%)   longest plateau 50.33 s
  >=  96   12.6 s of 59 s ( 21%)   longest plateau  0.93 s
```

*비율*이 높은데 *최장 평탄 구간*이 1초 미만이면 포화 유지가 아니라 톱니파다.
비율만 보면 오해를 부르기 때문에 두 숫자를 함께 출력한다.

**gNB 로그 패턴 발생 횟수** — `RRCReject`, `DU is not able to serve the UE`,
`rrcSetupComplete`, `NGAP InitialUEMessage`. 고유 메시지·UE 수가 아니며, 로그
중복과 로깅 범위의 영향을 받는다. 점유도 로그에서 재구성한 관측값이다.

**UE 측** — 시도 횟수와 한 시도 주기의 비용 분해.

### 주장할 수 있는 것

| 주장 | 필요한 근거 |
|---|---|
| 설정된 자원 한도에 도달했다 | 피크 점유가 용량에 도달 **그리고** `RRCReject` 존재 |
| 포화가 유지됐다 | 높은 비율만이 아니라 용량에서의 긴 평탄 구간 |
| RRCSetupComplete 미전송형과 일치하는 관측이다 | 충분한 로깅 범위에서 `rrcSetupComplete`와 `NGAP InitialUEMessage`가 관측되지 않음. 0건만으로는 입증 불가 |
| 정상 사용자가 서비스를 거부당했다 | 별도의 정상 UE가 접속 실패하는 것을 실측 |
| "gNB를 무력화했다" | 위 두 행을 함께 |

직접 ZMQ 포트 쌍 하나로는 마지막 두 항목을 볼 수 없다. GNU Radio 5 UE broker로
별도 프로세스 일반 witness 경로는 만들었지만 `sync=0` 경합, baseline 고손실과
비결정적 서비스 결과가 남아 안정 증거는 아니다.

---

## 도구에 들어간 최적화

아래는 모두 가정이 아니라 측정의 결과다.

**1. ZMQ TX 웨이크업 (시도 레이트 약 3배).** 업스트림의 TX 폴 스레드는 소켓
이벤트로만 깨어날 수 있다. 샘플 요청은 도착했지만 로컬 TX 큐가 아직 비어 있으면,
상대는 응답을 기다리며 블록된 상태라 더 이상 아무것도 보내지 않는다. 그래서
`zmq_poll`은 자기 자신의 **10 ms** 타임아웃으로만 복귀한다. UE와 DU는
`127.0.0.1`로 통신하고 왕복은 수십 마이크로초이므로, 그 10 ms는 전송 지연이 아니라
타임아웃 상수다: 1 ms 미만의 늦음이 무선 프레임 하나를 통째로 잡아먹었다. 수정 전
내부 기록: 요청 4,250건, 누적 대기 42,555 ms, 요청당 약 **10.01 ms**.
런·프로세스 수명에 관한 기록의 분모가 일치하지 않아 점유 비율은 제시하지 않는다.

| | 업스트림 (`=0`) | 수정 (`=-2`) |
|---|---:|---:|
| 벽시계 1초당 무선 시간 | 0.46-0.54 | **2.39-2.46** |
| 시도/초 | 6.7 | **19.5-33.8** |
| 피크 점유 | 20 / 96 | **90-96 / 96** |

**2. 한 프로세스 안에서의 무선 공유.** 여러 UE 인스턴스가 ZMQ 무선 하나를
공유한다. 한 인스턴스가 각 슬롯을 가져오고 나머지는 복사본을 받으며, 모든
인스턴스의 상향은 하나의 디바이스 write로 합산된다. 커스텀 C ZMQ broker는
REQ/REP 경계와 샘플 처리가 불안정해 기각했다. 공식 srsRAN GNU Radio flowgraph를
확장한 5 UE broker는 별도 프로세스 witness 실험에만 유지한다.

**3. UE별 읽기 커서.** 라운드로빈 복사는 호출자가 요청한 것과 다른 샘플 수를
반환해서 OAI의 `unitTransfer == res` 어서션을 깨뜨렸다. 커서를 쓰면 각
인스턴스가 요청한 만큼을 스트림 순서대로 정확히 받는다.

**4. 락스텝 커서 (`RSS_SHARE_LOCKSTEP=1`).** 인스턴스들은 셀 탐색 후 서로 다른
스트림 위치에서 합류해 일정한 오프셋을 유지하는데, 그러면 모든 슬롯이 병합된
배치 하나 대신 인스턴스마다 상향 배치 하나를 만든다. 게이트가 이들을 함께
묶는다. 효과는 부분적이며 4 UE 실측: 순서 어긋난 배치 9.19% -> 7.70%, 샘플 손실
33,144 -> 27,139, 무선 시간 1.12 -> 1.26.

**5. 오프라인 로그 분석.** `analysis/cu_occupancy.py`는 절차의 시작과
종료를 UE id로 짝지어 피크만이 아니라 평탄 구간을 보고한다. `analysis/cu_count.py`는
런 구간 안에서만 비교한다. 둘 다 이전 버전이 로그 전체 합계와 피크만을 조용히
보고했기 때문에 존재한다.

---

## 기각된 최적화 (다시 시도하지 말 것)

| 아이디어 | 결과 |
|---|---|
| `TRANSMIT_TS_ALIGN_TIMEOUT` 상향 | 구조상 무효과: `align()`은 타임아웃을 쓰기 전, 첫 분기에서 "timestamp passed"로 반환한다 |
| 슬립 대신 `sched_yield` 스핀 (`=-1`) | 굶은 대기 28.5초 -> 0.117초이지만 무선 시간 2.15 -> 1.26이고 시도가 줄었다. 자신이 기다리는 생산자 스레드를 굶긴다 |
| usleep 대신 조건 변수 (`=-2` vs `>0`) | 비용 동일: 237 us vs 240 us. 남은 대기는 대기 방식이 아니라 생산자의 실제 지연이다. CPU를 태우지 않으므로 기본값으로 유지 |
| ~~`MSG4_WAIT=0` (Msg3에서 포기)~~ — **기각 철회(2026-10-30)** | 과거 10,878 시도 대 컨텍스트 1개는 Msg3 PUSCH가 PHY로 넘어가기 전에 `reset_ra()`가 지운 훅 결함이었다. 현재는 MAC scheduler의 실제 `nr_rss_note_msg3_tx()` → atomic MAC/RRC bridge → `GO_TO_IDLE_KEEP_CAMPED` reset 순서다. p5 G2에서 10/10 CU 요청 조인을 확인했다 |
| `RSS_SHARE_WR_MONOTONIC=1` | 샘플 손실 21,178 -> 0이지만 시도 2387 -> **32**. 클램프가 flush당 읽기 1회씩 전진하는데 이는 슬롯당 flush 1회를 가정한다. 실제로는 더 많아서 미래로 달아났다 |
| 코어 핀닝 (`UE_TASKSET`) | 더 나쁨: 33.8 -> 24.2 시도/초, 피크 90 -> 51 |
| `ACK_GATE=0` | 변화 없음 (34.1 vs 33.8 시도/초) |

---

## 알려진 한계

- **한 시도 주기는 무선 시간 40 ms를 쓰고**, 그중 30 ms가 랜덤 액세스 절차
  자체다. UE가 줄일 수 없으므로 이 테스트베드에서 단일 인스턴스는 35회/초
  근처가 상한이다.
- **gNB 기본 설정에서는 포화 유지를 입증하지 못했다.** 용량에는 도달하지만(피크
  96, 거절 발생) rate-v2 D4의 96 최장 연속 평탄 구간도 0.885초였다. 제공률은
  48.652/s로 cleanup 39.407/s보다 높았지만, 8.558/s가 DU에서 선행 거절돼 실제
  admission률이 cleanup과 평형을 이뤘다. 평균 요청률이 아니라 모든 짧은 창의
  admitted start률을 기준으로 판정한다.
- **무선 시간은 실시간이 아니다.** TX 수정 이후 단일 인스턴스에서는 실시간보다
  약 2.4배 *빠르게* 흐른다. ZMQ에 페이싱이 없기 때문이다. 초당 수치를 보고할
  때는 런 로그의 `air_per_wall`을 함께 적는다.
- **세션 간 수치가 흔들린다.** 4 UE 런 3회에서 시도는 2202~2387이었지만 샘플
  손실은 21k~40k, 무선 시간은 0.87~1.63이었다. 비교는 같은 세션 안에서만 한다.
- **같은 프로세스의 mixed probe는 독립 정상 UE 증거가 아니다.** 공유 무선의 모든
  인스턴스를 `RSS_SHARE_NUE`에 포함하지 않으면 uplink 부분 flush와 타임스탬프
  역행이 발생해 crash할 수 있다. 모두 포함한 수정 런도 channel timeout 157,990건과
  out-of-order 공유 TX가 남는다. G13에서는 지연 probe의 Msg3 10개가 CU 요청과
  `DU is not able to serve`에 10/10 조인됐고 G14에서는 Registration/PDU/TUN이
  회복됐지만, 이는 통제된 진단 witness다. 실행기는 부분 배치를 거부하며 독립
  정상 UE 서비스 영향은 별도 프로세스/RF 경로나 차폐 OTA에서 검증한다.
- **OCUDU의 `ConRes CE ACKed` 문자열은 실제 ACK 증거가 아니다.** 동일 조건 ACK-on/off 비교 3회에서
  모두 10건이었지만 ACK 억제군의 DU FAPI 결과는 매번 ACK 0건·DTX 456~477건이었다. 판정은
  DU `harq_ack=ack|dtx|nack`, DL HARQ max-retx, UE `msg4_ack_withheld`를 사용한다.
- **직접 ZMQ 포트 쌍 하나로는 공격자와 정상 UE를 동시에 붙일 수 없다.** 5 UE
  GNU Radio broker로 서비스 비교를 수행했지만 사전고정 control의 유효 세 런도 손실이
  0.833333%~93.5484%였고, 공격군은 service false/true로 갈렸다. 빈번한 `sync=0`과
  서비스 변동 때문에 정상 사용자 DoS나 서비스 보존의 결정적 증거로 쓰지 않는다.
  종료 SIGSEGV는 원인을 특정해 2단계 종료로 해소했다.
- **2-endpoint broker도 지속 거부에는 실패했다.** 한 OAI 공격 프로세스에 6 UE를
  묶고 별도 정상 witness 프로세스를 둬 CPU 경합을 줄였지만, witness는 한 번 거절된
  뒤 공격 중 Registration·PDU·ping에 성공했다. 이 경로는 독립 witness와 처리율
  진단용이며 정상 사용자 DoS 증거가 아니다.

---

## 파일

```
bin/rss-bootstrap    OAI 트리 받기 + 기준 커밋 + 최초 스톡 빌드
bin/rss-doctor       전제 조건 진단 (읽기만, 블로커면 종료 코드 1)
bin/rss-build        OAI PUCCH 수정·RSS 패치 적용 후 UE 빌드
bin/rss-run          실험 1회 실행
bin/rss-cu200        인공 hold32에서 3개 RRCSetupComplete 미전송 셀 + 별도 witness 셀을 묶는 CU 200 진단
bin/rss-broker-witness  1/4/6 load·attack 프로세스 + 1 일반 witness를 별도 프로세스로 실행
bin/rss-broker-witness-retry  깨끗한 5/5 sync timeout만 새 run id로 제한 재시도
bin/rss-report       gNB 로그 + UE JSONL로 판정
bin/rss-gnb-profile  용량 12·보유 7초 진단 프로필 적용·원복 (설정만, gNB 소스 무수정)
conf/rss.conf.example  모든 노브, 주석으로 문서화
conf/ota-inventory.example.json  비밀값 없는 차폐 OTA G0 inventory 템플릿
patch/rss-ue-curated.patch  기본 UE 측 패치 (OAI 2026.w38, RRCSetupComplete 미전송형+RRCSetupRequest 후 중단형+probe+Msg4 ACK)
patch/rss-ue.patch   2026-10-20 RRCSetupComplete 미전송형 기준 패치 보관본(기본 빌드에는 사용하지 않음)
patch/oai-pucch-null-fix.patch  OAI 공식 PUCCH 충돌 수정 (2026.w38 기준)
analysis/            점유, 카운터, 시도 비용 분해
analysis/check_sensitive_artifacts.py  파일·압축본의 가입자/auth 평문 재유입 검사
analysis/sanitize_ue_log.py  UE 로그를 봉인하기 전 원자 정제하고 hash report 생성
analysis/capture_du_log.py  append-only DU 로그에서 이번 run의 byte slice 봉인
analysis/evidence_manifest.py  run 산출물 SHA-256 봉인과 matched 증거 교차검증
analysis/check_sensitive_history.py  모든 local ref의 reachable Git blob credential 검사
analysis/export_labels.py  raw UE 이벤트와 DU/CU 증거를 보수적 시도당 정답으로 정규화
analysis/validate_ota_inventory.py  송신 없이 G0 누락·중복·비밀값을 fail-closed 검사
tools/multi_ue_5ue.py  srsRAN GNU Radio flowgraph의 5 UE 확장본
tests/test_broker_witness.py  broker 역할·수명·lock 회귀 테스트
tests/test_broker_witness_retry.py  제한 재시도 정책·불변 run id 회귀 테스트
tests/test_sensitive_artifacts.py  평문·archive credential 검사 회귀 테스트
tests/test_du_log_capture.py  DU 로그 rotation·truncate·완결 행 경계 회귀 테스트
tests/test_label_export.py  label v1과 exact FAPI ACK 조인 회귀 테스트
tests/test_ota_inventory.py  OTA G0 manifest 안전·완결성 회귀 테스트
docs/MECHANISM.ko.md 공격이 왜 통하는지: 소스·설정·실측 논증
docs/MEASUREMENTS.md 내부 측정 요약과 근거의 한계 (영문)
docs/CURATED-VALIDATION-20261030.ko.md clean 빌드·Msg4 ACK·독립 witness 비교 검증
docs/LABEL-CONTRACT.ko.md 정답·탐지·대응·효과 판정과 시간 동기 계약
docs/P5-DU-ACK-JOIN.ko.md p5에서 exact DU ACK join 1회를 검증하는 승인·원복 게이트
docs/RESPONSE-PATH-AUDIT.ko.md RRCSetupComplete 미전송형 대응 경로 감사와 CSI-DTX RLF hardening 전/후 비교
docs/OTA-SMOKE.ko.md 차폐 OTA inventory·RF 안전·정상 UE 1→2대·공격 실행 게이트
NOTICE.md            사용 제한·출처·라이선스 고지
```

모든 런은 `run.json`(모든 노브와 셀)과 `ue.log`를 남기고, **공격 런(`-e 1`)은
추가로 `attempts.jsonl`**(이벤트당 레코드 1건, 두 시계 모두 포함)을 남긴다.

**`attempts.jsonl`은 이벤트 피드다.** 공통 필드는 `type`, `run_id`, `ue`, `seq`,
`t_ns`(벽시계), `air_ms`(무선), `event`다. identity·의도/실제 도달 범위 등은
이벤트별 선택 필드이며 모든 행에 존재하지 않는다. 한 시도에 여러 이벤트가 속하고
런 상태 이벤트도 있으므로 행 수를 시도 수로 쓰면 안 된다.

## 비공개 GitHub 게시 범위

현재 검수 대상은 `reproducers/rrc-signaling-storm/`의 코드·문서와 상위 디렉터리의 프로젝트 문서,
검토한 artifact 최상위 README·SHA-256·campaign 메타데이터다. 이전
`rss-publish` 브랜치는 오래된 상태이므로 최종 변경을 커밋한 뒤에만 다시 만든다.
원시 실험 로그·압축본·개인 설정은 로컬에 보존하고 Git에는 올리지 않는다.

오프라인 분석 검사는 이 디렉토리에서 `python3 -m unittest discover -s tests`로
실행한다. 이 검사는 빌드·실장비·과거 측정값을 검증하지 않는다.
