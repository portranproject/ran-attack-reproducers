# 통합 컨트롤러 사용 가이드

`ctl.sh`는 각 공격 모듈의 구현·설정·라벨을 합치지 않고 기존 빌드기·runner·판정기와 공통 detector 도구를 한 진입점에서 호출한다. E2E 토폴로지, `same-cell` 생명주기, 합격 조건은 [E2E 실행 가이드](E2E-EXECUTION-GUIDE.md)를 따른다.

## 대화형 메뉴와 CLI

인자 없이 `./ctl.sh`를 실행하면 14개 대상(L3 7종 + 레거시 `uplink-dos` + AN 6종) 중 하나를 골라 `상태점검`·`환경준비_및_빌드`·`정상대조`·`attack|emulation`·`3세트_캠페인`을 실행한다. active 실행과 캠페인은 메뉴에서 `ENABLE` 입력, CLI에서 `--enable` 플래그를 요구한다(`control`에 `--enable`을 붙이면 실패한다).

```bash
./ctl.sh list
./ctl.sh coverage
./ctl.sh validate
./ctl.sh doctor [ID|all] --profile p5
./ctl.sh setup <ID|all> --profile p5
./ctl.sh build <ID|all> --profile p5
./ctl.sh run <ID> control|attack|emulation <RUN_ID> --profile p5 [--enable] [--dry-run]
./ctl.sh campaign <ID> [CAMPAIGN_ID] --profile p5 --enable [--dry-run]
./ctl.sh same-cell doctor --profile p5
./ctl.sh same-cell run <ID> --profile p5 --mode control|attack|emulation [--run-id ID] [--enable] [--dry-run]
./ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable [--dry-run]
./ctl.sh replay <RUN_ID> --profile p5
./ctl.sh report <RUN_ID> [--profile p5]
./ctl.sh verify <RUN_ID> [--profile p5]
```

`--dry-run`은 실제 실행 없이 위임할 명령과 환경변수만 출력한다. `campaign`의 `CAMPAIGN_ID`를 생략하면 UTC 타임스탬프로 생성한다.

## `doctor` 검증 범위

`doctor`는 실행 환경의 정합성을 fail-closed로 검사한다(`tools/reproctl.py`, `ctl.sh`).

- **공통 checkout (`reproctl.py checkout`)**: Git clone 여부, `integration.lock.json`의 `reproducer.minimum_commit` 이상 여부, 추적 파일 변경 없음(`clean`), `reproducer.required_files` 40개 파일의 SHA-256 일치.
- **profile 및 원격 CU (`reproctl.py doctor --profile <NAME>`)**:
  - manifest 13개 유효성(`reproducers/*/reproducer.json`)
  - profile의 `configured=true`, `lab_only=true`, `telemetry.period_ms=100`, `limits`, `target_allowlist`, `credentials_file` 권한(`0600` 이하)
  - `p5` backend인 경우 `LIVE_E2E_CONF` 권한(`0600` 이하)·경로 일치 확인 후 SSH로 CU의 `tcpdump`·`tshark`, detector·telemetry `.deployed-revision`(profile에 적힌 commit과 비교), 실행 파일·`detector.json`·`dashboard_sender.py`·CA 파일 존재를 확인하고 SHA-256을 계산해 출력한다(detector/config SHA-256은 `integration.lock.json` 대조가 아니라 존재 확인 및 해시 수집이다).
  - OTA profile은 SDR serial 2개 이상과 `shielding_confirmed=true`를 확인한다.
- **로컬 모듈 (`ctl.sh doctor [ID|all]`)**: 위 검사 후 대상 모듈(기본 `all`)의 로컬 설정 파일 존재와 OAI UE 바이너리의 공격 마커·게이트 마커를 확인한다.
- **`same-cell doctor`**: 위 profile·CU 검사 + 로컬 `timeout`·`tshark` 존재 확인 + `normal-ue doctor --count 5` + live L3 7종의 로컬 설정·바이너리 확인.

## 환경 준비(`setup`)와 환경변수

`./ctl.sh setup <ID|all>`은 추적되지 않는 모듈 `conf/*.conf`가 없을 때 예제에서 `0600`으로 생성하고, 기준 OAI 저장소(`/root/OAI` 또는 `OAI_BASE`)에서 공격별 고정 commit(`rrc-storm`은 `1c2f4d3c...`, 그 외 6종은 `6d6782b4...` 로컬 패치 재생성)의 worktree를 만든 뒤 모듈 빌드기를 호출한다. 시스템 패키지, OCUDU, Open5GS, 가입자 설정, SSH 키, RF 케이블은 자동 설치·생성하지 않는다.

기본 경로가 다른 호스트는 profile의 `environment` 또는 셸 환경변수로 아래 키를 오버라이드할 수 있다(`--profile` 지정 시 profile 값이 runner로 전달된다).

| 구분 | 지원 변수 |
|---|---|
| OAI 경로 | `OAI_BASE`, `RRC_OAI`, `BLIND_OAI`, `UPLINK_OAI`, `AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`, `UE_CAPABILITY_OAI`, `NAS_DESYNC_OAI` |
| 모듈 설정 | `RSS_CONF`, `BLIND_CONF`, `UPLINK_CONF`, `AUTH_STALL_CELL_CONF`, `DOWNLINK_IMSI_CONF`, `UE_CAPABILITY_CONF`, `NAS_DESYNC_CONF`, `NORMAL_UE_CONF` |

- `auth-timeout`을 `ctl.sh`로 실행할 때는 **`AUTH_STALL_CELL_CONF`**(`conf/auth-stall-cell.conf`)를 사용한다. `AUTH_TIMEOUT_CONF`는 레거시 direct 4-cell runner(`auth-timeout-run` 등) 전용이다.
- `CU_DASHBOARD_ENV`는 `reproctl.py`가 `[A-Za-z0-9._-]`를 허용하지만 `uplink-credential-flood-run`·`nas-counter-desync-run`은 `^[a-z0-9][a-z0-9-]{0,31}$`만 허용하므로 소문자·숫자·하이픈(`p1`, `p4`, `p5`)만 사용한다.
- 현재 OTA 실행 adapter는 없으므로 OTA profile의 `setup|run|campaign`과 `same-cell run|campaign`은 실패하고 [포팅 가이드](../PORTING-GUIDE.md)를 안내한다.

## 공통 산출물과 `replay`·`report`·`verify` 범위

공통 입력 runner(`@common-signal` 기반 AN fixture 6종)는 `profile.run_root`(또는 `RAN_REPRO_RUN_ROOT`) 아래에 다음 7개 파일을 원자적으로 생성한다.

```text
runs/<run-id>/
├── run.json
├── observations.jsonl
├── oracle.jsonl
├── detector.jsonl
├── verdict.json
├── report.md
└── evidence_manifest.json
```

`./ctl.sh verify`, `report`, `replay`는 `tools/reproctl.py`가 `profile.run_root` 아래 **정확히 위 7개 파일만 있는 디렉터리**(AN fixture 실행)를 검증·조회·재실행할 때만 사용한다. live L3 실행(`tools/p5-live-e2e`, `same-cell`, `nas-counter-desync-run` 등)은 `LIVE_E2E_RUN_ROOT`나 모듈 `RUN_ROOT`에 `live/`·`mechanism.json`·`same-cell-*` 등을 함께 남기므로 `tools/verify_live_e2e.py` 또는 각 모듈의 `analysis/verify_*.py`로 판정한다.

각 ID의 전체 재현 유형·자격 상태·주장 경계는 [공격 카탈로그](ATTACK-CATALOG.md)와 [주장과 한계](ATTACK-CATALOG.md#주장과-한계)를 따른다.
