# 알려진 문제와 프로파일 (2026-10-27)

> **2026-10-30 정정:** V4의 CU 200·witness 17/17 결과는 hold32 진단이다. 기본
> 약 2초 정리시간을 늘렸으므로 attacker-controlled sustained denial 성공으로
> 인용하지 않는다. 후속 rate-v2도 기본 cleanup에서 실제 admission률이 정리율과
> 평형이어서 sustained denial에 실패했다(§10).

이 파일은 재현도구 검증 중 확인된 결함과 그 보완, 그리고 두 가지 포화 프로파일을 기록한다.

> 2026-10-30: probe pacing과 RRCReject reset-skip은 당시 실험 소스가 보존되지 않아
> `patch/rss-ue-curated.patch`에 문서대로 재구현했다. clean w38 적용성은 확인했지만,
> 아래 장비 수치와 SIGSEGV 0회는 새 패치로 다시 측정하기 전까지 이력 정보다.

## 1. 지연 투입한 probe UE가 RRCReject를 받으면 SIGSEGV — 수정

**증상.** `--rss.probe_ues 1 --rss.probe_delay_ms 5000`으로 정상 UE 인스턴스를 5초 뒤에
투입했을 때, CU가 `RRCReject`를 보내면 UE 프로세스가 SIGSEGV로 종료됐다. 로그 순서는
`[RSS] probe branch entered ue=0` → `Resynchronizing RX by N samples` 반복 → 세그폴트였다.
재현 런: `P2-r14`(인스턴스 2), `P3-r14`(인스턴스 3). CU 90·30 모두에서 발생했다.
gdb 아래에서는 재현되지 않았다. gdb가 공격 속도를 낮춰 CU가 포화되지 않았고, probe가
접속에 성공했기 때문이다(거부 경로를 타지 않음).

**원인.** `nr_rrc_process_rrcreject()`는 `RRCReject`를 받을 때마다 MAC에
`NR_MAC_RRC_CONFIG_RESET`(`cause=REJECT`)을 보낸다. 이 리셋이 RF 재동기화를 유발한다.
지연 투입된 probe는 그 시점까지 송신 이력이 없다가 첫 RA에서 거부되면서 리셋·재동기화
경로를 타고, 공유 ZMQ 링 버퍼 상태와 어긋나 크래시하는 것으로 보인다(로그 근거의 가설).
`probe_ra_only`는 처음부터 계속 송신하므로 같은 리셋을 받아도 재현되지 않았다.

**보완.** `nr_rrc_process_rrcreject()`에서 `nr_rss_enabled() && nr_rss_is_probe(ue)`이면
MAC 리셋 전송을 생략한다. probe는 `rss_poll()`에서 스스로 RA를 다시 시작하므로 리셋이
필요 없다. `--rss.probe_ues`를 쓰지 않는 일반 UE는 영향을 받지 않는다.

- 파일: `/root/OAI/openair2/RRC/NR_UE/rrc_UE.c` (`nr_rrc_process_rrcreject`)
- 재빌드: `cd /root/OAI/cmake_targets/ran_build/build && ninja -j8 nr-uesoftmodem`
- 백업: 같은 경로의 `rrc_UE.c.bak-probe`

**검증.** X1-r19·X2-r19·X4-r19에서 probe가 접속·유실·재접속을 반복했고
SIGSEGV는 0회였다. 최종 V4의 별도 셀 정상 증인도 16.31초 동안 17/17 `RRCReject`를
받으며 실행을 유지했고 Msg4·완료는 0이었다.

## 2. CU의 UE admission limit은 CU 전체가 공유한다 — 2026-10-30 정정

과거 “DU별 적용” 해석은 잘못됐다. `cu_cp_impl`은 CU당 `ue_manager` 하나를 만들고
모든 DU processor에 같은 참조를 넘긴다. admission 검사는 그 전역 manager의
`ues.size()`와 `max_nof_ues`를 비교한다. 따라서 여러 DU·셀의 context는 하나의 CU
상한에 합산된다.

과거 DU2 UE 성공은 per-DU 상한의 증거가 아니라 context 해제·재점유 사이의 빈틈과
양립한다. CU200을 실제로 채우려면 셀당 96인 현재 프로필에서 최소 3개 공격 셀이
필요하며, 정상 증인은 별도 셀에서도 CU 전역 admission 결과를 관측할 수 있다. 다만
정상 증인의 요청이 실제 CU까지 도달했는지는 `(du_index, C-RNTI, UE ID)`로 조인해야
RF/CPU 실패와 구분할 수 있다.

최종 V4는 이 구성을 인공 hold32 진단으로 확인했다. V4 계보 바이너리 `202934f7...`와 세 공격 셀에서
DU ACK 확인 RRCSetupComplete 미전송형 176건을 만들었고, CU 점유는 200에 도달해 15.68초
연속 유지됐다. 별도 네 번째 셀의 정상 증인은 16.31초 동안 17/17 거부됐고 Msg4·완료는
0이었다. 같은 4셀 정상 대조군은 성공했다. 다만 이 판정은 측정된 약 32초 컨텍스트
수명 전의 한정 창이다. 이후에는 만료 슬롯 경쟁이 시작되므로 무기한 거부로 확대하지
않는다. 진단 명령과 원문은 [V4 hold32 진단](../../artifacts/p5-cu200-3cell-20261030/README.md)과
[`rss-cu200`](../bin/rss-cu200)에 있다.

## 4. 같은 셀 증인 UE의 구조적 한계 (2026-10-27)

공유 ZMQ 무선에서 공격 인스턴스와 증인 인스턴스의 상향 링크를 함께 처리하는 방식에 한계가 있다.

- **증인을 배치에 포함**(`RSS_SHARE_NUE`를 전체 인스턴스 수로): 연결된 증인은 송신을 멈추므로
  배치가 매번 기다린다. 공격률이 35/s에서 1.6~11/s로 떨어져 CU가 계속 차지 않는다.
- **증인을 배치에서 제외**(`RSS_SHARE_NUE` = 공격 인스턴스 수): 증인의 상향(Msg3)이 배치에
  합류하지 못해 RA가 실패한다. 실측 `Y1-r21`(CU 15, 공격 1 + 증인 1, 5초 지연): 증인은
  2회 시도, Msg3 재전송 4회 반복, Msg4 없음, 접속 실패. 크래시는 없었다.

추가로 CU 한도를 15로 낮추면 공격 UE가 RRCReject를 받고 `reject_backoff_ms`(기본 1초)만큼
물러나 스스로 속도가 1~2/s로 떨어진다(`Y1-r21`, `Y2-r22`). `-r 0`(백오프 무시)으로도
`Y3-r22`는 공격 82회/45초(1.8/s)에 그쳤고, 증인은 28회 시도했지만 Msg4를 받지 못했다.
즉 낮은 CU 한도에서는 공격이 스스로 throttled 되어 지속 포화가 만들어지지 않는다.

따라서 "같은 셀 증인"과 "지속 포화"를 동시에 만족시키려면 두 가지를 함께 고쳐야 한다.
1) 공유 TX 배치가 고정 `n_ue` 대신 **최근 송신한 인스턴스만** 세도록 동적화(증인 UL 보장).
2) Reject 백오프와 무관하게 공격이 한도를 계속 채우도록 유지(예: `-r 0` + 더 높은 한도 조합).
그 전까지는 실제 RF 경로(UE별 독립 무선)나 다중 UE ZMQ 브로커가 필요하다.

2026-10-30에 GNU Radio 5 UE broker로 별도 프로세스 일반 witness 경로 자체는
구현했다. 따라서 “경로가 없다”는 문제는 좁혀졌지만, 5 UE sync race·baseline
고손실 때문에 안정 서비스 증거로는 아직 부족하다(§9). teardown SIGSEGV는 후속
원인 확인과 2단계 종료로 해소했지만 서비스 판정의 비결정성은 그대로다.

## 3. 포화 프로파일 두 가지

공격 성공 조건은 두 경우 모두 "정상 UE의 연결 실패"다. 어느 한도가 먼저 걸리는지만 다르다.

| 프로파일 | CU `max_nof_ues` | DU 셀 용량 | 먼저 걸리는 한도 | 비고 |
|---|---|---|---|---|
| CU 포화 진단 | 200; 과거 실측 90·30·15 | 셀당 96 | CU-wide admission limit | V4 hold32: 인공 hold 안에서 피크 200·15.68초 plateau·증인 17/17 거부; 기본 cleanup 성공 아님 |
| DU 포화 진단 | 200(현재 p5 유지) | 96 | DU PUCCH/UE context | G35 hold32: same-process probe 11/11 거부; 기본 RLF 정책에서는 지속 거부 실패 |

전환은 CU 호스트에서 `bin/rss-gnb-profile`로 한다. CU 설정만 만지고 OCUDU 소스는 건드리지 않는다.

```
# CU 포화 (CU admission limit이 먼저 걸림). 90 이하만 허용된다.
bin/rss-gnb-profile --role cu cap 90      # 또는 30, 15
bin/rss-gnb-profile --role cu cap show    # 현재 값 확인

# 과거 upstream 기본값으로 복귀하는 명령은 현재 p5 목표값 200과 다르다.
# 실제 실험 전에는 로드된 CU 설정 SHA와 max_nof_ues를 따로 확인한다.
bin/rss-gnb-profile --role cu cap default
```

DU 용량은 부팅 로그의 `SR (96), CSI (96)`로 확인한다. G35는 capacity를 그대로 둔 채
실험 관측창 안의 조기 CSI-RLF/CU timeout만 뒤로 미룬 hold32 프로필에서 정상 probe
11/11을 DU 자원 부족으로 거부했다. 프로필은 실험 전용이며 종료 후 원복한다.

## 5. CU 90 control/attack 비교 (2026-10-29, 랩 프로브 ra_only)

동일 조건 60초, CU `max_nof_ues: 90`, 같은 셀.

| 조건 | 총 시도 | 프로브 시도 | 프로브 Msg4 | 프로브 Reject | Msg4 대비 Reject | CU admission 로그 |
|---|---|---|---|---|---|---|
| 대조군(프로브 단독) | 1,927 | 1,927 | 351 (18.2%) | 31 | 8.8% | 153 |
| 공격(스톰 5 + 프로브) | 2,480 | 755 | 80 (10.6%) | 18 | 22.5% | 118 |

- 공격 아래에서 프로브의 Msg4 도달률이 18.2% → 10.6%로 떨어졌다(RA 경합).
- Msg4를 받은 뒤 CU admission에서 거부된 비율은 8.8% → 22.5%로 올랐다.
- 그러나 CU admission 로그 총량은 공격 조건에서 오히려 118로, 대조군 153보다 적다.
  프로브 단독 트래픽(35회/s)도 CU 90을 부분 포화시킨다.
- 결론: CU 90에서는 공격이 "정상 UE의 지속 연결 불가"를 만들지 못한다. 프로브 실패의
  대부분은 RA 단계이고, CU admission은 보조 요인이다. CU 30의 W1-r19(성공 RA 중
  CU 거부 27/33 = 82%)이 가장 강한 신호지만 대조군 자기포화가 교란한다.

## 6. 페이싱 증인의 control/attack 비교 (2026-10-29, CU 30)

증인이 스스로 CU를 포화시키는 문제를 없애기 위해 `--rss.probe_interval_ms`(기본 1000)를
추가했다. 증인은 초당 1회만 RRC 셋업을 시도한다(실제 UE의 T300 재시도와 같은 수준).

| 조건 (60초) | 증인 시도 | Msg4 | CU 거부 | Msg4 대비 거부 | CU admission 로그 |
|---|---|---|---|---|---|
| 대조군(증인 단독) | 78 | 78 (100%) | 0 | 0% | 0 |
| 공격(스톰 5 + 증인) | 80 | 81 | 51 | 63% | 196 |

- 공격 조건에서 증인의 거부는 air_ms 2.3초~65.2초로 **창 전체에 걸쳐** 발생했다.
- 대조군은 60초 동안 거부 0회, CU admission 로그 0회로 깨끗하다.
- 즉 CU 30 포화 시, 같은 셀 RA-only admission probe의 RRC 셋업 요청은 절반 이상이 CU admission에서
  지속적으로 거부된다.
- 한계: 증인은 `probe_ra_only`(Msg5 생략)라 "완전 접속(PDU까지) 실패"의 증거는 아니다.
  CU 거부는 RRCSetupRequest 단계에서 일어나므로 실제 UE도 같은 지점에서 거부되지만,
  완전 접속 실패를 직접 보인 것은 아니다. broker 일반 witness를 측정했지만
  서비스 성공/실패가 갈려 보완은 아직 끝나지 않았다.

## 7. 정상(Msg5) 증인의 첫 시도는 매번 통과했다 (2026-10-29)

지연 투입한 정상 증인(`probe_ra_only` 없이 Msg5까지 수행)을 CU 30·20·5에서 시험했다.

| CU cap | 스톰 | 총 시도(60초) | UE 로그 RRCReject | 증인 시도 | 증인 접속 | SIGSEGV |
|---|---|---|---|---|---|---|
| 30 | 5 UE | 995 | - | 1 | 성공(3초 지연) | 0 |
| 20 | 5 UE | 96 | 130 | 3 | 성공(5초 지연) | 0 |
| 20(-r 0) | 5 UE | 201 | 130 | 1 | 성공 | 0 |
| 5(-r 0) | 5 UE | 3,265 | 6,324 | 1 | 성공 | 0 |

- CU가 초당 54회 시도와 6,324회 거부를 기록하는 동안에도, 증인의 **첫 요청 한 번은
  수락**됐다. CU admission 카운터가 해제/재점유로 진동해 단일 시도가 빈틈에 들어간다.
- `probe_ra_only`(초당 1회, §6)는 재시도 요청의 63% 거부를 보였지만 정상 UE가 아니다.
  Msg5·Registration·PDU를 수행하지 않으므로 서비스 거부 증거로 세지 않는다.
- broker에서 정상(Msg5) 증인의 완전 접속 실패를 한 번 관측했지만 다른 유효 공격
  런에서는 서비스에 성공했다. 결정적 재현은 아니다(§9).

## 8. 페이싱 증인 control/attack 재현 (2026-10-29, CU 30, 2회 반복)

§6과 같은 조건으로 한 번 더 측정했다(각 60초, 같은 셀, `probe_interval_ms 1000`).

| 런 | 조건 | 증인 시도 | Msg4 | CU 거부 | msg4 대비 | CU admission 로그 |
|---|---|---|---|---|---|---|
| P2C-r34 | 대조군 | 78 | 78 | 0 | 0% | 0 |
| R2C-r36 | 대조군 | 78 | 78 | 0 | 0% | 0 |
| P2A-r34 | 공격 | 80 | 81 | 51 | 63% | 196 |
| R2A-r36 | 공격 | 83 | 72 | 40 | 56% | 196 |

- 대조군 2회 모두 거부 0회, CU admission 로그 0회로 동일했다.
- 공격 2회는 51회·40회 거부(63%·56%)로 재현됐고, CU admission 로그는 두 번 모두
  196회였다. 창 전체에서 거부가 발생하는 것도 동일했다.
- 결론: CU 30 포화 시 같은 셀 RA-only admission probe의 RRC 셋업 요청은 창 전체에서
  절반 이상 CU admission에서 거부됐다. 이는 요청단 거부율의 2회 반복이며 정상 UE의
  Registration/PDU 서비스 거부 증거가 아니다.

## 9. 5 UE broker 일반 witness의 비결정성 (2026-10-30)

curated OAI에서 RSS 옵션을 radio 시작 전에 eager 등록하고, 실행기의 lock FD 상속과
프로세스 소유권을 수정한 뒤 네 공격/대조 UE와 한 일반 witness를 각각 별도 프로세스로
실행했다. 조건은 DU 상한 12·PRACH64·CU cap200의 통제 profile이다.

| 런 | 모드 | 5 UE sync | 공격 시도 | 일반 witness 결과 |
|---|---|---:|---:|---|
| r21 | control | 5/5 | 0 | attach 6 s, Registration/PDU, ping 40/264 |
| r2 | attack | 5/5 | 8 | Registration/PDU/tunnel/ping 실패 |
| r3 | attack | 5/5 | 294 | attach 50 s, Registration/PDU, ping 51/52 |

r8 control도 전체 서비스와 ping 102/102에 성공했지만 구 validator의 오판으로
진단용으로만 보존했다. 반대로 r21 control은 service가 성립했어도 ping 손실이
84.8%였다. broker는 여러 실행에서 `sync=0`으로 끝났다. r21/r3 종료 중 SIGSEGV는
후속 kernel journal 확인에서 GNU Radio broker가 아니라 OAI UE `UL__actor`의
`init_RA()` 경로로 특정됐다.

결론: **독립 일반 witness 경로는 성립했지만 정상 사용자 DoS는 미입증**이다. 공격량이
더 큰 r3에서 서비스가 성공했으므로 공격 시도 수와 서비스 거부가 단조 관계라는 주장도
성립하지 않는다. 실행기는 이제 5/5 sync가 기본 30초 안에 되지 않으면 관측 창 전에
실패하고, 관측 경계의 crash marker와 종료 상태를 분리해 기록한다. 이 변경은 무효 런의
시간 낭비와 출처 혼동을 줄인다. OAI w38의 첫 INT가 deregistration 요청이라는 계약에
맞춰 UE마다 INT를 두 번 보내 teardown 결함을 해소했다. 별도 wrapper는 clean sync
timeout만 새 `BASE-tryNN` run id로 최대 3회 제한 재시도하고 유효한 서비스 실패나
종료 이상은 재시도하지 않는다.

사전 고정한 control 15회를 sync timeout 60초·관측 60초로 실행한 결과, 30초 이내
5/5 sync는 5회, 31~60초의 늦은 sync는 0회, clean timeout은 10회였다. sync 성공
5회 중 유효 control은 3회, 의미적 무효는 2회였다. 15회 모두 clean teardown이고
SIGSEGV는 0회였다. 유효 3회의 attach는 1~36초였지만 ping 손실은
0.833333%~93.5484%로 변동했다. 따라서 30초 제한은 운영상 유지하되 이 N=15로
percentile이나 성공률을 보장하지 않는다. 이 broker는 안정 서비스 증거로 부적합하며,
control-only 표본을 공격 효과나 DoS 주장에 사용하지 않는다. 다음 증거 게이트는
장비·안전값을 확정한 차폐 OTA control/attack 반복이다. 종료 근거는
[`artifacts/broker-stability-20261030/`](../../artifacts/broker-stability-20261030/)에,
고정 캠페인 결과는
[`artifacts/broker-sync-sampling-20261030/`](../../artifacts/broker-sync-sampling-20261030/)에
있다.

## 10. 기본 cleanup rate-v2도 sustained denial 실패 (2026-10-30)

OAI 프로세스 수를 줄인 2-endpoint broker에서 한 공격 프로세스의 RA-only UE 6개와
별도 full-service witness 1개를 120초 실행했다. CU `max_nof_ues: 200`, DU capacity와
cleanup/RLF 값은 유지했고, 실제 timeout은 median 1,999.517ms였다.

- F1 제공률 48.652/s, 정리율 39.407/s
- `DU is not able to serve` 선행 거절 1,033건(8.558/s)
- 실제 RRC Setup 생성률 40.095/s
- 워밍업 뒤 생성 40.026/s 대 정리 39.922/s
- 24개 5초 창 중 생성률이 정리율보다 큰 창 12개
- 점유 96 이상 총 1.678초, 최장 0.885초; CU 200 미도달
- 정상 witness는 첫 distinct 시도 거절 뒤 1.03초 만에 수락되어 Registration·PDU와
  ping 437/438 성공

따라서 제공 요청률이 정리율보다 높다는 조건만으로는 부족하다. 컨텍스트를 만들기 전
거절된 요청을 제외한 **실제 admission률**이 모든 짧은 창에서 cleanup률보다 높아야 한다.
현재 full OAI/ZMQ 경로는 이 조건을 만족하지 못한다. 여러 셀을 동시에 쓴 D3B2도 CU 200
최장 점유가 1.70초였고 정상 witness가 공격 중 서비스에 성공했다. 원문과 해시는
[rate-v2 실패 artifact](../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md)에 있다.
