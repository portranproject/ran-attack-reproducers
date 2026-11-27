# 인증 응답 미전송형 연결 컨텍스트 고갈 (L3-01-O)

서로 다른 랩 가입자 10명이 `Registration Request`를 보낸 뒤 AMF의 `Authentication Request`에 응답하지 않아 미인증 RRC·NGAP·5GMM 컨텍스트를 점유하는 NAS 고갈 계열 프로토콜 재현 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-01-O` |
| `reproducer.json` id | `authentication-timeout-exhaustion` |
| `tools/ctl.sh` ID / 별칭 | `auth-timeout` (`authentication-timeout-exhaustion`, `auth`) |
| 재현 수준 (`reproduction_level`) | `protocol` |
| active 모드 (`active_mode`) | `attack` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` E2E 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 Authentication Response를 정상 제출한다.

## 동작 요약

```text
공격 UE (10명)               OCUDU DU/CU                 Open5GS
   │ RRCSetupComplete + Registration Request │              │
   │────────────────────────────────────────>│ InitialUEMessage
   │                                         │─────────────>│
   │                    Authentication Request              │
   │<────────────────────────────────────────│<─────────────│
   │ (Authentication Response / Failure 생략)│ 미인증 컨텍스트 유지
```

- **control** (`-e 0`): 공격 슬롯 10개(`2프로세스×5 UE`) 모두 `Authentication Response`를 정상 제출한다.
- **attack** (`-e 1`): 10명 모두 `Authentication Response`와 `Authentication Failure`를 보내지 않는다. `auth-stall-cell-run`은 각 OAI 프로세스에 독립 virtual RU/ZMQ endpoint 5개를 구성하고 GNU Radio 브로커(`same_cell_broker.py`)로 한 DU·셀에 합친다.
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/auth-timeout-build`가 4개 패치(`ru-sharing-w38.patch`, `workloads/normal-ue/patch/normal-multi-ru.patch`, `auth-timeout-ue-w38.patch`, `same-cell-ra-gate-w38.patch`)를 적용한다. OCUDU·Open5GS 소스, timer, capacity는 수정하지 않는다.

## 실행 방법

### 통합 컨트롤러 (`tools/ctl.sh`)

```bash
./tools/ctl.sh setup auth-timeout --profile p1
./tools/ctl.sh doctor auth-timeout --profile p1

# 단발 실행 (한 셀 10-UE runner: bin/auth-stall-cell-run)
./tools/ctl.sh run auth-timeout control auth-ctrl-01 --profile p5
./tools/ctl.sh run auth-timeout attack auth-atk-01 --profile p5 --enable
./tools/ctl.sh campaign auth-timeout auth-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./tools/ctl.sh same-cell run auth-timeout --profile p1 --mode control --run-id sc-auth-ctrl-1
./tools/ctl.sh same-cell run auth-timeout --profile p1 --mode attack --run-id sc-auth-atk-1 --enable
```

### 직접 실행 (`bin/`)

기본 한 셀 10-UE runner는 `conf/auth-stall-cell.conf.example`을 복사한 `conf/auth-stall-cell.conf`(`AUTH_STALL_CELL_CONF`)를 사용한다.

```bash
bin/auth-timeout-build
AUTH_STALL_CELL_CONF=conf/auth-stall-cell.conf \
  bin/auth-stall-cell-run control -n auth-cell-control -e 0
AUTH_STALL_CELL_CONF=conf/auth-stall-cell.conf \
  bin/auth-stall-cell-run attack -n auth-cell-attack -e 1
```

과거 direct 4-cell 서비스 영향 측정 runner(`bin/auth-timeout-run`, `bin/auth-timeout-campaign`)는 `conf/auth-timeout.conf`(`AUTH_TIMEOUT_CONF`)를 사용한다. (`reproducer.json`의 `analyze`/`verify` 항목은 direct 4-cell용 `normalize_p5.py`/`verify_evidence.py`를 가리키지만, 실제 `tools/ctl.sh` 기본 runner인 `bin/auth-stall-cell-run`은 내부적으로 `analysis/verify_cell_flood.py`로 판정한다.)

## 합격 기준

- **control**: 10명 모두 `Authentication Response` 제출, `L3-01-O` 경보 0건, crash/forced kill 0건.
- **attack**: 10명 `Authentication Request` 수신 및 `Authentication Response` 미전송(`authentication_request_withheld`), TeleRAN 100 ms / gap 0 / KPM 존재, production detector `L3-01-O` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5 성공.
- **campaign**: 고정 순서 `control → attack` 3세트 모두 통과.
- **direct 4-cell `verdict.json` 필드**: `mechanism_reproduced`, `resource_accumulation_observed`, `witness_denial_observed`(선택 효과), `passed`(보수적 witness 거부 포함 게이트). 한 셀 runner `verdict.json`은 `mechanism_reproduced`, `resource_accumulation_observed`, `passed`를 기록한다.

## 한계 및 금지 주장

- **서비스 거부 미관측**: p1 same-cell E2E와 p5 direct 4-cell 모두 정상 UE가 등록·ping에 성공해 `service_denial`은 `not_observed`이다. DoS 성공으로 부르지 않는다.
- **동일 SUPI 복제·임의 IMSI 제외**: 서로 다른 팀 가입자 프로필만 사용하며, 20가입자·5-lane 분산 진단은 운영 범위에 포함하지 않는다.
- **OTA·상용망 미검증**: ZMQ 환경 검증만 완료됐으며 실 SDR OTA와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [사용 가이드](USAGE-GUIDE.md), [탐지 계약](DETECTION-CONTRACT.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 E2E 자격: [p5 L3 5종 E2E](../../artifacts/p5-live-e2e-five-20261117/README.md)
- 모듈 세부 증거: [p5 다중 UE 한계 실측](artifacts/p5-zmq-multiue-limit-20261111/README.md), [초기 기전 실측](artifacts/p5-zmq-mechanism-smoke-20261111/README.md)
