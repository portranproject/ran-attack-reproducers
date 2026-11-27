# NAS 카운터 reset 계열 재인증 (AN-06a)

이미 NAS·AS 보안을 수립한 같은 UE 컨텍스트에 `AuthenticationRequest`와 NAS `SecurityModeCommand`가 다시 나타나는 탐지 입력을 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-06a` |
| `reproducer.json` ID | `nas-counter-reset` |
| `tools/ctl.sh` ID / 별칭 | `nas-counter-reset`, `an-06a` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 4초(`duration_ms=4000`)의 JSONL을 생성한다.

- `control`: 정상 등록(`normal_flow`, 해제 없음) 1회만 생성한다.
- `emulation`: 동일 컨텍스트에서 보안 수립 뒤 `AuthenticationRequest`/`AuthenticationResponse`와 NAS `SecurityModeCommand`/`SecurityModeComplete` 1세트를 재발생시킨다.

## 실행 방법

```bash
./tools/ctl.sh run an-06a control an-06a-ctrl-1 --profile p5
./tools/ctl.sh run an-06a emulation an-06a-emu-1 --profile p5 --enable
./tools/ctl.sh campaign an-06a an-06a-matched --profile p5 --enable
./tools/ctl.sh replay an-06a-emu-1 --profile p5
./tools/ctl.sh report an-06a-emu-1 --profile p5
./tools/ctl.sh verify an-06a-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. 실제 NAS count reset이나 replay protection 우회는 수행하지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 50 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
