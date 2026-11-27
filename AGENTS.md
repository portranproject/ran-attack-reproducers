# AGENTS.md — 기지국 공격 재현 도구 작업 규칙

이 저장소는 팀 소유 5G/O-RAN 테스트베드(OCUDU 26.10 CU/DU, OAI 2026.w38 UE, Open5GS, TeleRAN 100 ms eBPF 프록시, production detector, dashboard)에서 기지국 공격을 재현하고 탐지·대응기 입력과 정답을 검증하는 도구 모음이다. (`CLAUDE.md`는 이 파일의 심볼릭 링크다.)

## 실행 전 필수 규칙

1. 사람과 AI 모두 [docs/E2E-EXECUTION-GUIDE.md](docs/E2E-EXECUTION-GUIDE.md)의 공식 토폴로지와 runner만 사용한다.
2. 개별 모듈은 `./tools/ctl.sh doctor --profile <환경>`, 정상 UE 5대 통합 실행은 `./tools/ctl.sh same-cell doctor --profile <환경>`이 실패하면 중단한다. OAI 바이너리 직접 실행이나 `/tmp` 수동 스크립트로 대체하지 않는다.
3. L3 7종 정상 UE 통합 자격은 `./tools/ctl.sh same-cell run` 또는 `./tools/ctl.sh same-cell campaign l3-live --sets 3 --count 5 --enable`만 사용한다. 같은 CU·DU 인스턴스와 셀 식별자를 유지한 채 phase마다 DU·broker·UE 프로세스를 cold-start하고 CU·코어·dashboard는 유지한다.
4. `run.sh`, `tools/ctl.sh`, `tools/reproctl.py` 등 핵심 파일은 `integration.lock.json`에 SHA-256이 고정돼 있다. ZIP/복사본이나 추적 파일 수정 상태에서는 자격 실행을 진행하지 않는다.
5. 과거 개별 자격(L3-01-O 2프로세스×5 UE, L3-20 direct 2-cell 등)을 `same-cell` 자격으로 바꿔 적지 않고, `p1`·`p5` 자격을 `p4`·`OTA` 자격으로 복사하지 않는다.

## 재현 도구 완료 기준 및 주장 경계

- **3단계 완료 기준**: (1) 3GPP·논문·공개 구현 고정 URL로 메시지 흐름 확인, (2) 정상 대조군과 공격군에서 실제 경로 또는 명시된 에뮬레이션 재현 및 원문·정답·SHA-256 봉인, (3) CU/F1/N2/eBPF 탐지 입력과 UE·코어 oracle 분리 및 특징·라벨·시간 경계 문서화.
- **기지국·코어·detector 무수정 원칙**: 공격은 UE 측만 수정한다. OCUDU·Open5GS·detector 소스를 바꾸거나 서비스 거부만 만들기 위해 timer/capacity를 완화·증설하지 않는다(기본 상한 CU 1대 + DU 1대).
- **독립 차원 판정**: `mechanism`, `detection_input`, `detector_result`, `service_impact`를 분리 판정한다. 서비스 거부가 `not_observed`여도 실패로 덮어쓰지 않으며, 관측되지 않은 RF overshadowing·MITM·counter wrap·OTA·상용망 일반화는 주장하지 않는다.
- **용어·경로 사실**: MobiFlow는 탐지기가 아니라 텔레메트리 구조화 프레임워크이며 탐지는 detector(`766f5569...`)가 수행한다. OCUDU E2SM-KPM 최소 보고 주기는 1초·노드 카운터 중심이므로 UE별 순서 검증에는 F1 수준 계측(`TeleRAN`)이 필요하다. E2 제어 대응은 별도 성립 조건이며 이 저장소 범위에서 입증된 폐루프가 아니다.

## 현재 자격 현황 요약

- **L3 7종 `p1` same-cell 자격 (`p1q9-20261119`)**: L3-01-V, L3-01-O, L3-20, L3-21, L3-24, L3-14, L3-06 전 종이 정상 UE 5대와 같은 셀에서 `control → active` 3세트(총 42/42) 통과. → [p1 자격 기록](artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- **L3 7종 `p5` 자격**: 5종 live E2E 요약([2026-11-17 요약](artifacts/p5-live-e2e-five-20261117/README.md)), L3-21 same-cell([p5-l3-21](reproducers/uplink-dos/artifacts/p5-l3-21-live-same-cell-20261116/README.md)), L3-06 live([p5-live-result](reproducers/nas-counter-desynchronization/artifacts/p5-live-result-20261117/README.md)) 모두 3/3 통과. OTA는 전원 `pending`.
- **AN 6종 (`AN-01`, `AN-06a`, `AN-02`, `AN-04`, `AN-07`, `AN-08`)**: 공격 1.0 자격 범위 밖의 `detector-input-emulation` 회귀 fixture. → [replay 기록](artifacts/production-detector-rule-replay-20261112/README.md)

## 저장소·문서 안내

| 영역 | 위치 |
|---|---|
| 빠른 시작·전체 구조 | [README.md](README.md), [docs/README.md](docs/README.md) |
| 공식 E2E 실행·`same-cell` 규칙 | [docs/E2E-EXECUTION-GUIDE.md](docs/E2E-EXECUTION-GUIDE.md) |
| `tools/ctl.sh` CLI·환경변수·`doctor` 범위 | [docs/CONTROL-GUIDE.md](docs/CONTROL-GUIDE.md) |
| 환경 포팅·p5/OTA 운영 | [PORTING-GUIDE.md](PORTING-GUIDE.md) ([p5 운영](PORTING-GUIDE.md#p5-운영-체크리스트), [OTA 운영](PORTING-GUIDE.md#차폐-ota-운영-체크리스트)) |
| 공격 카탈로그·주장 한계·레퍼런스 | [docs/ATTACK-CATALOG.md](docs/ATTACK-CATALOG.md) ([주장과 한계](docs/ATTACK-CATALOG.md#주장과-한계)), [docs/ATTACK-REFERENCES.md](docs/ATTACK-REFERENCES.md) |
| 모듈 추가·명명 규칙 | [docs/NEW-MODULE-GUIDE.md](docs/NEW-MODULE-GUIDE.md), [docs/NAMING-CONVENTIONS.md](docs/NAMING-CONVENTIONS.md) |
| 모듈별 상세 구현·계약 | [reproducers/README.md](reproducers/README.md), 각 `reproducers/<attack>/README.md`·`reproducer.json` |
| 정상 UE 5대 풀·broker | [workloads/normal-ue/README.md](workloads/normal-ue/README.md) |
| 봉인 증거·이력·RSS 연구 문서 | [artifacts/README.md](artifacts/README.md), [docs/history/README.md](docs/history/README.md) (`testbed-checklist.md`, `testbed-limitations.md`), `docs/research/` ([comparison-5g.md](docs/research/comparison-5g.md)·[design.md](docs/research/design.md)·[methodology.md](docs/research/methodology.md)·[rss-landscape.md](docs/research/rss-landscape.md)·[rss-theory.md](docs/research/rss-theory.md)·[tool-survey.md](docs/research/tool-survey.md)) |

## 문서·보안·증거 원칙

- **문서 언어·파일명**: Markdown은 한국어를 기본으로 하며 `.ko.md`·`.en.md` 언어 접미사를 두지 않는다.
- **봉인 증거 불변**: `artifacts/` 및 `reproducers/*/artifacts/`의 봉인 원문·manifest·해시 파일은 수정하지 않는다. 원시 로그·pcap·credential은 Git에 추가하지 않고 텍스트 판정·요약·SHA-256만 게시한다.
- **민감정보·1차 출처**: IMSI/SUPI/K/OPc/개인키/실제 사설·공인 IP를 문서나 코드에 복사하지 않는다. 외부 논문·코드는 고정 URL(arXiv·DOI·commit SHA)로만 참조하고 복사본을 Git에 두지 않는다.
