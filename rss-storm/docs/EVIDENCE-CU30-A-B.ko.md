# CU 포화 시 같은 셀 정상 UE의 RRC 셋업 거부 — 증거 정리

2026-10-29. CU 프로파일 `max_nof_ues: 30`(승인 범위: 90 이하), 같은 셀, 60초 런.

## 방법

- 공격: A형 RSS(스톰) UE 5개. `RSS_SHARE_NUE=5`로 증인을 TX 배치 계산에서 제외.
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

- CU가 포화되면 같은 셀 정상 UE의 RRC 셋업 요청이 CU admission 단계에서 절반 이상
  지속적으로 거부된다. 평상시에는 같은 요청이 전부 수락된다.
- 거부는 RRCSetupRequest 단계에서 일어나므로, Msg5를 생략한 증인과 실제 UE가 같은
  지점에서 같은 거부를 받는다. 다만 이 측정은 **RRC 셋업 요청 거부**까지의 증거이며,
  PDU 세션까지의 완전 접속 실패를 직접 보인 것은 아니다.

## 재현 명령

```
# 대조군
RSS_CONF=/dev/null PROBE_UES=1 PROBE_RA_ONLY=1 \
  UE_EXTRA="--rss.probe_interval_ms 1000" \
  GNB_RESTART_CMD=/root/du1-restart.sh \
  ./bin/rss-run -e 1 -u 1 -d 60 -n CTRL

# 공격
RSS_CONF=/dev/null PROBE_UES=1 PROBE_RA_ONLY=1 RSS_SHARE_NUE=5 \
  UE_EXTRA="--rss.probe_interval_ms 1000" \
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

- 정상 UE의 완전 접속(PDU) 실패를 직접 보이려면 UE별 독립 전송 경로가 필요하다.
  ZMQ 브로커(`tools/zmq_broker.c`)를 개발 중이나 아직 2 UE 안정화 전이다.
- 브로커가 안정화되면 같은 A/B를 정상 UE 프로세스로 반복해 완전 접속 실패를 측정한다.
