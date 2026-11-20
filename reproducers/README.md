# 공격 재현 모듈

`reproducers/` 아래 각 디렉터리는 하나의 시나리오만 다루는 독립 모듈이다. 모듈 목록과 계약은 각 디렉터리의 `reproducer.json`을 기준으로 `tools/reproctl.py`가 검증한다.

공통 실행 방법과 환경 준비 절차는 [E2E 실행 가이드](../docs/E2E-EXECUTION-GUIDE.md)와 [컨트롤러 가이드](../docs/CONTROL-GUIDE.md)를 따른다. 디렉터리명·`ctl.sh` ID·`reproducer.json` ID의 예외 대응표는 [명명 규칙](../docs/NAMING-CONVENTIONS.md)에 정리돼 있다.

## 공격 플랫폼 1.0 대상: L3 공격 7종

| 룰 ID | 디렉터리 | `ctl.sh` ID | 재현 수준 | 자격 현황 |
|---|---|---|---|---|
| `L3-01-V` | [rrc-signaling-storm](rrc-signaling-storm/README.md) | `rrc-storm` | `protocol` | p5 qualified · p1 same-cell 6/6 · OTA pending |
| `L3-01-O` | [authentication-timeout-exhaustion](authentication-timeout-exhaustion/README.md) | `auth-timeout` | `protocol` | p5 qualified · p1 same-cell 6/6 · OTA pending |
| `L3-20` | [blind-dos](blind-dos/README.md) | `blind-dos` | `protocol` | p5 qualified(direct 2-cell) · p1 same-cell 6/6 · OTA pending |
| `L3-21` | [uplink-dos](uplink-dos/README.md) | `uplink-credential-flood` | `protocol` | p5 qualified · p1 same-cell 6/6 · OTA pending |
| `L3-24` | [downlink-imsi-extractor](downlink-imsi-extractor/README.md) | `downlink-imsi` | `protocol-result-emulation` | p5 qualified · p1 same-cell 6/6 · OTA pending |
| `L3-14` | [ue-capability-hijacking](ue-capability-hijacking/README.md) | `ue-capability` | `protocol-observation-emulation` | p5 qualified · p1 same-cell 6/6 · OTA pending |
| `L3-06` | [nas-counter-desynchronization](nas-counter-desynchronization/README.md) | `nas-counter-desynchronization` (`l3-06`) | `protocol-result-emulation` | p5 qualified · p1 same-cell 6/6 · OTA pending |

`uplink-dos/` 디렉터리는 `L3-21` 프로토콜 재현 외에 과거 `NAS Service Request` MAC 단발 변조 에뮬레이션(`ctl.sh` ID `uplink-dos`)도 함께 보관한다. 이 legacy 변조형은 `same-cell` L3 자격 범위에서 제외한다.

## 참고용 탐지 입력 fixture: AN 6종

아래 6개 모듈은 `tools/generate_rule_signal.py`로 합성 JSONL을 생성해 production detector 회귀에만 사용하는 `detector-input-emulation`이다. 공격 플랫폼 1.0 자격 범위에서는 제외한다(`p5: pending`, `OTA: not-applicable`).

| 룰 ID | 디렉터리 | `ctl.sh` ID (별칭) | offline replay | 비고 |
|---|---|---|---|---|
| `AN-01` | [authentication-sync-failure](authentication-sync-failure/README.md) | `authentication-sync-failure` (`an-01`) | control 0/3 · emulation 3/3 | cause 21 뒤 재인증 |
| `AN-02` | [uplink-imsi-extractor](uplink-imsi-extractor/README.md) | `uplink-identifier-exposure` (`uplink-imsi`, `an-02`) | control 0/3 · emulation 3/3 | 폴더명 `uplink-imsi-extractor`는 `ctl.sh` 거부 |
| `AN-04` | [short-connection-repeat](short-connection-repeat/README.md) | `short-connection-repeat` (`an-04`) | control 0/3 · emulation 3/3 | 짧은 연결·해제 반복 |
| `AN-06a` | [nas-counter-reset](nas-counter-reset/README.md) | `nas-counter-reset` (`an-06a`) | control 0/3 · emulation 3/3 | 보안 수립 후 재인증·SMC |
| `AN-07` | [rrc-reject-release-imprisonment](rrc-reject-release-imprisonment/README.md) | `rrc-reject-release-imprisonment` (`an-07`) | control 0/3 · emulation 3/3 | 미완료 RRCSetup 반복 |
| `AN-08` | [tac-manipulation-return](tac-manipulation-return/README.md) | `tac-manipulation-return` (`an-08`) | control 0/3 · emulation 3/3 | known UE 5대 mobility 복귀 |

## 새 모듈 규칙

새 모듈 추가 절차와 `reproducer.json` 스키마·`ctl.sh` 잠금 제약은 [새 모듈 추가 가이드](../docs/NEW-MODULE-GUIDE.md)를 따른다.
