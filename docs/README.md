# 문서 목록

이 디렉터리는 운영 가이드, 공격 카탈로그, 명명 규칙, 초기 RSS 연구 문서, 이력 메모를 모은다. 저장소 전체 진입점은 [README.md](../README.md), AI 작업 규칙은 [AGENTS.md](../AGENTS.md)이다.

## 실행

- [E2E-EXECUTION-GUIDE.md](E2E-EXECUTION-GUIDE.md) — L3 7종 `same-cell` 공식 토폴로지, 실행 진입점, E2E 합격 조건을 정의한다.
- [CONTROL-GUIDE.md](CONTROL-GUIDE.md) — `./tools/ctl.sh` CLI 명령, `doctor` 검증 범위, 환경변수, 산출물 구조를 정리한다.
- [workloads/normal-ue/README.md](../workloads/normal-ue/README.md) — 정상 UE 5대 독립 virtual RU 풀과 `same-cell` broker 아키텍처를 설명한다.

## 공격 모듈

- [ATTACK-CATALOG.md](ATTACK-CATALOG.md) — L3 7종·AN 6종 카탈로그, 재현 수준 4단계, [주장과 한계](ATTACK-CATALOG.md#주장과-한계)를 정리한다.
- [ATTACK-REFERENCES.md](ATTACK-REFERENCES.md) — 13개 모듈의 3GPP·논문·공개 코드 레퍼런스와 자체 구현 범위를 구분한다.
- [NEW-MODULE-GUIDE.md](NEW-MODULE-GUIDE.md) — 신규 모듈 추가 절차, `reproducer.json` 스키마, `tools/ctl.sh`·lock 제약을 설명한다.
- [NAMING-CONVENTIONS.md](NAMING-CONVENTIONS.md) — 문서·디렉터리·ID 명명 규칙과 코드·lock 종속 예외 목록을 기록한다.
- [reproducers/README.md](../reproducers/README.md) — `reproducers/` 아래 L3 7종·AN 6종 모듈 인덱스와 별칭 대응표를 제공한다.

## 환경

- [PORTING-GUIDE.md](../PORTING-GUIDE.md) — 호스트 포팅 절차와 p5·차폐 OTA 운영 체크리스트를 정리한다(`tools/ctl.sh:98` 잠금으로 루트 유지).

## 연구

- [research/comparison-5g.md](research/comparison-5g.md) — 5G NR 기준 기존 RSS 연구·공격 도구의 원문 대조 요약판이다.
- [research/design.md](research/design.md) — `RRCSetupComplete` 미전송형 RSS 재현기 상태 기계·노브·라벨 설계 문서다.
- [research/methodology.md](research/methodology.md) — RSS 재현 실험 시나리오, F1-C 관측 경계, 단계별 합격 기준을 정의한다.
- [research/rss-landscape.md](research/rss-landscape.md) — RSS 공격 변종, 논문, 공개 도구의 비교와 재현기 요구사항을 정리한다.
- [research/rss-theory.md](research/rss-theory.md) — RSS 단계별 자원 할당, 고갈 동역학, OCUDU 기본 수치(§8 단일 출처)를 설명한다.
- [research/tool-survey.md](research/tool-survey.md) — OCUDU 정상 UE 연결 경로와 `5gattacks`·다중 UE 코드 재사용 범위를 정리한다.

## 이력

- [history/README.md](history/README.md) — 저장소 변천 요약과 `docs/history/`·`docs/research/` 문서 안내다.
- [history/testbed-limitations.md](history/testbed-limitations.md) — 2026-10-20 초기 RSS p5 ZMQ 환경 제약과 10 ms 폴 타임아웃 해결 기록이다.
- [history/testbed-checklist.md](history/testbed-checklist.md) — 2026-10-16~11-02 초기 RSS p5 디버깅 발췌록이다.
- [artifacts/README.md](../artifacts/README.md) — 루트 `artifacts/`(21개)와 모듈별 `reproducers/*/artifacts/`(11개) 봉인 증거 인덱스다.
