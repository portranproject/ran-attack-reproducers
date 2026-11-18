# 통합 컨트롤러 사용 가이드

`ctl.sh`는 각 공격 모듈을 합치지 않고 기존 빌드기·runner·판정기와 공통 detector replay를
한 화면에서 호출한다. 실행 원문과 라벨 계약은 계속 각 `reproducers/<attack>/`에 분리된다.
7개 L3 공격은 1.0 자격 대상으로, 6개 AN fixture는 참고용 detector 회귀로 검색한다.

> 처음 설치하거나 다른 환경으로 옮길 때는 [L3 공격 7종 E2E 실행 가이드](E2E-EXECUTION-GUIDE.md)를
> 먼저 따른다. 공식 runner가 없거나 `doctor`가 실패하면 OAI 바이너리 직접 실행이나
> `/tmp` 수동 스크립트로 대체하지 않는다.

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

`doctor`는 profile뿐 아니라 Git checkout, 최소 자격 커밋, 추적 파일 변경 여부와 핵심
runner 해시를 확인한다. Git 없는 파일 복사본, 구버전, 수정된 runner는 실행 환경으로
인정하지 않는다.

실제 실행 없이 위임 명령만 확인하려면 `--dry-run`을 붙인다.

```bash
./ctl.sh run uplink-dos emulation uplink-check --enable --dry-run
```

`campaign`의 ID를 생략하면 UTC timestamp로 생성한다. 공격·에뮬레이션에는 항상
`--enable`이 필요하고 control에 붙이면 실패한다.

## 정상 UE 5대 same-cell L3 자격

L3 7종을 정상 UE 5대와 같은 셀에서 검증할 때는 일반 `run|campaign`이나 모듈 runner를
직접 호출하지 않고 다음 공개 명령을 사용한다.

```bash
./ctl.sh same-cell doctor --profile p5
./ctl.sh same-cell run rrc-storm --profile p5 --mode control --run-id rrc-control-1
./ctl.sh same-cell run rrc-storm --profile p5 --mode attack --run-id rrc-attack-1 --enable
./ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable
```

`l3-live` 대상은 L3-01-V·L3-01-O·L3-20·L3-21·L3-24·L3-14·L3-06으로 고정한다. AN
fixture와 legacy uplink MAC 단발 변조형은 포함하지 않는다. `--sets 3`, `--count 5`도 자격
계약이라 다른 값으로 완화할 수 없다. control에는 `--enable`을 붙이지 않고, attack 또는
emulation에는 반드시 붙인다.

모든 phase는 같은 CU·DU EC2 인스턴스와 같은 셀 식별자를 사용한다. 공격 전환 때는 이전
실행의 무선 상태를 물려받지 않도록 DU·broker·UE 프로세스를 정리하고 cold-start한다.
CU·코어·production dashboard는 유지한다. 정상 UE 5대와 공격 슬롯은 DU 시작 전에 모두
broker에 연결하며, 정상 UE의 공격 전과 종료 직전 Registration·PDU·gateway ping 상태를
실행 증거에 남긴다.

정상 UE 5대는 OAI 설정의 `RUs`·`cells`·`zmq` 배열로 만든 독립 virtual RU/ZMQ endpoint
5개를 사용한다. indexed CLI ZMQ 옵션은 사용하지 않는다. 단일 shared RU 경로는 p5에서
channel timeout 약 9만 건과 서비스 1/5로 실패했으므로 자격 경로가 아니다.

공격 슬롯은 대기 중에도 downlink를 받아 DU와 같은 sample clock을 유지한다. broker가 공격
uplink를 활성화했다는 응답을 남긴 뒤 공격별 adapter가 UE 동작을 연다. RRC storm은 전용
gate를, 나머지 live L3 모듈은 공통 RA gate를 사용한다. Blind DoS는 피해 UE에만 공통 gate를
적용하고 공격 UE는 기존 GUTI target gate를 유지한다. 따라서 대기 중 PRACH 재시도를 소진하거나,
UE가 먼저 송신했지만 broker가 아직 버린 구간을 공격 성공으로 세지 않는다. 공격 runner가
완료를 게시하면 broker가 공격 uplink를 먼저 닫고 정상 UE 5/5 회복을 확인한다. 인증 미응답형은
공격 UE의 재시도를 끝내기 위해 UE를 먼저 종료한 뒤 회복을 측정하고 그 순서를 증거에 표시한다.

이 경로는 직접 KPM이나 detector 입력을 만들지 않는다. 실제
`UE → ZMQ → DU/CU → TeleRAN → production detector → dashboard` 경로만 자격으로 인정한다.
다만 에뮬레이션 모듈의 주장 범위는 바뀌지 않는다. L3-24는 RF overshadowing 이후 결과,
L3-14는 MITM 이후 관측 신호, L3-06은 요청되지 않은 SecurityModeReject 결과를 UE에서
생성할 뿐 원래 RF·MITM·counter-wrap 원인을 재현한 것이 아니다.

새 통합 경로를 코드에 추가한 것과 p5 자격 통과는 별개다. 현재 L3-21의 정상 UE 5대
matched 3/3만 기존 봉인 근거가 있다. Blind DoS·L3-01-O·L3-06을 포함한 새 7종 캠페인은
p5에서 control→active 3/3과 dashboard 전송을 새로 봉인하기 전까지 **구현됐으나 미자격**으로
표시한다. 기존 direct 경로의 자격은 유지하지만 same-cell 자격으로 바꾸어 적지 않는다.

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

p5 자격 검증에서는 `tools/p5-live-e2e`가 기존 runner를 감싸고 TeleRAN과 production
detector를 같은 실행 시간창에 기동한다. 직접 KPM이나 탐지 이벤트를 생성하지 않으며,
실제 F1/N2 계측 원문만 detector에 전달한다. 검증기는 100 ms 보고 주기, sequence 연속성,
gap 0, KPM 존재, 예상 RAISE 수, dashboard 수락과 child 기전 판정을 함께 확인한다.
2026-11-17 다섯 룰의 matched 3/3 결과는
[E2E 자격 요약](artifacts/p5-live-e2e-five-20261117/)을 따른다.

## profile

`profiles/p4.example.json`, `profiles/p5.example.json` 또는 `profiles/ota.example.json`을
같은 디렉터리의 `.json`으로 복사해 실제 경로를 채운다. 실제 profile은 Git에서 제외된다.
`doctor`는 다음을 fail-closed로 확인한다.

- Git clone과 최소 자격 커밋, clean tracked worktree, 핵심 runner SHA-256
- `configured=true`, `lab_only=true`, target allowlist와 실행 상한
- detector·telemetry 고정 commit과 실행 파일, detector config SHA-256
- telemetry `period_ms=100`
- p5의 경우 `credentials_file`의 `SSH_KEY`·`KNOWN_HOSTS`로 CU production 구성 원격 확인
- DU의 공통 실행 명령과 L3-24·L3-14 증거 수집에 필요한 `tshark`
- credential 파일이 있으면 권한 0600 이하
- OTA는 SDR serial 두 개 이상과 `shielding_confirmed=true`

명시적으로 `--profile`을 붙인 protocol 실행은 profile의 environment를 runner에 전달한다.
모듈별 conf를 저장소 밖에 둘 때는 `RSS_CONF`, `BLIND_CONF`, `UPLINK_CONF`,
`AUTH_TIMEOUT_CONF`, `DOWNLINK_IMSI_CONF`, `UE_CAPABILITY_CONF`, `NAS_DESYNC_CONF` 중
해당 키에 절대경로를 넣는다. 현재 OTA run adapter는 없으므로 OTA profile의
`setup|run|campaign`은 실행하지 않고 [포팅 가이드](PORTING-GUIDE.md)를 안내한다.

setup은 module build와 의존 경로를 자동화하지만 시스템 패키지·OCUDU·Open5GS를
설치하거나 credential을 만들거나 RF 케이블·차폐를 대신 확인하지 않는다. 지원 호스트와
선행 패키지는 [포팅 가이드](PORTING-GUIDE.md)를 따른다.

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
`AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`, `UE_CAPABILITY_OAI`, `NAS_DESYNC_OAI`다.

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
| `l3-06` | 프로토콜 결과 에뮬레이션 | UE가 요청되지 않은 NAS SecurityModeReject를 실제 RAN·계측 경로로 송신. MITM·counter wrap은 범위 밖 |
| `an-01`, `an-06a`, `an-02`, `an-04`, `an-07`, `an-08` | 참고용 탐지 입력 fixture | 공격 1.0 자격 범위 밖. production detector 회귀에만 사용 |

컨트롤러의 유형 표시는 기존 모듈의 주장 범위를 바꾸지 않는다. 상세 성공 조건과 탐지 입력,
검증 한계는 각 모듈 README와 사용 가이드를 기준으로 한다.

기존 개별 자격에서 L3-01-O는 한 셀 10 UE 전용 `auth-stall-cell-run`, Blind DoS는 direct
2-cell이다. 새 same-cell 컨트롤러가 내부 adapter로 이 동작을 조합하지만, 사용자가 해당
runner를 직접 호출해서 통합 자격을 만들지는 않는다. 정확한 lifecycle과 금지 조합은
[E2E 실행 가이드](E2E-EXECUTION-GUIDE.md)에 고정한다.

전체 정규 명칭과 p5/OTA 자격 상태는 [공격 카탈로그](ATTACK-CATALOG.md), 주장 경계는
[주장과 한계](CLAIMS-AND-LIMITS.md)를 따른다.
