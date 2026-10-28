# 중간발표 첨부 가이드 — 어떤 로그의 어느 부분을 쓰고 무엇을 강조할지

로그가 두 벌 있고 **쓰임이 다르다.** 섞어 써야 주장이 완성된다.

| 로그 | 경로 | 강점 | 약점 |
|---|---|---|---|
| **모드 B** (2026-10-19) | `artifacts/midterm-modeb/ocu-modeb-window.log` | 용량 12 축소 상태에서 **용량 100% 점유 도달**, 보유 7000 ms | `[RRC]` 필터 발췌라 **NGAP 줄이 없음** → 코어 미도달을 직접 못 보여줌 |
| **모드 A** (2026-10-21, 어제 측정) | `artifacts/verify-20261021/ocu-window-raw.log` | **가공 없는 전체 로그 199,382줄**, 코어 미도달 진술 4,370줄, 용량 96 선언 | 만석 유지는 0.87초 (지속 포화 아님) |

---

## 슬라이드 1 — 셀이 선언한 용량 (전제 제시)

**첨부**: `du-capacity-declaration-modeb.txt` 전문 1줄

```
2026-10-19T22:09:16 [CONFIG] [I] The upper-bound on the number of UEs supported by cell
{pci=1, du_cell_index=0} is 12 ... lowest of the following limits: SR (12), CSI (96),
SRS (n/a) and UE contexts per cell (1984). Up to 76 UE contexts can be created in the
cell, the extra ones being used to RRC Reject UEs.
```

**강조**: 12는 우리가 정한 숫자가 아니라 **기지국이 자기 로그에 선언한 한도**다.
그리고 `min(SR 12, CSI 96, ...)` 이므로 **용량을 정하는 것은 SR 자원 수**다.

**캡션에 반드시 넣을 전제**: "gNB 설정에서 `nof_cell_sr_res`를 8→1로 낮춘 상태(소스 무수정).
기본값에서는 같은 줄이 96으로 찍힌다 — 모드 A 로그 참조."

> 대비용으로 모드 A의 같은 줄을 나란히 두면 효과가 크다:
> `artifacts/verify-20261021/du-capacity-declaration.txt` → `... is 96 ... SR (96), CSI (96) ... Up to 160 ...`

---

## 슬라이드 2 — 공격의 핵심: 보유 시간 동안 자원을 붙잡는다

**첨부**: `ocu-modeb-window.log` **1행과 28행** (한 UE의 생애)

```
[원문 1행]  22:03:31.124655 [RRC] [I] ue=7 c-rnti=0x4601: "RRC Setup Procedure" started...
[원문 28행] 22:03:38.123679 [RRC] [W] ue=7 c-rnti=0x4601: "RRC Setup Procedure" timed out after 7000ms
```

**강조**: 두 줄의 간격이 정확히 **6.999초**다. 그리고 `7000ms`는 우리가 측정한 값이 아니라
**gNB가 자기 로그에 찍은 값**이고, 이는 설정값 `t300`(2000) + CU 가드(5000)의 합과 일치한다.
즉 **미완료 절차가 자원을 붙잡는 시간은 기지국 설정이 정한다**는 것이 로그 한 줄로 증명된다.

**이 숫자가 모드를 식별한다**: `7000ms` = 모드 B, `2000ms` = 기본 설정. 발표 자료에 만료 시간을
항상 같이 표시하면 두 실험이 헷갈리지 않는다.

---

## 슬라이드 3 — 용량에 닿으면 신규 접속이 거절된다

**첨부**: `ocu-modeb-window.log` **13~14행**

```
[원문 13행] 22:03:32.616990 [RRC] [W] ue=19 c-rnti=0x460d: Sending rrcReject. Cause: DU is not able to serve the UE
[원문 14행] 22:03:32.617015 [RRC] [D] ue=19 c-rnti=0x460d: Tx SRB0 CCCH DL rrcReject (1 B)
```

**강조**: 거절 **이유 문구**가 핵심이다 — `DU is not able to serve the UE`. 기지국이 스스로
"서비스할 수 없다"고 말한 것이다.

**숫자를 인용할 때 주의**: 창 전체에서 `Sending rrcReject`는 **45건**이다. `rrcReject`를 포함한
줄은 더 많지만(한 번 거절에 2~3줄이 찍힌다) **거절 횟수는 `Sending rrcReject` 기준으로 센다.**
줄 수를 거절 횟수로 쓰면 2~3배 과장이 된다.

---

## 슬라이드 4 — 코어에 닿지 않았다 (A형의 정의)

**첨부**: 모드 B 로그가 아니라 **모드 A 전체 로그**를 쓴다
`artifacts/verify-20261021/ocu-window-raw.log`

```
[RRC ] [W] ue=17 c-rnti=0x4612: "RRC Setup Procedure" timed out after 2000ms
[NGAP] [I] ue=17: Ignoring UEContextReleaseRequest. Cause: UE has no NGAP context
[CU-CP] [D] ue=17: Skipping NG UE Context Release Request. Cause: UE does not have an NG UE context
```

창 안 집계: `UE has no NGAP context` **4,370줄**, `rrcSetupComplete` **0**,
NGAP `InitialUEMessage` **0**.

**강조**: "코어 미도달"을 **없음(0건)으로 증명하지 말고 있음으로 증명한다.** CU가 적극적으로
"이 UE엔 NG 컨텍스트가 없다"고 4,370번 진술한 것이 훨씬 강한 증거다.

재현 명령 (발표 중 시연 가능):
```bash
cd artifacts/verify-20261021
awk '$1>="2026-10-21T01:13:41" && $1<"2026-10-21T01:15:41"' ocu-window-raw.log \
  | grep -E '"RRC Setup Procedure" (started|timed out)|no NGAP context' | grep -v PDCP | head -24
```

---

## 슬라이드 5 — 통제 가능성 (이게 우리 도구의 차별점)

**첨부**: `analysis.md`의 세 런 표

| 요청 점유 | 피크 점유 | 보유 시간 실측 |
|---:|---:|---:|
| 3 | **3** | 6,999 ms |
| 6 | **6** | 6,999 ms |
| 12 (= 용량 100%) | **12** | 6,999 ms |

**강조**: "강한 공격"이 아니라 **"파라미터가 통제되는 재현기"**라는 점. 탐지기 임계값을 찾으려면
부하를 원하는 수준에 고정할 수 있어야 하고, 폐루프 제어가 요청값에 **정확히** 착지했다.

---

## 슬라이드 6 — 한계를 먼저 말한다 (심사에서 반드시 물어볼 것)

| 주장 | 가능 | 근거 |
|---|---|---|
| 선언된 자원 상한에 도달 | ✅ | 피크 12/12 + `rrcReject` 45건 |
| 요청 점유 수준 유지 | ✅ | 목표 3/6/12 → 피크 정확히 일치 |
| 코어 미도달 | ✅ | `no NGAP context` 4,370줄, `InitialUEMessage` 0 |
| 보유 시간이 설정으로 정해짐 | ✅ | 실측 6,999 ms = 설정 합 7,000 ms |
| **"반영구 마비"** | ❌ | 만석 유지 **최장 5.80초** (총 56.2초 / 390초 = 14%) |
| 정상 사용자 서비스 거부 | ❌ | 별도 정상 UE 미측정. ZMQ 포트 쌍 1개로는 동시 접속 불가 |

**쓸 수 있는 표현**: "설정된 자원 상한에 도달하고 그 지점에서 신규 접속이 거절됐다."
**쓰면 안 되는 표현**: "기지국을 마비시켰다", "서비스를 중단시켰다".

---

## 슬라이드 7 (선택) — 왜 기본 설정에서는 더 어려운가

산수 한 줄이 두 실험을 모두 설명한다.

```
평형 점유  N = R × T_hold          포화 조건  R × T_hold ≥ N_cap
```

| | 모드 A (기본값) | 모드 B |
|---|---:|---:|
| 용량 | 96 | 12 |
| 보유 시간 (실측) | 1,999 ms | 6,999 ms |
| 포화에 필요한 시도율 | **48.0/s** | **1.7/s** |
| 측정된 시도율 | 37.9/s → **최적화 후 49.4/s** | — |

**강조**: 모드 B가 되는 이유는 공격이 강해서가 아니라 **필요 시도율이 낮아져서**다. 이 대비가
"방어 측이 `nof_cell_sr_res`를 넉넉히 두는 것 자체가 완화책"이라는 결론으로 이어진다.

> 진행 중: 재현기 최적화로 모드 A에서 시도율 37.9 → **49.4/s**(필요치 48/s 돌파)를 90초 런에서
> 측정했다. 장시간 유지 검증이 끝나면 이 슬라이드를 "기본 설정에서도 도달"로 갱신할 수 있다.

---

## 첨부 파일 체크리스트

```
artifacts/midterm-modeb/
  du-capacity-declaration-modeb.txt   슬라이드 1
  ocu-modeb-window.log                슬라이드 2, 3 (1행, 28행, 13~14행)
  analysis.md                          슬라이드 5, 6 (런별 수치 전문)
  runs/*/run.json                      실험 조건 (재현성)
artifacts/verify-20261021/
  du-capacity-declaration.txt          슬라이드 1 대비용 (용량 96)
  ocu-window-raw.log                   슬라이드 4 (가공 없는 전체 로그)
  rss-report-attack-body.txt           슬라이드 7 (모드 A 판정 전문)
  SHA256SUMS                           무결성
```
