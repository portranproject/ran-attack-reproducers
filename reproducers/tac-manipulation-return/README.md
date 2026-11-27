# TAC 조작·가짜 기지국 복귀 신호 (AN-08)

미리 등록된 가명 UE 5대가 짧은 창에 `mobility` `RegistrationRequest`로 복귀하는 탐지 입력을 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-08` |
| `reproducer.json` ID | `tac-manipulation-return` |
| `tools/ctl.sh` ID / 별칭 | `tac-manipulation-return`, `an-08` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 68초(`duration_ms=68000`)의 JSONL을 생성한다. 먼저 5대(`0x0000b0000001`~`5`)에 `s_tmsi`를 배정해 정상 등록·해제한 뒤, 10초 간격으로 `mobility` `RegistrationRequest` 복귀를 생성한다.

- `control`: known UE 5대 중 **4대**만 복귀한다.
- `emulation`: known UE **5대**가 모두 복귀한다.

## 실행 방법

```bash
./tools/ctl.sh run an-08 control an-08-ctrl-1 --profile p5
./tools/ctl.sh run an-08 emulation an-08-emu-1 --profile p5 --enable
./tools/ctl.sh campaign an-08 an-08-matched --profile p5 --enable
./tools/ctl.sh replay an-08-emu-1 --profile p5
./tools/ctl.sh report an-08-emu-1 --profile p5
./tools/ctl.sh verify an-08-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. SigOver 계열의 TAC 송출, rogue gNB, 실제 UE 이동 등록은 만들지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 100 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
