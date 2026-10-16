# 팀 테스트베드 체크리스트와 베이스 UE 결정

> 작성 2026-10-16. 표시 규칙은 [comparison-5g.md](comparison-5g.md) §0과 같다(✅ 원본 대조 / 📄 리포 문서 출처만 / 🔍 추론·미확인).

## 0. 출처와 상태

팀 Drive `PortRAN Project > 실습 자료 > res` 폴더(2026-10-16 공유받음)를 읽었다. 폴더에는 다음 파일이 있다.

| 파일 | 내용 | 이번에 읽은 범위 |
|---|---|---|
| `AWS EC2 기반 5G NR SA 종단간 실습 환경-1.pdf` (2026-10-09) | 실습 절차: 인스턴스 기동 → CU 먼저, DU 다음 → 로그·KPM 확인 → UE 등록 | 본문 텍스트만. 로그 스크린샷 이미지는 판독하지 못함 |
| `p1.zip` ~ `p5.zip` (2026-10-14) | 팀원별 EC2 제어판: `README.md`, `ctl.sh`, `setup.sh`, 그리고 비밀 파일 `credentials`, `portran-key.pem` | `p1.zip`의 `README.md`·`ctl.sh`·`setup.sh`만. 비밀 파일은 열지 않았다. p2~p5는 세트 번호만 다른 사본으로 보인다 🔍 (README의 "`pN` → CU `172.31.N.10`" 규칙) |

**핵심 발견**: 현재 팀 실습 테스트베드는 RF 차폐 박스가 아니라 **AWS EC2 2대(CU 박스·DU 박스) 위의 ZMQ 가상 RF**다 ✅. [AGENTS.md](AGENTS.md)의 "3-노트북 RF 차폐" 구성과 다르다. 차폐 OTA 구성이 따로 계획돼 있는지는 이 폴더로 알 수 없다 🔍.

**남은 공백**: band·SCS·대역폭·`dl_arfcn`은 DU 박스 안의 `/root/OCUDU/configs/du.yaml`에만 있다 ✅(`ctl.sh`가 이 경로를 편집함). Drive 폴더에는 이 파일이 없다. 그래서 **TDD/FDD는 아직 미확인**이다.

## 1. 체크리스트

| 항목 | 값 | 근거 | 표시 |
|---|---|---|---|
| **TDD/FDD** | 미확인 | DU 박스 `/root/OCUDU/configs/du.yaml`의 `cell_cfg.band`를 봐야 함 | 🔍 |
| SCS (`common_scs`) | 미확인 | 위와 같음 | 🔍 |
| 대역폭 (`channel_bandwidth_MHz`) | 미확인 | 위와 같음 | 🔍 |
| `dl_arfcn` / `band` | 미확인 | 위와 같음 | 🔍 |
| CU/DU 분리 여부 | **분리.** CU 박스(c6i.xlarge)와 DU 박스(c6i.2xlarge)가 F1으로 연결. 사설 IP는 세트별 고정 CU `172.31.N.10` / DU `172.31.N.11` | `p1/README.md`, `p1/ctl.sh`(`cu.yaml`·`du.yaml` 따로 존재, DU의 `addrs`가 CU를 가리킴) | ✅ |
| RF 경로 | **ZMQ 가상 RF.** UE가 DU 박스에서 함께 실행됨 | `ctl.sh` 주석 "DU 8vCPU/16GB (ZMQ 이중 PHY라 넉넉히)", "DU 골든 (odu+UE …)". "이중 PHY"는 DU PHY와 UE PHY가 한 박스에서 돈다는 뜻으로 읽음 🔍 | ✅ (ZMQ) |
| OCUDU 버전·커밋 | 미확인. 소스 위치는 `/root/OCUDU`, 골든 이미지 날짜는 2026-10-14 | `ctl.sh` 이미지 주석·설정 경로 | 🔍 |
| 코어 종류 | 미확인. CU 박스에 함께 있음("코어+RIC+ocu") | `ctl.sh` 주석 | 🔍 |
| RIC | FlexRIC, E2(KPM) 연결 | `ctl.sh` "FlexRIC 가 죽는다", "E2(KPM)→RIC OK" | ✅ |
| 현재 쓰는 UE | 종류 미확인. DU 박스의 `/root/workspace/ctl.sh ue`로 실행, 재시도 기능 있음. PDF는 코어 로그에서 등록 성공을 확인했다고 적음 | `ctl.sh`, PDF §3 | 🔍 (종류) / ✅ (존재) |

### 남은 값을 얻는 명령

DU 박스(`./ctl.sh ssh du`)에서:

```bash
sudo grep -nE 'band|dl_arfcn|common_scs|channel_bandwidth_MHz|tdd_ul_dl_cfg|device_driver|device_args' /root/OCUDU/configs/du.yaml
sudo git -C /root/OCUDU rev-parse HEAD
sudo grep -nE 'nr-uesoftmodem|srsue' /root/workspace/ctl.sh     # 어떤 UE를 띄우는지
```

CU 박스(`./ctl.sh ssh cu`)에서:

```bash
sudo grep -nE 'open5gs|amf|free5gc|oai' /root/workspace/ctl.sh   # 코어 종류
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

## 3. 베이스 UE 결정 규칙

아직 결정하지 않았다. band와 현재 UE 종류를 받으면 아래 규칙으로 정한다.

| 팀 셀 | 베이스 UE 후보 | 근거 |
|---|---|---|
| TDD (예: n78) | 최신 OAI UE (`2026.w25` 이상)에 A형 재구현 | OCUDU 공식 OAI UE 튜토리얼은 n78 TDD·30 kHz·20 MHz 📄 ([tool-survey.md](tool-survey.md)). srsUE는 TDD에 쓸 수 없다 📄 |
| FDD (예: n3, 15 kHz, ≤20 MHz) | srsUE와 최신 OAI UE 모두 후보 | OCUDU가 srsUE용 FDD 예제를 직접 제공 ✅(§2.2). srsUE 제약은 15 kHz·FDD·최대 20 MHz 📄. OAI UE의 OCUDU FDD 연동 사례는 미확인 📄 ([tool-survey.md](tool-survey.md) 그림 2) |

### 지름길: DU 박스에 이미 있는 UE

DU 박스에는 이미 OCUDU 셀에 접속해 코어 등록까지 마친 UE가 있다(PDF §3) ✅. 이 UE가 무엇인지 알면 두 가지가 한꺼번에 풀린다.

- **interop 스모크 테스트**: 분리 CU/DU + ZMQ 구성에서 정상 UE 접속은 이미 성공한 상태다. 차폐 OTA 경로는 여전히 별도 확인이 필요하다.
- **TDD/FDD 간접 판정**: 그 UE가 srsUE라면 셀은 FDD·15 kHz다(srsUE는 FDD 전용 📄). OAI UE라면 TDD/FDD 둘 다 가능하므로 `du.yaml`의 `band`를 따로 봐야 한다.

따라서 첫 후보는 **이미 접속되는 그 UE**다. A형은 5gattacks 패치를 그대로 쓰지 않고 다시 구현할 계획이므로, 어느 UE든 재구현 비용은 비슷하다 🔍. 반면 이미 접속되는 UE를 고르면 interop 위험이 사라진다.

## 4. 값을 채우려면 필요한 것

우선순위순. §1의 명령을 실행하면 모두 나온다.

1. DU 박스 `/root/OCUDU/configs/du.yaml`의 `cell_cfg` 블록 → TDD/FDD, SCS, 대역폭, `dl_arfcn`/band.
2. DU 박스의 UE 실행 명령(`/root/workspace/ctl.sh`의 `ue` 부분) → 현재 UE 종류.
3. `/root/OCUDU`의 커밋 해시.
4. CU 박스의 코어 실행 명령 → 코어 종류.
5. PDF의 로그 스크린샷 원본(텍스트로 판독하지 못함). 로그에 UE 종류나 band가 찍혀 있을 수 있다.
