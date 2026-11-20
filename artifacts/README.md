# 봉인 증거 인덱스 (`artifacts/`)

이 문서는 저장소 루트 `artifacts/`(21개 디렉토리)와 모듈별 `reproducers/*/artifacts/`(11개 디렉토리)의 봉인 증거 목록을 정리한다. 현재 통합 자격 기준선은 [p1-clean-origin-live-e2e-20261119](p1-clean-origin-live-e2e-20261119/README.md)(L3 7종 × 정상 UE 5대 same-cell 42/42 통과)이다.

봉인된 하위 디렉토리의 보고서·해시·JSON 파일은 수정하지 않는다. 원시 로그·가입자 키·IP 같은 민감 원문은 Git 밖에 보관한다.

## 1. 최신 자격 기준선 및 플랫폼 E2E

| 디렉토리 | 날짜 | 무결성 파일 | 구분 및 핵심 내용 |
|---|---|---|---|
| [p1-clean-origin-live-e2e-20261119](p1-clean-origin-live-e2e-20261119/README.md) | 2026-11-19 | `MANIFEST.sha256` | **현행 기준선**: p1 clean-origin, L3 7종 × 정상 UE 5대 same-cell 42/42 통과 |
| [p5-live-e2e-five-20261117](p5-live-e2e-five-20261117/README.md) | 2026-11-17 | README 내 원격 SHA-256 | **자격**: p5 개별 경로 L3 5종(L3-01-V/O, L3-20, L3-24, L3-14) 각 3/3 통과 |
| [p5-platform-e2e-20261113](p5-platform-e2e-20261113/README.md) | 2026-11-13 | README 내 SHA-256 | **플랫폼 기준선**: p5 4개 저장소 고정 리비전 정상 UE live, 7개 replay, L3-21, 대시보드 전송 통과 |
| [production-detector-rule-replay-20261112](production-detector-rule-replay-20261112/README.md) | 2026-11-12 | — (`campaign.json`) | **오프라인 회귀**: L3-06 및 AN 참고 fixture 6종 탐지기 입력 재생 각 3/3 통과 |

## 2. L3-01-V (RRC Signaling Storm) 정선·브로커 증거

| 디렉토리 | 날짜 | 무결성 파일 | 구분 및 핵심 내용 |
|---|---|---|---|
| [curated-verify-20261030](curated-verify-20261030/README.md) | 2026-10-30 | `SHA256SUMS.remote` | **자격**: p5 curated OAI UE 빌드 정상 회귀 및 Msg4 ACK 확인 |
| [label-v1-rlf20-20261030](label-v1-rlf20-20261030/README.md) | 2026-10-30 | `SHA256SUMS.remote` | **자격/대응 감사**: label v1 ACK-on/off 비교 및 CSI-DTX RLF20 조기 해제 실측 |
| [broker-witness-20261030](broker-witness-20261030/README.md) | 2026-10-30 | `SHA256SUMS.remote` | **자격**: 5-UE GNU Radio 브로커 독립 정상 UE 증인 A/B 검증 |
| [broker-stability-20261030](broker-stability-20261030/README.md) | 2026-10-30 | `SHA256SUMS.remote` | **안정화**: 5-UE 브로커 5/5 시작 sync 게이트 및 2단계 종료 검증 |
| [broker-sync-sampling-20261030](broker-sync-sampling-20261030/README.md) | 2026-10-30 | `SHA256SUMS.remote` | **표본 검증**: 15회 사전 고정 대조군 sync 시작 분포 및 종료 건전성 |
| [p5-du-ack-join-current-20261030](p5-du-ack-join-current-20261030/README.md) | 2026-10-30 | — | **보강 증거**: 현재 curated 빌드 J2 exact DU HARQ-ACK 조인 9/9 확인 |

## 3. 과거·진단·중단된 RSS 실험 기록

이 범주의 디렉토리는 초기 `rss-storm` v1 기록이거나 hold32·용량 변경 진단 자료이다. 기본 cleanup 공격 성공 또는 현행 통합 자격 근거로 쓰지 않는다.

| 디렉토리 | 날짜 | 무결성 파일 | 성격 및 비고 |
|---|---|---|---|
| [p5-du-ack-join-20261030](p5-du-ack-join-20261030/README.md) | 2026-10-30 | — | **과거 빌드**: 구버전 바이너리 exact DU ACK 조인 10/10 |
| [p5-cu200-3cell-20261030](p5-cu200-3cell-20261030/README.md) | 2026-10-30 | — | **진단 전용**: hold32(`CU 200`, 3셀) 진단. 기본 cleanup 성공 근거 아님 |
| [p5-default-cleanup-rate-v2-20261030](p5-default-cleanup-rate-v2-20261030/README.md) | 2026-10-30 | `SHA256SUMS`, `raw/*/SHA256SUMS` | **진단/한계**: 기본 약 2초 cleanup `A-early` on/off 3/3 및 지속포화 한계 |
| [p5-msg3-cap96-20261030](p5-msg3-cap96-20261030/README.md) | 2026-10-30 | — | **진단 전용**: DU cap-96 `A_early` 기본 RLF vs hold32 probe 거부 비교 |
| [p5-msg3-only-20261030](p5-msg3-only-20261030/README.md) | 2026-10-30 | — | **진단 전용**: Msg3-only 및 cap12 설정 오류 정정 기록 |
| [archive-du-cell-resource-20261026](archive-du-cell-resource-20261026/README.md) | 2026-10-26 | `MANIFEST.sha256` | **개발 중단 보존**: `rss-storm` v1(DU 셀 자원 고갈) 봉인 아카이브 |
| [spike-cu90-20261026](spike-cu90-20261026/README.md) | 2026-10-26 | `MANIFEST.sha256` | **진단 스파이크**: CU `max_nof_ues=90` vs DU 96 선착 거절 실험 |
| [ro-arbitration-20261022](ro-arbitration-20261022/README.md) | 2026-10-22 | `SHA256SUMS` | **과거 실험**: PRACH 기회 중재(`RSS_RO_ARBITRATE=1`, 6 UE, 120초) |
| [verify-20261021](verify-20261021/README.md) | 2026-10-21 | `SHA256SUMS`, `run2-r0/SHA256SUMS` | **과거 검증**: 초기 `rss-storm` Mode A 96/96 gNB 로그 판정(10-30 정제 포함) |
| [modeA-peak-6ue-20261021](modeA-peak-6ue-20261021/SHA256SUMS) | 2026-10-21 | `SHA256SUMS` | **과거 원시 해시**: Mode A 6-UE 피크 실행 해시(`README.md` 없음) |
| [modeA-sustained-20261021](modeA-sustained-20261021/SHA256SUMS) | 2026-10-21 | `SHA256SUMS` | **과거 원시 해시**: Mode A 590초 지속 실행 해시(`README.md` 없음) |

## 4. 모듈별 봉인 근거 (`reproducers/*/artifacts/`)

`reproducers/rrc-signaling-storm/`의 증거는 위 §2–§3에 있으며 별도 `artifacts/` 하위 디렉토리는 두지 않는다. 나머지 6개 L3 모듈은 각 모듈 아래에 자체 `artifacts/` 디렉토리를 둔다.

| 모듈 | 디렉토리 | 날짜 | 무결성 파일 | 구분 및 핵심 내용 |
|---|---|---|---|---|
| `authentication-timeout-exhaustion` | [p5-zmq-multiue-limit-20261111](../reproducers/authentication-timeout-exhaustion/artifacts/p5-zmq-multiue-limit-20261111/README.md) | 2026-11-11 | — | **한계/기전**: direct 4-cell 3×2 UICC 동시 pre-auth 6건, DoS 미달 |
| `authentication-timeout-exhaustion` | [p5-zmq-mechanism-smoke-20261111](../reproducers/authentication-timeout-exhaustion/artifacts/p5-zmq-mechanism-smoke-20261111/README.md) | 2026-11-11 | — | **스모크 진단**: direct 3-cell 공격자 2 + witness 1 기전 확인 |
| `blind-dos` | [p5-zmq-nas-guti-g5-20261102](../reproducers/blind-dos/artifacts/p5-zmq-nas-guti-g5-20261102/README.md) | 2026-11-02 | `REMOTE-HASHES.sha256` | **자격**: direct 2-cell 5G-GUTI 재사용형 G5 matched 3/3 통과 |
| `blind-dos` | [p5-same-cell-limit-20261116](../reproducers/blind-dos/artifacts/p5-same-cell-limit-20261116/README.md) | 2026-11-16 | — | **진단/한계**: same-cell oracle 수정 및 ZMQ 시간축 한계 기록 |
| `blind-dos` | [p5-zmq-20261102](../reproducers/blind-dos/artifacts/p5-zmq-20261102/README.md) | 2026-11-02 | — | **과거 실패 기록**: 5G-S-TMSI 재사용형 30초 회복 미달 `valid-failure` |
| `downlink-imsi-extractor` | [p5-zmq-identity-response-20261111](../reproducers/downlink-imsi-extractor/artifacts/p5-zmq-identity-response-20261111/README.md) | 2026-11-11 | — | **자격**: p5 1-cell SUCI Identity Response 에뮬레이션 3/3 통과 |
| `nas-counter-desynchronization` | [p5-live-result-20261117](../reproducers/nas-counter-desynchronization/artifacts/p5-live-result-20261117/README.md) | 2026-11-17 | — | **자격**: p5 live RAN→TeleRAN→detector L3-06 3/3 통과 |
| `ue-capability-hijacking` | [p5-zmq-pre-security-information-20261111](../reproducers/ue-capability-hijacking/artifacts/p5-zmq-pre-security-information-20261111/README.md) | 2026-11-11 | `SHA256SUMS.remote` | **자격**: p5 1-cell 보안 전 Capability Information 3/3 통과 |
| `uplink-dos` | [p5-l3-21-live-same-cell-20261116](../reproducers/uplink-dos/artifacts/p5-l3-21-live-same-cell-20261116/README.md) | 2026-11-16 | — | **자격**: p5 정상 UE 5대 same-cell L3-21 live matched 3/3 통과 |
| `uplink-dos` | [p5-zmq-protocol-impact-20261105](../reproducers/uplink-dos/artifacts/p5-zmq-protocol-impact-20261105/README.md) | 2026-11-05 | `REMOTE-HASHES.sha256` | **자격(레거시)**: `Service Request` MAC 단발 변조 영향 3/3 통과 |
| `uplink-dos` | [p5-l3-21-input-emulation-20261111](../reproducers/uplink-dos/artifacts/p5-l3-21-input-emulation-20261111/README.md) | 2026-11-11 | — | **중간 재생**: 참조 기반 L3-21 탐지기 입력 재생 3/3 통과 |

## 5. 무결성·명칭·비공개 규칙

- **해시 파일 규약**: `MANIFEST.sha256`과 `SHA256SUMS`는 저장소 안의 요약 파일 또는 로컬 번들 목록을 검증한다. `SHA256SUMS.remote`와 `REMOTE-HASHES.sha256`은 원격 실행 서버의 비공개 원문(원시 로그·pcap·가입자 설정) 해시를 고정한다.
- **비공개 원칙**: `.gitignore`에 따라 `/artifacts/*/**` 아래 원시 산출물은 Git에 올리지 않으며 요약 Markdown·해시·`campaign.json`만 게시한다.
- **과거 명칭 대응**: 봉인 기록에 남은 `A`, `canonical A`, `Mode A` 등 과거 시나리오명의 현행 설명형 명칭 대응은 [LEGACY-NAMES.md](LEGACY-NAMES.md)에 있다.
- **민감정보 정제 이력**: 2026-10-30 과거 UE 로그 credential 정제 경위와 검사 방법은 [SECURITY-REDACTION-20261030.md](SECURITY-REDACTION-20261030.md)에 있다.

### 봉인 기록 무수정 예외

봉인 증거 불변 원칙에 따라 아래 1건은 사후 수정이나 해시 재계산을 하지 않고 기존 상태로 유지한다.

- `artifacts/p5-default-cleanup-rate-v2-20261030/SHA256SUMS`: `./README.md` 항목의 기존 해시 불일치(`d69221e` 이후)는 봉인 기록 불변 원칙에 따라 수정하지 않고 그대로 둔다.
