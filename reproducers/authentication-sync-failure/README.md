# 인증 동기 실패 (AN-01)

`AuthenticationFailure`의 5GMM cause 21(synchronization failure) 뒤 재인증이 이어지는 탐지 입력을 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-01` |
| `reproducer.json` ID | `authentication-sync-failure` |
| `tools/ctl.sh` ID / 별칭 | `authentication-sync-failure`, `an-01` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 3초(`duration_ms=3000`)의 JSONL을 생성한다.

- `control`: 정상 초기 등록(`normal_flow`) 1회만 생성한다.
- `emulation`: `AuthenticationRequest` 뒤 `AuthenticationFailure`(`cause=21`)를 보내고 재인증·등록을 완료하는 1회 흐름을 생성한다.

## 실행 방법

```bash
./tools/ctl.sh run an-01 control an-01-ctrl-1 --profile p5
./tools/ctl.sh run an-01 emulation an-01-emu-1 --profile p5 --enable
./tools/ctl.sh campaign an-01 an-01-matched --profile p5 --enable
./tools/ctl.sh replay an-01-emu-1 --profile p5
./tools/ctl.sh report an-01-emu-1 --profile p5
./tools/ctl.sh verify an-01-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. 실제 USIM SQN 비동기화나 AUTS 검증은 수행하지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 82 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
