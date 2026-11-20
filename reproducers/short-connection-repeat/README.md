# 짧은 RRC 연결 반복 (AN-04)

같은 가명 `5G-S-TMSI`가 RRC setup, service accept, release를 짧게 반복하는 탐지 입력을 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-04` |
| `reproducer.json` ID | `short-connection-repeat` |
| `ctl.sh` ID / 별칭 | `short-connection-repeat`, `an-04` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 25초(`duration_ms=25000`)의 JSONL을 생성한다. 각 연결은 `RRCSetupRequest` → `ServiceRequest` → `ServiceAccept` → `RRCRelease` 순서로 1.2초 내 해제되며 10초 간격으로 배치된다.

- `control`: 같은 가명 `5G-S-TMSI`의 짧은 연결을 **2회** 생성한다.
- `emulation`: 같은 짧은 연결을 **3회** 생성한다.

## 실행 방법

```bash
./ctl.sh run an-04 control an-04-ctrl-1 --profile p5
./ctl.sh run an-04 emulation an-04-emu-1 --profile p5 --enable
./ctl.sh campaign an-04 an-04-matched --profile p5 --enable
./ctl.sh replay an-04-emu-1 --profile p5
./ctl.sh report an-04-emu-1 --profile p5
./ctl.sh verify an-04-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. 여러 원인에서 나타날 수 있는 신호이므로 특정 공격 기전에 귀속하지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 1,300 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
