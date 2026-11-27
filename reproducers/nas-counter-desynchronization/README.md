# 요청되지 않은 NAS SecurityModeReject 결과 (L3-06)

OAI UE가 선행 NAS `SecurityModeCommand` 없이 상향 `SecurityModeReject`를 한 번 송신해, 5GReasoner 계열 Uplink NAS Counter Desynchronization의 탐지 입력 신호를 실제 UE→RAN→TeleRAN→detector 경로로 재현하는 에뮬레이션 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-06` |
| `reproducer.json` id | `nas-counter-desynchronization` |
| `tools/ctl.sh` ID / 별칭 | `nas-counter-desynchronization` (`l3-06`) |
| 재현 수준 (`reproduction_level`) | `protocol-result-emulation` |
| active 모드 (`active_mode`) | `emulation` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` direct 1-cell 6/6 통과 (`p5` same-cell 미승인), `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 정상 `Authentication Response`를 제출한다.

## 동작 요약

```text
OAI UE                       OCUDU DU/CU / Open5GS          TeleRAN → detector
   │ Authentication Request  │                                │
   │<────────────────────────│                                │
   │ (control)   AuthenticationResponse → 정상 등록/PDU/ping  │
   │ (emulation) SecurityModeReject(1회) ────────────────────>│ L3-06 RAISE
```

- **control** (`-e 0`): 정상 `Authentication Response`와 Registration·PDU·ping을 수행하며 `SecurityModeReject`는 0건이다.
- **emulation** (`-e 1`): `OAI_NAS_DESYNC_RESULT_EMULATE=1`로 선행 NAS `SecurityModeCommand` 없이 상향 `SecurityModeReject`를 1회 송신한다. OCUDU DU/CU, Open5GS, TeleRAN, production detector 소스와 임계값은 수정하지 않는다.
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/nas-counter-desync-build`가 2개 패치(`patch/nas-counter-desync-result-w38.patch`, `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`)를 적용한다.

## 실행 방법

### 통합 컨트롤러 (`tools/ctl.sh`)

```bash
./tools/ctl.sh setup l3-06 --profile p1
./tools/ctl.sh doctor l3-06 --profile p1

# 단발 및 matched 3세트 캠페인 (p5 direct 1-cell)
./tools/ctl.sh run l3-06 control l3-06-control --profile p5
./tools/ctl.sh run l3-06 emulation l3-06-emulation --profile p5 --enable
./tools/ctl.sh campaign l3-06 l3-06-matched --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1)
./tools/ctl.sh same-cell run l3-06 --profile p1 --mode control --run-id sc-l306-ctrl-1
./tools/ctl.sh same-cell run l3-06 --profile p1 --mode emulation --run-id sc-l306-emu-1 --enable
```

### 직접 실행 (`bin/`)

설정은 `conf/nas-counter-desync.conf.example`을 복사한 `conf/nas-counter-desync.conf`(`NAS_DESYNC_CONF`)를 사용한다.

```bash
OAI=/root/OAI-nas-desync-w38 bin/nas-counter-desync-build
NAS_DESYNC_CONF=conf/nas-counter-desync.conf bin/nas-counter-desync-run control -n l306-ctrl -e 0
NAS_DESYNC_CONF=conf/nas-counter-desync.conf bin/nas-counter-desync-run emulation -n l306-emu -e 1
NAS_DESYNC_CONF=conf/nas-counter-desync.conf bin/nas-counter-desync-campaign -n l306-camp -e 1
```

## dashboard 전송 시점

기본값 `CU_DASHBOARD_FOLLOW=1`은 `start_live()` 끝에서 같은 `sender.json`·같은 `sudo -u` 사용자로 전송기를 따라가기 모드로 띄워 경보·KPM을 실행 중에 실시간으로 보내고(`sender.pid`), 종료 시 telemetry·detector를 내린 뒤 SIGTERM·최대 10초 대기로 멈추고 `--once`로 나머지 줄을 이어 보낸다(`sender.stdout`·`sender.log` 이어쓰기). `CU_DASHBOARD_FOLLOW=0`이면 실행이 끝난 뒤 `dashboard_sender.py --once` 한 번만 전송한다. 합격 기준은 두 모드 모두 같다.

## 합격 기준

- **control**: `SecurityModeReject=0`, `L3-06` 경보 0건, Registration·PDU·ping 성공.
- **emulation**: 실제 상향 `SecurityModeReject=1`, 선행 NAS `SecurityModeCommand=0`, `observations.jsonl`의 TeleRAN 원문/detector recorder SHA-256 일치, TeleRAN 100 ms / gap 0 / KPM 존재, production `L3-06` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5, UE crash 0건.
- **campaign**: 고정 순서 `control → emulation` 3세트 모두 통과.
- **고정 주장 필드 (`verdict.json`)**: `passed=true`, `live_protocol_path_observed=true`, `mitm_observed=false`, `invalid_smc_received_observed=false`, `nas_counter_wrap_observed=false`, `service_denial_observed=false`.

## 한계 및 금지 주장

- **원 공격 원인 미재현**: MITM 기지국, 무결성이 틀린 `SecurityModeCommand` 실제 수신, 8-bit NAS sequence wrap-around, 이후 정상 상향 NAS 폐기는 재현·관측하지 않는다.
- **서비스 거부 미관측**: `service_denial`은 `not_observed`이며 합격 조건이 아니다.
- **p5 vs p1 same-cell 구분**: `p1` clean-origin 정상 UE 5대 same-cell E2E(`p1q9-20261119`)는 6/6 통과했다. 반면 2026-11-17 p5 same-cell 실험에서는 broker 전환 뒤 정상 풀 health가 회복되지 않았으므로 p5 direct 1-cell 자격과 p5 same-cell을 섞어 주장하지 않는다.
- **OTA·상용망 미검증**: 실 SDR 차폐 OTA와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 direct 1-cell 자격: [2026-11-17 자격 기록](artifacts/p5-live-result-20261117/README.md)
- 참고 문헌: [5GReasoner](https://syed-rafiul-hussain.github.io/wp-content/uploads/2019/10/5GReasoner.pdf), [5G-SPECTOR](https://dev.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf)
