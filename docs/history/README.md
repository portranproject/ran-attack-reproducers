# 이력 및 연구 문서 안내

이 디렉토리는 초기 RSS(L3-01-V) 단계의 p5 ZMQ 실험 메모를 보존한다. 현행 운영 절차와 주장 범위는 저장소 가이드([README.md](../../README.md), [docs/E2E-EXECUTION-GUIDE.md](../E2E-EXECUTION-GUIDE.md), [docs/ATTACK-CATALOG.md#주장과-한계](../ATTACK-CATALOG.md#주장과-한계))를 따른다.

## 저장소 변천 요약

- **2026-10**: `RRCSetupComplete` 미전송형(`L3-01-V`) 문헌 조사, 재현기 설계, p5 ZMQ 다중 UE·브로커 실측을 수행했다.
- **2026-11 초~중순**: L3 공격 7종(레거시 `uplink-dos` MAC 변조 에뮬레이션 포함)과 AN 참고 fixture 6종을 `reproducer.json`·`ctl.sh`·`tools/reproctl.py` 플랫폼으로 통합하고 p5 개별 자격을 완료했다.
- **2026-11-19**: p1 clean-origin 환경에서 정상 UE 5대와 같은 셀로 L3 7종을 실행해 42/42 same-cell E2E 자격을 통과했다([p1 자격 결과](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)).

## `docs/history/` 문서 목록

| 문서 | 작성 시점 | 내용 및 현행 대체 위치 |
|---|---|---|
| [testbed-limitations.md](testbed-limitations.md) | 2026-10-20 | p5 ZMQ 환경 초기 제약 메모. 단일 라디오 포트쌍 한계와 `./ctl.sh status`는 [normal-ue](../../workloads/normal-ue/README.md)와 [docs/ATTACK-CATALOG.md#주장과-한계](../ATTACK-CATALOG.md#주장과-한계)로 대체됐다 |
| [testbed-checklist.md](testbed-checklist.md) | 2026-10-16~11-02 | `## 16.`부터 시작하는 p5 RSS 디버깅 발췌본. 제거된 스크립트(`collect.sh`, `deploy.sh`, `run_attack.sh`, `./ctl.sh up`) 기록은 [PORTING-GUIDE.md](../../PORTING-GUIDE.md)와 [docs/E2E-EXECUTION-GUIDE.md](../E2E-EXECUTION-GUIDE.md)로 대체됐다 |

로컬 작업 메모였던 `HANDOFF.md`와 `midterm-rss-draft.md`는 `.gitignore`에 의해 Git 추적 대상에서 제외돼 있다. `midterm-rss-draft.md`의 2026-10-26 보존본만 [archive-du-cell-resource-20261026](../../artifacts/archive-du-cell-resource-20261026/README.md) 안에 남아 있다.

## `docs/research/`의 RSS 연구 문서 6종

초기 RSS(`L3-01-V`) 연구·설계 문서 6종은 `docs/research/` 아래로 옮겨 관리한다. [comparison-5g.md](../research/comparison-5g.md) §8의 작성자 보류 구간(`TODO(human)`)과 원문 바이트를 보존한 채 이동했다.

| 문서 | 주제 |
|---|---|
| [rss-theory.md](../research/rss-theory.md) | RSS 단계별 자원 할당, 고갈 동역학, OCUDU 기본 수치(§8 단일 출처) |
| [rss-landscape.md](../research/rss-landscape.md) | RSS 변종 분류, 논문·공개 도구 비교, 부록 A 정정 목록 |
| [tool-survey.md](../research/tool-survey.md) | OCUDU 정상 UE 연결 경로와 `5gattacks`·다중 UE ZMQ 재사용 범위 |
| [methodology.md](../research/methodology.md) | RSS 실험 시나리오, F1-C 관측 경계, 실행 기록, 단계별 합격 기준 |
| [design.md](../research/design.md) | `RRCSetupComplete` 미전송형 재현기 상태 기계·노브·라벨 스키마 설계 |
| [comparison-5g.md](../research/comparison-5g.md) | 5G 기준 연구·공격 도구 대조 요약판(§8 작성자 보류 구간 포함) |

## 관련 디렉토리

- [artifacts/README.md](../../artifacts/README.md) — 루트 `artifacts/` 21개와 `reproducers/*/artifacts/` 11개 봉인 근거 전체 인덱스
