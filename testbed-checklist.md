# 팀 테스트베드 체크리스트와 베이스 UE 결정

> 작성 2026-10-16. 표시 규칙은 [comparison-5g.md](comparison-5g.md) §0과 같다(✅ 원본 대조 / 📄 리포 문서 출처만 / 🔍 추론·미확인).

## 0. 출처와 상태

팀 Drive `PortRAN Project > 실습 자료 > res` 폴더(2026-10-16 공유받음)를 읽었다. 폴더에는 다음 파일이 있다.

| 파일 | 내용 | 이번에 읽은 범위 |
|---|---|---|
| `AWS EC2 기반 5G NR SA 종단간 실습 환경-1.pdf` (2026-10-09) | 실습 절차: 인스턴스 기동 → CU 먼저, DU 다음 → 로그·KPM 확인 → UE 등록 | 본문 텍스트만. 로그 스크린샷 이미지는 판독하지 못함 |
| `p1.zip` ~ `p5.zip` (2026-10-14) | 팀원별 EC2 제어판: `README.md`, `ctl.sh`, `setup.sh`, 그리고 비밀 파일 `credentials`, `portran-key.pem` | `p1.zip`의 `README.md`·`ctl.sh`·`setup.sh`만. 비밀 파일은 열지 않았다. p2~p5는 세트 번호만 다른 사본으로 보인다 🔍 (README의 "`pN` → CU `172.31.N.10`" 규칙) |

**핵심 발견**: 현재 팀 실습 테스트베드는 RF 차폐 박스가 아니라 **AWS EC2 2대(CU 박스·DU 박스) 위의 ZMQ 가상 RF**다 ✅. [AGENTS.md](AGENTS.md)의 "3-노트북 RF 차폐" 구성과 다르다. 차폐 OTA 구성이 따로 계획돼 있는지는 이 폴더로 알 수 없다 🔍.

**셀 설정 확인**: 2026-10-16 사용자가 세트 p5의 DU 박스(`ip-172-31-5-11`)와 CU 박스(`ip-172-31-5-10`)에서 명령을 실행해 출력을 붙여 주었다. 아래 ✅ 중 "박스 출력" 근거는 그 출력이다.

## 1. 체크리스트

| 항목 | 값 | 근거 | 표시 |
|---|---|---|---|
| **TDD/FDD** | **TDD** | `du.yaml`의 `band: 78`. OCUDU `lib/ran/band_helper.cpp`의 이중화 표에 `{nr_band::n78, duplex_mode::TDD}` | ✅ |
| TDD 패턴 | 기본 패턴 `DDDDDDXUUU`(10슬롯 주기, DL 6 + 특수 1 + UL 3)으로 추정 | `du.yaml` grep에 `tdd_ul_dl_cfg`가 나오지 않음 → OCUDU가 기본 패턴 자동 생성(§2.1). 다른 설정 파일을 함께 불러오는지는 미확인 | 🔍 |
| SCS (`common_scs`) | **30 kHz** | 박스 출력 `common_scs: 30` | ✅ |
| 대역폭 (`channel_bandwidth_MHz`) | **20 MHz** | 박스 출력 | ✅ |
| `dl_arfcn` / `band` | **632628 / n78** | 박스 출력. OCUDU 공식 예제 `gnb_rf_b200_tdd_n78_20mhz.yml`의 셀 값과 같다(§2.2) | ✅ |
| CU/DU 분리 여부 | **분리.** CU 박스(c6i.xlarge)와 DU 박스(c6i.2xlarge)가 F1으로 연결. 사설 IP는 세트별 고정 CU `172.31.N.10` / DU `172.31.N.11` | `p1/README.md`, `p1/ctl.sh`(`cu.yaml`·`du.yaml` 따로 존재). 박스 호스트명 `ip-172-31-5-10`/`-11`도 이 규칙과 맞음 | ✅ |
| RF 경로 | **ZMQ 가상 RF.** UE가 DU 박스에서 함께 실행됨 | 박스 출력 `device_driver: zmq`. `ctl.sh` 주석 "ZMQ 이중 PHY" | ✅ |
| OCUDU 버전·커밋 | **`e0db566a` = 태그 `release_26_10`** (2026-09-30, "bump version to 26.10") | 박스 출력 `rev-parse HEAD`. `gitlab.com/ocudu/ocudu`에서 `git ls-remote --tags`와 커밋 조회로 대조 | ✅ |
| 코어 종류 | **Open5GS** (Docker 컨테이너 `open5gs_5gc`, CU 박스) | 박스 출력: CU `ctl.sh`의 `docker logs -f open5gs_5gc` | ✅ |
| RIC | FlexRIC, E2(KPM) 연결 | `ctl.sh` "FlexRIC 가 죽는다", "E2(KPM)→RIC OK" | ✅ |
| 현재 쓰는 UE | **OAI UE** (`nr-uesoftmodem`, `/root/OAI/cmake_targets/ran_build/build/`) | 박스 출력: DU `ctl.sh` 26·29행 `OAI=/root/OAI`, `UE_BIN=$OAI/…/nr-uesoftmodem` | ✅ |
| **OAI UE 버전** | **`2026.w38`** / 커밋 `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (2026-09-20, `Merge … integration_2026_w38 into develop`). 빌드 바이너리는 2026-10-08 | 박스 출력 `git describe --tags --always`, `git log -1`, 바이너리 `ls -la`. 리모트는 `OPENAIRINTERFACE/openairinterface5g.git` | ✅ |

### 1.1 OAI UE 버전 판정 ✅

| 기준 | 값 | 판정 |
|---|---|---|
| OCUDU 공식 OAI UE 튜토리얼 요구 | `2026.w25` 이상 📄 | **충족** (w38 > w25, 13주 앞섬) |
| 5gattacks 패치의 기준 트리 | OAI `2025.w46` (2025-11-16) 📄 | **약 10개월 뒤** — 패치는 그대로 적용되지 않는다 |

`2026.w38`은 공식 튜토리얼 하한보다 새롭고, 이 박스에서 Open5GS 등록까지 성공한 버전이다. 반면 5gattacks 패치 기준보다 약 10개월 뒤이므로, 패치를 `git apply`로 얹는 방식은 쓸 수 없고 **동작을 읽어서 다시 구현**해야 한다(§4).

## 2. 설정 파일에서 값을 읽는 법 (OCUDU 원본 대조)

대조 기준: [ocudu/ocudu](https://gitlab.com/ocudu/ocudu) `de11750b` (2026-10-15 커밋, `git clone`으로 확인).

### 2.1 TDD/FDD는 `band`가 정한다 ✅

OCUDU는 `cell_cfg.band` 값으로 이중화 방식을 결정한다. `band`가 없으면 `dl_arfcn`에서 band를 먼저 도출한다.

```cpp
// apps/units/flexible_o_du/o_du_high/du_high/du_high_config_cli11_schema.cpp, derive_cell_auto_params()
if (not cell_cfg.band.has_value()) {
  cell_cfg.band = band_helper::get_band_from_dl_arfcn(cell_cfg.dl_f_ref_arfcn);
}
const duplex_mode dplx_mode = band_helper::get_duplex_mode(cell_cfg.band.value());
if (dplx_mode == duplex_mode::TDD and not cell_cfg.tdd_ul_dl_cfg.has_value()) {
  // 기본 패턴 DDDDDDXUUU 생성
```

따라서 **`tdd_ul_dl_cfg` 섹션이 없다고 FDD는 아니다.** TDD 밴드면 OCUDU가 기본 TDD 패턴을 자동으로 만든다. 판정은 `band`(없으면 `dl_arfcn`)로 한다.

### 2.2 공식 예제 두 개 비교 ✅

| | `configs/gnb_rf_b210_fdd_srsUE.yml` | `configs/gnb_rf_b200_tdd_n78_20mhz.yml` |
|---|---|---|
| 파일 주석 | "single FDD cell transmitting in band 3 … intended to be used with srsUE" | "single TDD cell transmitting in band 78" |
| `band` | 3 | 78 |
| `dl_arfcn` | 368500 | 632628 |
| `common_scs` | 15 | 30 |
| `channel_bandwidth_MHz` | 20 | 20 |
| `ru_sdr.device_driver` | `uhd` (`type=b200`) | `uhd` (`type=b200`) |
| 그 밖 | srsUE 능력에 맞춘 `pdcch` 설정, 외부 클럭 | CFO 보정 `expert_phy` |

DU 단독 예제 `configs/du_rf_b200_tdd_n78_20mhz.yml`은 `f1ap:` 섹션을 갖는다. 팀 설정에 `gnb.yml` 하나가 아니라 `cu.yml`/`du.yml`이 따로 있고 DU 쪽에 `f1ap.addrs`가 있으면 CU/DU 분리 배치다 ✅(예제 구조 기준).

### 2.3 B210은 TDD/FDD를 정하지 않는다 ✅

OCUDU는 같은 B200 계열 USRP로 FDD 예제와 TDD 예제를 모두 제공한다(§2.2). 이전 주제 보고서(2026-09-10)에 "USRP B210 사용 예정"이라는 문장이 있지만, 그 사실만으로는 베이스 UE가 정해지지 않는다. 현재 EC2 실습 환경은 SDR이 아닌 ZMQ를 쓴다(§1).

## 3. 베이스 UE 결정

**결정: OAI UE.** DU 박스 골든 이미지에 이미 있는 `nr-uesoftmodem`을 출발점으로 A형을 다시 구현한다.

| 근거 | 내용 | 표시 |
|---|---|---|
| 셀이 TDD | 팀 셀은 n78 TDD·30 kHz. srsUE는 15 kHz·FDD 전용이므로 이 셀에 쓸 수 없다 | ✅ (셀) / 📄 (srsUE 제약, [tool-survey.md](tool-survey.md)) |
| 공식 경로와 일치 | OCUDU 공식 OAI UE 튜토리얼도 n78 TDD·30 kHz·20 MHz·ZMQ다 | 📄 |
| interop 이미 통과 | 팀 박스의 OAI UE가 분리 CU/DU + ZMQ 구성에서 Open5GS 등록까지 성공했다 | ✅ (PDF §3 서술) |

적용했던 규칙(참고):

| 팀 셀 | 베이스 UE 후보 |
|---|---|
| TDD (예: n78) ← **해당** | 최신 OAI UE (`2026.w25` 이상) |
| FDD (예: n3, 15 kHz, ≤20 MHz) | srsUE와 최신 OAI UE 모두 후보 |

### 남은 확인

1. ~~**OAI UE 버전**~~ → **해결**: `2026.w38` ✅ (§1.1). 공식 하한 `2026.w25`를 넘고, 5gattacks 기준보다 약 10개월 뒤다.
2. **차폐 OTA**: 이 결정은 EC2 ZMQ 환경 기준이다. RF 차폐 박스에서 SDR로 돌릴 때의 접속은 따로 확인해야 한다.
3. **A형 효과**: OCUDU 26.10에서 A형이 미완료 컨텍스트를 실제로 쌓는지는 여전히 실험 전이다 🔍.

---

## 4. UE 실행 방식 (DU 박스) ✅

출처: DU 박스 `/root/workspace/ctl.sh` (2026-10-16 판독). 가입자 값(IMSI·키·OPc·DNN)은 `/root/oai_nrue.conf`에 있고 **이 리포에 적지 않는다**.

### 4.1 실행 인자

```
nr-uesoftmodem -O /root/oai_nrue.conf \
  --band 78 -C 3489420000 --numerology 1 -r 51 -E --ue-scan-carrier \
  --uecap_file /root/OAI/targets/PROJECTS/GENERIC-NR-5GC/CONF/uecap_ports1.xml \
  --device.name oai_zmqdevif \
  '--zmq.[0].tx_channels' tcp://127.0.0.1:4557 \
  '--zmq.[0].rx_channels' tcp://127.0.0.1:4556
```

| 인자 | 뜻 | 셀 설정과의 대응 |
|---|---|---|
| `--band 78` | n78 | §1 `band: 78` ✅ |
| `-C 3489420000` | 중심주파수 3489.42 MHz | `dl_arfcn` 632628 → 3489.42 MHz ✅ |
| `--numerology 1` | μ=1 = SCS 30 kHz | §1 `common_scs: 30` ✅ |
| `-r 51` | 51 PRB | 20 MHz / 30 kHz = 51 PRB ✅ |
| `-E` | 3/4 샘플링 레이트 | ZMQ 부하 절감용 🔍 |
| `--device.name oai_zmqdevif` + `--zmq.[0].*` | ZMQ 가상 RF, UE tx 4557 / rx 4556 | DU의 ZMQ 포트와 교차 연결 ✅ |

UE와 odu가 **같은 박스**에서 `127.0.0.1`로 샘플을 주고받는다. 즉 RF는 전혀 없고 ZMQ 소켓 한 쌍이 공중 구간 전부다.

### 4.2 기동 절차에서 드러난 제약 ✅

`ctl.sh`의 `ue_up()`이 알려 주는 두 가지는 A형 재현기 설계에 직접 걸린다.

1. **UE만 재시작할 수 없다.** 주석: "UE만 재시작하면 odu 와 샘플스트림이 어긋나 `Intializing UE Threads`에서 멈춤." → 그래서 `ue` 명령은 **항상 odu+UE를 동반 재기동**한다.
   → B형(UE 재시작 반복) 시나리오는 이 환경에서 **odu까지 재기동되므로 그대로 쓸 수 없다**. A형(한 프로세스 안에서 반복)을 먼저 하는 선택이 환경 측면에서도 맞다.
2. **ZMQ에서 `RRCSetupComplete`가 가끔 유실된다.** 주석: "2026-10-14 시험 24회 중 2회 UE 의 RRCSetupComplete 가 유실돼 CU 가 **2초 뒤** UE 를 해제한다."
   → 이것은 §5의 `t300 + guard = 2000 ms`와 **정확히 일치하는 실측 증거**다 ✅. 동시에 **정상 상태에서도 약 8%의 미완료 접속이 발생**한다는 뜻이므로, 탐지팀 지표의 오탐 기준선으로 반드시 알려야 한다.

---

## 5. RRCSetup 완료 대기 시간 — 실측 확정 ✅

### 5.1 계산식 (원본 코드)

```cpp
// /root/OCUDU/lib/rrc/ue/procedures/rrc_setup_procedure.cpp:40
procedure_timeout = context.cell.timers.t300 + context.cfg.rrc_procedure_guard_time_ms;
// :53  transaction = event_mng.transactions.create_transaction(procedure_timeout);
// :62  if (transaction.failure_cause() == protocol_transaction_failure::timeout) {
// :63    logger.log_warning("\"{}\" timed out after {}ms", name(), procedure_timeout.count());
// :65    rrc_ue.on_ue_release_required(cause_protocol_t::unspecified);
```

핸드오프의 📄 계산식이 박스 소스에서 확인됐다 → **✅로 승격**.

### 5.2 로드된 값

| 값 | 설정 파일 | 로드된 값 | 근거 | 표시 |
|---|---|---|---|---|
| `t300` | `du.yaml`에 **없음** (grep 결과 0건) | **1000 ms** | DU 유효 설정 덤프 `/tmp/odu.log`의 `t300: 1000`. SIB1 ASN.1에도 `"t300": "ms1000"` → 실제로 공중에 뿌려지는 값 | ✅ |
| `rrc_procedure_guard_time_ms` | `cu.yaml`에 **없음** (`cu_cp`에 `rrc:` 섹션 자체가 없음) | **1000 ms** | CU 유효 설정 덤프 `/tmp/ocu.log`의 `rrc: { … rrc_procedure_guard_time_ms: 1000 }` | ✅ |
| **합계 = 미완료 UE 수명** | — | **2000 ms** | 위 두 값의 합. §4.2의 "2초 뒤 해제" 관찰과 일치 | ✅ |

주의: OCUDU 소스에는 guard time 기본값이 **두 가지**로 적혀 있다 — `cu_cp_unit_config.h:240`과 `cu_cp_configuration.h:133`은 1000, `rrc_config.h:32`와 `rrc_ue_config.h:27`은 500. 실제 CU 앱 경로에서 적용된 값은 **1000**이다(유효 설정 덤프 기준) ✅. 500은 라이브러리 단독 기본값이다.

`t300`은 CLI에서 `{100, 200, 300, 400, 600, 1000, 1500, 2000}` 중 하나만 받는다(`du_high_config_cli11_schema.cpp:2309`). 즉 **대기 시간은 최소 100+guard까지 줄일 수 있다** — 나중에 대조 실험의 변수로 쓸 수 있지만, gNB 설정 변경이므로 사용자 승인 사항이다.

참고로 `cu.yaml`의 `inactivity_timer: 7200`은 **접속 완료 후** 유휴 UE 해제용이고 A형(완료 전)과 무관하다 ✅.

### 5.3 A형 설계에 주는 숫자

미완료 컨텍스트 하나의 수명이 2초이므로, 동시에 유지되는 미완료 UE 수는 대략 **시도율 × 2초**다 🔍(상한·용량 제한이 먼저 걸릴 수 있으므로 실측 필요). 초당 10회 시도면 동시 약 20개 수준이라는 계산이 나온다.

---

## 6. A형 이식 지점 — 5gattacks 패치 ↔ 박스 OAI 트리 1:1 대응 ✅

`sources/5gattacks_storm-attack.patch`(13개 hunk)를 박스의 `/root/OAI`(2026.w38)와 대조했다. **코드 읽기만 했고 아무것도 수정하지 않았다.**

### 6.1 UE 측 (우리가 참고할 부분)

| # | 패치 위치 | 패치가 하는 일 | 박스 트리 대응 위치 | 성격 |
|---|---|---|---|---|
| U1 | `openair2/RRC/NR_UE/rrc_UE.c` `nr_rrc_ue_decode_ccch()` → `case …c1_PR_rrcSetup` (패치 기준 1996행) | `RRCSetup` 수신 시 원래의 `nr_rrc_process_rrcsetup()` 호출을 **하지 않고**, `T300`을 멈추고 자체 타이머를 건다 | **`rrc_UE.c:2465–2467`** (`case NR_DL_CCCH_MessageType__c1_PR_rrcSetup:` → `nr_rrc_process_rrcsetup(…)`) | **A형의 핵심 분기점.** `nr_rrc_process_rrcsetup()`이 `rrc_ue_generate_RRCSetupComplete()`(`:2243`, 호출은 `:2393`)를 부르므로, 이 호출 여부가 "Msg5를 보내는가"를 가른다 |
| U2 | 같은 파일 `case …c1_PR_rrcReject` (패치 기준 1991행) | `RRCReject`를 정상 처리(`nr_rrc_process_rrcreject`) 대신 **T300 만료와 같게** 취급해 곧바로 재시도 | **`rrc_UE.c:2459–2461`** | gNB가 거절해도 멈추지 않게 만드는 부분. **윤리·통제 관점의 판단 필요** — 재현기를 "통제 가능"하게 두려면 거절을 존중하는 편이 맞을 수 있다 |
| U3 | `rrc_defs.h` `NR_UE_Timers_Constants_t`에 `attack_rach_timer` 필드 추가 | 재시도 간격 타이머 저장소 | **`rrc_defs.h:144`** (`NR_timer_t T300;` 바로 뒤) | 구조체 한 줄 |
| U4 | `rrc_timers_and_constants.c` `nr_rrc_handle_timers()`에 tick/만료 처리 추가 | 타이머 만료 시 `handle_t300_expiry()` 호출 → `RRCSetupRequest` 재생성 → 반복 | **`rrc_timers_and_constants.c:174–175`**(T300 처리 바로 뒤), 만료 핸들러는 **`rrc_UE.c:3778` `handle_t300_expiry()`** | 반복 루프의 몸통 |
| U5 | 같은 파일 `nr_rrc_set_sib1_timers_and_constants()`에 `nr_timer_setup(&tac->attack_rach_timer, 10, 10)` | 재시도 간격 = **10 tick × 10 ms = 100 ms, 빌드 상수** | **`rrc_timers_and_constants.c:446`** (`nr_timer_setup(&tac->T300, k, 10);` 바로 뒤) | **여기가 "런타임 노브가 없다"의 정체다** ✅. 우리 재현기는 이 값을 설정/인자로 뺀다 |
| U6 | 같은 파일 T302 만료 시 `handle_302_expired_stopped(rrc)` **주석 처리** | access barring 해제 처리를 막는다 | **`rrc_timers_and_constants.c:188–193`** | 부수 효과가 큰 변경. 이식 여부는 별도 판단 |
| U7 | `nr_ra_procedures.c` `nr_Msg3_transmitted()`에 `Msg3_buffer` 해제 추가 | 반복 RA에서 Msg3 버퍼 누수 방지 | **`nr_ra_procedures.c:966`** — 단 시그니처가 다르고(`(NR_UE_MAC_INST_t *mac)` vs 패치의 `(mac, CC_id, frameP, slot)`), 박스 트리에는 이미 `free_and_zero(ra->Msg3_buffer)`가 `:779, :1078, :1099`에 있다 | **아마 상류에 이미 반영됨** 🔍. 이식 전 확인 필요 |
| U8 | `nr_ue_scheduler.c` `nr_ue_pucch_scheduler()`에 `LOG_W` 한 줄 | 디버그 로그 | `nr_ue_scheduler.c` 내 동일 함수 | 측정용. 선택 |

핵심은 **U1 + U3 + U4 + U5 = 4곳**이다. "RRCSetup을 받고도 RRCSetupComplete를 만들지 않고, 일정 간격으로 RRCSetupRequest를 다시 낸다"가 전부다.

### 6.2 gNB 측 (이식하지 않음 — 팀 방침)

| # | 패치 위치 | 패치가 하는 일 | 왜 제외하는가 |
|---|---|---|---|
| G1 | `gNB_scheduler_primitives.c` `UL_FAILURE_REQ_GRACE` 10000→**1000**, `UL_FAILURE_TIMEOUT` 30000→**5000** | **gNB의 UL failure 타이머를 1/10 ~ 1/6로 단축** | **핸드오프가 지적한 "UE와 분리해야 하는 지점"이 바로 이것이다** ✅. 기지국 무수정 방침 위반이고, 우리 gNB는 OCUDU라 이 매크로가 아예 없다. OCUDU의 해당 역할은 §5의 `t300+guard=2000 ms`가 맡는다. 저자가 왜 줄였는지는 패치만으로 알 수 없다 🔍 |
| G2 | `openair1/SCHED_NR/nr_prach_procedures.c` | PRACH 수신 로그에 `time_us` 추가 | 측정용 gNB 로그. OCUDU엔 해당 코드 없음 |
| G3 | `gNB_scheduler_primitives.c` `prepare_initial_ul_rrc_message()` | UID 고갈 시점 로그에 `time_us` 추가, UID 해제 전 로그 | 같음 (단 "UID 고갈"이 A형의 **고갈 지표**라는 힌트는 유용) |
| G4 | `gNB_scheduler_RA.c` | 로그 레벨 `LOG_D→LOG_E`, contention 만료 로그에 `ra_state` 추가 | 로그만 |
| G5 | `gNB_scheduler_ulsch.c` | `prepare_initial_ul_rrc_message` 호출 전 `LOG_W` | 로그만 |
| G6 | `nr_radio_config.c` `get_nb_pucch2_per_slot()` | PUCCH PRB 소요량 로그 추가 | 로그만. `MAX_MOBILES_PER_GNB`가 PUCCH PRB로 상한을 받는다는 점은 §5.3의 "용량 한도" 후보 |
| G7 | `targets/…/gnb.sa.band78.fr1.106PRB.usrpb210.conf` | `physCellId 0→2`, `sdr_addrs = "serial=8002816"` | **저자 랩의 USRP 시리얼**. 우리와 무관 |

**정리: 13개 hunk 중 UE 동작에 실제로 관여하는 것은 U1·U2·U6, 타이머 배선이 U3·U4·U5, 나머지 7개는 gNB 수정 또는 로그다.** 패치 전체를 적용하면 팀 방침(기지국 무수정)을 어기게 되므로, 적용이 아니라 **U1·U3·U4·U5만 다시 구현**하는 것이 맞다.

---

## 7. 정상 접속 기준선 ✅

새로 실행하지 않고, 박스에 이미 남아 있던 CU 로그(`/tmp/ocu.log`, 2026-10-16 07:02:47 UTC의 정상 1회 접속)에서 뽑았다. `cu.yaml`의 `all_level: debug` 덕에 RRC 메시지가 전부 찍혀 있다.

| 시각 (UTC) | 로그 | Δ |
|---|---|---|
| 07:02:47.083796 | `[CU-CP-F1] Rx InitialULRRCMessageTransfer` (DU→CU, Msg3 도착) | 0 |
| 07:02:47.254967 | `[RRC] Rx SRB0 CCCH UL rrcSetupRequest (6 B)` | +171.2 ms 🔍 |
| 07:02:47.254977 | `[RRC] "RRC Setup Procedure" started…` | +0.01 ms |
| 07:02:47.260630 | `[RRC] Tx SRB0 CCCH DL rrcSetup (302 B)` | +5.7 ms |
| 07:02:47.357966 | `[RRC] Rx SRB1 DCCH UL rrcSetupComplete (33 B)` | **+97.3 ms** |
| 07:02:47.358325 | `[NGAP] Tx InitialUEMessage` (코어로 처음 나가는 지점) | +0.4 ms |
| 07:02:47.358667 | `[RRC] "RRC Setup Procedure" finished successfully` | +0.3 ms |

**핵심 숫자**
- 정상 `RRCSetupRequest → RRCSetupComplete` = **약 103 ms** (`.254977 → .357966`)
- 허용 한도 = **2000 ms** (§5) → 정상 접속은 한도의 **약 5%**만 쓴다. A형은 이 103 ms 자리에 2000 ms를 쓰게 만드는 공격이다.
- `InitialUEMessage`가 `rrcSetupComplete` **뒤에** 나간다 ✅ → 핸드오프의 "A형은 코어에 도달하지 않는다"가 이 박스 로그로 확인됐다. 📄였던 항목을 ✅로 승격.
- 첫 줄의 171 ms 간격은 CU-CP의 F1 UE 컨텍스트 생성/CellGroup 처리 구간으로 보이지만 단정하지 않는다 🔍.

### A형 실험 때 볼 로그 (gNB 무수정으로 얻을 수 있는 것)

```
# CU 박스
grep -E '"RRC Setup Procedure" (started|finished|timed out)' /tmp/ocu.log
grep -E 'rrcSetupRequest|rrcSetup \(|rrcSetupComplete' /tmp/ocu.log
```
A형이 통하면 `timed out after 2000ms` + `on_ue_release_required`가 쌓이고, `rrcSetupComplete`는 나타나지 않아야 한다 🔍(실험 전).


---

## 8. M1a 실측 — A형 성립 확인 ✅

실행 2026-10-20 06:12~06:14 KST(로그 UTC 21:12:16~21:13:35), 세트 p5. 산출물은 [tool/runs/A-1019T211216Z/](tool/runs/A-1019T211216Z/)에 있다(`ue.log`의 가입자 값은 마스킹).

| 항목 | 값 |
|---|---|
| UE | OAI `2026.w38` + [tool/oai-patch/rss-ue.patch](tool/oai-patch/rss-ue.patch), 박스 브랜치 `rss-ue-a-type` |
| gNB | OCUDU `e0db566a`(release_26_10) **무수정** |
| 노브 | `interval_ms=100, completion_pct=0, honor_reject=1, ack_gate=1, max_duration_s=30` |

### 8.1 회귀 시험(공격 off) ✅

패치된 바이너리로 `--rss.enable 0`일 때 정상 접속이 그대로 됐다.

| 로그 | 값 |
|---|---|
| `"RRC Setup Procedure" started → finished successfully` | **103.8 ms** (20:50:00.043510 → .147319) |
| `timed out after` | 0 |
| UE | `Generating RRCSetupComplete` → `oaitun_ue1` IPv4 10.45.1.2 |
| `[RSS]` 배너 / JSONL 파일 | 없음 (0건) |

§7의 정상 기준선 ~103 ms와 일치 → **패치가 정상 경로를 바꾸지 않는다**는 것이 실측으로 확인됐다.

### 8.2 A형 실행(30초) — CU 측 ✅

절차 이름까지 묶어 센 값이다(느슨한 `grep 'finished successfully'`는 해제 루틴까지 세어 144가 나온다 — 주의).

| CU 로그 (`/tmp/ocu.log`, 윈도우 21:12:16~21:13:40) | 값 |
|---|---|
| `"RRC Setup Procedure" started` | **72** |
| `"RRC Setup Procedure" timed out after 2000ms` | **72** |
| `"RRC Setup Procedure" finished successfully` | **0** |
| `rrcSetupComplete` | **0** |
| `NGAP … InitialUEMessage` | **0** |
| `"UE Context Release Routine" finished successfully` | 72 |
| `"UE Removal Routine" finished successfully` | 72 |
| 생성된 CU UE 컨텍스트 | `ue=1` ~ `ue=72` (72개) |
| **동시 미완료 피크** | **6** (started/timed out 누적 차의 최대) |

**판정: M1a 합격.** 미완료 절차가 72건 생성 → 전부 2000 ms 뒤 타임아웃 → 해제까지 완결되고, Msg5와 코어 도달은 0이다. §7에서 `InitialUEMessage`가 `rrcSetupComplete` 뒤에 나간다고 확인한 것과 일치한다(A형은 코어에 닿지 않는다).

`rrcSetupRequest`가 144로 보이는 것은 CU가 건당 `Rx SRB0 CCCH UL rrcSetupRequest`와 `Containerized rrcSetupRequest` 두 줄을 쓰기 때문이다. 실제 수신은 72건이다.

### 8.3 A형 실행 — UE 측 JSONL ✅

| 이벤트 | 값 |
|---|---|
| `attempt_start` | 143 |
| `msg4_rx` (전부 `actual_reach=msg5_skip`) | 85 |
| `retrigger` | 71 |
| `rrc_reject` | 0 |
| `ack_pending_postpone` | 0 |
| `kill_switch` | 1 (30초에 정상 발동) |
| 관측 구간 | 30.21 s |
| 고유 `ue_identity` | **143 / 143** (매 시도 새 randomValue) |

### 8.4 설정값 vs 실측 — 설계 §5 "관측 분리 원칙"의 실제 사례 ✅

| 지표 | 설정 | 실측 |
|---|---|---|
| 재시도 간격 | 100 ms | **Msg4→재시도 중앙값 306.5 ms** (최소 198.7 / 최대 367.3) |
| 시도율 R | — | 4.73 시도/s (UE), CU 수신 기준 2.4 Msg3/s |
| Msg4 도달률 | — | 2.81/s |

설정 100 ms인데 실측 306 ms인 이유는 미확인 🔍. OAI UE의 RRC 타이머는 새 무선 프레임(10 ms)마다 틱하므로, ZMQ 가상 RF에서 프레임 처리가 실시간보다 느리면 틱 간격이 늘어난다는 가설이 유력하다(M2에서 `interval_ms` 스윕으로 확인). **설계가 예고한 "설정 간격 ≠ 실제 Msg3/s"가 실측으로 확인됐다.**

### 8.5 고갈 공식 검증 ✅

[rss-theory.md](rss-theory.md) §6의 `N ≈ R × T_hold`:

- 실측 Msg4 도달률 2.81/s × 보유 시간 2.0 s = **5.6**
- 실측 동시 미완료 피크 = **6**

공식이 이 환경에서 맞는다. 동시 6개는 DU 상한 추정치(~96)에 훨씬 못 미치므로 **포화는 일어나지 않았다** — 설계 §9가 M1a에서 예상한 그대로이고, 합격 조건이 아니다. KAUST의 단일 UE 25 요청/s와 비교하면 우리 ZMQ 경로는 약 1/9 속도다.

### 8.6 남은 확인 🔍

1. **UE `msg4_rx` 85 vs CU `Tx rrcSetup` 72** — 13건 차이의 원인 미확인. UE가 같은 Msg4를 중복 디코드했을 가능성과 로그 윈도우 경계 효과를 M2에서 분리한다.
2. **UE 시도 143 vs CU 수신 72** — 시도 절반가량이 Msg3 이전(RAR 미수신·경합 실패)에서 끝났다. 원인 미측정.
3. `ack_pending_postpone` 0건 — 재시도가 306 ms로 느려 ACK PUCCH가 항상 먼저 나갔다는 뜻이다. `interval_ms`를 낮추면 이 게이트가 실제로 작동하는지 M2에서 확인한다.
4. 포화(M1b)는 다중 UE 브로커 또는 설정 프로필 변경이 필요하다.


---

## 9. M2·M1b 실측 — 속도 제어 교정과 실제 거절(denial) ✅

실행 2026-10-20 06:53~07:10 KST(로그 UTC 21:53~22:10), 세트 p5. 산출물 [tool/runs/](tool/runs/).
UE는 `rss-ue.patch` v4(벽시계 데드라인 + 폐루프 점유 제어). **OCUDU 소스는 끝까지 무수정이다.**

### 9.1 306 ms 수수께끼의 원인 — RRC 틱이 10 ms가 아니다 ✅

패치에 틱 계측(`tick_rate` 이벤트)을 넣어 측정했다.

| 설정 interval | 시도율 | Msg4 도달률 | **실측 ms/tick** |
|---|---|---|---|
| 0 ms | 7.20/s | 3.66/s | 33.1 |
| 20 ms | 6.74/s | 3.79/s | 24.8 |
| 50 ms | 5.60/s | 3.83/s | 34.0 |
| 100 ms | 4.05/s | 2.60/s | 21.9 |

`nr_rrc_handle_timers()`는 새 무선 프레임 메시지마다 호출되고 `nr_timer_tick()`은 호출마다 고정 10 ms를 더한다. 그런데 ZMQ 경로에서 프레임 메시지는 **22~34 ms 간격**으로 온다. 따라서 **틱을 세는 방식은 노브 전체에 2~3배 오차를 곱한다** — §8.4의 100 ms → 306 ms가 정확히 이것이다 ✅.

**수정**: 목표를 틱 수가 아니라 `rss_deadline_ns`(벽시계)로 잡고 타이머는 틱마다 폴링만 하게 했다. 오차가 누적되지 않고 **한 틱 이내로 묶인다**.

### 9.2 남은 천장: Msg4 도달률 ≈ 3.8/s 🔍

간격을 0으로 내려도 Msg4 도달률은 3.8/s에서 더 오르지 않는다(위 표). 즉 교정 후 병목은 재현기 타이머가 아니라 **RA 주기 + 27 ms 틱 해상도**다. 시도의 절반 이상이 Msg4 전에 끝난다(`no_msg4`). 원인 분리는 미완 🔍.

### 9.3 셀 용량 실측 — 기본 96, 거절용 64 예약 ✅

DU 기동 CONFIG 로그(원문 [tool/runs/du_capacity.txt](tool/runs/du_capacity.txt)):

> upper-bound ... is **96** ... lowest of: SR (96), CSI (96), SRS (n/a), UE contexts per cell (1984). Up to **160** UE contexts can be created, **the extra ones being used to RRC Reject UEs**.

팀 문서의 "~96" 추정이 맞았다 ✅. 기본 설정에서 포화에 필요한 요청률은 `96 / 2 s = 48 Msg4/s`이고, 측정 천장 3.8/s의 **약 13배**다 → **단일 UE로는 기본 설정 포화 불가**가 수치로 확정됐다.

### 9.4 포화 프로필 (gNB **설정만**, 소스 무수정) ✅

[tool/box/gnb_profile.sh](tool/box/gnb_profile.sh)가 백업(`.orig`)을 두고 멱등하게 적용/복원한다. 움직인 항목은 운영자가 설정으로 통제하는 두 항목뿐이다.

| 항목 | 기본 | 프로필 | 효과 |
|---|---|---|---|
| `cell_cfg.pucch.nof_cell_sr_res` | 8 | **1** | N_cap 96 → **12** (SR 12, CSI 96 중 최솟값) ✅ |
| `cell_cfg.sib.t300` (DU) | 1000 | **2000** | T_hold ↑ (3GPP 최댓값) |
| `cu_cp.rrc.rrc_procedure_guard_time_ms` (CU) | 1000 | **5000** | T_hold = **7000 ms** ✅ (실측 `timed out after 7000ms`) |

### 9.5 실제 거절 발생 — run `SAT2-1019T220308Z` ✅

60초, interval 20 ms, `completion_pct 0`. CU 로그 윈도우 22:03:08~22:04:52.

| 지표 | 값 |
|---|---|
| `"RRC Setup Procedure" started` / `timed out after 7000ms` | 93 / **93** |
| **동시 미완료 피크** | **12** = N_cap |
| **`Sending rrcReject`** | **126** |
| 거절 사유 (CU 원문) | **`Cause: DU is not able to serve the UE`** |
| `rrcSetupComplete` / NGAP `InitialUEMessage` | 0 / 0 |
| UE 측 | 거절 15.6%, `no_msg4` 65.4%, 첫 거절 t+1.6 s → t+57.7 s 지속 |

**판정: 실제 서비스 거절 성립.** 셀 용량이 가득 차서 gNB가 새 RRC 연결을 거부한다. 이 거절은 공격 UE를 식별해서 내리는 것이 아니므로 **같은 Msg3를 보내는 정상 UE도 동일하게 거절된다**. 단 이는 **위 프로필에서의 결과**이고 기본 설정 결과가 아니다 — per-run `gnb_config_profile`로 반드시 구분해 보고한다.

### 9.6 포화도 정밀 제어 — 폐루프 점유 제어 ✅

간격 노브로는 포화도를 못 맞춘다(9.2). 대신 **UE가 자기 점유를 직접 센다**: 미완료로 남긴 시도의 타임스탬프를 `hold_ms` 창에서 세어 목표 이상이면 다음 RA를 멈춘다(`--rss.target_occupancy`, `--rss.hold_ms`).

| 목표 점유 | **CU 실측 동시 점유** | 타임아웃 | RRCReject | UE 자체추정 최대 |
|---|---|---|---|---|
| 3 | **3** | 15 | 0 | 5 |
| 6 | **6** | 27 | 0 | 8 |
| 12 (=N_cap) | **12** | 48 | 3 | 12 |

**gNB 실측값이 목표와 정확히 일치한다** ✅. UE 자체추정이 조금 높게 나오는 것은 UE가 Msg4 수신 시각부터 세는데 gNB의 보유 시간은 그보다 앞선 절차 시작부터 흐르기 때문이다(코드 판독, 보정 안 함). 판정에는 CU 값을 쓴다.

### 9.7 되돌린 변경: probe 자동해제 경로 ❌

`completion_pct > 0`으로 완료한 시도를 1초 뒤 `nr_rrc_going_to_IDLE()`로 해제해 루프를 잇는 기능을 넣었다가, 첫 실행에서 **UE가 SIGSEGV로 죽었다**(run `SAT-1019T220108Z`: `msg5_sent` → `probe_release` → 다음 시도가 `ng-5G-S-TMSI-Part1` → 코어 덤프). 해당 경로를 패치에서 제거했다.

**대체**: 거절 측정에 probe가 필요 없다. 용량이 차면 gNB가 평범한 `RRCSetupRequest`에 RRCReject를 보내고(9.5), 그것이 곧 정상 UE가 받을 응답이다. `completion_pct > 0`은 현재 **첫 완료에서 런이 멈춘다**(RRC_CONNECTED에서 새 요청이 안 나감)고 README에 명시했다.

### 9.8 남은 확인 🔍

1. 기본 설정(N_cap 96) 포화에는 48 Msg4/s가 필요 → 다중 공격 UE가 필수다. OAI w38은 **UE 1개 = RU(ZMQ 포트쌍) 1개**로 묶여 있어(`"skip cells that are already used by an UE"`) 한 프로세스 다중 UE로는 안 되고 **ZMQ 브로커**가 필요하다(M1b-i).
2. UE측 천장 3.8/s의 분해(RA 주기 vs 27 ms 틱 해상도). MAC 레벨에서 재시작을 걸면 틱 제약이 사라질 가능성 🔍.
3. `ack_pending_postpone` 0건 유지 — 틱이 27 ms라 ACK PUCCH가 항상 먼저 나간다. 틱 제약이 풀리면 이 게이트가 실제로 필요해진다.
4. 정상 UE를 동시에 붙여 피해를 **직접** 재는 것은 ZMQ 1:1 제약 때문에 여전히 브로커 대기다.


---

## 10. KAUST 논문의 실제 조건 — 우리 결과와의 비교 ✅

출처: [sources/2608.16441](sources/) 원문 §VI-A. 2026-10-20 `pdftotext`로 원문 대조.

### 10.1 논문이 밝힌 조건 (직접 인용)

> "In our experiments, the maximum number of supported UEs was configured in OAI. ... In our testbed, the highest value that could be used reliably was **90 UEs**. **The waiting time for incomplete connections was configured to 5 seconds.**"

> "We first evaluated the attack using the **default OAI limit of 16 UEs**. After starting the malicious OAI UE, the number of half-open RRC connections increased quickly until the gNB reached its maximum capacity after approximately **0.65 seconds**. At that point, the gNB logs showed that no more UE contexts could be allocated, and **new connection attempts were rejected using RRCReject messages**."

> "We repeated the same experiment with the gNB configured to support **90 UEs** ... reached its maximum configured capacity after approximately **3.61 seconds**."

> "the attacker generates incomplete connection attempts at an average rate of approximately **25 requests per second** ... with a waiting time of 5 seconds, the attacker would occupy around **125 contexts**"

> "During the attack, however, **the phone failed to connect** even after multiple attempts ... This confirms that the attack creates a denial of service (DoS) on commercial phones."

**핵심: 논문도 보유 시간(5 s)과 UE 용량(16 / 90)을 설정해서 실험했다.** 5초는 OAI 기본값이 아니라 **설정값**이다. 즉 "단일 UE로 아무 설정도 바꾸지 않고 마비시켰다"는 주장은 논문에 없다.

### 10.2 작업점(working point) 비교 — 왜 우리는 기본 설정에서 안 됐는가

고갈 조건은 `R × T_hold ≥ N_cap`이다(§9.3). 필요 요청률 `R_req = N_cap / T_hold`로 환산하면:

| 환경 | N_cap | T_hold | **필요 R** | 달성 R | 결과 |
|---|---|---|---|---|---|
| KAUST, OAI 기본 용량 | **16** | 5 s (설정) | **3.2/s** | 25/s | 0.65 s에 포화 ✅ |
| KAUST, 용량 90 설정 | 90 | 5 s (설정) | 18/s | 25/s | 3.61 s에 포화 ✅ |
| **우리 OCUDU 기본** | **96** | **2 s** | **48/s** | 3.8/s | 포화 안 됨 ❌ (§8·§9.2) |
| **우리 포화 프로필** | 12 | 7 s | **1.7/s** | 3.8/s | 포화 ✅ (§9.5) |

**결론 세 가지.**
1. 우리 기본 설정이 KAUST 기본 조건보다 **15배 어렵다** (48/s vs 3.2/s). 용량이 6배 크고(96 vs 16) 보유 시간이 2.5배 짧다(2 s vs 5 s).
2. 우리 포화 프로필(필요 1.7/s)은 KAUST의 기본 OAI 조건(필요 3.2/s)보다 오히려 **덜 공격적인 작업점**이다. 즉 프로필 실행은 "임의로 약화시킨 표적"이 아니라 **공개 논문이 성공을 보고한 조건과 같은 범위**다. 단 이 비교는 필요 요청률 기준이며, 프로필이 기본 설정이 아니라는 사실은 그대로 보고한다.
3. 우리의 미달은 **공격 기법의 문제가 아니라 요청률(3.8/s)의 문제**다. KAUST의 25/s와 6.6배 차이다.

### 10.3 "UE 컨텍스트 해제 타이머"는 표준이 아니다 ✅

> "The prior work assumes that after sending Msg4, the gNB keeps the UE context for a waiting time while expecting Msg5. However, **the 3GPP specifications do not define a dedicated timer for this exact waiting period.** Therefore, in this paper, we treat this timer as an **implementation-dependent** behavior because, in practice, a gNB still needs some cleanup logic for incomplete connections."

따라서 "상용 기지국의 표준 값"은 존재하지 않는다. 확인 가능한 것만 정리하면:

| 값 | 성격 | 근거 |
|---|---|---|
| UE측 `T300` 100~2000 ms | **표준.** SIB1으로 방송, 허용값 8개 | 38.331 §6.3.2 / OCUDU CLI `--t300` enum ✅ |
| gNB측 해제 대기 | **표준 없음.** 구현 의존 | KAUST §II 인용 위 ✅ |
| OCUDU 26.10 = `t300` + `rrc_procedure_guard_time_ms` = 1000 + 1000 = **2000 ms** | 오픈소스 기본값(설치본 실측) | §5 ✅ |
| KAUST 실험 = **5000 ms** | 설정값(기본값 아님) | §10.1 ✅ |
| 상용 벤더 값 | **미공개 / 미확인** 🔍 | — |

**방어 논리로 쓸 수 있는 하한**: 단말은 `T300` 만료 전까지 Msg5를 보낼 권리가 있으므로, 표준을 지키는 gNB는 **자신이 방송한 `T300`만큼은 컨텍스트를 유지해야 한다**. 즉 운영자가 커버리지 때문에 `T300`을 2000 ms로 방송하면 공격자의 보유 시간도 최소 2000 ms가 된다. 상용 환경의 실제 위험은 보유 시간보다 **용량(수백~수천 UE/셀)** 쪽이 지배적이므로, 상용 셀에서 이 공격은 단일 UE가 아니라 **다수 단말(봇넷) 규모**의 공격으로 봐야 한다 🔍(추론).

### 10.4 이 비교가 다음 작업에 주는 것

우리 요청률 3.8/s의 내역(§9 실측): 성공 주기 = RA 88.4 ms + 재시작 35.5 ms, 그런데 **시도의 52~65%가 Msg4 전에 죽는다**. 낭비를 제거하면 `1000/88.4 ≈ 11.3/s`가 단일 MAC의 구조적 천장이다(한 MAC = 동시 RA 1개, 38.321 §5.1.1).

- 11.3/s를 달성하면 동시 점유는 2 s × 11.3 ≈ **22.6** → **KAUST 기본 조건(용량 16)은 설정 변경 없이 포화 가능**.
- 우리 기본 설정(96) 포화에 필요한 공격 UE 수는 `96 / 22.6 ≈ 4.2` → **5대**(현재 3.8/s 기준으로는 13대). 즉 **요청률 개선이 브로커 규모를 1/3로 줄인다** → M1b 전에 M2b(요청률 천장 분해)를 먼저 하는 것이 맞다.


---

## 11. M2b 요청률 천장 분해 — 가설 하나 반증, 진짜 병목 특정 🔶

실행 2026-10-20 07:35~07:44 KST(로그 UTC 22:35~22:44), 세트 p5.
**gNB 설정은 기본값 그대로**(t300 1000 + guard 1000 = 2000 ms, 상한 96). 사용자 지시에 따라 5000 ms는 쓰지 않았다.

### 11.1 반증된 가설: "RA 진행 중 재시작이 공격을 망친다" ❌

`nr_mac_start_ra(NR_MAC_RA_START_T300)`가 조건 없이 `reset_ra()`(= `memset(ra, 0, …)`)를 호출하므로,
우리 재시작이 진행 중 RA를 지운다고 의심했다. `--rss.ra_gate` 노브(RA 진행 중이면 재시작 보류, 500 ms 후 강제)를
넣어 같은 조건에서 A/B를 돌렸다.

| `ra_gate` | 시도 | Msg4 | 낭비율 | Msg4/s | **`gate_hold`** | RA 주기 | 재시작 지연 |
|---|---|---|---|---|---|---|---|
| 0 (기존) | 403 | 202 | 49.9% | 4.46 | **0** | 111.5 ms | 21.5 ms |
| 1 (게이트) | 401 | 203 | 49.4% | 4.00 | **0** | 111.8 ms | 21.4 ms |

**게이트가 한 번도 걸리지 않았다.** 즉 재시작 시점의 `ra_state`는 항상 대기 상태가 아니었고,
가설은 틀렸다. 노브는 안전장치로 남겨 두되(기본 1, 비용 0) **성능 개선 효과는 없다**고 기록한다.

### 11.2 "낭비 50%"는 성능 문제가 아니라 계측 아티팩트다 🔍

시도:Msg4 비율이 세 런에서 거의 정확히 2:1이다 — 403:202, 401:203, 143:72(§8.3).
`nr_rrc_ue_ue_prepare_RRCSetupRequest()`의 호출 지점이 우리 `handle_t300_expiry` 외에 2곳 더 있어서
(`rrc_UE.c:2125`, `:3451`) **실제 RA 1회당 `attempt_start`가 2번 기록**되는 것으로 보인다.
실패 시도의 비용 중앙값이 10.4 ms(p10 0.8 ms)로 RA 한 주기에 전혀 못 미치는 것도 같은 방향이다.

→ **따라서 "되찾을 50%"는 없다.** 실제 시도율은 Msg4 수로 보는 것이 맞다. 계측을 고쳐야 할 대상은
재현기 성능이 아니라 라벨이다(아래 11.5). 이 사실을 모른 채 §9.2를 읽으면 존재하지 않는 낭비를 쫓게 된다.

### 11.3 진짜 병목: UE가 실시간으로 못 돈다 ✅

| 지표 | 실측 | 정상/비교 |
|---|---|---|
| **`ms_per_tick`** | **26.4 ~ 36.0 ms** | 무선 프레임 = **10 ms** |
| RA 주기(시도→Msg4) | **111.5 ms** | KAUST 보고 **40 ms**/요청 |
| 재시작 지연(Msg4→재시작) | 21.5 ms | ≈ 1 틱 |
| 사이클 예산 | 111.5 + 21.5 = **133 ms → 7.5/s** | 실측 4.0~4.5/s |
| odu CPU | 170~190% | 박스 8 vCPU(=800%) |

틱이 10 ms가 아니라 26~36 ms라는 것은 **UE의 프레임 처리가 실시간의 1/3 수준**이라는 뜻이다.
ZMQ는 샘플 동기 방식이라 UE가 느리면 공중 구간 전체가 느려지는데, **gNB의 보유 타이머는 벽시계로 흐른다.**
즉 UE가 느린 만큼 "보유 2초 동안 넣을 수 있는 시도 수"가 그대로 깎인다. KAUST와의 6.6배 차이는
공격 로직 차이가 아니라 **이 실시간성 차이**로 대부분 설명된다(추론, 11.5에서 검증).

odu가 1.7~1.9코어만 쓰므로 박스 전체가 포화된 것은 아니다 → 단순 CPU 부족이 아니라
**UE 쪽 스레드/actor 배치 또는 ZMQ 흐름 제어** 문제로 보인다 🔍. UE 정상 상태 CPU는 측정 실패(11.4).

### 11.4 측정 실패와 원인 (재시도용 메모) ❌

1. `cpu_probe.sh` 1차: `run_attack.sh`가 odu를 먼저 재기동하는데 프로브가 그 사이에 `pgrep`을 해서
   `ODU=none`을 잡았고, UE는 초기화 중(스레드 2개, 25% CPU)을 샘플링했다 → 무효.
2. 2차: JSONL 생성까지 기다리게 고쳤으나 90초 안에 공격이 기동하지 않았다. odu·UE 모두 부재.
   패널 README가 경고한 **"E2 미완료 DU가 끊기면 FlexRIC가 죽는다"**에 해당할 가능성이 높다 🔍 —
   이 세션에서 odu를 10회 이상 재기동했다.
3. 교훈: **측정 스크립트는 `run_attack.sh`와 같은 프로세스에서 odu를 만지지 말 것.** odu 기동은
   `ctl.sh up`으로 분리하고, 프로브는 이미 돌고 있는 공격에만 붙는다.

### 11.5 다음 작업 (순서 고정)

1. **라벨 수정 먼저** — `attempt_start`를 실제 RA 시작에만 기록한다(또는 `ra_started` 이벤트 분리).
   그래야 §9·§11의 "낭비율"이 의미를 갖는다. 코드 변경 1~2줄.
2. **UE 실시간성 확보** — `--num-ul-actors`/`--num-dl-actors`/`--actor-affinity`로 UE 스레드를 odu와
   분리된 코어에 고정하고 `ms_per_tick`을 10 ms에 접근시킨다. 목표: 틱 26~36 → 10~12 ms.
   이것이 성공하면 사이클 예산 133 → 50~60 ms, 즉 **16~20 Msg4/s**가 되고 동시 점유는
   2 s × 18 ≈ 36(상한 96의 37%)까지 올라간다.
3. 그래도 96에 못 닿으면 **공격 UE 수**가 유일하게 남는 변수다: `96 / (2 s × R)`.
   R=18/s면 **3대**, R=4.5/s면 11대. (§10.4의 5대 추정은 R=11.3/s 가정이었다.)
4. 5000 ms(KAUST 값)는 2·3번을 모두 소진한 뒤에만 쓴다 — 사용자 지시.


---

## 12. 판정 — 기본 설정(2000 ms, 상한 96)에서 단일 UE는 **실패** ❌

실행 2026-10-20 08:06~08:17 KST. **gNB 설정 무변경**(`timed out after 2000ms`로 확인). run `VERDICT`.

### 12.1 최적화 스윕 — 효과 없음

30초씩 5변형, 전부 기본 gNB 설정.

| 변형 | Msg4/s | tick | RA 주기 | 동시점유@2s |
|---|---|---|---|---|
| baseline | 3.90 | 41.3 ms | 123.0 ms | 7.8 |
| 로그레벨 error | 4.04 | 38.7 ms | 122.9 ms | 8.1 |
| 코어 고정(odu 0-2 / UE 3-7) | 3.86 | 38.4 ms | 124.4 ms | 7.7 |
| 로그+고정 | 3.72 | **26.5 ms** | 114.7 ms | 7.4 |
| 로그+고정+actor 0 | 3.79 | 28.7 ms | 114.9 ms | 7.6 |

틱은 41 → 26.5 ms로 **36% 개선됐는데 Msg4율은 전혀 오르지 않았다.** → 병목은 UE의 CPU·로깅·스레드 배치가 **아니다**.

### 12.2 라벨 버그 수정 확인 ✅

`nr_rrc_prepare_msg3_payload()`가 `nr_rrc_ue_prepare_RRCSetupRequest()`를 "in advance"로 한 번 더 부르는 것이
§11.2의 2:1 정체였다. 실제 공중 전송분은 이쪽이므로 **`attempt_start`를 이 경로로 옮기고** 다른 경로는
`setup_req_prebuilt`로 분리했다. 결과: attempts 182 / prebuilt 181 / msg4 184 → **1:1:1**.
→ "낭비 50%"는 존재하지 않았고, **탐지팀 정답지의 `ue_identity`도 이제 실제 전송값**이다(이전에는 절반이 폐기된 값이었다).

### 12.3 진짜 한계: 공중 시간이 벽시계보다 훨씬 느리다 ✅

MAC 프레임 번호로 본 RA 한 주기(RAR→RAR): **3~4 프레임 = 30~40 ms (공중 시간)**.
같은 주기를 벽시계로 재면 **217~256 ms**(3.9~4.6 Msg4/s).

> 즉 이 ZMQ 테스트베드의 공중 구간은 **실시간의 약 1/6 속도**로 흐른다.
> 그런데 **gNB의 보유 타이머(2000 ms)는 벽시계로 흐른다.** 공격자는 공중 시간 기준으로는
> 초당 25~33회라는 KAUST급 속도를 내고 있지만, 벽시계 2초 동안에는 그 1/6만 밀어 넣을 수 있다.

KAUST와의 6.6배 차이는 공격 로직이 아니라 **대부분 이 시간 스케일 차이**다.

### 12.4 최종 판정 런 ❌

60초, 기본 gNB 설정, 최적 UE 설정(코어 고정), `interval 0`.

| CU 지표 | 값 |
|---|---|
| `"RRC Setup Procedure" started` / `timed out` | 377 / **377** |
| 타임아웃 값 | **2000 ms** (기본값 확인) |
| **동시 미완료 피크** | **19** |
| 셀 상한 | **96** |
| **`Sending rrcReject`** | **0** |
| `rrcSetupComplete` | 0 |

**달성률 19/96 = 20%. 거절 0건 → 마비 실패.**

### 12.5 결론과 전환 근거 (숫자 고정)

- 단일 UE 상한은 **동시 19개**다. 이 환경에서 96을 채우려면 `96 / 19 ≈ 5.1` → **최소 6대**(여유 포함).
- 공중 구간이 실시간이었다면 주기 30~40 ms → 25~33회/s → 동시 50~66개. **그래도 96에는 미달**이므로,
  테스트베드가 완벽해져도 단일 UE로는 이 셀을 못 채운다(한 MAC = 동시 RA 1개, 38.321 §5.1.1).
- → **단일 UE 방식의 한계를 인정하고 다중 UE로 전환한다.**

### 12.6 다중 UE 설계 선택 (브로커 ✗ / 인프로세스 ✓)

| 방식 | 장단점 |
|---|---|
| 외부 ZMQ 브로커 | DL 복제 + UL 합산. 프로세스가 하나 늘고 `cf_t` 23.04 MS/s × 8 B ≈ **184 MB/s/방향**이 추가로 복사된다. 이미 1/6로 느린 공중 구간을 **더 느리게** 만들 가능성이 크다 🔍 |
| **인프로세스 다중 UE (선택)** | OAI는 이미 `--num-ues`로 RRC/MAC/PHY 인스턴스를 N개 만든다(`MAX_NUM_NR_UE_INST 32`). 막는 것은 `nr-ue-ru.c`의 **"UE 1개 = RU 1개"** 배정뿐이다. 여기만 고치면 ZMQ 왕복 횟수는 그대로이고 UE만 늘어난다 |

수정 지점(모두 UE 측, gNB 무수정):
1. `nrue_ru_read()` — 지정된 UE 하나가 슬롯 샘플을 읽고 나머지 UE에 **같은 버퍼를 복제**한다.
2. `nrue_ru_write()` — N개 UE의 상향 샘플을 **int16 포화 합산** 후 1회만 장치에 쓴다.
3. `nrue_cells[].used_by_ue` 1:1 배정 완화 + 슬롯 단위 배리어.


---

## 13. 다중 UE 전환 — 구현 완료, 스케일링 한계 확인 🔶

실행 2026-10-20 08:27~08:38 KST. **gNB 설정 기본값**(`timed out after 2000ms`, 상한 96).

### 13.1 구현: 인프로세스 RU 공유 ✅

OAI는 `nr-uesoftmodem.c`에서 명시적으로 거부한다:

> `"Cell %d is already used by UE %d ... as cells map 1:1 to RUs and RU sharing is not implemented"`

패치는 이 1:1 규칙만 푼다(모두 UE 측, gNB 무수정):

| 파일 | 변경 |
|---|---|
| `executables/nr-ue-ru.c` | 슬롯마다 UE 하나가 샘플을 읽고 나머지에 **복제**(`rss_shared_read`), 모든 UE의 상향을 int16 포화 **합산** 후 1회만 장치에 기록(`rss_shared_write`) |
| `executables/nr-uesoftmodem.c` | 공유 모드에서 셀 1:1 배정·`cell_id++` 건너뜀, `nrue_ru_sharing_init()` 호출 |
| `executables/nr-ue-ru.h` | `nrue_ru_sharing_enabled/init` 선언 |

`--num-ues N`(러너는 `-u N`)으로 켜지며 `[RSS] RU sharing enabled: N UE instances on one radio`를 찍는다.
외부 ZMQ 브로커를 쓰지 않은 이유는 §12.6과 같다 — 이미 느린 경로에 184 MB/s/방향을 더 복사하지 않기 위해서다.

### 13.2 구현 중 잡은 버그 2개 ✅

1. **배치 키 없음** — 4대 이상에서 서로 다른 슬롯/형상의 쓰기가 한 배치에 섞여
   `tmp == writeBlockSize`(nr-ue.c RU_write)와 `cc == tx_stream.channels_.size()`(zmq_write)가 터졌다.
   → 배치를 `(timestamp, nsamps, nant)`로 키잉하고, 호출자에게는 **항상 `nsamps`를 반환**하도록 고쳤다
   (장치 쓰기는 집계되므로 호출자 계약은 "네 샘플은 수락됐다"이다).
2. **`deploy.sh`의 리셋 범위** — `openair2/RRC/NR_UE`만 되돌려서, `executables/`를 건드리는 새 패치가
   조용히 적용되지 않았다(`patch does not apply`). `git checkout -- .`로 고쳤다.
   이 사이 3개 런이 **옛 바이너리로 돌아 무효**였다 — 배포 후 `files changed` 줄을 항상 확인할 것.

### 13.3 스케일링 실측 — 뚜렷한 포화 🔶

| 공격 UE 수 | UE 시도(45 s) | **CU 동시 미완료 피크** | 상한 | RRCReject |
|---|---|---|---|---|
| 1 | 377 (60 s) | **19** | 96 | 0 |
| 2 | 497 | **31** | 96 | 0 |
| 4 | 878 | **39** | 96 | 0 |
| 6 | — | **실패(기동 못 함)** | 96 | — |

UE를 2배(2→4)로 늘려도 점유는 **+26%**에 그친다. 선형이 아니다.

### 13.4 6대가 깨지는 이유 ✅ (로직 버그 아님)

```
[HW] Error, channel timeout        (반복 다수)
Assertion ((uint)cc == s->tx_stream.channels_.size()) failed!
  zmq_radio.cpp:171  Request to write on more antennas (1) than configured (0)
```

채널이 **타임아웃으로 무너져 채널 수가 0**이 된 뒤의 2차 증상이다. 해당 런은 CBRA를 **0회**밖에 못 했다
(= 접속 시도조차 못 함). 즉 공유 샘플 경로가 6개 UE를 감당하지 못한다.

§12.3에서 잰 대로 이 테스트베드의 공중 구간은 이미 **실시간의 약 1/6**로 돈다. 공유 라디오는 UE 수와
무관하게 고정된 슬롯 예산을 가지므로, UE를 늘리면 **같은 예산을 나눠 쓸 뿐**이고 어느 지점에서 무너진다.

### 13.5 결론

- **다중 UE 전환은 완료**됐고 **1~4대 범위에서 검증**됐다. 4대에서 동시 점유 39 = 상한의 41%.
- 그러나 **기본 설정(96) 포화는 이 테스트베드에서 다중 UE로도 도달하지 못한다.** 한계는 공격 도구가
  아니라 **ZMQ 가상 RF의 속도**다. 필요 48 Msg4/s 대비 4대 합계가 약 19.5/s다.
- 포화·거절 시연이 필요하면 §9의 **gNB 설정 전용 프로필**을 쓴다(RRCReject 126건 재현 완료).
- 실제 포화를 기본 설정에서 보려면 테스트베드 쪽이 바뀌어야 한다 🔍:
  (a) UE를 DU와 **다른 박스**로 분리해 ZMQ를 네트워크로 돌리거나,
  (b) 샘플레이트를 낮춘 셀(예: 10 MHz)로 슬롯 예산을 키우거나,
  (c) 실제 SDR OTA로 가는 것.
