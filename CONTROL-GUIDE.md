# 통합 컨트롤러 사용 가이드

`ctl.sh`는 각 공격 모듈을 합치지 않고 기존 빌드기·runner·판정기와 공통 detector replay를
한 화면에서 호출한다. 실행 원문과 라벨 계약은 계속 각 `reproducers/<attack>/`에 분리된다.
13개 대표 시나리오는 모듈별 `reproducer.json`에서 자동 검색한다.

## 가장 빠른 사용법

인자 없이 실행하면 메뉴가 열린다.

```bash
./ctl.sh
```

메뉴에서 공격을 고른 뒤 다음 작업을 선택한다.

- `상태점검`: 로컬 설정 파일과 해당 공격용 UE 빌드 마커를 확인한다.
- `환경준비_및_빌드`: 추적되지 않는 설정 파일을 예제에서 만들고, 전용 OAI worktree를
  준비한 뒤 기존 모듈 빌드기를 실행한다.
- `정상대조`: 공격 기능이 꺼진 control 한 건을 실행한다.
- `attack` 또는 `emulation`: 공격·에뮬레이션 한 건을 실행한다.
- `3세트_캠페인`: `control → attack/emulation` matched 3세트를 실행하고 기존 판정기로
  검증한다. RRC 모듈도 동결된 기존 runner를 변경하지 않고 순차 3세트만 수행한다.

공격·에뮬레이션은 메뉴에서 `ENABLE`을 입력해야 실행된다. CLI에서도 `--enable`을 생략하면
중단한다. 각 모듈 자체의 `-e 1` 게이트도 그대로 유지된다.

## CLI 사용법

```bash
./ctl.sh list
./ctl.sh coverage
./ctl.sh doctor --profile p5
./ctl.sh setup blind-dos --profile p5
./ctl.sh run blind-dos control blind-smoke-control --profile p5
./ctl.sh run blind-dos attack blind-smoke-attack --profile p5 --enable
./ctl.sh campaign an-01 an-01-matched-3 --profile p5 --enable
./ctl.sh replay an-01-matched-3-emulation-1 --profile p5
./ctl.sh report an-01-matched-3-emulation-1 --profile p5
./ctl.sh verify an-01-matched-3-emulation-1 --profile p5
```

실제 실행 없이 위임 명령만 확인하려면 `--dry-run`을 붙인다.

```bash
./ctl.sh run uplink-dos emulation uplink-check --enable --dry-run
```

`campaign`의 ID를 생략하면 UTC timestamp로 생성한다. 공격·에뮬레이션에는 항상
`--enable`이 필요하고 control에 붙이면 실패한다.

## 공통 실행 결과

공통 입력 runner는 profile의 `run_root` 아래에 다음 파일을 원자적으로 생성한다.

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

`verify`는 여섯 증거 파일의 크기와 SHA-256, run identity, 입력 seq·gap·period를 다시
검사한다. `replay`는 봉인된 `observations.jsonl`을 현재 profile의 production detector에
재생하고 예상 룰의 RAISE 여부를 다시 판정한다. 기존 protocol 모듈은 검증된 runner를 계속
사용하며 공통 형식 이관 전까지 해당 모듈의 기존 artifact 계약이 우선한다.

## profile

`profiles/p5.example.json` 또는 `profiles/ota.example.json`을 같은 디렉터리의 `.json`으로
복사해 실제 경로를 채운다. 실제 profile은 Git에서 제외된다. `doctor`는 다음을 fail-closed로
확인한다.

- `configured=true`, `lab_only=true`, target allowlist와 실행 상한
- detector·telemetry 고정 commit과 실행 파일, detector config SHA-256
- telemetry `period_ms=100`
- credential 파일이 있으면 권한 0600 이하
- OTA는 SDR serial 두 개 이상과 `shielding_confirmed=true`

setup은 module build와 의존 경로를 자동화하지만 credential을 만들거나 RF 케이블·차폐를
대신 확인하지 않는다.

## 환경 준비 범위

`setup`은 다음 반복 작업을 자동화한다.

1. 모듈별 로컬 설정 파일이 없으면 p5용 예제에서 권한 `0600`으로 생성한다.
2. `/root/OAI`를 기준 저장소로 사용해 공격별 고정 commit의 전용 worktree를 만든다.
3. 기존 모듈 빌드기를 실행하고 바이너리의 공격별 마커를 확인한다.
4. 이미 마커가 있는 빌드는 다시 패치하지 않고 재사용한다.

가입자 설정, SSH 개인키, CU 주소, clock·inventory 해시는 자동 생성하지 않는다. 이 값은
랩 자산과 실험 계약이므로 생성된 `conf/*.conf`에서 한 번 검토해야 한다. 시스템 패키지
설치도 자동으로 `sudo`하지 않는다. OAI 빌드 의존성은 호스트에 준비돼 있어야 한다.

기본 p5 경로가 아닌 호스트에서는 경로를 환경변수로 바꿀 수 있다.

```bash
OAI_BASE=/srv/OAI \
BLIND_OAI=/srv/OAI-blind-dos-w38 \
  ./ctl.sh setup blind-dos
```

지원 변수는 `OAI_BASE`, `RRC_OAI`, `BLIND_OAI`, `UPLINK_OAI`,
`AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`, `UE_CAPABILITY_OAI`다.

## 표시되는 재현 유형

| ID | 유형 | 의미 |
|---|---|---|
| `rrc-storm` | 프로토콜 재현 | OAI UE가 RRC 절차를 지정 지점에서 실제 중단 |
| `blind-dos` | 프로토콜 재현 | 유효 5G-GUTI를 실제 RRC·NAS 경로에서 재사용 |
| `auth-timeout` | 프로토콜 재현 | Authentication Request를 받은 UE가 응답을 미전송 |
| `uplink-dos` | 프로토콜 결과 에뮬레이션 | RF 송신 우위 이후의 NAS·서비스 영향을 재현 |
| `uplink-credential-flood` | 프로토콜 재현 | 수정 UE가 실제 RAN 경로에 L3-21 등록 거절 10건을 생성 |
| `downlink-imsi` | 프로토콜 결과 에뮬레이션 | RF overshadowing 이후 식별자 응답 결과를 재현 |
| `ue-capability` | 프로토콜 관측 에뮬레이션 | 보안 전·선행 질의 없는 Capability Information을 F1에 재현 |
| `l3-06`, `an-01`, `an-06a`, `an-02`, `an-04`, `an-07`, `an-08` | 탐지 입력 에뮬레이션 | 연구 기반 메시지 순서를 production detector 기본 설정에 재생 |

컨트롤러의 유형 표시는 기존 모듈의 주장 범위를 바꾸지 않는다. 상세 성공 조건과 탐지 입력,
검증 한계는 각 모듈 README와 사용 가이드를 기준으로 한다.

전체 정규 명칭과 p5/OTA 자격 상태는 [공격 카탈로그](ATTACK-CATALOG.md), 주장 경계는
[주장과 한계](CLAIMS-AND-LIMITS.md)를 따른다.
