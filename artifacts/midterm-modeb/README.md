# 모드 B 재현 증거 (중간발표용)

2026-10-19 실험을 **현재 분석 도구로 재계산**한 결과다. 숫자는 전부 gNB(CU) 자신의 로그에서 나왔다.

## 1. 실험 조건

**gNB 설정만 변경했고 소스는 수정하지 않았다**(`bin/rss-gnb-profile`, `.orig` 백업 유지).

| 항목 | 기본값 (모드 A) | 이 실험 (모드 B) | 변경한 키 |
|---|---:|---:|---|
| 셀 용량 | 96 | **12** | `cell_cfg.pucch.nof_cell_sr_res` 8 → 1 (DU) |
| `t300` | 1000 ms | 2000 ms | `cell_cfg.sib.t300` (DU, 3GPP 최대) |
| RRC 절차 가드 | 1000 ms | 5000 ms | `cu_cp.rrc.rrc_procedure_guard_time_ms` (CU) |
| **보유 시간** | 2000 ms | **7000 ms** | 위 둘의 합 |

DU 기동 로그가 용량을 스스로 선언한다 (`du-capacity-declaration-modeb.txt` 원문):

```
The upper-bound on the number of UEs supported by cell {pci=1, du_cell_index=0} is 12
(the actual number might be lower than that). This is determined by the lowest of the
following limits: SR (12), CSI (96), SRS (n/a) and UE contexts per cell (1984).
Up to 76 UE contexts can be created in the cell, the extra ones being used to RRC Reject UEs.
```

`min(SR 12, CSI 96, 1984) = 12`. 즉 **용량을 정하는 것은 SR 자원 수**이고, 그 값만 설정으로 내렸다.

## 2. 측정 결과

### 2.1 폐루프 점유 제어 — 요청한 수준에 정확히 착지

| 런 | 요청 점유 | **피크 점유** | 목표 수준 평탄 구간 | 보유 시간 실측 | `RRCReject` |
|---|---:|---:|---:|---:|---:|
| `OCC-t3` | 3 | **3** | 6.75 s | 6,999 ms | 0 |
| `OCC-t6` | 6 | **6** | 6.45 s | 6,999 ms | 0 |
| `OCC-t12` | 12 (= 용량 100%) | **12** | 5.77 s | 6,999 ms | **3** |

`OCC-t12`에서는 `DU is not able to serve the UE`도 1건 발생했다 — 셀이 한도에 닿았다는 뜻이다.

### 2.2 전체 창 (390초, 세 데모 연속)

| 관측 | 값 |
|---|---:|
| 시작된 절차 | 171건 |
| 피크 점유 | **12 / 12** |
| 점유 = 12 (만석) | **56.2 s / 390 s (14%)**, 최장 연속 **5.80 s** |
| 점유 >= 3 | 157.8 s (40%), 최장 연속 **28.80 s** |
| 보유 시간 실측 | 중앙값 **6,999 ms**, p90 7,000 ms |
| 종료 사유 | `timed out` 171건 — 완료 0건 |
| `rrcSetupComplete` | **0** |
| NGAP `InitialUEMessage` | **0** |

**보유 시간 6,999 ms는 설정값 합(2000 + 5000 = 7000 ms)과 밀리초 단위로 일치한다.** OCUDU
소스의 `procedure_timeout = t300 + rrc_procedure_guard_time_ms`가 실측으로 확인된 것이다.

## 3. 주장할 수 있는 것과 없는 것

| 주장 | 가능? | 근거 |
|---|---|---|
| 셀이 선언한 자원 상한(12)에 도달했다 | **가능** | 피크 12/12 + `RRCReject` + `DU is not able to serve` |
| 요청한 점유 수준을 재현 가능하게 유지했다 | **가능** | 목표 3/6/12 → 피크 정확히 3/6/12 |
| 시나리오가 A형을 벗어나지 않았다 | **가능** | `rrcSetupComplete` 0, NGAP `InitialUEMessage` 0 |
| 보유 시간이 gNB 설정으로 정해진다 | **가능** | 실측 6,999 ms = 설정 합 7,000 ms |
| **"반영구/지속 마비"** | **불가** | 만석 유지는 **최장 5.80초**. 총 점유 시간은 창의 14% |
| 정상 사용자가 서비스를 거부당했다 | **불가** | 별도 정상 UE로 측정하지 않았다. ZMQ 포트 쌍 하나로는 공격 UE와 정상 UE를 동시에 붙일 수 없다 |

**발표에서 "마비"라는 단어를 쓰려면 위 두 줄이 필요하다.** 현재 쓸 수 있는 표현은
"설정된 자원 상한에 도달하고 그 지점에서 신규 접속이 거절됐다"다.

## 4. 모드 A(기본 설정)와의 대비 — 같은 도구, 같은 산수

2026-10-21 모드 A 측정(`../verify-20261021/`)과 나란히 놓으면 결과가 하나의 식으로 설명된다.

```
평형 점유  N = R × T_hold        (R = 시도율, T_hold = 보유 시간)
포화 조건  R × T_hold ≥ N_cap
```

| | 모드 A (기본값) | 모드 B (이 실험) |
|---|---:|---:|
| 용량 `N_cap` | 96 | 12 |
| 보유 시간 `T_hold` (실측) | 1,999 ms | 6,999 ms |
| 포화에 필요한 `R` | **48.0/s** | **1.7/s** |
| 도구가 내는 `R` | 37.9/s (필요량의 79%) | 폐루프로 조절 |
| 결과 | 피크 96 도달, 만석 최장 **0.87 s**, 평형 점유 76 | 피크 12 도달, 만석 최장 **5.80 s** |

**모드 B가 "되는" 이유는 공격이 강해서가 아니라 필요 시도율이 1.7/s로 낮아졌기 때문이다.**
이 대비 자체가 결과다 — 상용 셀 용량(96)에서는 같은 도구로 지속 포화가 안 되고, 그 이유가
산수로 설명된다.

## 5. 파일

| 파일 | 내용 |
|---|---|
| `ocu-modeb-window.log` | CU 로그 원문 발췌 (501줄, `[RRC]` 필터, 22:03:31~22:10:08) |
| `du-capacity-declaration-modeb.txt` | DU 기동 로그의 용량 12 선언 원문 |
| `analysis.md` | 런별·전체 창 분석 전문 (현재 도구로 재계산) |
| `runs/*/run.json` | 각 런의 모든 노브 |
| `runs/*/attempts.jsonl` | UE 쪽 시도별 기록 |

**원본 로그의 한계**: 이 로그는 `[RRC]` 줄만 남긴 **발췌**다. 전체 CU 로그는 보존되지 않았다.
점유 재구성은 이 발췌의 `"RRC Setup Procedure" started / timed out` 줄로 했고, 분석 도구가
`evidence uncertain: initial occupancy is unknown`을 함께 출력한다. 창 시작 시점에 이미 12개가
살아 있었으므로(`observed carry-in 12`) 그 직전 `SAT2` 런도 용량에 도달해 있었다.

## 6. 발표 슬라이드용 한 줄

> 용량 12로 설정한 셀에서, UE 측만 변조한 A형 RSS 재현기가 **요청한 점유 수준(3/6/12)에 정확히
> 도달**했고, 용량 100%(12/12)에서 `RRCReject`가 발생했다. 보유 시간 실측 6,999 ms는 gNB 설정값
> 합과 일치했으며, `rrcSetupComplete`와 NGAP `InitialUEMessage`는 0으로 코어에 닿지 않았다.
> 기본 설정(용량 96)에서는 같은 도구로 피크 96에 도달하지만 지속 포화에는 48 시도/초가 필요해
> 현재 37.9/초로는 미달이며, 그 차이는 `N = R × T_hold`로 설명된다.
