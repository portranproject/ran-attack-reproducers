# 5 UE broker 시작·종료 안정화 검증 (2026-10-30 KST)

## 결론

5 UE broker의 두 결함은 서로 달랐다.

1. **시작 경합은 남아 있다.** 새 5/5 sync 게이트를 적용한 7회에서 성공 3회는
   3~4초에 모두 동기했고, 실패 4회는 30초까지 0/5였다. 실행기는 이제 실패 런에서
   요청한 관측 창을 시작하지 않는다. 표본이 작으므로 30초 기본값은 유지한다.
2. **종료 SIGSEGV/강제 종료는 해결했다.** OAI w38은 첫 INT/TERM을 NAS deregistration
   요청으로 쓰고 `Press ^C again to trigger immediate shutdown`을 출력한다. 이전
   실행기는 신호를 한 번만 보낸 뒤 1초에 KILL했다. UE마다 INT를 0.2초 간격으로 두 번
   보내고 최대 5초 기다리자 3회 모두 UE 5개와 broker가 exit 0, forced kill 0,
   kernel SIGSEGV 0으로 끝났다.

gNB 소스는 수정하지 않았고, 팀 소유 AWS ZMQ 격리 환경에서만 검증했다.

## 과거 SIGSEGV의 실제 주체

이전 문서의 “Qt/GNU Radio 자식 추정”은 부정확했다. 이전 부팅의 보존된 kernel
journal은 유효 r21/r3의 종료 직전에 다음을 기록했다.

```text
Oct 29 21:25:32 ... UL__actor[33290]: segfault ... in nr-uesoftmodem[53737a,...]
Oct 29 21:27:17 ... UL__actor[34917]: segfault ... in nr-uesoftmodem[53737a,...]
```

검증된 curated 바이너리의 `0x53737a`는
`openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c:789`의 `init_RA()`로 매핑된다.
해당 줄은 `mac->current_UL_BWP->rach_ConfigCommon`을 읽는다. OAI의
`itti_wait_tasks_end(trigger_deregistration)`는 첫 신호에서 deregistration을 요청하고
두 번째 신호에서 즉시 종료한다. 첫 신호 뒤 RA가 다시 시작되는 동안 종료 상태와
경합한 것이 이번 SIGSEGV의 직접 경로다.

## 비교 실험

모든 런은 control, 15초 관측, 5/5 sync 제한 30초였다. 서비스 판정이 목적이 아니라
시작·종료 수명 검증이 목적이다.

| 종료 방식 | 런 | sync wait | sync | UE status | broker | forced kill |
|---|---|---:|---:|---|---:|---:|
| INT 1회 + 1초 | int-r1 | 4 s | 5/5 | 137×5 | 0 | 5 |
| INT 1회 + 1초 | int-r2 | 3 s | 5/5 | 137×5 | 0 | 5 |
| INT 1회 + 1초 | int-r3 | 30 s | 0/5 | 137×5 | 0 | 5 |
| TERM 1회 + 1초 | term-r1 | 30 s | 0/5 | 137×5 | 0 | 5 |
| **INT 2회 + 최대 5초** | int2-r1 | 30 s | 0/5 | **0×5** | **0** | **0** |
| **INT 2회 + 최대 5초** | int2-r2 | 3 s | 5/5 | **0×5** | **0** | **0** |
| **INT 2회 + 최대 5초** | int2-r3 | 30 s | 0/5 | **0×5** | **0** | **0** |

int2-r2의 witness는 attach 6초, Registration/PDU까지 갔지만 ping 수신은 0이었다.
짧은 수명 시험이므로 이 결과를 서비스 A/B 증거로 사용하지 않는다.

## 구현된 안전장치

- `BROKER_SYNC_TIMEOUT_S` 기본 30초: 5/5가 아니면 관측 창 전 인프라 실패.
- `startup.sync_wait_s`/`sync_timeout`: 이후 제한값 교정 근거.
- 관측 경계에서 `crash_markers` 동결.
- `teardown.ue_exit_statuses`, `broker_exit_status`, SIGSEGV·forced-kill 수 기록.
- UE에는 INT 두 번, GNU Radio broker에는 INT 한 번.
- `rss-broker-witness-retry`: `sync_timeout=true`, sync<5, 관측/종료 crash 0,
  UE 5개와 broker exit 0, forced kill 0일 때만 `BASE-tryNN`의 새 run id로 재시도.
  유효한 서비스 실패와 모든 teardown 이상은 재시도하지 않는다.

## 해시와 보존

```text
60bd5350e2ec652363fc126cbeba7975db82cd76d0d140a3a1c62fd871e4750e  rss-broker-witness
cb9e876c6f37483695085a5311e6c904b942f2b881f0863c80585965cfca11b0  rss-broker-witness-retry
81cfd3bd4c5ea21cc934f8a7f251ab27a5e607a2f6e51c16b5935e3eab444356  test_broker_witness.py
2bd59c08d9c220b2569a90b50d62405389bfae96d67fbff798ad7261d7fad226  test_broker_witness_retry.py
24395619907e87f37607f9d5cd71669b8f9537e70d29874e74ab36ab5b36e250  du.yaml (실험 중)
7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3  du.yaml (원복 후)
```

원문은 DU의 `/root/rss-broker-provenance-*`에 남겼다. UE 로그에는 가입자·NAS·IP
식별자가 포함될 수 있어 저장소에는 복사하지 않았다. 안전한 결과 파일의 원격 SHA-256은
`SHA256SUMS.remote`에 있다. 검증 뒤 DU 설정을 원본 해시로 복원했고 CU/DU 인스턴스를
중지했다.

## 남은 한계

- 5 UE 시작 성공률과 control ping 품질은 안정화되지 않았다.
- 성공 sync 표본은 3개뿐이라 30초 제한의 분위수 근거가 충분하지 않다.
- 차폐 OTA와 정상 서비스 DoS는 이 검증 범위가 아니다.
