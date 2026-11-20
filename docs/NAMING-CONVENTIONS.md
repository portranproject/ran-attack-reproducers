# 명명 규칙 (Naming Conventions)

이 문서는 저장소 내 디렉터리, Markdown 문서, manifest ID, `ctl.sh` 명령, 스크립트, 설정, 아티팩트의 명명 규칙과 현재 lock으로 유지 중인 예외 목록을 정리한다.

## 1. 표준 명명 규칙

| 대상 | 규칙 | 예시 |
|---|---|---|
| 최상위·`docs/` 운영 가이드 | `ALL-CAPS-KEBAB.md` (한국어 기본, `.ko.md`/`.en.md` 접미사 금지) | `README.md`, `PORTING-GUIDE.md`, `docs/E2E-EXECUTION-GUIDE.md`, `docs/ATTACK-CATALOG.md` |
| AI 규칙 문서 | `AGENTS.md` + 심볼릭 링크 `CLAUDE.md -> AGENTS.md` | `AGENTS.md`, `CLAUDE.md` |
| 문서 인덱스·연구·이력 문서 | `docs/` 하위 목적별 경로 (`docs/README.md`, `research/`·`history/`는 소문자 kebab-case 허용) | `docs/README.md`, `docs/NAMING-CONVENTIONS.md`, `docs/research/`, `docs/history/` |
| 모듈 디렉터리 | `reproducers/<설명형-kebab-case>/` (`reproducer.json`의 `module`과 일치 필수) | `reproducers/blind-dos/`, `reproducers/ue-capability-hijacking/` |
| 모듈 내부 문서 | `README.md`, `USAGE-GUIDE.md`, `DETECTION-CONTRACT.md`, `DESIGN.md`, `IMPLEMENTATION-PLAN.md`, `PROVENANCE.md`, `NOTICE.md` | `reproducers/blind-dos/USAGE-GUIDE.md` |
| 모듈 내부 스크립트 | `bin/<prefix>-build`, `<prefix>-run`, `<prefix>-campaign` | `bin/blind-build`, `bin/blind-run`, `bin/blind-campaign` |
| 설정 예제 | `conf/<prefix>.conf.example` (실제 `.conf`는 Git 제외, `0600` 이하) | `conf/rss.conf.example`, `conf/uplink.conf.example` |
| 봉인 아티팩트 | `artifacts/<scope>-<YYYYMMDD>/` | `artifacts/p1-clean-origin-live-e2e-20261119/` |

`E2E-EXECUTION-GUIDE.md`, `CONTROL-GUIDE.md`, `ATTACK-CATALOG.md`, `ATTACK-REFERENCES.md`, `NEW-MODULE-GUIDE.md` 상세 가이드는 `docs/` 아래에 두고 루트에는 1줄 리다이렉트 스텁을 유지한다. `README.md`, `PORTING-GUIDE.md`(`ctl.sh:98` 및 `integration.lock.json` 잠금), `AGENTS.md`, `CLAUDE.md`, `NOTICE.md`는 루트에 둔다. `P5-OPERATIONS.md`, `OTA-OPERATIONS.md`, `CLAIMS-AND-LIMITS.md`는 각각 `PORTING-GUIDE.md`와 `docs/ATTACK-CATALOG.md#주장과-한계`를 가리키는 1줄 스텁만 남긴다.

## 2. 현재 유지 중인 예외 (코드·Lock 종속)

아래 항목은 `integration.lock.json`, `ctl.sh`, `tools/reproctl.py`, `workloads/normal-ue/bin/same-cell-run`, 또는 봉인된 아티팩트 링크와 맞물려 있어 임의로 이름을 바꾸지 않는다. 2026-11-19 오너 결정에 따라 현 단계에서는 lock·봉인 호환성을 위해 그대로 유지한다.

| 예외 항목 | 실제 상태 | 종속·제약 근거 |
|---|---|---|
| `reproducers/` 평면 배치 | L3 7종과 AN 6종이 `reproducers/` 아래 같은 깊이에 공존 (현 단계 구조 유지, 오너 결정 #2) | `ctl.sh:69-81`, `reproctl.py:176` (`reproducers/*/reproducer.json`) |
| `uplink-imsi-extractor/` vs `uplink-identifier-exposure` (`AN-02`) | 디렉터리/`module`은 `uplink-imsi-extractor`, `reproducer.json` `id`는 `uplink-identifier-exposure`; `ctl.sh`는 폴더명을 거부하고 `an-02`·`uplink-identifier-exposure`·`uplink-imsi`만 허용 | `ctl.sh:30,77`, `reproctl.py:145` |
| `rrc-signaling-storm/` vs `rrc-context-exhaustion` vs `rrc-storm` (`L3-01-V`) | 디렉터리 `rrc-signaling-storm`, manifest `id` `rrc-context-exhaustion`, `ctl.sh` 기본 ID `rrc-storm`, 스크립트 접두어 `rss-*` | `ctl.sh:20,71,111,343`, `integration.lock.json` |
| `downlink-imsi-extractor/` vs `downlink-identifier-exposure` vs `downlink-imsi` (`L3-24`) | 디렉터리 `downlink-imsi-extractor`, manifest `id` `downlink-identifier-exposure`, `ctl.sh` 기본 ID `downlink-imsi` | `ctl.sh:25,75,348`, `integration.lock.json` |
| `authentication-timeout-exhaustion/` vs `auth-timeout` (`L3-01-O`) | `ctl.sh` ID `auth-timeout`, runner `bin/auth-stall-cell-run`, 환경변수 `AUTH_STALL_CELL_CONF` (레거시 `auth-timeout-run`만 `AUTH_TIMEOUT_CONF` 사용) | `ctl.sh:24,114,333,347`, `integration.lock.json` |
| `uplink-dos/` 공존 구조 | L3-21(`uplink-credential-flood`)과 레거시 단발 MAC 변조(`uplink-dos`, manifest 없음)가 한 디렉터리 공유 | `ctl.sh:22-23,73,345-346`, `integration.lock.json` |
| `nas-counter-desynchronization/` 축약형 (`L3-06`) | 디렉터리 `nas-counter-desynchronization`, `ctl.sh` 별칭 `l3-06`, `bin/nas-counter-desync-*`, `same-cell-run` 내부 별칭 `nas-counter-desync` | `ctl.sh:27,350,492`, `same-cell-run:24,103`, `integration.lock.json` |
| `conf/p5-zmq.conf.example` | `blind-dos`, `downlink-imsi-extractor`, `ue-capability-hijacking`이 `ctl.sh` 기본 설정 예제로 `p5-zmq.conf.example` 사용 | `ctl.sh:125,128-129` |
| 날짜형·봉인 링크 예외 | `docs/history/testbed-*.md`, `workloads/normal-ue/docs/*-20261113.md`(`SAME-CELL-HOT-SWAP-20261113.md`는 `same-cell-run:704` 참조) | `integration.lock.json:13`, 봉인 불변 원칙, `docs/research/comparison-5g.md` 무수정 보존 |
