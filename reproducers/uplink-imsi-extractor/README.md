# GUTI 불일치 후 상향 식별자 요청 결과 (AN-02)

`5G-GUTI` 기반 `mobility` 등록 뒤 `IdentityRequest`가 반복되는 탐지 입력을 재현한다. OAI UE나 무선 경로를 거치지 않는 **탐지 입력 에뮬레이션**이며 공격 플랫폼 1.0 자격 범위에서는 제외한다.

| 항목 | 값 |
|---|---|
| 룰 ID | `AN-02` |
| `reproducer.json` ID | `uplink-identifier-exposure` (`module`: `uplink-imsi-extractor`) |
| `tools/ctl.sh` ID / 별칭 | `uplink-identifier-exposure`, `uplink-imsi`, `an-02` |
| 재현 수준 | `detector-input-emulation` (`active_mode=emulation`) |
| 자격 범위 | 공격 플랫폼 1.0 제외, production detector 회귀 전용 (`p5: pending`, `OTA: not-applicable`) |

## 신호 패턴 (control vs emulation)

`tools/generate_rule_signal.py`가 `period_ms=100`, 길이 8초(`duration_ms=8000`)의 JSONL을 생성하며, `observations.jsonl`에는 가명 `5G-S-TMSI`(`0x00000a0b0c0d`)만 사용한다.

- `control`: `5G-GUTI` mobility 등록 뒤 `IdentityRequest`/`IdentityResponse`가 나타나는 흐름을 **4회** 생성한다.
- `emulation`: 같은 흐름을 **5회** 생성해 production detector threshold 경계를 넘긴다.

## 실행 방법

`tools/ctl.sh`는 디렉터리명 `uplink-imsi-extractor`를 거부하므로 반드시 `an-02`, `uplink-imsi`, 또는 `uplink-identifier-exposure`를 사용한다.

```bash
./tools/ctl.sh run an-02 control an-02-ctrl-1 --profile p5
./tools/ctl.sh run an-02 emulation an-02-emu-1 --profile p5 --enable
./tools/ctl.sh campaign an-02 an-02-matched --profile p5 --enable
./tools/ctl.sh replay an-02-emu-1 --profile p5
./tools/ctl.sh report an-02-emu-1 --profile p5
./tools/ctl.sh verify an-02-emu-1 --profile p5
```

`replay`·`report`·`verify`는 로컬의 `profile["detector"]["binary"]` 경로를 사용한다.

## 한계 및 근거

- 고정 주장 플래그: `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`. 실제 rogue gNB, GUTI 변조, IMSI/SUPI 획득은 수행하지 않는다.
- offline replay 검증: 2026-11-12 기준 `control 0/3`, `emulation 3/3` RAISE(지연 5 ms)를 통과했다. 당시 detector 커밋(`a34b358e...`)은 현행 `integration.lock.json`(`766f5569...`) 이전 버전이다.
- 상세 근거: [2026-11-12 replay 결과](../../artifacts/production-detector-rule-replay-20261112/README.md), [계보 및 기여](PROVENANCE.md).
