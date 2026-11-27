# 공격 카탈로그

공격 재현 플랫폼 1.0의 자격 기준은 아래 **L3 7종**이다. 각 모듈의 메타데이터는 `reproducers/*/reproducer.json`에 있으며(루트 `reproducer.json`은 없음), `./tools/ctl.sh coverage`가 `reproducer.json`의 `p5`·`ota` 상태를 집계해 출력한다.

`qualified`는 해당 환경에서 기전·실측 TeleRAN 입력·production detector·dashboard를 연결한 matched 3/3 증거가 있음을 뜻한다. `pending`은 구현 또는 해당 환경 자격 검증이 남았음을 뜻한다.

## L3 공격 7종 (플랫폼 1.0 기준)

| 룰 | 대표 시나리오 | 재현 수준 | `reproducer.json` ID (`tools/ctl.sh` ID) | p5 | p1 same-cell | OTA |
|---|---|---|---|---|---|---|
| L3-01-V | RRC UE 컨텍스트 고갈 | `protocol` | `rrc-context-exhaustion` (`rrc-storm`) | qualified | 6/6 | pending |
| L3-01-O | 인증 응답 미전송형 연결 컨텍스트 고갈 | `protocol` | `authentication-timeout-exhaustion` (`auth-timeout`) | qualified | 6/6 | pending |
| L3-20 | 현재 유효 5G-GUTI 재사용형 Blind DoS | `protocol` | `blind-dos` (`blind-dos`) | qualified | 6/6 | pending |
| L3-21 | 무효·위조 자격증명 실패 플러드형 상향 DoS | `protocol` | `uplink-credential-flood` (`uplink-credential-flood`) | qualified | 6/6 | pending |
| L3-24 | 비정상 Identity Response·식별자 노출 | `protocol-result-emulation` | `downlink-identifier-exposure` (`downlink-imsi`) | qualified | 6/6 | pending |
| L3-14 | 보안 전 UE Capability Information 주입 | `protocol-observation-emulation` | `ue-capability-hijacking` (`ue-capability`) | qualified | 6/6 | pending |
| L3-06 | 요청되지 않은 NAS SecurityModeReject 결과 | `protocol-result-emulation` | `nas-counter-desynchronization` (`l3-06`) | qualified | 6/6 | pending |

- **레거시 변형 (`uplink-dos`)**: `reproducers/uplink-dos/bin/uplink-run`은 Service Request MAC 한 비트를 변조하는 `protocol-result-emulation` 모듈이다. 별도 `reproducer.json` 없이 `./tools/ctl.sh list`에 `legacy`로 표시되며 p5 matched 3/3을 통과했으나 `l3-live` same-cell 자격 대상에서는 제외한다.
- **환경별 자격 분리**: `p5` 개별/모듈별 결과([2026-11-17 5종 요약](../artifacts/p5-live-e2e-five-20261117/README.md) 및 각 모듈 `artifacts/`)와 `p1` same-cell 결과([2026-11-19 42/42 요약](../artifacts/p1-clean-origin-live-e2e-20261119/README.md))는 별도 자격이며 `p4`·`OTA`로 복사하지 않는다. 전체 아티팩트 목록은 [artifacts/README.md](../artifacts/README.md)를 따른다.

## 참고용 AN 이상탐지 fixture 6종 (1.0 자격 제외)

아래 6종은 production detector 회귀용 `detector-input-emulation` fixture이며 공격 1.0 자격 범위에서 제외한다.

| 룰 | 대표 시나리오 | `reproducer.json` ID (`tools/ctl.sh` alias) | p5 | OTA |
|---|---|---|---|---|
| AN-01 | 인증 동기 실패 | `authentication-sync-failure` (`an-01`) | pending | not-applicable |
| AN-06a | NAS 카운터 reset 계열 재인증 | `nas-counter-reset` (`an-06a`) | pending | not-applicable |
| AN-02 | GUTI 불일치 후 상향 식별자 요청 결과 | `uplink-identifier-exposure` (`an-02`) | pending | not-applicable |
| AN-04 | 짧은 RRC 연결 반복 | `short-connection-repeat` (`an-04`) | pending | not-applicable |
| AN-07 | RRC 거절·해제 투옥 계열 미완료 반복 | `rrc-reject-release-imprisonment` (`an-07`) | pending | not-applicable |
| AN-08 | TAC 조작·가짜 기지국 복귀 신호 | `tac-manipulation-return` (`an-08`) | pending | not-applicable |

6종 모두 2026-11-12 production detector offline replay(`a34b358e...`)에서 matched `control → emulation` 3/3을 통과했다([replay 검증 기록](../artifacts/production-detector-rule-replay-20261112/README.md)). live RAN 경로와 RF 원인은 관측하지 않았다.

## 재현 수준 4단계

1. `protocol`: 수정 OAI UE와 정상 OCUDU gNB·Open5GS 코어 사이에서 공격 원인 기전을 실제 메시지 경로로 재현한다.
2. `protocol-result-emulation`: 현재 토폴로지에서 만들 수 없는 RF/MITM 원인 이후의 프로토콜 결과를 실제 `UE → RAN → 코어` 경로에 만든다.
3. `protocol-observation-emulation`: 탐지가 보는 프로토콜 관측은 live 경로에 만들지만 원 공격의 원인·내용 변조·피해 효과는 만들지 않는다.
4. `detector-input-emulation`: 연구·관측 기반 `hello`·`ue_evt`·`kpm2` 입력을 `tools/generate_rule_signal.py`로 생성해 detector에 재생한다.

## 주장과 한계

모든 실행은 기전, 탐지 입력, 탐지 결과, 서비스 영향을 독립 차원으로 기록한다. 한 차원의 성공을 다른 차원의 성공으로 일반화하지 않는다.

### 허용 주장 vs 금지 주장

| 범위 | 현재 허용 주장 | 주장하지 않는 것 |
|---|---|---|
| 프로토콜 재현 4종 (`L3-01-V`, `L3-01-O`, `L3-20`, `L3-21`) | p5 및 p1 same-cell(`p1q9-20261119`)에서 실제 `UE → ZMQ → DU/CU → TeleRAN → detector → dashboard` 기전 재현·검출 matched 3/3 | 상용망 일반화, RF 송신 우위, 물리 UE 10대(`L3-21`은 1대 순차 10연결), 비특권 GUTI 스캔(`L3-20`은 랩 oracle 사용), 필수 서비스 거부 |
| 결과·관측 에뮬레이션 3종 (`L3-24`, `L3-14`, `L3-06`) + 레거시 `uplink-dos` | p5 및 p1 same-cell(`uplink-dos` 제외)에서 실제 RAN·TeleRAN 경로를 통한 후속 프로토콜 결과·F1/N2 관측 재현 matched 3/3 | RF overshadowing(`L3-24`, `uplink-dos`), MITM relay 및 capability 변조(`L3-14`), 실제 invalid SMC 수신 및 NAS 카운터 랩어라운드(`L3-06`), Profile A SUCI 복호화 |
| AN 회귀 fixture 6종 (`AN-01`, `AN-06a`, `AN-02`, `AN-04`, `AN-07`, `AN-08`) | `tools/generate_rule_signal.py` 기반 입력으로 production detector offline replay matched 3/3 (`a34b358e...`) | live `UE → RAN` 메시지 경로, 실제 공격 효과, RF/MITM/rogue gNB 원인 |
| 서비스 영향 (`service_impact`) | 개별 `verdict.json`에 실측된 경우에만 기록 (`p1q9-20261119` 7종 모두 `not_observed`) | 재현 성공과 기지국 마비의 동일시, 서비스 거부를 위한 다중 인스턴스 증설·timer 임의 완화 |
| 차폐 OTA | `profiles/ota.example.json`·`doctor`·계약 준비 완료 | OTA 실행 adapter 구현, 실 SDR matched 3/3 완료 |

`p1` clean-origin same-cell 42/42 자격([p1q9-20261119](../artifacts/p1-clean-origin-live-e2e-20261119/README.md))은 `p1`에 대한 자격이며 `p4`나 `OTA` 자격을 대신하지 않는다. 과거 2026-10 단일 ZMQ 실험의 한계 기록은 [이력 한계 문서](history/testbed-limitations.md)에 보존한다.

### 공통 판정 상태 계약 (`verdict.json`, `run.json`)

- `verdict.json` `dimensions`: `mechanism`, `detection_input`, `detector_result`, `service_impact` 네 차원을 독립 기록한다.
- 허용 상태값(`schemas/verdict.schema.json`): `pass`, `fail`, `not_observed`, `not_applicable`, `inconclusive`.
- `run.json` `claims` 플래그(`schemas/run.schema.json`):
  - `live_protocol_path_observed`: `@common-signal` fixture 실행(`detector-input-emulation`)에서는 항상 `false`다.
  - `rf_cause_observed`: 현재 ZMQ 기반 프로토콜·결과 에뮬레이션 전체에서 `false`다.
  - `service_denial_observed`: 서비스 거부가 직접 관측된 실행에서만 `true`다(`p1q9-20261119` 42회는 `false`).
