# 알려진 문제와 프로파일 (2026-10-27)

이 파일은 재현도구 검증 중 확인된 결함과 그 보완, 그리고 두 가지 포화 프로파일을 기록한다.

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

**검증(진행 중).** X1-r19·X2-r19·X4-r19에서 probe가 접속·유실·재접속을 반복했고
SIGSEGV는 0회였다. 거부 상태에서의 생존 검증은 X5-r19 결과로 갱신한다.

## 2. CU의 UE admission limit은 DU별로 적용된다

`du_processor_impl.cpp`가 DU 프로세서마다 `max_nof_ues`를 검사한다. 공격 셀이 포화돼도
같은 CU의 다른 셀에 붙는 UE는 정상 접속한다. 실측: CU 30에서 공격 셀(DU1)이 포화인 동안
두 번째 셀(DU2)의 재고 UE가 RRCSetupComplete → Registration Accept → PDU(10.45.1.2)까지
성공했다(`U2-r16`).

따라서 "정상 UE" 증인은 반드시 공격 셀과 **같은 DU**에 있어야 한다. 두 번째 DU를
증인으로 쓰는 설계는 성립하지 않는다(토폴로지는 1 CU 1 DU 그대로다).

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

## 3. 포화 프로파일 두 가지

공격 성공 조건은 두 경우 모두 "정상 UE의 연결 실패"다. 어느 한도가 먼저 걸리는지만 다르다.

| 프로파일 | CU `max_nof_ues` | DU 셀 용량 | 먼저 걸리는 한도 | 비고 |
|---|---|---|---|---|
| CU 포화 | 90 이하(실측 30·15) | 96(기본) | CU admission limit | 검증 진행 |
| DU 포화 | 8192(기본) | 96(기본) | DU 컨텍스트/RA 자원 | 다음 단계 |

전환은 CU 호스트에서 `bin/rss-gnb-profile`로 한다. CU 설정만 만지고 OCUDU 소스는 건드리지 않는다.

```
# CU 포화 (CU admission limit이 먼저 걸림). 90 이하만 허용된다.
bin/rss-gnb-profile --role cu cap 90      # 또는 30, 15
bin/rss-gnb-profile --role cu cap show    # 현재 값 확인

# DU 포화 (CU는 기본 8192, DU 용량 96이 먼저 걸림)
bin/rss-gnb-profile --role cu cap default
```

DU 용량은 `du.yaml` 기본값 그대로 둔다(부팅 로그의 `Capacity: 96`). DU 포화 버전에서는
공격 UE를 2개 이상으로 올려 96개 컨텍스트를 채운다. 두 버전 모두 재시작 후 적용된다.
