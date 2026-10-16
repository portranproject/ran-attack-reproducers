# 팀 테스트베드 체크리스트와 베이스 UE 결정

> 작성 2026-10-16. 표시 규칙은 [comparison-5g.md](comparison-5g.md) §0과 같다(✅ 원본 대조 / 📄 리포 문서 출처만 / 🔍 추론·미확인).

## 0. 상태: 값은 아직 비어 있다

팀 기준 테스트베드 Drive 폴더(`1gRmlhkUs3JMa_stI7826hgvlDNGWs9A2`)를 **읽지 못했다.**

- 이 세션의 Google Drive 커넥터 계정(`coketazo20040501@gmail.com`)으로 폴더 ID를 조회하면 "Requested entity was not found"가 반환된다.
- 폴더 URL에 `/u/1/`이 있으므로 브라우저의 **두 번째 Google 계정**에 있는 폴더일 가능성이 있다 🔍.
- 같은 계정에서 `OCUDU`, `B210`, `USRP`, `TDD`, `FDD`, `ZMQ`, `테스트베드`로 검색했으나 결과는 9월의 이전 주제(스마트항만 Audit) 자료뿐이었다.

아래 값은 추측으로 채우지 않는다. 폴더를 커넥터 계정과 공유하거나 설정 파일을 리포에 넣으면 채운다.

## 1. 체크리스트

| 항목 | 값 | 근거 파일 | 표시 |
|---|---|---|---|
| **TDD/FDD** | 미확인 | | 🔍 |
| SCS (`common_scs`) | 미확인 | | 🔍 |
| 대역폭 (`channel_bandwidth_MHz`) | 미확인 | | 🔍 |
| `dl_arfcn` / `band` | 미확인 | | 🔍 |
| CU/DU 분리 여부 | 미확인 | | 🔍 |
| RF 경로 (`ru_sdr.device_driver`: `zmq` / `uhd`) | 미확인 | | 🔍 |
| OCUDU 버전·커밋 | 미확인 | | 🔍 |
| 코어 종류 | 미확인 | | 🔍 |
| 현재 쓰는 UE | 미확인 | | 🔍 |

참고로 접근 가능한 자료 중 하드웨어 언급은 하나뿐이다. 이전 주제 보고서(`01_기지국·코어와 보안 감사_발표자 보충 보고서.pdf`, 2026-09-10)에 "USRP B210 사용 예정"이라는 문장이 있다. 이는 현재 테스트베드의 설정이 아니며, 아래 §2.3처럼 B210만으로는 TDD/FDD가 정해지지도 않는다.

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

OCUDU는 같은 B200 계열 USRP로 FDD 예제와 TDD 예제를 모두 제공한다(§2.2). "B210을 쓴다"는 사실만으로는 베이스 UE가 정해지지 않는다. 팀 설정의 `band`를 확인해야 한다.

## 3. 베이스 UE 결정 규칙

값을 받으면 이 규칙으로 결정한다. 아직 결정하지 않았다.

| 팀 셀 | 베이스 UE 후보 | 근거 |
|---|---|---|
| TDD (예: n78) | 최신 OAI UE (`2026.w25` 이상)에 A형 재구현 | OCUDU 공식 OAI UE 튜토리얼은 n78 TDD·30 kHz·20 MHz 📄 ([tool-survey.md](tool-survey.md)). srsUE는 TDD에 쓸 수 없다 📄 |
| FDD (예: n3, 15 kHz, ≤20 MHz) | srsUE와 최신 OAI UE 모두 후보 | OCUDU가 srsUE용 FDD 예제를 직접 제공 ✅(§2.2). srsUE 제약은 15 kHz·FDD·최대 20 MHz 📄. OAI UE의 OCUDU FDD 연동 사례는 미확인 📄 ([tool-survey.md](tool-survey.md) 그림 2) |

두 경우 모두 다음 단계는 같다. 정상 UE로 팀 셀에 먼저 접속해 보고(interop 스모크 테스트), 그 뒤에 A형 동작을 넣는다.

## 4. 값을 채우려면 필요한 것

우선순위순.

1. 팀 OCUDU 설정 파일(`gnb.yml` 또는 `cu.yml`+`du.yml`). §1의 앞쪽 6개 항목이 대부분 여기서 나온다.
2. OCUDU 빌드 커밋(`git rev-parse HEAD` 또는 실행 로그 첫 줄).
3. 코어 설정(Open5GS면 `amf.yaml`) 또는 코어 이름.
4. 현재 시험에 쓰는 UE 종류(상용 단말, srsUE, OAI UE)와 그 설정 파일.
