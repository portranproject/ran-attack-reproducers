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
| 현재 쓰는 UE | **OAI UE** (`nr-uesoftmodem`, `$OAI/cmake_targets/ran_build/build/`). 버전 미확인 | 박스 출력: DU `ctl.sh` 29행 `UE_BIN=…/nr-uesoftmodem`. PDF는 코어 로그에서 등록 성공을 확인했다고 적음 | ✅ (종류) / 🔍 (버전) |

### 남은 값을 얻는 명령

DU 박스에서 OAI UE 버전 확인:

```bash
sudo grep -nE '^OAI=' /root/workspace/ctl.sh
sudo git -C <위 OAI 경로> describe --tags --always
sudo git -C <위 OAI 경로> log -1 --format='%H %cd'
```

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

1. **OAI UE 버전**: 이미 등록에 성공했으므로 OCUDU와 맞는 버전일 가능성이 높다 🔍. 하지만 5gattacks 패치(OAI 2025.w46 기준)를 참고해 이식할 때 코드 차이를 가늠하려면 정확한 태그·커밋이 필요하다.
2. **차폐 OTA**: 이 결정은 EC2 ZMQ 환경 기준이다. RF 차폐 박스에서 SDR로 돌릴 때의 접속은 따로 확인해야 한다.
3. **A형 효과**: OCUDU 26.10에서 A형이 미완료 컨텍스트를 실제로 쌓는지는 여전히 실험 전이다 🔍.
