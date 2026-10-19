# tool/ — A형 RSS 재현기 (OAI nr-UE 패치)

> 상태: **초안, 박스 미적용·미빌드.** 2026-10-20. 근거 표시는 [../comparison-5g.md](../comparison-5g.md) §0 규칙.

[../HANDOFF.md](../HANDOFF.md) "제안 구현 구조"의 1차 산출물이다. 목표는 M1a —
기본 설정에서 A형이 성립하는지(미완료 절차가 생겼다가 2초 뒤 해제되는 것이 반복되는지)만 본다.

## 무엇을 바꿨나

`oai-patch/rss-ue.patch` — 박스 `/root/OAI`(OAI `2026.w38`, `1c2f4d3c`) 전용. **UE 4파일만** 건드린다.

| 파일 | 내용 |
|---|---|
| `rrc_defs.h` | `rss_retry_timer` 필드 1줄 (U3 대응) |
| `rrc_proto.h` | `nr_rss_*` API 선언 |
| `rrc_timers_and_constants.c` | 노브 표(`rss` prefix)·JSONL 로거·재시도 타이머 tick (U4·U5 대응) |
| `rrc_UE.c` | rrcSetup 분기(U1), RRCReject 재시도 예약, going_to_IDLE 정리, 시도 로깅 |

**gNB 파일은 0건.** 5gattacks 패치의 gNB UL failure 타이머 단축(G1)과 로그 훅 6곳은
팀 방침(기지국 무수정)에 따라 이식하지 않았다. 동작만 읽고 새로 썼으므로 5gattacks 코드 복사가 아니다.

새 파일을 만들지 않았다 → **CMakeLists 수정이 없다**. 빌드 타깃은 `nr-uesoftmodem` 하나.

## 동작

1. Msg4(`RRCSetup`) 수신 → MAC이 예약해 둔 HARQ ACK PUCCH는 그대로 나간다.
2. `nr_rrc_process_rrcsetup()` **호출을 건너뛴다** → cell group 미적용, `RRCSetupComplete` 미생성, RRC는 IDLE 유지.
3. `rss_retry_timer` 만료 시 `handle_t300_expiry()`를 불러 **같은 프로세스 안에서** 새 `RRCSetupRequest`를 낸다
   (박스 제약 1: UE만 재시작하면 ZMQ 샘플 스트림이 어긋난다).
4. CU에는 미완료 절차가 남아 `t300 1000 + guard 1000 = 2000 ms` 뒤 해제된다.

### 안전장치 (설계 §4 지점 1)
`ack_gate=1`이면 `mac->ra.ra_pucch`가 아직 대기 중일 때 RA를 다시 걸지 않고 1 tick(10 ms) 미룬다.
RA 재시작의 `reset_ra()` memset이 예약된 ACK PUCCH를 지우기 때문이다. ACK가 없으면 gNB가
경합을 일찍 끊어 미완료 컨텍스트가 쌓이지 않는다(KAUST §V-B).

## 노브

실행 인자로 나온다. 기본값은 **공격 off**이므로 같은 바이너리가 회귀 시험용이다.

| 인자 | 기본 | 뜻 |
|---|---|---|
| `--rss.enable` | 0 | 1이면 A형 |
| `--rss.interval_ms` | 100 | Msg5 생략 후 다음 `RRCSetupRequest`까지. **벽시계 기준**(틱 누적 아님). 0 = 다음 틱 즉시 |
| **`--rss.target_occupancy`** | 0 | **포화도 조절.** gNB에 유지할 미완료 컨텍스트 수. 0 = 무제한. 실측 결과 CU 동시 점유가 이 값과 일치 |
| **`--rss.hold_ms`** | 2000 | gNB의 컨텍스트 보유 시간(= `t300` + guard). 위 폐루프가 쓰는 창 길이 |
| `--rss.tick_report` | 100 | N틱마다 실측 ms/tick을 JSONL에 기록(설정 vs 실측 분리용) |
| `--rss.completion_pct` | 0 | 정상 완료시킬 시도 비율(%). **>0이면 첫 완료에서 런이 멈춘다**(RRC_CONNECTED에서 새 요청이 안 나감). 자동해제는 UE를 죽여서 제거함 — checklist §9.7 |
| `--rss.honor_reject` | 1 | `RRCReject` 존중(waitTime 있으면 T302 잔여, 없으면 `reject_backoff_ms`) |
| `--rss.reject_backoff_ms` | 1000 | OCUDU 기본은 waitTime 미포함이라 이 값이 실제 재시도 간격 |
| `--rss.ack_gate` | 1 | 위 안전장치 |
| `--rss.max_duration_s` | 60 | **인프로세스 킬 스위치.** 만료 시 공격을 끄고 정상 접속으로 복귀 |
| `--rss.run_id` | `rss-run` | JSONL 라벨 |
| `--rss.log_file` | `/tmp/rss_attempts.jsonl` | per-attempt 정답지 |

5gattacks는 간격이 **빌드 상수 100 ms**였다(U5). 그 100 ms를 그대로 기본값으로 쓰되 인자로 뺐다.

## 라벨 (JSONL)

`design.md` §8 스키마의 1차 구현. 이벤트 단위 한 줄씩 남기고 `collect.sh`가 집계한다.

```json
{"type":"event","run_id":"A-001","seq":17,"t_ns":1792441600000000000,"event":"attempt_start","ue_identity":"0x1a2b3c4d5e","identity_type":"randomValue"}
{"type":"event","run_id":"A-001","seq":17,"t_ns":1792441600012000000,"event":"msg4_rx","intended_reach":"msg5_skip","actual_reach":"msg5_skip","tc_rnti":"0x4601"}
{"type":"event","run_id":"A-001","seq":17,"t_ns":1792441600112000000,"event":"retrigger"}
```

`ue_identity`는 실제 공중에 나가는 값이다(`randomValue` = rv[0..4], 마지막 비트 unused).
`tc_rnti`로 탐지팀의 F1 캡처와 조인한다.

## 쓰는 순서

```bash
# 로컬 p5 폴더에서 박스를 띄운 뒤 (CU 먼저 → DU)
./ctl.sh up

# 1) 패치와 스크립트를 DU 박스로 복사 (키·경로는 p5 폴더 것)
scp -i portran-key.pem tool/oai-patch/rss-ue.patch tool/box/*.sh ubuntu@<DU>:/root/

# 2) 적용 + 빌드 (DU 박스에서)
bash /root/deploy.sh

# 3) 회귀 시험: 공격 off로 정상 접속이 그대로 되는지
bash /root/run_attack.sh -e 0

# 4) 승인 후: 30초 A형
bash /root/run_attack.sh -e 1 -i 100 -d 30 -n A-$(date -u +%m%dT%H%M)

# 5) 판정 (CU 박스에서)
OCU_LOG=/tmp/ocu.log JSONL=/root/rss-runs/<run_id>/attempts.jsonl bash /root/collect.sh

# 6) 끝나면 과금 중단
./ctl.sh stop
```

`run_attack.sh`는 UE 실행 인자를 **출력**한다. `ctl.sh`의 UE 기동부에 그 인자를 넘기는 방법
(`UE_EXTRA_ARGS` 환경변수 추가 등)은 박스 `ctl.sh`를 읽고 확정해야 한다 🔍.

## 되돌리기

```bash
git -C /root/OAI checkout -- openair2/RRC/NR_UE
git -C /root/OAI checkout develop          # 또는 원래 브랜치
cp -p /root/OAI/cmake_targets/ran_build/build/nr-uesoftmodem.orig \
      /root/OAI/cmake_targets/ran_build/build/nr-uesoftmodem
```
`destroy`하면 박스 변경은 모두 사라진다. 원본은 항상 이 리포에 둔다.

## 포화(실제 거절) 재현

기본 설정의 셀 상한은 **96**이고 단일 UE의 Msg4 천장은 **3.8/s**다. 96을 채우려면 48/s가 필요하므로
**단일 UE로는 기본 설정에서 포화가 불가능하다**(checklist §9.3). 그래서 포화는 `R × T_hold ≥ N_cap`의
나머지 두 항을 **gNB 설정만으로** 움직인다 — OCUDU 소스는 건드리지 않는다.

```bash
# CU 박스: guard 1000 -> 5000 ms,  DU 박스: nof_cell_sr_res 8 -> 1, t300 -> 2000
sudo bash gnb_profile.sh --role cu apply     # CU에서
sudo bash gnb_profile.sh --role du apply     # DU에서
./ctl.sh up                                   # 설정 반영

# 상한 12 / 보유 7000 ms 상태에서 포화
sudo bash run_attack.sh -e 1 -i 20 -d 60 -n SAT-$(date -u +%m%dT%H%M)

# 포화도를 지정해 돌리기 (CU 실측 동시 점유 = 이 값)
sudo bash run_attack.sh -e 1 -i 0 -o 6 -H 7000 -d 30 -n OCC-t6

# 끝나면 반드시 설정 복원
sudo bash gnb_profile.sh --role cu restore
sudo bash gnb_profile.sh --role du restore
```

판정은 CU 로그의 `Sending rrcReject. Cause: DU is not able to serve the UE` 수와
동시 미완료 피크(= `started` − `timed out` 누적 최대)로 한다. 실측 결과는 checklist §9.5~§9.6.

**프로필 실행은 기본 설정 실행과 반드시 분리해 보고한다**(per-run `gnb_config_profile`).

## 미확인 / 주의

- **박스에서 빌드·실행 검증 완료** ✅ (2026-10-20, OAI `2026.w38`, 브랜치 `rss-ue-a-type`). 공격 off 회귀는 정상 접속 103.8 ms로 통과.
- **RRC 틱은 10 ms가 아니다** — ZMQ 경로 실측 22~34 ms. 그래서 타이머를 벽시계로 바꿨다(checklist §9.1).
- `ack_pending_postpone`은 아직 0건이다. 틱이 27 ms라 ACK PUCCH가 늘 먼저 나가기 때문이며, 틱 제약이 풀리면 이 게이트가 실제로 필요해진다.
- 정상 상태에서도 ZMQ에서 Msg5가 약 8% 유실된다(24회 중 2회) ✅ → 판정 시 기준선으로 뺀다.
- `completion_pct > 0`은 NAS 등록·release 경로를 타므로 A형의 '코어 미도달' 전제가 깨진다. 별도 라벨로 본다.
- 공격 실행은 사용자 승인 후, p5 세트 전용. `max_duration_s`와 `timeout` 둘 다 켠다.
