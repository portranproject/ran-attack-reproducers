# 통합 컨트롤러 사용 가이드

사용자는 DU 호스트에서 `./run.sh`로 시작한다. 내부 CLI인 `tools/ctl.sh`는 각 공격 모듈의 기존 빌드기·runner·판정기와 공통 detector 도구를 호출한다. E2E 토폴로지, `same-cell` 생명주기, 합격 조건은 [E2E 실행 가이드](E2E-EXECUTION-GUIDE.md)를 따른다.

## 사용자 화면

`./run.sh`는 **환경 → L3 공격 → 작업** 순서로 진행한다. 가상 환경에서는 `same-cell doctor`, 정상 대조, 공격 phase, L3 7종 통합 캠페인을 실행한다. 실장비 환경에서는 USRP ↔ gNB 공격 모션만 제공하며 OTA 실행 adapter는 준비 중이다. 모션은 동작 설명이고 실측 결과가 아니다.

`RUN_ID`·`CAMPAIGN_ID`는 UTC 시각과 난수 접미사로 자동 생성한다. 작업 선택이 실행 요청이며 `ENABLE`을 다시 입력하지 않는다. 내부 CLI의 active 실행에는 화면이 `--enable`을 전달한다. 실제 실행에서는 준비 점검, 정상 UE 기준선 대기, phase 경과, 결과 수집 상태를 출력한다. `Ctrl-C`를 누르면 중단 접수를 즉시 표시하고 runner 정리 절차를 진행한다. 반복 입력으로 정리 절차를 끊지 않으며 phase의 기존 강제 종료 상한은 60초다.

프로필 선택 화면은 없으며 DU에 준비한 설정을 아래 순서로 사용한다. `RAN_REPRO_PROFILE_DIR`로 설정 디렉터리를 바꿀 수 있다.

1. `RAN_REPRO_PROFILE_ID`로 지정한 설정 이름 또는 경로
2. 설정 디렉터리의 `du.json`
3. `.example.json`을 제외하고 `configured=true`, `backend=p5`인 유일한 설정

선택된 설정은 기존 profile 검증을 거친다. 설정이 없거나 후보가 여러 개면 실행 메뉴로 넘어가지 않는다. `profiles/du.json`을 사용할 때도 내부 `id`와 `environment`의 설정·바이너리 경로는 실제 DU에 맞춰 작성한다. 빌드는 설치 시 `tools/ctl.sh setup/build`로 먼저 완료해야 한다.

`--dry-run`은 run·campaign의 명령만 출력하고 doctor도 생략한다. `--no-anim`은 애니메이션을 끄며, 실장비 메뉴에서는 정지 화면을 표시한다. 비터미널·`NO_COLOR` 환경에서도 번호 입력으로 조작할 수 있다. `--frames <DIR>`은 장비 연결 없이 양쪽 환경의 프레임을 저장한다.

## 내부 CLI

인자 없이 `./tools/ctl.sh`를 실행하면 14개 대상(L3 7종 + 레거시 `uplink-dos` + AN 6종) 중 하나를 골라 `상태점검`·`환경준비_및_빌드`·`정상대조`·`attack|emulation`·`3세트_캠페인`을 실행한다. active 실행과 캠페인은 메뉴에서 `ENABLE` 입력, CLI에서 `--enable` 플래그를 요구한다(`control`에 `--enable`을 붙이면 실패한다).

```bash
./tools/ctl.sh list
./tools/ctl.sh coverage
./tools/ctl.sh validate
./tools/ctl.sh doctor [ID|all] --profile p5
./tools/ctl.sh setup <ID|all> --profile p5
./tools/ctl.sh build <ID|all> --profile p5
./tools/ctl.sh run <ID> control|attack|emulation <RUN_ID> --profile p5 [--enable] [--dry-run]
./tools/ctl.sh campaign <ID> [CAMPAIGN_ID] --profile p5 --enable [--dry-run]
./tools/ctl.sh same-cell doctor --profile p5
./tools/ctl.sh same-cell run <ID> --profile p5 --mode control|attack|emulation [--run-id ID] [--enable] [--dry-run]
./tools/ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable [--dry-run]
./tools/ctl.sh replay <RUN_ID> --profile p5
./tools/ctl.sh report <RUN_ID> [--profile p5]
./tools/ctl.sh verify <RUN_ID> [--profile p5]
```

`--dry-run`은 실제 실행 없이 위임할 명령과 환경변수만 출력한다. `campaign`의 `CAMPAIGN_ID`를 생략하면 UTC 타임스탬프로 생성한다.

## `doctor` 검증 범위

`doctor`는 실행 환경의 정합성을 fail-closed로 검사한다(`tools/reproctl.py`, `tools/ctl.sh`).

- **공통 checkout (`reproctl.py checkout`)**: Git clone 여부, `integration.lock.json`의 `reproducer.minimum_commit` 이상 여부, 추적 파일 변경 없음(`clean`), `reproducer.required_files`에 기록된 파일의 SHA-256 일치.
- **profile 및 원격 CU (`reproctl.py doctor --profile <NAME>`)**:
  - manifest 13개 유효성(`reproducers/*/reproducer.json`)
  - profile의 `configured=true`, `lab_only=true`, `telemetry.period_ms=100`, `limits`, `target_allowlist`, `credentials_file` 권한(`0600` 이하)
  - `p5` backend인 경우 `LIVE_E2E_CONF` 권한(`0600` 이하)·경로 일치 확인 후 SSH로 CU의 `tcpdump`·`tshark`, detector·telemetry `.deployed-revision`(profile에 적힌 commit과 비교), 실행 파일·`detector.json`·`dashboard_sender.py`·CA 파일 존재를 확인하고 SHA-256을 계산해 출력한다(detector/config SHA-256은 `integration.lock.json` 대조가 아니라 존재 확인 및 해시 수집이다).
  - OTA profile은 SDR serial 2개 이상과 `shielding_confirmed=true`를 확인한다.
- **로컬 모듈 (`tools/ctl.sh doctor [ID|all]`)**: 위 검사 후 대상 모듈(기본 `all`)의 로컬 설정 파일 존재와 OAI UE 바이너리의 공격 마커·게이트 마커를 확인한다.
- **`same-cell doctor`**: 위 profile·CU 검사 + 로컬 `timeout`·`tshark` 존재 확인 + `normal-ue doctor --count 5` + live L3 7종의 로컬 설정·바이너리 확인.

## 환경 준비(`setup`)와 환경변수

`./tools/ctl.sh setup <ID|all>`은 추적되지 않는 모듈 `conf/*.conf`가 없을 때 예제에서 `0600`으로 생성하고, 기준 OAI 저장소(`/root/OAI` 또는 `OAI_BASE`)에서 공격별 고정 commit(`rrc-storm`은 `1c2f4d3c...`, 그 외 6종은 `6d6782b4...` 로컬 패치 재생성)의 worktree를 만든 뒤 모듈 빌드기를 호출한다. 시스템 패키지, OCUDU, Open5GS, 가입자 설정, SSH 키, RF 케이블은 자동 설치·생성하지 않는다.

기본 경로가 다른 호스트는 profile의 `environment` 또는 셸 환경변수로 아래 키를 오버라이드할 수 있다(`--profile` 지정 시 profile 값이 runner로 전달된다).

| 구분 | 지원 변수 |
|---|---|
| OAI 경로 | `OAI_BASE`, `RRC_OAI`, `BLIND_OAI`, `UPLINK_OAI`, `AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`, `UE_CAPABILITY_OAI`, `NAS_DESYNC_OAI` |
| 모듈 설정 | `RSS_CONF`, `BLIND_CONF`, `UPLINK_CONF`, `AUTH_STALL_CELL_CONF`, `DOWNLINK_IMSI_CONF`, `UE_CAPABILITY_CONF`, `NAS_DESYNC_CONF`, `NORMAL_UE_CONF` |

- `auth-timeout`을 `tools/ctl.sh`로 실행할 때는 **`AUTH_STALL_CELL_CONF`**(`conf/auth-stall-cell.conf`)를 사용한다. `AUTH_TIMEOUT_CONF`는 레거시 direct 4-cell runner(`auth-timeout-run` 등) 전용이다.
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

`./tools/ctl.sh verify`, `report`, `replay`는 `tools/reproctl.py`가 `profile.run_root` 아래 **정확히 위 7개 파일만 있는 디렉터리**(AN fixture 실행)를 검증·조회·재실행할 때만 사용한다. live L3 실행(`tools/p5-live-e2e`, `same-cell`, `nas-counter-desync-run` 등)은 `LIVE_E2E_RUN_ROOT`나 모듈 `RUN_ROOT`에 `live/`·`mechanism.json`·`same-cell-*` 등을 함께 남기므로 `tools/verify_live_e2e.py` 또는 각 모듈의 `analysis/verify_*.py`로 판정한다.

각 ID의 전체 재현 유형·자격 상태·주장 경계는 [공격 카탈로그](ATTACK-CATALOG.md)와 [주장과 한계](ATTACK-CATALOG.md#주장과-한계)를 따른다.
