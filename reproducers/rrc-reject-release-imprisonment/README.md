# RRC 거절·해제 투옥 계열 미완료 반복 (AN-07)

같은 `5G-S-TMSI-Part1`의 `RRCSetupRequest`가 `RRCSetupComplete` 없이 `UEContextRelease`로 끝나는 미완료 반복 신호를 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-07` |
| `reproducer.json` ID | `rrc-reject-release-imprisonment` |
| `tools/ctl.sh` ID / 별칭 | `rrc-reject-release-imprisonment`, `an-07` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 25초(`duration_ms=25000`)의 JSONL을 생성한다. 각 시도는 `RRCSetupRequest` → `RRCSetup` 뒤 2초 후 `UEContextReleaseCommand`/`Complete`로 끝나며 10초 간격으로 배치된다.

- `control`: 미완료 RRC 절차를 **2회** 생성한다.
- `emulation`: 같은 미완료 RRC 절차를 **3회** 생성한다.

## 실행 방법

```bash
./tools/ctl.sh run an-07 control an-07-ctrl-1 --profile p5
./tools/ctl.sh run an-07 emulation an-07-emu-1 --profile p5 --enable
./tools/ctl.sh campaign an-07 an-07-matched --profile p5 --enable
./tools/ctl.sh replay an-07-emu-1 --profile p5
./tools/ctl.sh report an-07-emu-1 --profile p5
./tools/ctl.sh verify an-07-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. rogue gNB가 UE를 실제로 거절·해제 상태에 가두는 원인은 만들지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 2,100 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
