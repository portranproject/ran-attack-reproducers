# 내부 측정 요약

기준 테스트베드는 OCUDU 26.10(srsRAN 계열)이며 CU와 DU를 서로 다른 호스트에 두고,
F1은 IP로 연결했다. 공격 UE는 DU 호스트에서 ZMQ 가상 무선
(`tcp://127.0.0.1`)을 사용했다. 셀은 n78, SCS 30 kHz, 51 PRB이고 OAI UE는
`1c2f4d3c2e68181cdef9f426d161163147ad4b77`(`2026.w38`)이다.

별도로 보존된 artifact를 명시한 절이 아니면, 아래 내용은 gNB 로그와 UE 계측에 근거한
과거 내부 기록이다. **과거 절의 원시 로그, run manifest, 정확한 관측창 경계와 분석
버전은 포함돼 있지 않다.** 인용할 때 이 구분을 유지해야 한다. 이 파일은 요약이지 현재
parser의 회귀 fixture가 아니다. §5는
`artifacts/p5-msg3-only-20261030/`에 보존된 최신 p5 증거를 기록한다.

일치하는 로그 행 수는 **고유 메시지 수나 UE 수가 아니다**. 중복 기록과 불완전한
관측 범위가 집계에 영향을 줄 수 있다. 일치 행이 0개라는 사실만으로 해당 이벤트가 전혀
없었다고 입증할 수 없다. 과거 절은 정상 사용자의 접속 실패를 측정하지 않았다. §5에서
추가한 것도 같은 프로세스의 ZMQ probe일 뿐 독립 UE가 아니다.
현재 오프라인 parser는 시작 시각 포함·종료 시각 제외의 명시적 관측창과 보수적인 관측
라벨을 사용한다. 아래 과거 출력은 이러한 검사를 도입하기 전의 결과다.

---

## 1. 가장 큰 영향을 준 단일 변경

upstream ZMQ TX poll thread는 socket 이벤트가 있어야만 깨어날 수 있다. sample 요청이
도착했지만 로컬 TX queue가 아직 비어 있으면 peer는 응답을 기다리며 막히고 추가 데이터를
보내지 않는다. 따라서 `zmq_poll`은 자체 10 ms timeout이 끝나야 반환할 수 있다.

계측한 단일 UE, 60초:

```
TX antenna 0: 4250 REQs starved / 36203 served,
              42555 ms waiting for the local TX queue
```

42555 / 4250 = **starved 요청당 10.01 ms**로 poll timeout과 정확히 같다.
초기 기록에는 process lifetime의 85%라는 주장도 있었지만 분모가 기록돼 있지 않고
명시된 60초 run과도 충돌한다. 따라서 lifetime 비율은 결과로 보존하지 않는다.

| | `RSS_ZMQ_TX_WAIT_US=0` (upstream) | `=-2` (기본값) |
|---|---:|---:|
| wall 1초당 radio time | 0.46 – 0.54 | 2.39 – 2.46 |
| starved 요청당 비용 | 10.01 ms | 0.185 ms |
| 처리한 요청 수 | 36,203 | 219,597 |
| 시도/s (wall) | 6.7 | 19.5 – 33.8 |
| 최대 점유 | 20 / 96 | 90 – 96 / 96 |

UE와 DU는 같은 호스트에서 loopback으로 연결돼 있으며, 기록에 따르면 왕복 시간은 수십
microseconds다. 이 대기를 timeout 탓으로 해석한 것은 추론이며 원시 timing 증거는 없다.

---

## 2. 시도 비용

`attempts.jsonl`의 두 시계를 읽는 `analysis/attempt_phases.py` 결과다.
단일 UE, gNB 기본 설정:

| 단계 | wall | radio | wall 비중 |
|---|---:|---:|---:|
| Msg3에서 Msg4까지 | 22.8 ms | 30 ms | **79%** |
| Msg4에서 재시작까지 | 3.6 ms | 10 ms | 13% |
| 재시작에서 다음 Msg3까지 | 1.2 ms | 0 ms | 4% |
| **주기** | **28.9 ms** | **40 ms** | 100% |

Msg3에서 Msg4까지의 radio time 30 ms는 wall time이 6배 차이 난 두 session
(radio/wall 0.29에서 100–113 ms, 1.41에서 22.8 ms)에서 같았다. 당시에는 한 수치를
schedule 관련 값으로 해석했다. 이 기록만으로 host 병목을 배제하거나 보편적인 rate
상한을 정할 수 없다. gNB log level 비교는 하지 않았다.

---

## 3. UE 수

60초 run, gNB 기본 설정(capacity 96, hold 2000 ms):

| UE | 시도/s | 최대 점유 | `RRCReject` | sample loss | 200 ms 이상 공백 |
|---:|---:|---:|---:|---:|---:|
| 1 | 33.8 | 90 / 96 | 0 | 0 | 0 |
| 2 | 38.6 | 96 / 96 | 33 | 5,136 | 3 (5%) |
| 3 | 36.2 | 96 / 96 | 198 | 14,718 | 22 (39%) |
| 4 | 37.4 | 96 / 96 | 312 | 39,765 | 25 (45%) |

2 UE로 실행한 120초 run은 3904회 시도(32.5/s), 최대 점유 96, hold 중앙값
1896 ms였고 200 ms 이상 공백은 4개(run의 1%)뿐이었다. 점유 48 이상은
**run의 99%였고 최장 연속 plateau는 55.41초**였다.

UE가 2개를 넘으면 시도율이 더 늘지 않는다. 모든 instance가 하나의 radio와 하나의
DU MAC을 공유한다. 대신 sample loss가 늘고, 그 손실이 점유를 비우는 수초짜리 정지로
나타난다.

---

## 4. 점유와 반복되는 거절 로그

내부 기록은 기본 설정에서 capacity 96, 약 2초의 hold, 33–38/s의 시도율을 보고한다.
기록된 최대 점유는 96이지만 full-capacity 최장 plateau는 0.93초뿐이었다. 별도의
축소 capacity 설정은 capacity 12와 약 1.6초로 측정된 hold를 사용했다. 이 수치만으로는
지속적인 capacity 점유나 사용자 서비스 거부가 성립하지 않는다.

2 UE, capacity 12. `HONOR_REJECT=0` 열은 420초 run(`ZWfinal-064626Z`) 중
200초 관측창이고, `=1` 열은 102초 관측창(`ZWsat-063645Z`)이다. 반면 거절 집계 행은
`=0`에 대해 보고된 123.2초 관측창을 사용한다. 정확한 경계와 관측창 사이 관계는 이
package만으로 검증할 수 없다.

| | `HONOR_REJECT=1` | `HONOR_REJECT=0` |
|---|---:|---:|
| 내부 기록 시도/s (정의·관측창 미검증) | 5.6 | 6.5 |
| 최대 점유 | 12 / 12 | 12 / 12 |
| hold 중앙값 | 1457 ms | 1610 ms |
| `RRCReject` 포함 로그 행 | 388 | **7,551 (보고된 123.2초 관측창)** |
| `DU is not able to serve` 포함 로그 행 | 130 | **2,517 (보고된 123.2초 관측창)** |
| 점유 6 이상 | — | **반올림 100%, 199.8초 연속** |
| 점유 9 이상 | — | 94%, 15.2초 연속 |
| 점유 12 이상 | — | 33%, 0.87초 연속 |
| `rrcSetupComplete` 포함 로그 행 | 0 | **0** |
| NGAP `InitialUEMessage` 포함 로그 행 | 0 | **0** |

기록은 `HONOR_REJECT=1`이 해당 관측창의 95% 동안 idle이었다고 설명한다. 이는 검증하지
못한 요약이며 특정 설정 하나가 거부를 지속한다는 통제된 증거가 아니다.

과거 counter 출력에는 123.2초 관측창, 최초 거절 로그까지 0.02초, 첫 발생 뒤
123.17초 span이 기록돼 있다. 보고된 공백은 p50 0 ms, p99 177 ms, 최대 454 ms
(표에서는 0.45초로 반올림)였다. 이는 서비스 가용성이 아니라 **로그 발생 간격**을
설명한다. 또한 200초 관측창의 점유 수치와 합쳐 해석할 수 없다.

---

## 5. p5에서 MAC으로 확인한 RRCSetupRequest 후 중단형 (2026-10-30)

초기 `MSG4_WAIT=0` 실험은 queue에 있던 Msg3가 PHY에 도달하기 전에 random access를
reset했다. 그 결과 UE counter는 증가했지만 gNB는 context 하나만 생성했다. 현재의
RRCSetupRequest 후 중단 구현은 MAC scheduler가 실제로 Msg3를 넘긴 다음으로 결정
시점을 옮기고, 그 확인을 RRC로 전달한 뒤 camped-idle reset을 수행한다. 이는
RRCSetupComplete 미전송형과 다른 별도 변종이다.

| run | 관측 결과 |
|---|---|
| `G2-msg3-0140` | UE `msg3_tx` 10건, 공격자 Msg4 0건, 고유 TC-RNTI 10/10이 current-run CU `Rx ... rrcSetupRequest`와 join |
| `G4-u1-i0-clean` | capacity-12 profile(`nof_cell_sr_res: 1`): MAC 확인 Msg3 661건과 CU 요청 661건, RRC procedure 시작 55건, `DU is not able to serve` 거절 606건, 복원 최대 점유 12 |
| `G13-pair-attack-valid` | 같은 capacity-12 profile: marker 인증 duration SIGKILL, 전체 Msg3 1,029건, 공격자/probe Msg4 0건, CU 요청 921건, 시작 84건, 자원 거절 837건, `InitialUEMessage` 및 PDU 성공 0건 |
| `G14-pair-recovery-control` | capacity-12 재시작 후 대조군, probe가 첫 시도에 접속해 Registration/PDU/TUN 완료 |
| `G34-control-cap96-hold32-valid` | 수정한 capacity-96 profile, attack-off Registration/PDU/TUN 성공 |
| `G35-msg3-cap96-hold32-probe` | 수정한 capacity-96 profile, probe TC-RNTI 11/11이 CU에 도달해 자원 거절, 10.13초 동안 Msg4/Msg5/연결 0건 |

G13 probe TC-RNTI 10개 모두 정확히 하나의 CU 요청과 하나의
`DU is not able to serve` 거절에 일치했다. 따라서 probe는 UE의 공유 radio 경로에서
사라진 것이 아니라 gNB에 도달했다. G4 최대 점유 12는 명시적인 SR resource override가
만든 것으로, 숨은 두 번째 pool의 증거가 아니다.

수정한 capacity-96 campaign은 먼저 지속 거부 가설을 반증했다. G21과 G32에서 모두
정상 probe가 연결됐다. G26은 원인을 연속 100회의 decode되지 않은 CSI report 뒤
`t310=1000ms`가 이어지는 것으로 분리했다. capacity를 바꾸지 않고 실험 cleanup
관측창을 늘려 G35를 만들었다. 그 결과 10.13초 동안 정상 probe Msg3 송신 11건,
정확한 CU 요청 11건, DU 자원 거절 11건, Msg4/Msg5/연결 0건이 관측됐다. 최종 profile과
hash는 [capacity-96 artifact](../../../artifacts/p5-msg3-cap96-20261030/README.md)에
보존돼 있다.

G13/G14는 **같은 OAI process와 공유 ZMQ radio**의 일반 probe를 사용한다. 이는 admission
거부와 재시작 뒤 서비스 가용성에 대한 통제된 진단 증거이지, 자연 회복이나 독립적인 실제
정상 UE DoS 결과가 아니다. 독립 서비스 영향 주장은 여전히 안정적인 별도 process
broker 또는 차폐 OTA witness가 필요하다. 선별한 JSON 증거, G13 CU slice와 hash는
[p5 RRCSetupRequest 후 중단형 artifact](../../../artifacts/p5-msg3-only-20261030/README.md)에
보존돼 있다.

---

## 6. 기각한 아이디어

| 아이디어 | 측정 결과 |
|---|---|
| `TRANSMIT_TS_ALIGN_TIMEOUT`을 0 ms보다 크게 설정 | 구조상 효과 없음. `align()`은 timeout을 읽기 전 첫 분기에서 "timestamp passed"를 반환한다 |
| `sched_yield` spin(`=-1`) | starved wait는 28.5초에서 0.117초로 줄었지만 radio time도 2.15에서 1.26으로 줄고 시도 수도 감소했다. 기다리는 producer를 굶긴다 |
| condition variable과 usleep 비교 | starved 요청당 237 us와 240 us. 남은 시간은 wait 기법이 아니라 producer의 실제 latency다 |
| 과거 pre-PHY `MSG4_WAIT=0` hook | reset이 PHY 송신 전에 queue의 Msg3를 지워 UE가 10,878회 시도를 기록하는 동안 gNB는 context **1개**만 생성했다. §5의 MAC 확인 RRCSetupRequest 후 중단 경로로 대체됐다 |
| `RSS_SHARE_WR_MONOTONIC=1` | sample loss가 21,178에서 0으로 줄었지만 시도 수도 2,387에서 **32**로 줄었다. flush마다 clamp가 한 번 전진하고 slot보다 flush가 많아 미래로 달렸다 |
| `RSS_SHARE_LOCKSTEP=1` | 부분 효과: out-of-order batch 9.19%에서 7.70%, loss 33,144에서 27,139, radio time 1.12에서 1.26. 유지함 |
| core pinning | 악화: 33.8에서 24.2 attempts/s, 최대 점유 90에서 51 |
| `ACK_GATE=0` | 변화 없음(34.1과 33.8 attempts/s) |

---

## 7. 변동성

서로 다른 session의 4-UE run 3개에서 시도 수는 2202–2387, sample loss는
21k–40k, radio time은 0.87–1.63이었다. 시도 수는 안정적이지만 loss와 radio time은
그렇지 않다. **loss와 timing은 같은 session 안에서만 비교한다.**

---

## 8. 측정 중 발견한 도구 결함

재도입을 막기 위해 기록한다.

- `nr-uesoftmodem` target만 빌드하면 과거 `liboai_zmqdevif.so`가 남았다.
  따라서 `radio/zmq/` 수정이 source tree에는 반영돼도 실행에는 들어가지 않았다.
  이제 `bin/rss-build`는 세 target을 모두 빌드하고 각 artifact에 필요한 knob가
  포함됐는지 grep한다.
- `$0 >= "HH:MM:SS"` 형태의 관측창 filter는 전체 로그 행을 비교한다. 모든 행이
  `2026-...`으로 시작해 어떤 시각보다도 정렬상 뒤에 있으므로 filter가 전체 로그를
  통과시켰고, whole-log 합계를 단일 run 합계로 읽었다.
- procedure 종료를 `timed out`만 세면 DU가 먼저 release할 때 대부분 발생하는
  `cancelled`를 놓친다. 그 결과 capacity 96인데 점유가 591로 계산됐다. 이 불가능한
  수치로 결함을 발견했다.
- 과거 report는 최초 거절 이전 구간을 denial 중단으로 해석했다. 그 해석과 연속 denial
  주장은 모두 근거가 없었다. 현재 report는 관측된 거절 간격만 설명한다.
- 점유를 두 번 추적했다. 최대값은 live UE id set으로, plateau는 +1/-1 event timeline으로
  계산했다. 관측창 전에 시작한 context의 종료가 timeline에 -1을 넣고, 일반 tuple
  정렬은 같은 timestamp에서 start보다 end를 먼저 적용해 두 결과가 달랐다. report에는
  "최대 점유 12" 옆에 "9 이상 0.0초"가 표시됐다. 이제 점유는 하나의 원천만 사용하며,
  모든 변경 뒤 `len(live)`를 sample한다.
- 두 번째 문자가 `O`인 run id는 UE를 시작할 때 종료시킨다. OAI의 `-O` scan이 선행
  `-` 유무를 확인하지 않고 `argv[i][1] == 'O'`를 검사하기 때문이다. `bin/rss-run`은
  이런 id를 거부한다.

---

## 9. 배포 도구의 과거 장시간 run

run `ZWperm`, 2026-10-20. 개발 script가 아니라 DU host에 배포한 **packaged**
`rss-storm`을 전부 `bin/rss-run`으로 구동하고, CU host에서 packaged `analysis/`로
다시 읽었다. 축소 capacity 진단 profile(`nof_cell_sr_res 1`, `t300 2000`,
capacity 12)을 적용했다. 명령:

```
bin/rss-run -e 1 -u 2 -r 0 -H 1500 -d 0 -n ZWperm
```

기록은 약 **2191초(36.5분)** run을 보고한다. 원시 로그 없이는 정확한 분석 관측창을
조정할 수 없다. 점유는 2191초로 표시됐지만 거절 수·rate와 별도의 25.2초 ramp-up은
서로 다른 분모를 가리킨다. 이를 하나의 검증된 공통 관측창으로 취급하면 안 된다.

과거 `analysis/cu_occupancy.py` 요약(capacity 12, 보고된 관측창 2191초):

| 수준 | 관측창 비중 | 최장 연속 plateau |
|---|---:|---:|
| 점유 3 이상 | **100%** | **428.4초** |
| 점유 6 이상 | 98% | **426.1초** |
| 점유 9 이상 | 89% | 50.1초 |
| 점유 12 이상(full cap) | 36% | 1.8초 |

최대 점유 12/12, 종료 사유 `cancelled` 12,339건, `timed out` 1건,
hold 중앙값 1846 ms.

과거 `analysis/cu_count.py` 요약(정확한 관측창 미검증):

| 일치 로그 pattern | 발생 수 |
|---|---:|
| `rrcReject` | 85,797 |
| `DU is not able to serve` | 28,599 |
| `rrcSetupComplete` | **0** |
| NGAP `InitialUEMessage` | **0** |

이전에 보고한 rate는 일관되지 않은 분모를 사용했으므로 제외한다. 발생 수를 고유
over-the-air 메시지 수로 다시 해석하면 안 된다.

과거 발생 간격 기록은 최초 거절까지 25.2초, 공백 p50 0 ms / p99 256 ms,
**최대 공백 2.53초**(한 번 보고됨)다. ramp-up 뒤 2191초 전체라는 별도 주장은 명시된
전체 관측창과 충돌하므로 철회한다.

UE 측(`attempts.jsonl`): 시도 40,253건, `msg4_rx` 13,420건,
`rrc_reject` 27,597건, sample loss 1.40 M.

해석 한계:

- 절반 capacity 이상으로 기록된 비율은 **98%이지 전체 run이 아니다**. 최장 연속 구간은
  426.1초다. 1/4 capacity에서 표시된 100%는 반올림 값이며 중단 없는 점유를 입증하지
  않는다.
- full capacity는 36%로 기록됐고 최장 구간은 1.8초다. 반복 거절 로그는 연속 denial을
  입증하지 않는다. 특히 기록된 2.53초 공백과 미해결 분석 관측창 경계를 고려해야 한다.
- completion/core-message 일치 행이 0개인 것은 충분한 logging 아래에서는
  RRCSetupComplete 미전송형과 일치하지만, 여기서는 관측 범위를 다시 검사할 수 없다.
- 정상 사용자 서비스 영향과 이 run보다 긴 안정성은 시험하지 않았다.
- 기록상 이 run에서 `--rss.gate_timeout_ms`(기본값 500) 문제는 없었다. 일반적인
  신뢰성 보장은 아니다.
