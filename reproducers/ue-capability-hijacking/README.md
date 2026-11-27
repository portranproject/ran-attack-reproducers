# 보안 전 UE Capability Information 주입 (L3-14)

OAI UE가 `RRCSetupComplete`를 보낸 직후, 아직 `SecurityModeCommand`와 `UECapabilityEnquiry`를 받기 전에 표준 `UECapabilityInformation`을 상향으로 1회 주입해 탐지 룰 `L3-14`의 보안 전 관측 신호를 재현하는 에뮬레이션 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-14` |
| `reproducer.json` id | `ue-capability-hijacking` |
| `tools/ctl.sh` ID / 별칭 | `ue-capability` (`ue-capability-hijacking`, `capability`) |
| 재현 수준 (`reproduction_level`) | `protocol-observation-emulation` |
| active 모드 (`active_mode`) | `emulation` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` E2E 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 보안 전 주입이 비활성이다.

## 동작 요약

```text
OAI UE                       OCUDU DU/CU (F1AP)
   │ RRCSetupComplete            │
   │────────────────────────────>│
   │ UECapabilityInformation     │ (emulation 1회, security OFF, 선행 Enquiry 없음)
   │────────────────────────────>│
   │ SecurityModeCommand / 이후 정상 capability 절차
```

- **control** (`-e 0`): 주입 없이 보안 뒤 정상 `UECapabilityEnquiry → UECapabilityInformation`과 Registration·PDU·ping을 수행한다.
- **emulation** (`-e 1`): `OAI_UE_CAPABILITY_INJECT=1`로 UE 인스턴스당 1회 표준 인코더를 호출한다. capability payload는 변조하지 않는다.
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/ue-capability-build`가 2개 패치(`patch/ue-capability-injection-w38.patch`, `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`)를 적용한다. OCUDU·Open5GS 소스와 timer/capacity는 수정하지 않는다.

## 실행 방법

### 통합 컨트롤러 (`tools/ctl.sh`)

```bash
./tools/ctl.sh setup ue-capability --profile p1
./tools/ctl.sh doctor ue-capability --profile p1

# 단발 및 matched 3세트 캠페인 (p5 direct)
./tools/ctl.sh run ue-capability control cap-ctrl-01 --profile p5
./tools/ctl.sh run ue-capability emulation cap-emu-01 --profile p5 --enable
./tools/ctl.sh campaign ue-capability cap-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./tools/ctl.sh same-cell run ue-capability --profile p1 --mode control --run-id sc-cap-ctrl-1
./tools/ctl.sh same-cell run ue-capability --profile p1 --mode emulation --run-id sc-cap-emu-1 --enable
```

### 직접 실행 (`bin/`)

설정은 `conf/p5-zmq.conf.example`을 복사한 `conf/ue-capability.conf`(`UE_CAPABILITY_CONF`)를 사용한다. 직접 빌드 전에는 `6d6782b4...` 기준 worktree가 미리 준비돼 있어야 한다(없으면 `./tools/ctl.sh setup ue-capability` 사용).

```bash
OAI=/root/OAI-ue-capability-w38 bin/ue-capability-build
UE_CAPABILITY_CONF=conf/ue-capability.conf bin/ue-capability-run control -n cap-ctrl -e 0
UE_CAPABILITY_CONF=conf/ue-capability.conf bin/ue-capability-run emulation -n cap-emu -e 1
UE_CAPABILITY_CONF=conf/ue-capability.conf bin/ue-capability-campaign -n cap-camp -e 1
```

## 합격 기준

- **control**: 주입 marker 0회, 보안 전 `UECapabilityInformation` 0건, Registration·PDU·ping 성공, `L3-14` 경보 0건.
- **emulation**: 동일 `(GNB_DU_UE_F1AP_ID, GNB_CU_UE_F1AP_ID)`에서 `RRCSetupComplete` 뒤 선행 `UECapabilityEnquiry`·`SecurityModeCommand` 없는 `UECapabilityInformation` 1건, `verdict.json`에서 `passed=true`, `pre_security_injection_observed=true`, `unsolicited_information_observed=true`, `mitm_relay_observed=false`, TeleRAN 100 ms / gap 0 / KPM 존재, production `L3-14` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5.
- **campaign**: 고정 순서 `control → emulation` 3세트 모두 통과.

## 한계 및 금지 주장

- **MITM·내용 변조·강등 미관측**: 가짜 기지국/MITM relay, capability 내용 변조, gNB의 강등 수락은 재현하지 않는다(`mitm_relay_observed=false`).
- **서비스 거부 미관측**: 정상 서비스 유지가 관측됐으며 `service_denial`은 `not_observed`다.
- **OTA·상용망 미검증**: ZMQ 환경 검증만 완료됐으며 실 SDR OTA와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [설계](DESIGN.md), [사용 가이드](USAGE-GUIDE.md), [탐지 계약](DETECTION-CONTRACT.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 E2E 자격: [p5 L3 5종 E2E](../../artifacts/p5-live-e2e-five-20261117/README.md)
- 모듈 세부 증거: [p5 1-cell 3/3 실측](artifacts/p5-zmq-pre-security-information-20261111/README.md)
