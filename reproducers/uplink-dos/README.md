# 무효·위조 자격증명 실패 플러드형 상향 DoS (L3-21)

수정 OAI UE 1대가 10초 안에 서로 다른 10개 RAN 연결에서 `RegistrationRequest → RegistrationReject` 실패를 생성해 탐지 룰 `L3-21`을 검증하는 프로토콜 재현 모듈이다. 같은 디렉터리에 단발 NAS `Service Request` MAC 1비트 변조용 구버전 시나리오(`uplink-dos`, `emulation`)도 함께 보관한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-21` |
| `reproducer.json` id | `uplink-credential-flood` |
| `ctl.sh` ID / 별칭 | `uplink-credential-flood` (`credential-flood`, `uplink-l3-21`) · 레거시: `uplink-dos` (`uplink`) |
| 재현 수준 (`reproduction_level`) | `protocol` (`L3-21`) · 레거시: `protocol-result-emulation` (`uplink-dos`) |
| active 모드 (`active_mode`) | `attack` (`L3-21`) · 레거시: `emulation` (`uplink-dos`) |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` same-cell 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 공격·에뮬레이션이 비활성이다.

## 동작 요약

```text
무효 자격증명 OAI UE (1대)    OCUDU DU/CU / Open5GS          TeleRAN → detector
   │ 10초 내 10개 새 RAN 연결  │                                │
   │ RRCSetupComplete + RegistrationRequest                    │
   │─────────────────────────>│───────────────────────────────>│ (F1/N2 100 ms)
   │ RegistrationReject (10건)│                                │
   │<─────────────────────────│───────────────────────────────>│ L3-21 branch 1 RAISE
```

- **`L3-21` 실패 플러드형 (`uplink-credential-flood`)**: control(`-e 0`)은 실패 연결 1건만 만들고, attack(`-e 1`)은 10초 창 내 10건의 `RegistrationReject`를 생성해 production 기준 `max(5, ceil(96×0.1))=10`을 만족한다.
- **레거시 단발 MAC 변조형 (`uplink-dos`)**: 등록 후 idle 상태의 첫 `Service Request` 계산 완료 MAC 1비트를 1회 변조해 Open5GS `NAS MAC verification failed`와 피해 ping 손실·회복을 관측한다(AMF가 조용히 폐기하므로 Reject 0건, L3-21 미탐은 변형 불일치).
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/uplink-build`가 3개 패치(`patch/uplink-dos-emulator-w38.patch`, `patch/uplink-credential-flood-w38.patch`, `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`)를 적용한다. OCUDU·Open5GS 소스와 timer/capacity는 수정하지 않는다.

## 실행 방법

### 통합 컨트롤러 (`ctl.sh`)

```bash
./ctl.sh setup uplink-credential-flood --profile p1
./ctl.sh doctor uplink-credential-flood --profile p1

# L3-21 단발 및 matched 3세트 캠페인
./ctl.sh run uplink-credential-flood control l321-ctrl-01 --profile p5
./ctl.sh run uplink-credential-flood attack l321-atk-01 --profile p5 --enable
./ctl.sh campaign uplink-credential-flood l321-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./ctl.sh same-cell run uplink-credential-flood --profile p1 --mode control --run-id sc-l321-ctrl-1
./ctl.sh same-cell run uplink-credential-flood --profile p1 --mode attack --run-id sc-l321-atk-1 --enable

# 레거시 단발 MAC 변조 시나리오 (p5 direct)
./ctl.sh run uplink-dos control ul-ctrl-01 --profile p5
./ctl.sh run uplink-dos emulation ul-emu-01 --profile p5 --enable
```

### 직접 실행 (`bin/`)

설정은 `conf/uplink.conf.example`을 `conf/uplink.conf`(`UPLINK_CONF`)로 복사해 사용한다.

```bash
OAI=/root/OAI-uplink-dos-w38 bin/uplink-build

# L3-21 실패 플러드 (control|attack)
UPLINK_CONF=conf/uplink.conf bin/uplink-credential-flood-run control -n l321-ctrl -e 0
UPLINK_CONF=conf/uplink.conf bin/uplink-credential-flood-run attack -n l321-atk -e 1
UPLINK_CONF=conf/uplink.conf bin/uplink-credential-flood-campaign -n l321-camp -e 1

# 레거시 단발 MAC 변조 (control|emulation; CU idle 프로필 적용·원복 필요)
UPLINK_CONF=conf/uplink.conf bin/uplink-run control -n ul-ctrl -e 0
UPLINK_CONF=conf/uplink.conf bin/uplink-run emulation -n ul-emu -e 1
```

경계 회귀 전용 합성 fixture 실행기는 `bin/uplink-credential-flood-fixture-run`이며, `bin/uplink-profile`은 레거시 단발형용 CU idle 전환 프로필 적용·해시 원복에 사용한다.

## dashboard 전송 시점

기본값 `CU_DASHBOARD_FOLLOW=1`은 `start_live()` 끝에서 같은 `sender.json`·같은 `sudo -u` 사용자로 전송기를 따라가기 모드로 띄워 경보·KPM을 실행 중에 실시간으로 보내고(`sender.pid`), 종료 시 telemetry·detector를 내린 뒤 SIGTERM·최대 10초 대기로 멈추고 `--once`로 나머지 줄을 이어 보낸다(`sender.stdout`·`sender.log` 이어쓰기). `CU_DASHBOARD_FOLLOW=0`이면 실행이 끝난 뒤 `dashboard_sender.py --once` 한 번만 전송한다. 합격 기준은 두 모드 모두 같다.

## 합격 기준

- **`L3-21` control**: 완전한 `RRC → RegistrationReject` 연결 1개, 수락 0, `L3-21` 경보 0건.
- **`L3-21` attack**: 10초 미만 간격의 서로 다른 실패 연결 10개(`RegistrationRequest`/`RegistrationReject` 각 10건), 수락 0, TeleRAN 100 ms / gap 0 / KPM 존재, production `L3-21` `branch=1` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5.
- **`L3-21` `verdict.json` 필드**: `passed=true`, `live_protocol_path_observed=true`, `rf_cause_observed=false`, `service_denial_observed=false`.
- **레거시 `uplink-dos` (`emulation`)**: baseline ping 5/5, MAC 변조 정확히 1회, AMF `NAS MAC verification failed`, impact ping 5회 연속 손실, 동일 PID 회복 5/5, `rf_overshadowing_observed=false`, crash/forced kill 0건.

## 한계 및 금지 주장

- **RF 송신 우위 미관측**: 실제 uplink RF overshadowing을 만들지 않았으며 `rf_overshadowing_observed` / `rf_cause_observed`는 항상 `false`다.
- **물리 UE 1대 기준**: `L3-21`은 수정 UE 1대가 만든 10개 RAN 연결이며 물리 UE 10대나 서비스 거부를 뜻하지 않는다(`service_denial` `not_observed`).
- **OTA·상용망 미검증**: ZMQ 환경 검증만 완료됐으며 실 SDR OTA와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [사용 가이드](USAGE-GUIDE.md), [탐지 계약](DETECTION-CONTRACT.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- 모듈 세부 증거: [L3-21 p5 same-cell 실측](artifacts/p5-l3-21-live-same-cell-20261116/README.md), [레거시 MAC 변조 p5 실측](artifacts/p5-zmq-protocol-impact-20261105/README.md), [L3-21 입력 에뮬레이션 회귀](artifacts/p5-l3-21-input-emulation-20261111/README.md)
