# CU 포화 시 같은 셀 RA-only admission probe의 RRC 셋업 요청 거부 — 증거 정리

2026-10-29. CU 프로파일 `max_nof_ues: 30`(승인 범위: 90 이하), 같은 셀, 60초 런.

> 재현성 상태(2026-10-30): 당시 사용한 `probe_interval_ms` 소스와 원시 런 로그는
> 저장소에 남지 않았다. `patch/rss-ue-curated.patch`에 같은 인터페이스를 최소 재구현했지만,
> 아래 수치는 새 패치로 재검증하기 전까지 **과거 관측값**이지 clean checkout 재현 결과가 아니다.

## 방법

- 공격: RRCSetupComplete 미전송형 RSS(스톰) UE 5개. `RSS_SHARE_NUE=5`로 증인을 TX 배치 계산에서 제외.
- 증인: `--rss.probe_ues 1 --rss.probe_ra_only 1 --rss.probe_interval_ms 1000`.
  초당 1회만 RRC 셋업을 시도한다(실제 UE의 T300 재시도 수준). Msg5는 생략한다.
- 측정: `attempts.jsonl`의 `attempt_start`·`msg4_rx`·`rrc_reject`, CU 로그의
  `UE admission limit reached` 개수(런 창 기준).

## 결과 (2회 반복)

| 런 | 조건 | 증인 시도 | Msg4 | CU 거부 | msg4 대비 | CU admission 로그 |
|---|---|---|---|---|---|---|
| P2C-r34 | 대조군(증인 단독) | 78 | 78 | 0 | 0% | 0 |
| R2C-r36 | 대조군(증인 단독) | 78 | 78 | 0 | 0% | 0 |
| P2A-r34 | 공격(스톰 5 + 증인) | 80 | 81 | 51 | 63% | 196 |
| R2A-r36 | 공격(스톰 5 + 증인) | 83 | 72 | 40 | 56% | 196 |

- 공격 조건에서 증인의 CU 거부는 런 시작 2.3초부터 65.2초까지 창 전체에 걸쳐 발생했다.
- 대조군은 두 번 모두 거부 0회, CU admission 로그 0회였다.
- 공격 조건의 CU admission 로그는 두 번 모두 196회로 같았다.

## 해석

- CU가 포화되면 같은 셀 RA-only admission probe의 RRC 셋업 요청이 CU admission
  단계에서 절반 이상 거부됐다. 평상시에는 같은 probe 요청이 전부 수락됐다.
- probe는 Msg5·Registration·PDU를 수행하지 않는다. 따라서 이 측정은 **요청단 거부율**의
  증거일 뿐 정상 UE의 완전 접속 실패나 서비스 DoS를 직접 보인 것이 아니다.

## 재현 명령

> **주의 (현재 `bin/rss-run` 계약 차이):** 아래 당시 공격 명령은 `RSS_SHARE_NUE=5`와 `-u 6`을 함께 전달한다. 현재 `bin/rss-run`은 부분 공유 배치를 금지하므로 `RSS_SHARE_NUE == NUM_UES`가 아니면 거부한다([REFERENCE.md](REFERENCE.md) 참고).
>
```
# 대조군
RSS_CONF=/dev/null PROBE_UES=1 PROBE_RA_ONLY=1 \
  PROBE_INTERVAL_MS=1000 \
  GNB_RESTART_CMD=/root/du1-restart.sh \
  ./bin/rss-run -e 1 -u 1 -d 60 -n CTRL

# 공격
RSS_CONF=/dev/null PROBE_UES=1 PROBE_RA_ONLY=1 RSS_SHARE_NUE=5 \
  PROBE_INTERVAL_MS=1000 \
  GNB_RESTART_CMD=/root/du1-restart.sh \
  ./bin/rss-run -e 1 -u 6 -d 60 -n ATK
```

집계:

```
grep -c attempt_start runs/<id>/attempts.jsonl
grep '"ue":0,' runs/<id>/attempts.jsonl | grep -c msg4_rx
grep '"ue":0,' runs/<id>/attempts.jsonl | grep -c rrc_reject
# CU 호스트에서 런 창으로 awk 필터 후:
grep -c "UE admission limit reached" /tmp/ocu.log
```

## 남은 한계와 다음 단계

- 후속 GNU Radio broker는 별도 full-service witness 경로를 확보했지만 서비스 결과가
  불안정했고, rate-v2 D4도 공격 중 witness의 Registration·PDU 성공으로 끝났다.
- 정상 UE 서비스 DoS는 [기본 cleanup 실패 분석](../../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md)의
  합격 기준을 별도 경로에서 통과해야 한다.

> **2026-10-30 후속 정정:** GNU Radio 5 UE broker로 별도 프로세스 일반 witness
> 경로는 확보했다. 다만 사전 고정 control 15회 중 유효 런이 3회뿐이고 ping 손실도
> 0.833333%~93.5484%여서, 안정적인 정상 UE 기준선이나 DoS 증거로는 쓰지 않는다.
> 결과는 [`broker-sync-sampling-20261030`](../../../artifacts/broker-sync-sampling-20261030/)에 있다.
