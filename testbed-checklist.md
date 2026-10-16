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
