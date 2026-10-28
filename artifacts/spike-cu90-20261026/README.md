# Spike — CU `max_nof_ues=90` vs DU 96 (2026-10-26)

## 목적

CU-CP의 UE admission cap을 DU 셀 용량(96)보다 낮은 90으로 두었을 때,
CU가 DU보다 먼저 새 UE를 거절하는지 확인한다.

## 구성

- CU: OCUDU 26.10, `cu.yaml`의 `cu_cp.max_nof_ues: 90` (임시). gNB 소스 무수정.
- DU: OCUDU 26.10 기본 설정(셀 용량 96), OAI `2026.w38` + RSS 패치.
- ZMQ 가상 무선, 단일 셀, n78 TDD 30 kHz 51 PRB.
- CU 스택 재기동 후 DU 기동.

## 실행

- first: `bin/rss-run -e 1 -u 6 -d 20 -H 2000 -r 0` (프로브 없음)
- second: 동일 + `UE_EXTRA="--rss.probe_ues 1"` (프로브 1 + 공격 5)

## 결과 — first run (02:00:51–02:01:14 UTC)

- CU 피크 점유 **90** (capacity reference 96), `UE admission limit reached` **627건**.
  - 첫 발생: `02:00:52.212 ue=90` — 첫 RRC Setup 시작(`02:00:51.427`) 후 약 **0.8초**.
  - 마지막: `02:01:10.827 ue=1346`.
- `started 758 (33.0/s wall)`, `timed out 754`, `finished successfully 4`, 보유 중앙값 **1,999ms**.
- DU `not able to serve` **0건**. DU 셀 용량 96에 여유가 있었다.
- CU `rrcReject` **0건**. admission limit 경로는 `UE admission limit reached` 경고 후
  UE를 release하며, RRCReject를 로그로 남기지 않는다.
- 같은 창에서 `rrcSetupComplete` 14, `InitialUEMessage` 4 — **킬 스위치 꼬리**의 정상 완료로,
  A형 순도 판정에서는 제외해야 한다(README §"킬 스위치 직후 완료"). `msg5_skip` 763.

## 결과 — second run (probe 포함)

- `attempts 82`, `ch.timeout 35,200`, outer timeout 40 s. 공유 ZMQ가 붕괴해
  프로브 분기가 측정되지 않았다(`probe_attempt`/`probe_connected` 없음).
- `run.json`은 `probe_ues: 0`으로 기록했으나, UE 명령행에는 `--rss.probe_ues 1`이
  중복 append되어 UE 로그에는 `probe_ues knob = 1`이 찍혔다. 하네스 로깅 불일치.
- **정상 UE 차단은 이 실행으로 입증되지 않았다.** 프로세스 내 프로브의 공유 ZMQ
  교란(기존 findings) 때문이며, 별도 무선/지연 프로브가 필요하다.

## 판정

- **CU cap 90이 DU 96보다 먼저 걸린다.** CU 피크 90, DU `not able` 0.
  기술 기전은 확인되었다.
- CU의 거절은 `RRCReject`가 아니라 **admission-limit release**다.
  탐지 신호는 CU-CP 경고 + F1 UE context release이며, `rrcReject` 카운터는 0이다.
- **주장 범위**: "CU-CP를 90으로 설정한 조건에서 CU admission denial이 발생한다."
  기본 `max_nof_ues=8192` CU를 마비시켰다는 주장은 성립하지 않는다.
- **정상 UE 차단**은 아직 미입증. 다음 단계는 별도 무선/별도 프로세스 프로브
  또는 프로브 시작 지연 설계다.

## 파일

- `cu/cu.yaml` — 90 설정 원본(증거)
- `cu/ocu-config-head.txt` — CU 로그의 config dump
- `cu/ocu-first-run-filtered.log` — 첫 런의 RRC/admission/완료/거절 라인
- `cu/rss-report-first.txt` — 첫 런 점유 보고
- `cu/admission-count.txt` — 627
- `cu/source-notes.txt` — `ue_admission_limit_reached` / `max_nof_ues` 소스 위치
- `du/not-able-count.txt` — 0
- `du/odu-first-run-filtered.log` — DU 로그 필터. 타임스탬프 형식이 달라 **비어 있다**.
  DU 여유의 근거는 `du/not-able-count.txt`(0)와 `du/run-first/`의 부팅 로그다.
  DU 원본 `/tmp/odu.log` 전체는 stop 전에 복사하지 않았고, `not able` 0은 실행 중 로그에서 센 값이다.
- `du/run-first/`, `du/run-probe/` — UE 로그·attempts·run.json
- `cu/spike-cu90-cu.tar.gz`, `du/spike-cu90-du.tar.gz` — 원본 묶음

## 원복

- CU `cu.yaml`은 `cu.yaml.bak-spike-20261026`으로 원복했다. 테스트베드는 stop.
