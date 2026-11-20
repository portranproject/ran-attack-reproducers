# L3 공격 7종 E2E 실행 가이드

이 문서는 팀원과 AI가 검증된 토폴로지와 공식 runner만 사용하도록 고정한 운영 기준이다. 공격 이론과 개별 판정 기준은 각 모듈 README를 따르며, 여기서는 설치·토폴로지·실행 진입점·합격 조건만 정한다.

## 필수 원칙

1. ZIP·파일 복사본이 아니라 Git clone을 사용한다.
2. 개별 모듈은 `./ctl.sh doctor --profile <환경>`, 정상 UE 5대 통합 실행은 `./ctl.sh same-cell doctor --profile <환경>`을 먼저 통과한다.
3. 공식 runner가 없거나 `doctor`가 실패하면 중단한다. OAI 바이너리 직접 실행이나 `/tmp` 수동 스크립트로 대체하지 않는다.
4. `control`을 먼저 실행하고 `attack`·`emulation`에는 `--enable`을 붙인다.
5. CU·DU 인스턴스는 그대로 재사용한다. runner가 공격별 DU **프로세스와 설정**을 시작·정리할 수 있지만 인스턴스를 새로 만들거나 삭제하지 않는다.

## 처음 설치 및 환경 준비 (`p1`·`p5`)

```bash
git clone https://github.com/portranproject/ran-attack-reproducers.git
cd ran-attack-reproducers
git switch main
git pull --ff-only
git status --short
```

패킷·실행 도구 설치(`setup`은 시스템 패키지를 자동 설치하지 않는다):
- **CU 호스트**: `tcpdump`, `tshark` (`tools/reproctl.py`가 SSH로 확인)
- **DU 호스트**: `tshark`, `timeout` (`ctl.sh same-cell doctor`가 로컬 확인; 원문 수집 필요 시 `tcpdump` 포함)

```bash
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y tcpdump tshark
```

`git status --short`가 비어 있어야 한다. `p1` 기준 실제 설정 파일은 Git 밖에 권한 `0600` 이하로 준비한다.

```bash
cp profiles/p1.example.json profiles/p1.json
chmod 600 profiles/p1.json
install -m 600 profiles/live-e2e.example.conf /root/.config/ran-reproducer/p1-live-e2e.env
# /root/.config/ran-reproducer/p1.env (credentials_file, 0600 이하)를 생성해 SSH_KEY·KNOWN_HOSTS를 기록한다.
# p1.json의 endpoint·target_allowlist와 p1-live-e2e.env의 CU_HOST·SSH_KEY·KNOWN_HOSTS·인터페이스를 채운다.
./ctl.sh normal-ue setup --profile p1
./ctl.sh normal-ue build --profile p1
./ctl.sh setup all --profile p1
./ctl.sh doctor --profile p1
./ctl.sh same-cell doctor --profile p1
```

`credentials_file`(`p1.env`)과 `LIVE_E2E_CONF`(`p1-live-e2e.env`)의 `SSH_KEY`·`KNOWN_HOSTS` 경로는 같아야 한다. profile의 `CU_PLATFORM_ROOT`는 CU의 detector·telemetry 상위 경로이며 `CU_DASHBOARD_ENV`와 `CU_TELEMETRY_NODE`는 환경 이름(`p1`, `p1-e2e` 등 소문자·숫자·하이픈)을 사용한다.

## L3 7종 `same-cell` 통합 실행

공개 진입점은 아래 세 명령뿐이다.

```bash
./ctl.sh same-cell doctor --profile p5
./ctl.sh same-cell run blind-dos --profile p5 --mode control --run-id blind-control-1
./ctl.sh same-cell run blind-dos --profile p5 --mode attack --run-id blind-attack-1 --enable
./ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable
```

- **대상 및 모드**: `l3-live`는 L3-01-V·L3-01-O·L3-20·L3-21·L3-24·L3-14·L3-06 7종만 포함한다(AN fixture와 레거시 `uplink-dos` MAC 변조형 제외). 프로토콜 재현은 `attack`, 결과·관측 에뮬레이션은 `emulation`을 사용하며 `--sets 3 --count 5`로 고정한다.
- **프로세스 생명주기**: 같은 CU·DU 인스턴스와 셀 식별자를 유지한 채 각 `control`/`active` phase마다 DU·broker·UE 프로세스를 정리하고 cold-start한다. CU·코어·dashboard는 유지한다. 실행 중 RF 스트림에 UE를 hot-swap하는 방식이 아니므로 dashboard 시간축에 phase 간 재시작 구간이 남는다.
- **정상 UE 5대 게이트**: 정상 UE 5대는 OAI `RUs`·`cells`·`zmq` 배열의 독립 virtual RU 5개를 사용한다(공유 RU 경로는 미승인). DU 시작 전 정상 UE 5대와 공격 슬롯이 broker에 연결되며, 공격 전과 종료 직전 정상 UE 5대의 Registration·PDU·gateway ping `5/5`를 기록한다. 공격 슬롯은 대기 중 downlink clock을 유지하고 broker 활성화 응답 뒤 공격별 게이트(`rrc-storm` 전용 게이트, `blind-dos` 피해 UE 공통 RA 게이트 + 공격 UE GUTI 게이트, 나머지 공통 RA 게이트)로 열린다.
- **경로 및 주장 경계**: 탐지 입력을 직접 만들거나 KPM/detector 소켓으로 주입하지 않으며 `UE → ZMQ broker → DU/CU → TeleRAN → production detector → dashboard` 경로만 인정한다. L3-24·L3-14·L3-06은 UE 측 에뮬레이션이며 RF overshadowing·MITM·실제 NAS counter wrap 원인을 주장하지 않는다.

## 기존 개별 자격 토폴로지 (이력 기준)

모든 기존 자격도 **CU 1대 + DU 1대**를 순차 재사용했다(Blind DoS의 2-cell은 동일 DU 프로세스의 논리 셀 2개). 새 `same-cell` 자격을 만들 때는 이 runner를 직접 호출하지 않고 위 `ctl.sh same-cell`을 사용한다. 기존 개별 자격을 `same-cell` 자격으로 옮겨 적지 않는다.

| 룰 | 공격 runner 진입점 | 기존 자격 토폴로지 | 당시 비승인·제외 경로 |
|---|---|---|---|
| L3-01-V | `ctl.sh campaign rrc-storm` | 1 DU·1 cell | 임의 timer/capacity 완화 |
| L3-06 | `ctl.sh campaign l3-06` | direct 1-cell | 정상 UE same-cell (p5 2026-11-17 기준) |
| L3-24 | `ctl.sh campaign downlink-imsi` | direct 1-cell | RF 원인 재현 주장 |
| L3-14 | `ctl.sh campaign ue-capability` | direct 1-cell | MITM·내용 변조 주장 |
| L3-21 | `ctl.sh campaign uplink-credential-flood` | 한 UE가 10개 실패 연결 생성 | 단발 MAC 변조를 L3-21로 주장 |
| L3-01-O | `ctl.sh campaign auth-timeout` | 한 셀, 2 OAI 프로세스×5 UE, shared endpoint 2개 | 한 프로세스 `--num-ues 10` |
| L3-20 | `bin/blind-run`·`bin/blind-p5-phase` | direct 2-cell, victim·attacker 동시 실행 | 순차 재사용·직접 same-cell |

## E2E 합격 조건

공격별 `control → attack/emulation` 3세트를 실행해 아래를 모두 만족해야 한다.

- 기존 모듈 기전 판정 통과
- `UE → ZMQ → DU/CU → TeleRAN → production detector → dashboard` 경로 사용
- TeleRAN `period_ms=100`, sequence 연속, `gap=0`, `kpm2` 존재
- `control`의 대상 룰 경보 `0건`, `active`의 대상 룰 `RAISE` `1건 이상`(`tools/verify_live_e2e.py` 판정 기준 `>= 1`; p1/p5 실측에서는 각 `1건`)
- dashboard 수락 `1건 이상`·거절 `0건`
- runner·바이너리·설정·증거 SHA-256 봉인
- (`same-cell`) 정상 UE 5대의 공격 전·종료 직전 Registration·PDU·ping `5/5` 봉인
- **dashboard 전송 시점**: 기본값 `CU_DASHBOARD_FOLLOW=1`은 관측이 시작되는 지점(`tools/p5-live-e2e`는 baseline 뒤 detector 재기동 직후, `LIVE_E2E_WAIT_FOR_BASELINE=0`이면 `start_live()` 직후, L3-21·L3-06 runner는 `start_live()` 끝)에서 전송기를 따라가기 모드로 띄워 경보·KPM을 실행 중에 보내고, 종료 시 telemetry·detector를 내린 뒤 SIGTERM으로 멈추고 `--once`로 나머지를 이어 보낸다(같은 `sender.json`, `sender.stdout`·`sender.log`는 이어쓰기). `CU_DASHBOARD_FOLLOW=0`이면 지금처럼 실행이 끝난 뒤 `dashboard_sender.py --once` 한 번만 전송한다. 검증 판정 기준은 두 모드 모두 같다.

2026-11-19 p1 clean-origin에서는 이 절차로 L3 7종 42/42를 통과했다([p1 자격 기록](../artifacts/p1-clean-origin-live-e2e-20261119/README.md)). p1·p5 자격을 p4나 OTA 자격으로 복사하지 않는다.

## 실패 시 보존 절차

수동 스크립트로 우회하지 않고 아래 자료를 그대로 보존한다. 공식 토폴로지와 다른 실행은 공격 실패가 아니라 **시험 무효**로 분류한다.

- `git rev-parse HEAD`, `git status --short`
- 실행 명령과 profile 이름
- runner·OAI UE·DU 설정 SHA-256
- UE·broker·DU·CU·detector 로그와 run 디렉터리
- 인스턴스 유형, 셀 수, UE 프로세스×논리 UE 수
