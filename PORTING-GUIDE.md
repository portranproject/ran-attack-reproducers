# 다른 테스트베드로 포팅하는 방법

이 저장소는 임의의 PC에서 바로 실행되는 설치형 제품이 아니다. 현재 자격이 확인된 환경은 Linux x86-64, OAI 2026.w38 UE, OCUDU 26.10 CU/DU, Open5GS, GNU Radio ZMQ 가상 RF로 구성된 `p5`와 clean-origin에서 재설치한 `p1`이다.

## 환경별 지원 범위

| 대상 환경 | 현재 상태 | 필요한 작업 |
|---|---|---|
| `p1` clean-origin | 자격 완료 | 정상 UE 5대 same-cell L3 7종 42/42 ([p1 자격 기록](artifacts/p1-clean-origin-live-e2e-20261119/README.md)) |
| `p5` ZMQ | 자격 완료 | 개별·live L3 7종 통과 ([p5 운영](#p5-운영-체크리스트)) |
| `p4` 등 동일 스택 ZMQ 호스트 | 포팅 가능, 미자격 | `backend: "p5"` profile·모듈 conf·credential 작성 후 control부터 재검증 |
| 노트북+USRP+차폐박스 OTA | adapter 미구현 | USRP UE/DU run adapter 구현 및 RF inventory·차폐 게이트 적용 ([OTA 운영](#차폐-ota-운영-체크리스트)) |
| 다른 gNB·코어 | 백엔드 개발 필요 | build/run adapter와 F1/N2 로그 parser 교체(기존 oracle·artifact 계약 유지) |
| macOS·Windows 네이티브 | 미지원 | Linux VM 또는 별도 Linux 호스트 사용 |

`p1` 또는 `p5` 자격을 다른 환경으로 복사해 적지 않는다. 대상 호스트에서는 반드시 Git clone과 `git pull --ff-only`로 깨끗한 checkout을 유지한다(ZIP/`scp` 복사본 불가).

## 호스트 선행조건

runner는 Linux GNU 명령을 사용하며 아래 패키지를 자동 설치하지 않는다.

- Bash, Python 3.10 이상, Git, GNU coreutils, `flock`, `setsid`, `pgrep`, `jq`, `timeout`, `sha256sum`
- OpenSSH client와 고정 `known_hosts`
- OAI 빌드 의존성 및 기준 OAI 저장소(`OAI_BASE`)
- OCUDU 26.10 CU/DU와 Open5GS
- ZMQ 환경: GNU Radio와 ZeroMQ
- 패킷 도구: CU `tcpdump`·`tshark`, DU `tshark`
- 고정 production 컴포넌트(`integration.lock.json`):
  - detector `766f5569d0ddb425c14bf210a31c38ac60eceef9`
  - TeleRAN `7550153a58a993942303bd3d4a6cd635b664468b` (`portran`, `period_ms=100`)
  - dashboard `01a1a44a12ed7b3b6a1fe7465849d1f3daa41e20`

## 같은 스택의 다른 ZMQ 호스트 포팅 (`p1`·`p4`·커스텀)

1. DU/공격 UE 호스트에 저장소를 clone하고 `git status --short`가 비어 있는지 확인한다.
2. `profiles/p1.example.json`, `profiles/p4.example.json`, `profiles/p5.example.json` 중 하나를 같은 디렉터리(또는 `RAN_REPRO_PROFILE_DIR`)의 `<profile>.json`(`0600`)으로 복사해 `configured=true`, CU/DU endpoint, detector·telemetry·run 경로를 채운다. (`p4`는 `backend`를 `"p5"`로 유지한다.)
3. Git 밖에 권한 `0600` 이하의 `credentials_file`(`SSH_KEY`, `KNOWN_HOSTS`)과 `LIVE_E2E_CONF`(`profiles/live-e2e.example.conf` 참고)를 만들고 두 파일의 SSH 경로를 일치시킨다. `CU_DASHBOARD_ENV`는 소문자·숫자·하이픈만 사용한다.
4. 모듈별 `conf/*.conf`를 준비하거나 profile `environment`에 외부 절대경로를 지정한다.
   - 지원 키: `RSS_CONF`, `BLIND_CONF`, `UPLINK_CONF`, `AUTH_STALL_CELL_CONF`, `DOWNLINK_IMSI_CONF`, `UE_CAPABILITY_CONF`, `NAS_DESYNC_CONF`, `NORMAL_UE_CONF`
   - 추가 경로 키: `OAI_BASE`, `RRC_OAI`, `BLIND_OAI`, `UPLINK_OAI`, `AUTH_TIMEOUT_OAI`, `DOWNLINK_IMSI_OAI`, `UE_CAPABILITY_OAI`, `NAS_DESYNC_OAI`
5. `./tools/ctl.sh normal-ue setup --profile <name>`과 `./tools/ctl.sh normal-ue build --profile <name>`으로 정상 UE 5대 설정·빌드를 준비한다.
6. `./tools/ctl.sh setup all --profile <name>` → `./tools/ctl.sh doctor --profile <name>` → `./tools/ctl.sh same-cell doctor --profile <name>`을 통과한 뒤 [E2E 실행 가이드](docs/E2E-EXECUTION-GUIDE.md) 순서로 `control → active`를 검증한다.

준비가 끝나면 DU에서 `./run.sh`를 실행한다. `RAN_REPRO_PROFILE_ID`에 설정 이름을 지정하거나 `profiles/du.json`을 준비하면 매번 프로필을 선택하지 않아도 된다. 둘 다 없으면 준비 완료된 ZMQ 설정이 하나일 때 자동 적용한다. 자세한 선택 순서는 [사용자 화면](docs/CONTROL-GUIDE.md#사용자-화면)을 따른다.

모듈 `conf/*.conf`의 `DU_CTL`, `CU_CTL`, `CORE_CONTAINER`, 네트워크 인터페이스, ZMQ endpoint, TUN 이름도 새 호스트에 맞게 검토해야 한다. `DU_CTL`·`CU_CTL`의 `/root/workspace/ctl.sh`는 테스트베드 기동용 외부 스크립트이며 이 저장소의 `tools/ctl.sh`와 별개다.

```json
"environment": {
  "OAI_BASE": "/opt/oai",
  "BLIND_OAI": "/opt/oai-blind",
  "BLIND_CONF": "/etc/ran-reproducer/blind.conf",
  "P5_CU_HOST": "lab-cu.example",
  "P5_DU_HOST": "lab-du.example",
  "P5_CU_PRIVATE_IP": "10.10.0.10",
  "P5_DU_PRIVATE_IP": "10.10.0.11"
}
```

## OTA 포팅

현재 `./tools/ctl.sh setup|run|campaign --profile ota` 및 `same-cell run|campaign`은 p5 ZMQ 설정을 OTA로 오인 실행하지 않도록 실패한다(`tools/ctl.sh:96-99`). OTA를 포팅할 때는 아래 순서를 따른다.

1. `profiles/ota.example.json`을 `profiles/ota.json`(`0600`)으로 복사해 실제 SDR serial, clock source, gain 상한을 기록한다(추적되는 `.example.json`은 수정하지 않는다).
2. 사람이 RF 케이블·감쇠기·차폐박스를 점검한 뒤에만 `shielding_confirmed=true`로 바꾼다.
3. 각 Uu 모듈에 USRP용 UE 인자와 DU RF 설정을 전달하는 OTA run adapter를 구현한다.
4. F1/N2 수집과 UE oracle을 `run_id`·단조 타임스탬프로 조인한다.
5. 정상 UE attach·Registration·PDU·ping 통과 후 `control → active` 3세트를 봉인한다. RF 원인이 없는 결과 에뮬레이션은 OTA에서도 `rf_cause_observed=false`를 유지한다.

## p5 운영 체크리스트

- **인스턴스 원칙**: 기본 자원 상한은 `role=cu` 1대와 `role=du` 1대다. 과거 `rss-smooth-lane` 인스턴스는 서비스 거부 재현을 위해 다시 켜지 않으며, stopped 상태의 같은 세트 인스턴스를 모두 켜는 제어판 `start`는 기본 검증에 직접 쓰지 않는다. 실행 전후 EC2 tag·state와 CU/DU instance ID를 읽기 전용으로 조회하고, 종료 시 같은 두 ID만 `stopped`인지 확인한다.
- **실행 전 점검**: `./tools/ctl.sh doctor --profile p5` 기본 `target=all`은 manifest 13개, CU 원격 production 컴포넌트(detector `766f5569...`·TeleRAN `7550153a...` `period_ms=100`·`tcpdump`/`tshark`), checkout·runner 해시와 **로컬 모듈 14개(OAI 빌드 8개 포함)의 conf와 UE 바이너리**까지 확인한다. 특정 모듈만 점검하려면 `./tools/ctl.sh doctor <ID> --profile p5`를 쓰고, `same-cell` 실행 전에는 `./tools/ctl.sh same-cell doctor --profile p5`를 통과한다.
- **실행·정리·자격 범위**: 정상 CU→DU 기동과 정상 UE attach·PDU·ping을 확인한 뒤 `control`을 먼저 실행하고 `active`에는 `--enable`을 붙인다. 중단·timeout 후에는 UE·broker·DU·TeleRAN·detector 잔존 프로세스가 없는지와 설정 원복을 확인한다. 대용량 원시 로그는 p5 원격에 두고 Git에는 요약·판정·SHA-256만 남긴다. p5에서는 L3 7종 모두 개별 또는 live E2E matched 3/3을 통과했으며([5종 E2E 요약](artifacts/p5-live-e2e-five-20261117/README.md)), AN fixture 6종은 공격 1.0 자격 범위 밖의 회귀 replay로만 유지한다.

## 차폐 OTA 운영 체크리스트

공통 OTA run adapter는 아직 구현되지 않았고 실제 SDR inventory와 차폐 확인이 없으므로 모든 OTA 자격은 `pending`이다(`tools/ctl.sh:96-99` 차단 유지). adapter 구현 뒤 승인 절차는 다음과 같다.

1. `profiles/ota.json`(`0600`)에 공격 UE와 O-DU SDR의 서로 다른 serial, clock source, gain 상한을 기록한다.
2. RF 케이블·감쇠기·차폐박스가 외부 누설을 막는지 사람이 직접 점검한 뒤에만 `shielding_confirmed=true`로 바꾼다.
3. `./tools/ctl.sh doctor --profile ota`로 SDR inventory, `credentials_file` 권한, detector·telemetry 경로와 `period_ms=100`을 확인한다.
4. 공격 기능을 끈 정상 UE로 attach·Registration·PDU·ping과 TeleRAN `gap=0`을 먼저 통과시킨다.
5. Uu 프로토콜 모듈(L3 7종)만 matched `control → attack/emulation` 3세트를 실행하고 매 세트 뒤 정상 회복을 확인한다.
6. p5 ZMQ와 OTA의 메시지 흐름, input gap, detector 지연을 비교 기록한다.

RF 원인이 없는 AN `detector-input-emulation` 모듈은 OTA에서 실행하지 않고 `not-applicable`로 둔다. 결과 에뮬레이션 모듈(`L3-24`, `L3-14`, `L3-06`, `uplink-dos`)은 OTA에서 동작하더라도 RF overshadowing·MITM을 별도 계측하지 않았다면 `rf_cause_observed=false`를 유지한다.

## 포팅 완료 조건

- gNB·코어·detector에 공격 성공을 유도하는 코드/timer/capacity 수정이 없다.
- 동일 `rule_ids`와 `run`/`verdict`/`evidence` 계약을 유지한다.
- `control`과 `active` 실행의 바이너리·설정·runner SHA-256이 일치한다.
- TeleRAN `period_ms=100`, sequence 연속, `gap=0`, 타임스탬프 비역행을 만족한다.
- production detector 기본 설정에서 `control` 0/3, `active` 3/3을 확인한다.
- UE·코어 oracle은 detector 출력 봉인 뒤에만 조인하고 `live_protocol_path_observed`, `rf_cause_observed`, `service_denial_observed`를 사실대로 기록한다.
