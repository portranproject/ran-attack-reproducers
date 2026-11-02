# 96/96 재현 검증 — 2026-10-21, 현재 도구 버전

p5 AWS 테스트베드(ZMQ 가상 RF)에서 현재 `rss-storm` 버전으로 모드 A(gNB 기본 설정)
공격을 실행하고, **gNB 자신의 로그**로 판정한 기록이다. UE 로그의 과거
`UICC simulation` credential 행 2개는 2026-10-30에 고정 marker로 정제했고 gzip
복사본도 다시 만들었다. 그 외 실험 행은 유지했지만 디렉토리 전체를 더 이상 byte
원문이라고 부르지 않는다.

## 실행 조건

| 항목 | 값 |
|---|---|
| run_id | `Au2-20261021T011315Z` |
| 시작(UTC) | 2026-10-21T01:13:15Z (DU 재기동 포함), 공격 본체 01:13:41 |
| 노브 | `-e 1 -u 2 -d 120`, `completion_pct=0`, `honor_reject=1`, `msg4_wait=1`, `target_occupancy=0` |
| gNB | OCUDU `release_26_10` (`e0db566a`), **설정 기본값**(모드 B 프로필 미적용) |
| 공격 UE | OAI `2026.w38-1-g6d6782b` + `patch/rss-ue.patch` |
| | `6d6782b`은 공식 OAI PUCCH 크래시 수정(`#493`) 1커밋. 태그 `2026.w38` 자체에는 없다 |
| 패치 md5 | `c68428c87094b04fc063540fc82cd5da` |
| 셀 | n78 TDD, 3489.42 MHz, 30 kHz SCS, 51 PRB, ZMQ `127.0.0.1:4556/4557` |

## 셀이 선언한 용량 (96의 출처)

`du-capacity-declaration.txt` 원문:

```
The upper-bound on the number of UEs supported by cell {pci=1, du_cell_index=0} is 96
(the actual number might be lower than that). This is determined by the lowest of the
following limits: SR (96), CSI (96), SRS (n/a) and UE contexts per cell (1984).
Up to 160 UE contexts can be created in the cell, the extra ones being used to RRC Reject UEs.
```

`min(SR 96, CSI 96, 1984) = 96`이고, 거절용 64를 더한 160이 셀의 단말 객체 상한이다.
`docs/MECHANISM.md` §5.1의 용량 식이 기동 로그로 확인된 것이다.

## 판정 — 공격 본체 구간 (01:13:41 ~ 01:15:41, 120.0 s)

`rss-report-attack-body.txt` 전문 참조.

| 관측 | 값 |
|---|---|
| 시작된 절차 | 4,438건 (37.0/s) |
| **피크 점유** | **96 / 96** — 2026-10-21T01:13:43.026573 (시작 2.0초 후) |
| 종료 사유 | `timed out` 4,365건 (완료 0건) |
| 보유 시간 실측 | 중앙값 **1,999 ms**, p90 2,000 ms (= `t300` 1000 + 가드 1000) |
| 점유 >= 24 | 119.2 s / 120.0 s (99%), 최장 평탄 119.16 s |
| 점유 >= 48 | 118.4 s / 120.0 s (99%), 최장 평탄 115.84 s |
| 점유 >= 72 | 79.7 s / 120.0 s (66%), 최장 평탄 13.14 s |
| 점유 >= 96 | 0.5 s / 120.0 s (0%), 최장 평탄 **0.45 s** |
| `rrcReject` | 15건 |
| `DU is not able to serve` | 5건 |
| `rrcSetupComplete` | **0건** |
| NGAP `InitialUEMessage` | **0건** |

UE 쪽(`attempts.jsonl`, 4,469 시도): `actual_reach`가 `msg5_skip` 4,604 /
`rrc_reject` 5 / `no_msg4` 14, **`msg5_sent` 0건**. `ch.timeout` 7,241.

### 읽는 법

- **용량에는 도달했고(96/96), 그 상태가 유지되지는 않는다.** 96에서의 최장 평탄
  구간은 0.45초다. README "포화 유지" 모드 A 설명과 같은 결과다(과거 측정 0.93초).
- 유지된 것은 **용량 절반 수준**이다: 점유 >= 48이 구간의 99%, 끊김 없이 115.84초.
- 보유 시간 실측 1,999 ms가 설정값 합(1000+1000)과 일치한다.

## 킬 스위치 직후 완료 2건 (주의)

전체 창(01:13:15~01:15:42)으로 보면 `rrcSetupComplete` 6줄, `InitialUEMessage`
2건이 나온다. 위치는 **01:15:41.52~41.54**, 즉 킬 스위치가 발동한 순간이고 UE id는
`4458`·`4459`(인스턴스당 1개)다.

재현기가 스스로 무장해제되면 그 시점에 **진행 중이던 시도 2개가 스톡 경로로 정상
완료**되어 코어까지 닿는다. 따라서

- "시나리오가 A형을 유지했다"를 `rrcSetupComplete == 0`으로 판정할 때는
  **판정 창에서 킬 스위치 꼬리를 제외**해야 한다(위 본체 구간처럼).
- 탐지팀에 라벨을 넘길 때 이 2건은 `msg5_sent`가 아니라 **무장해제 후 스톡 완료**로
  구분해야 한다. `attempts.jsonl`에는 `kill_switch` 이벤트 1건만 남고 완료 기록은
  없다.

## 파일

| 파일 | 내용 |
|---|---|
| `ocu-window-raw.log` | CU 로그 원문, 01:13:15~01:15:42 구간 **199,382줄** (가공 없음) |
| `rss-report-attack-body.txt` | 본체 구간 판정 전문 |
| `rss-report-full-window.txt` | 전체 창 판정 전문(킬 스위치 꼬리 포함) |
| `du-capacity-declaration.txt` | DU 기동 로그의 용량 선언 원문 |
| `rss-run-shell.log` | `bin/rss-run` 실행 출력 원문 |
| `run.json` | 런의 모든 노브와 셀 파라미터 |
| `attempts.jsonl` | UE 쪽 시도별 기록 4,469건 |
| `ue.log` | UE 표준 출력 전문 |
| `SHA256SUMS` | 위 파일들의 해시 |

## 원문 로그에서 A형의 서명 3종

`ocu-window-raw.log`(또는 박스의 `/tmp/ocu.log`)에서 아래 세 줄이 A형을 증명한다.

```
[RRC  ] [W] ue=17 c-rnti=0x4612: "RRC Setup Procedure" timed out after 2000ms
[NGAP ] [I] ue=17: Ignoring UEContextReleaseRequest. Cause: UE has no NGAP context
[CU-CP] [D] ue=17: Skipping NG UE Context Release Request. Cause: UE does not have an NG UE context
```

| 줄 | 증명하는 것 |
|---|---|
| `timed out after 2000ms` | 미완료 절차가 보유 시간까지 자원을 점유했다. 2000 = `t300` 1000 + 가드 1000, 곧 `procedure_timeout` 식의 실측값 |
| `UE has no NGAP context` | **코어에 닿지 않았다.** CU가 적극적으로 진술한다 — `InitialUEMessage`가 "없다"는 부재 증명보다 강하다 |
| `UEContextReleaseCommand` + `SRB1 DL: TX SDU` | gNB가 혼자 해제를 진행한다. 공격 UE는 이미 다음 시도로 넘어가 `RRCRelease`를 받지 않는다 |

깨끗한 화면으로 보려면(16진 덤프·페이저 제외):

```bash
awk '$1>="2026-10-21T01:13:41" && $1<"2026-10-21T01:15:41"' ocu-window-raw.log \
  | grep -E '"RRC Setup Procedure" (started|timed out)|no NGAP context|rrcReject' \
  | grep -v PDCP | head -24
```

UE 하나의 생애 전체:

```bash
grep -E ' ue=17[ :]' ocu-window-raw.log | grep -vE '\[PDCP|\[RLC|^ +0000:' | head -14
```

## 실제 쉘 스크린샷을 찍는 방법

이 저장소의 기록은 텍스트 원문이다. 발표용 **실제 터미널 스크린샷**이 필요하면
아래 중 하나를 네 터미널에서 직접 실행하고 캡처한다.

### A. 박스에서 라이브로 (박스가 켜져 있어야 함)

```bash
cd /Volumes/owc/Users/ideal/tmp/p5-panel/p5
./ctl.sh ssh cu
# 접속된 박스에서:
cd /root/rss-storm
bin/rss-report --since 01:13:41 --until 01:15:41 --capacity 96
```

원문 로그를 직접 보여 주려면 같은 세션에서:

```bash
sudo grep -m1 'upper-bound on the number of UEs' /tmp/odu.log   # DU 박스에서
sudo grep -m3 '"RRC Setup Procedure" timed out' /tmp/ocu.log
sudo grep -m3 'rrcReject' /tmp/ocu.log
```

### B. 보존된 원문으로 (박스 없이)

```bash
cd /Volumes/owc/Users/ideal/s-dev/ran-rrc-storm/artifacts/verify-20261021
cat rss-report-attack-body.txt
grep -m3 '"RRC Setup Procedure" timed out' ocu-window-raw.log
grep -m1 'peak occupancy' rss-report-attack-body.txt
shasum -a 256 -c SHA256SUMS
```
