# 통합 컨트롤러 사용 가이드

`ctl.sh`는 각 공격 모듈을 합치지 않고, 기존 빌드기·runner·판정기를 한 화면에서 호출하는
얇은 통합 컨트롤러다. 실행 원문과 라벨 계약은 계속 각 `reproducers/<attack>/`에 분리된다.

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
  검증한다. 동결된 RRC 모듈은 이 공통 캠페인을 지원하지 않는다.

공격·에뮬레이션은 메뉴에서 `ENABLE`을 입력해야 실행된다. CLI에서도 `--enable`을 생략하면
중단한다. 각 모듈 자체의 `-e 1` 게이트도 그대로 유지된다.

## CLI 사용법

```bash
./ctl.sh list
./ctl.sh doctor all
./ctl.sh setup blind-dos
./ctl.sh run blind-dos control blind-smoke-control
./ctl.sh run blind-dos attack blind-smoke-attack --enable
./ctl.sh campaign blind-dos blind-matched-3 --enable
```

실제 실행 없이 위임 명령만 확인하려면 `--dry-run`을 붙인다.

```bash
./ctl.sh run uplink-dos emulation uplink-check --enable --dry-run
```

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
`AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`다.

## 표시되는 재현 유형

| ID | 유형 | 의미 |
|---|---|---|
| `rrc-storm` | 프로토콜 재현 | OAI UE가 RRC 절차를 지정 지점에서 실제 중단 |
| `blind-dos` | 프로토콜 재현 | 유효 5G-GUTI를 실제 RRC·NAS 경로에서 재사용 |
| `auth-timeout` | 프로토콜 재현 | Authentication Request를 받은 UE가 응답을 미전송 |
| `uplink-dos` | 프로토콜 결과 에뮬레이션 | RF 송신 우위 이후의 NAS·서비스 영향을 재현 |
| `downlink-imsi` | 프로토콜 결과 에뮬레이션 | RF overshadowing 이후 식별자 응답 결과를 재현 |

컨트롤러의 유형 표시는 기존 모듈의 주장 범위를 바꾸지 않는다. 상세 성공 조건과 탐지 입력,
검증 한계는 각 모듈 README와 사용 가이드를 기준으로 한다.
