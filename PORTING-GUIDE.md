# 다른 테스트베드로 포팅하는 방법

## 먼저 알아둘 결론

이 저장소는 **임의의 PC에서 바로 실행되는 설치형 제품이 아니다.** 현재 자격이 끝난 환경은
Linux x86-64, OAI 2026.w38 UE, OCUDU 26.10 CU/DU, Open5GS, GNU Radio ZMQ 가상 RF로
구성한 p5뿐이다. AWS 자체에 종속된 공격 로직은 없지만, 각 runner의 경로·원격 제어·로그
parser는 이 스택을 기준으로 한다.

| 옮길 환경 | 현재 상태 | 필요한 작업 |
|---|---|---|
| 같은 OAI·OCUDU·Open5GS의 다른 ZMQ 호스트 | 포팅 가능, 미자격 | profile·모듈 conf의 절대경로·IP·SSH hook 변경 후 control부터 재검증 |
| 노트북+USRP+차폐박스 OTA | adapter 미구현 | ZMQ 장치 인자를 USRP로 교체하고 RF inventory·gain·clock·차폐 doctor 및 로그 수집 hook 구현 |
| 다른 gNB·코어 | backend 개발 필요 | build/run adapter와 F1/N2 로그 parser 교체, 기존 oracle·artifact 계약 유지 |
| macOS·Windows 네이티브 | 미지원 | Linux VM 또는 별도 Linux 호스트 사용 |

`qualified`는 p5에서의 자격이다. 다른 환경에 저장소를 복사했다고 그 환경까지 qualified가
되지는 않는다.

ZIP·`scp` 파일 복사본은 사용하지 않는다. 대상 호스트에서 Git clone 또는 `git pull
--ff-only`로 갱신하고 `doctor`가 현재 checkout과 핵심 runner 해시를 확인하게 한다. 공식
runner가 없으면 포팅 실패이며 수동 스크립트를 새로 작성해 대체하지 않는다.

## 호스트 선행조건

runner는 Linux의 GNU 명령 동작을 사용한다. 다음 항목은 자동 설치하지 않는다.

- Bash, Python 3.10 이상, Git, GNU coreutils, `flock`, `setsid`, `pgrep`, `jq`
- OpenSSH client와 고정 `known_hosts`
- OAI 빌드 의존성 및 고정 OAI commit
- OCUDU 26.10 CU/DU와 Open5GS
- ZMQ 포팅: GNU Radio와 ZeroMQ
- 원문 수집 모듈: `tcpdump`, `tshark`
- production detector `766f5569d0ddb425c14bf210a31c38ac60eceef9`
- TeleRAN `7550153a58a993942303bd3d4a6cd635b664468b`, 실행 파일 `portran`

CU와 DU가 나뉜 구성은 SSH로 CU 로그와 N2 원문을 수집한다. 개인키·가입자 설정·실제
profile과 module conf는 Git 밖에 두고 권한을 0600 이하로 설정한다.

## 같은 스택의 다른 ZMQ 환경

1. 저장소를 DU/공격 UE 실행 호스트에 clone하고 `git switch main && git pull --ff-only`를
   실행한다. `git status --short`는 비어 있어야 한다.
2. OAI 기준 저장소를 준비하고 `OAI_BASE`를 실제 절대경로로 지정한다.
3. `profiles/p5.example.json`을 별도 profile 디렉터리에 복사해 `configured=true`, CU/DU
   endpoint, detector·telemetry·run 경로를 실제 값으로 바꾼다.
4. 모듈별 conf를 Git 밖에 만들고 아래 profile environment 키로 절대경로를 연결한다.
5. `doctor → setup → control → active` 순서로 실행한다. control이 등록·PDU·ping과
   telemetry gap 0을 통과하기 전에는 공격을 실행하지 않는다.

p4에서는 `profiles/p4.example.json`을 `profiles/p4.json`으로 복사한다. `backend` 이름은
현재 ZMQ adapter 호환을 위해 `p5`로 유지하되 profile ID와 endpoint·allowlist·credential
경로는 p4 값으로 채운다. 이후 다음 명령이 실패하면 공격을 실행하지 않는다.

```bash
./ctl.sh doctor --profile p4
```

L3-01-O는 `auth-stall-cell-run`의 `2프로세스×5 UE`, L3-20은 direct 2-cell runner만
자격 경로다. 자세한 실행표는 [E2E 실행 가이드](E2E-EXECUTION-GUIDE.md)를 따른다.

profile에서 사용할 수 있는 module conf 키는 다음과 같다.

| 모듈 | profile environment 키 |
|---|---|
| RRC 컨텍스트 고갈 | `RSS_CONF` |
| Blind DoS | `BLIND_CONF` |
| 상향 DoS·L3-21 | `UPLINK_CONF` |
| 인증 응답 미전송 | `AUTH_TIMEOUT_CONF` |
| 하향 식별자 노출 | `DOWNLINK_IMSI_CONF` |
| UE Capability | `UE_CAPABILITY_CONF` |
| NAS 카운터 비동기화 | `NAS_DESYNC_CONF` |

예:

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

```bash
export RAN_REPRO_PROFILE_DIR=/etc/ran-reproducer/profiles
./ctl.sh doctor blind-dos --profile lab-zmq
./ctl.sh setup blind-dos --profile lab-zmq
./ctl.sh run blind-dos control blind-control-1 --profile lab-zmq
./ctl.sh run blind-dos attack blind-attack-1 --profile lab-zmq --enable
```

profile은 경로를 전달할 뿐 OCUDU/Open5GS를 설치하거나 가입자·SSH key를 만들지 않는다.
모듈 conf의 `DU_CTL`, `CU_CTL`, `CORE_CONTAINER`, interface, ZMQ endpoint와 TUN 이름도 새
환경에 맞게 검토해야 한다.

## OTA 포팅

현재 `./ctl.sh setup|run|campaign --profile ota`는 실패하도록 막혀 있다. 아래 adapter가
없는 상태에서 p5용 ZMQ 설정을 OTA로 오인해 실행하지 않기 위해서다.

1. `profiles/ota.example.json`에 실제 SDR serial, clock source, gain 상한을 기록한다.
2. RF 케이블·감쇠기·차폐박스를 사람이 확인한 뒤에만 `shielding_confirmed=true`로 바꾼다.
3. 각 protocol 모듈에 USRP용 UE 인자와 DU RF 설정을 전달하는 run adapter를 만든다.
4. F1/N2 수집과 UE oracle을 기존 `run_id`·monotonic timestamp로 조인한다.
5. 정상 UE attach·Registration·PDU·ping을 먼저 통과시킨다.
6. control→attack/emulation을 3세트 실행해 새 환경의 artifact를 별도로 봉인한다.

RF 원인이 없는 결과 에뮬레이션은 OTA에서 실행됐더라도
`rf_cause_observed=false`를 유지한다.

## 포팅 완료 조건

- gNB·코어·detector에 공격 성공을 보상하는 수정이 없다.
- 동일 manifest rule ID와 공통 run/verdict/evidence 구조를 유지한다.
- control과 active run의 바이너리·설정·runner 해시가 같다.
- telemetry `period_ms=100`, sequence 연속, gap 0, timestamp 비역행을 확인한다.
- production detector 기본 설정에서 control 0/3, active 3/3을 확인한다.
- UE·코어 oracle은 detector 출력 봉인 뒤에만 조인한다.
- 새 환경의 한계와 `live_protocol_path_observed`, `rf_cause_observed`,
  `service_denial_observed`를 사실대로 기록한다.
