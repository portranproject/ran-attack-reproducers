<a id="readme-top"></a>

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/portran-slogan-dark-transparent.png">
  <img src="docs/assets/portran-slogan-light-transparent.png" alt="PortRAN — Passive security for the 5G RAN" width="560">
</picture>

# 기지국 공격 재현 도구

팀 5G/O-RAN 테스트베드에서 기지국 공격을 재현하고 탐지·대응기 입력과 정답을 검증하는 도구 모음

[문서 보기 »](docs/README.md) · [실행 가이드](docs/E2E-EXECUTION-GUIDE.md) · [공격 카탈로그](docs/ATTACK-CATALOG.md)

</div>

<details>
<summary>목차</summary>

1. [프로젝트 소개](#프로젝트-소개)
   - [사용 기술](#사용-기술)
2. [시작하기](#시작하기)
   - [사전 준비](#사전-준비)
   - [설치](#설치)
3. [사용법](#사용법)
4. [저장소 구조](#저장소-구조)
5. [문서 목록](#문서-목록)
6. [한계](#한계)
7. [팀·연계 저장소](#팀연계-저장소)
8. [참고](#참고)

</details>

## 프로젝트 소개

이 저장소는 팀 소유 O-RAN IDS/IPS 테스트베드에서 5G 기지국 공격과 이상 신호를 통제된 조건으로 재현한다. 기지국(CU/DU)·코어·detector 소스는 수정하지 않고 UE 측만 수정하거나 격리된 입력을 생성해 탐지·대응기의 입력과 정답을 검증한다. RF 차폐 환경 또는 격리된 가상 RF에서만 사용한다.

| 룰 ID | 공격명 | `tools/ctl.sh` ID | 모듈 문서 |
|---|---|---|---|
| L3-01-V | RRC UE 컨텍스트 고갈 | `rrc-storm` | [rrc-signaling-storm](reproducers/rrc-signaling-storm/README.md) |
| L3-01-O | 인증 응답 미전송형 연결 컨텍스트 고갈 | `auth-timeout` | [authentication-timeout-exhaustion](reproducers/authentication-timeout-exhaustion/README.md) |
| L3-20 | 현재 유효 5G-GUTI 재사용형 Blind DoS | `blind-dos` | [blind-dos](reproducers/blind-dos/README.md) |
| L3-21 | 무효·위조 자격증명 실패 플러드형 상향 DoS | `uplink-credential-flood` | [uplink-dos](reproducers/uplink-dos/README.md) |
| L3-24 | 비정상 Identity Response·식별자 노출 | `downlink-imsi` | [downlink-imsi-extractor](reproducers/downlink-imsi-extractor/README.md) |
| L3-14 | 보안 전 UE Capability Information 주입 | `ue-capability` | [ue-capability-hijacking](reproducers/ue-capability-hijacking/README.md) |
| L3-06 | 요청되지 않은 NAS SecurityModeReject 결과 | `l3-06` | [nas-counter-desynchronization](reproducers/nas-counter-desynchronization/README.md) |

레거시 단발 MAC 변조(`uplink-dos`)와 공격 1.0 자격 범위 밖의 AN 탐지 회귀 fixture 6종(`AN-01`·`AN-06a`·`AN-02`·`AN-04`·`AN-07`·`AN-08`)은 [공격 카탈로그](docs/ATTACK-CATALOG.md)에서 관리한다.

현재 자격 상태는 `p1` 정상 UE 5대 `same-cell` 42/42 통과([p1 clean-origin 자격 기록](artifacts/p1-clean-origin-live-e2e-20261119/README.md)), `p5` 개별 3/3 통과, `OTA`는 `pending`이다.

### 사용 기술

- OCUDU 26.10 (srsRAN 기반) gNB (CU/DU)
- OAI 2026.w38 UE
- Open5GS
- TeleRAN (100 ms eBPF 프록시) · FlexRIC (O-RAN 테스트베드 RIC, E2 폐루프는 별도 범위)
- ZMQ 가상 RF
- Python / Bash

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 시작하기

### 사전 준비

현재 실행 자격이 확인된 환경은 `p1`·`p5` ZMQ이며, `p4` 등 동일 스택 ZMQ 호스트는 포팅 가능하다(미자격). 실 SDR 차폐 `OTA` 실행 adapter는 미구현이다([PORTING-GUIDE.md](PORTING-GUIDE.md)).

- `profiles/<env>.json`, `credentials_file`, `LIVE_E2E_CONF`, 모듈 `conf/*.conf`는 Git 밖에 권한 `0600` 이하로 준비한다.
- 시스템 패키지는 `setup`이 자동 설치하지 않으므로 CU에 `tcpdump`·`tshark`, DU에 `tshark`·`timeout`을 설치한다([실행 가이드](docs/E2E-EXECUTION-GUIDE.md)).
- `doctor`는 `integration.lock.json`에 기록된 필수 파일 SHA-256과 clean checkout, CU `tcpdump`·`tshark`·`.deployed-revision`을 검사하며, `same-cell doctor`는 DU `timeout`·`tshark`와 정상 UE 5대·L3 7종 준비 상태를 추가 확인한다.

### 설치

```bash
git clone https://github.com/portranproject/ran-attack-reproducers.git
cd ran-attack-reproducers
cp profiles/p1.example.json profiles/<env>.json   # 또는 profiles/p5.example.json
chmod 600 profiles/<env>.json
install -m 600 profiles/live-e2e.example.conf /root/.config/ran-reproducer/<env>-live-e2e.env
# <env>.json, credentials_file(0600 이하), <env>-live-e2e.env에 호스트·키·대상 정보를 입력한다.
./tools/ctl.sh normal-ue setup --profile <env>
./tools/ctl.sh normal-ue build --profile <env>
./tools/ctl.sh setup <attack> --profile <env>          # 전체 준비 시 <attack> 대신 all
./tools/ctl.sh doctor --profile <env>
./tools/ctl.sh same-cell doctor --profile <env>
```

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 사용법

준비가 끝난 DU 호스트에서 사용자 화면을 시작한다.

```bash
./run.sh
```

1. **가상 환경**을 고르면 이 DU의 설정을 자동으로 읽는다. 순서는 `RAN_REPRO_PROFILE_ID` → `profiles/du.json` → `backend=p5`, `configured=true`인 유일한 실제 설정이다. 설정이 없거나 여러 개라 결정할 수 없으면 안내를 표시한다. 프로필 선택 메뉴는 없다.
2. **L3 공격**을 고른 뒤 **준비 점검 → 정상 대조 → 공격 phase** 순서로 실행한다. L3 7종 전체를 검증하려면 **3세트 캠페인**을 고른다. 작업을 선택하면 실행 ID를 자동 생성해 바로 실행하며 추가 입력은 없다.
3. **실장비 환경**에서는 공격별 **USRP ↔ gNB 동작 설명 모션**을 볼 수 있다. OTA 실행 adapter는 미구현이며 모션은 실장비를 실행하거나 실행 결과를 표시하지 않는다.

`./run.sh --dry-run`은 실제 실행 없이 생성 명령을 확인하고, `--no-anim`은 애니메이션을 끈다. `--frames <DIR>`은 ZMQ·USRP 모션의 텍스트 프레임을 저장한다. 상세 옵션은 `./run.sh --help`를 따른다.

모션은 실행 전 동작 설명이다. 실제 실행 중에는 준비 점검·정상 UE 기준선·관측 경과·결과 수집 상태와 로그 경로를 표시한다. `Ctrl-C`는 runner에 중단을 전달하고 UE·수집기를 정리한 뒤 종료한다.

패치 적용과 UE 바이너리 빌드는 위 설치 단계에서 `tools/ctl.sh setup/build`로 수행한다. `run.sh`는 준비된 바이너리를 공식 `same-cell` runner로 실행한다. 자동화·개별 모듈·AN fixture용 명령은 `tools/ctl.sh`에 유지한다([컨트롤러 가이드](docs/CONTROL-GUIDE.md)).

`same-cell` 결과는 `LIVE_E2E_RUN_ROOT`에 저장되고 `tools/verify_live_e2e.py`가 판정한다. `./tools/ctl.sh replay|report|verify`는 `profile.run_root` 아래 `@common-signal` 7-파일 계약(AN fixture) 전용이며, 봉인된 요약은 [artifacts/README.md](artifacts/README.md), 전체 CLI와 합격 조건은 [실행 가이드](docs/E2E-EXECUTION-GUIDE.md)와 [컨트롤러 가이드](docs/CONTROL-GUIDE.md)를 따른다.

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 저장소 구조

```text
├── run.sh                  # DU에서 실행하는 사용자 메뉴·공격 모션
├── reproducers/            # L3 7종 + AN 6종 독립 공격·회귀 모듈
├── workloads/              # same-cell 정상 UE 5대 풀(normal-ue) 및 ZMQ broker
├── docs/                   # 문서 인덱스, 실행·카탈로그·명명 가이드, research/, history/
├── artifacts/              # 봉인된 판정·요약·SHA-256 (원시 로그 제외)
├── profiles/               # p1/p4/p5/ota/live-e2e 예제 (실제 profile·키는 Git 밖)
├── tools/                  # ctl.sh 내부 CLI, reproctl.py, p5-live-e2e, 판정·fixture 도구
├── schemas/                # module/profile/run/verdict/evidence JSON 스키마
├── tests/                  # 플랫폼·컨트롤러·live E2E 단위 테스트
├── PORTING-GUIDE.md        # 호스트 선행조건, 환경 포팅, p5·차폐 OTA 운영 체크리스트
├── AGENTS.md / CLAUDE.md   # AI 에이전트 작업 규칙 (CLAUDE.md -> AGENTS.md)
└── NOTICE.md               # 격리 테스트베드 사용 범위·비라이선스 고지
```

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 문서 목록

- [docs/README.md](docs/README.md) — 저장소 전체 문서 인덱스
- [docs/E2E-EXECUTION-GUIDE.md](docs/E2E-EXECUTION-GUIDE.md) — `p1`/`p5` 설치, `same-cell` 토폴로지, E2E 합격 조건
- [docs/CONTROL-GUIDE.md](docs/CONTROL-GUIDE.md) — `tools/ctl.sh` CLI·`doctor` 범위·환경변수·산출물 구분
- [docs/ATTACK-CATALOG.md](docs/ATTACK-CATALOG.md) — L3 7종·AN 6종 카탈로그, 재현 수준, 주장과 한계
- [docs/ATTACK-REFERENCES.md](docs/ATTACK-REFERENCES.md) — 모듈별 외부 레퍼런스 URL 및 자체 구현 범위
- [docs/NEW-MODULE-GUIDE.md](docs/NEW-MODULE-GUIDE.md) — 신규 모듈 추가 절차 및 `tools/ctl.sh`·lock 제약
- [docs/NAMING-CONVENTIONS.md](docs/NAMING-CONVENTIONS.md) — 디렉터리·문서·ID 명명 규칙과 lock 예외
- [docs/history/README.md](docs/history/README.md) — 이력 및 `docs/research/` RSS 연구 6종 안내
- [PORTING-GUIDE.md](PORTING-GUIDE.md) — 호스트 선행조건, 환경 포팅, p5·차폐 OTA 운영 체크리스트
- [artifacts/README.md](artifacts/README.md) — 루트 21개 + 모듈 11개 봉인 증거 인덱스

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 한계

- **OTA 미구현**: 실 SDR 차폐 OTA 실행 adapter가 미구현이므로 모든 OTA 자격은 `pending` 상태다.
- **원인 범위 제한**: 결과·관측 에뮬레이션 3종(`L3-24`, `L3-14`, `L3-06`)과 AN 회귀 fixture 6종은 RF overshadowing·MITM·NAS counter wrap 등 원 공격 원인을 재현하거나 주장하지 않는다.
- **ZMQ 시간축·일반화 불가**: ZMQ 가상 RF는 실제 무선 시간축과 다를 수 있으며, `p1`·`p5` 결과를 다른 환경이나 상용망으로 일반화하지 않는다.
- **서비스 거부·E2 폐루프 범위 밖**: `p1` 42/42에서 `service_impact`는 전 종 `not_observed`이며, E2 폐루프 대응은 이 저장소 범위 밖이다.

자세한 내용은 [주장과 한계](docs/ATTACK-CATALOG.md#주장과-한계)와 [이력 한계 문서](docs/history/testbed-limitations.md)를 본다.

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>

## 팀·연계 저장소

"O-RAN 기반 5G 기지국 위협 탐지" 팀 프로젝트의 공격 재현 저장소다. `integration.lock.json`에 고정한 연계 저장소는 다음과 같다.

- 탐지기 (`766f5569...`): [portranproject/detection](https://github.com/portranproject/detection)
- 텔레메트리 (`7550153a...`, 100 ms): [portranproject/telemetry](https://github.com/portranproject/telemetry)
- 대시보드 (`01a1a44a...`): [portranproject/dashboard](https://github.com/portranproject/dashboard)

사용 범위와 비라이선스 고지는 [NOTICE.md](NOTICE.md)에 있다(루트 `LICENSE` 파일 없음).

## 참고

- 기반 오픈소스 프로젝트: OCUDU, OpenAirInterface 5G (OAI), Open5GS
- 모듈별 논문·표준·공개 구현 출처와 제3자 라이선스 고지: [docs/ATTACK-REFERENCES.md](docs/ATTACK-REFERENCES.md), [reproducers/rrc-signaling-storm/NOTICE.md](reproducers/rrc-signaling-storm/NOTICE.md)

<p align="right">(<a href="#readme-top">맨 위로</a>)</p>
