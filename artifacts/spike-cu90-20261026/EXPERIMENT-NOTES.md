# CU 90 spike 실험 한국어 안내

이 문서는 다음 두 영문 실험 기록의 한국어 안내본이다.

- [Round 4 원문](round4-probe/README.md)
- [Second-DU 분리 원문](second-du/README.md)

두 원문은 `MANIFEST.sha256`의 checksum 대상이므로 수정하지 않고 보존한다. 이 문서는
새로운 실험 증거나 원문 대체물이 아니다. 내용이 충돌하면 checksum으로 확인되는 영문
원문을 기준으로 한다.

## 1. Round 4 — probe 단독 성공, 동시 probe는 계속 CPU 부족

### 결과

- **두 번째 DU에서 probe만 실행**:
  `SSB 0 SINR 59.2 dB RSRP -22 dBm`,
  `RRCSetupComplete`, `Registration Accept`,
  `PDU Session Establishment Accept`, IPv4 `10.45.1.2`,
  `oaitun_ue1`.
  → round 2/3 실패의 원인은 두 번째 DU에 적용한 `taskset -c 4-5`였다
  (PHY/ZMQ thread 자원 부족). taskset을 제거하면 두 번째 DU 셀은 정상이다.
- **공격 UE 5대만 실행**: 시도 3,178건, `msg5_skip` 2,168건,
  `ch.timeout` 277건으로 안정적이었다.
- **CU admission limit**: 969건(최신 `ue=3092~3094`). CU 90 한도에
  계속 도달하고 있다.
- **공격 중 probe**: SSB는 없고 `[SIM]`/`SA init`만 있었다. 두 번째 DU
  `odu2` process는 계속 살아 있었다. 같은 8-vCPU host의 첫 번째 DU와 5-UE 공격이
  probe의 자원을 고갈시켰다.

### 판정

- CU 90 공격은 안정적이고 지속됐다.
- 두 번째 DU에서 probe만 실행하면 동작한다.
- 동시 probe는 host CPU 경합 때문에 여전히 셀 동기화에 실패한다.
- 목표인 지속적인 정상 UE 서비스 거부는 아직 성립하지 않았다.

### 다음 조치

1. 첫 번째 DU/공격은 core 0–3, 두 번째 DU/probe는 4–7에 고정한다.
   두 번째 DU 자체에는 `taskset`을 적용하면 안 된다. 그것만으로 앞선 실패가 발생했다.
2. 또는 DU host의 `e0db566a` `odu2`를 사용해 두 번째 DU/probe를 CU host로
   옮기고 그곳의 OAI segfault를 수정한다. CU의 `ocu`는 `e0db566a`이고,
   CU host 자체의 `odu` `27871a4`는 F1AP 불일치를 일으켰다.
3. probe의 `RRCSetupRequest`가 CU에 도달해 `UE admission limit`으로
   거절되는지 확인한다(`RRCSetupComplete`와 PDU는 없어야 함). 그런 다음 3회 반복한다.

### 파일

- `cu/cu.yaml`, `cu/admission-count.txt`(969), `cu/ocu-tail.log`
- `du/du2.yaml`, `du/ue2-alone.log`(성공), `du/ue2-attack.log`(SSB 없음),
  `du/attack.log`(시도 3,178건 / `msg5_skip` 2,168건),
  `du/probe-*.log`

UE 로그의 과거 `UICC simulation` credential 행은 2026-10-30에 고정 marker로
정제했고 `du/du.tar.gz`도 정제 파일로 다시 만들었다.

## 2. Second-DU probe 분리 — 2026-10-26

### 구성

- CU `max_nof_ues=90`(임시 설정이며 run 뒤 원복).
- 두 번째 DU `odu2`: `du2.yaml` — `pci: 2`, `sector_id: 1`,
  ZMQ 4558/4559, F1-U port 2153, `gnb_du_id 2`. F1과 E2가 연결됐다.
- probe: stock OAI 정상 UE, ZMQ 4559/4558, `uicc0`, RSS 옵션 없음.
- 공격: 첫 번째 DU의 UE 6대, ZMQ 4556/4557.

### 결과

- **probe 단독 실행**(두 번째 DU): `RRCSetupComplete`,
  `Registration Accept`, `PDU Session Establishment Accept`,
  IPv4 `10.45.1.2`, `oaitun_ue1`.
  → 두 번째 DU/probe 경로는 유효하다.
- **공격 단독 30초**: 시도 1,716건, `msg5_skip` 1,084건,
  `ch.timeout` 127건으로 안정적이었다.
- **공격 60초 + probe**: 시도 137건, `msg5_skip` 89건,
  `ch.timeout` 1,082건, shared-TX late-drop 55,990건. probe는 SIM 행만
  출력했고 `RRCSetupRequest`/`RRCSetupComplete`/PDU는 없었다.
  probe가 두 번째 셀에 동기화되지 못했다.
- CU `UE admission limit reached` 집계는 668건(run 누적)이다.
  앞선 6-UE run에서 CU cap 90이 첫 번째 한도였다
  (최대 점유 90, DU `not able to serve` 0건).

### 판정

- CU 90이 첫 번째 admission limit임은 앞선 spike에서 확인됐다.
- 두 번째 DU/probe 분리는 **단독 실행에서는** 유효하다.
- 같은 DU host에서 공격과 probe를 동시에 실행하면 불안정하다. 첫 번째 DU의
  shared TX가 무너지고(`ch.timeout` 1,082건, late-drop 55,990건)
  probe는 셀 동기화에 실패한다. 이는 CU cap 효과가 아니라 하나의 8-vCPU DU host에서
  발생한 자원 경합이다(DU 2개 + UE 2개).
- **이 round에서도 지속적인 정상 UE 서비스 거부 목표는 성립하지 않았다.**

### 다음 조치

1. 첫 번째 DU와 공격은 DU host에 남기고 두 번째 DU/probe를 CU host(4 vCPU)로
   옮기거나, 두 DU/UE를 겹치지 않는 core에 고정한다.
2. 공격 UE를 5대로 줄여 다시 시험한다. probe가 시도하는 동안 CU cap을 채워야 한다.
3. probe의 `RRCSetupRequest`가 CU에 도달해 `UE admission limit` 경로에서
   거절되는지 확인한다(`RRCSetupComplete`와 PDU는 없어야 함). 그런 다음 3회 반복한다.

### 파일

- `cu/cu.yaml` — CU 90 설정 snapshot
- `cu/ocu-window.log` — CU 관측창(admission/RRC)
- `cu/admission-count.txt` — 668
- `du/du2.yaml` — 두 번째 DU 설정
- `du/odu2.boot.log`, `du/odu2-window.log` — 두 번째 DU F1/E2/probe trace
- `du/ue2-alone.log` — probe 단독 실행(성공)
- `du/ue2-attack.log` — 공격 중 probe(RRC 없음)
- `du/attack2.log` — 공격 60초 self-check(collapse)
- `cu/cu.tar.gz`, `du/du.tar.gz` — 보존 bundle. DU UE 로그의 과거
  `UICC simulation` credential 행은 2026-10-30에 정제했고 DU bundle도 다시 만들었다.
