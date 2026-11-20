# 문서 구조 개편 보고서 (`docs/restructure-20261119`)

2026-11-19 기준 저장소 전역의 Markdown 문서를 코드·설정·봉인 증거(`p1q9-20261119` 42/42 포함) 및 오너 결정 8건에 맞춰 단일 출처(SSOT) 구조로 개편한 결과를 정리한다.

## 1. 개요 및 변경 요약

- **원칙 준수**: 코드·스크립트·패치·설정 예제(`.conf.example`/`.json`)·테스트·`NOTICE.md`·`CLAUDE.md` 심볼릭 링크는 수정하지 않았다. 봉인된 `artifacts/` 및 `reproducers/*/artifacts/` 원문·manifest·해시 파일도 수정하지 않았으며, `docs/research/comparison-5g.md`는 `git mv`로 이동하되 §8 `TODO(human)` 포함 바이트 단위 무수정(`10f91521...`)을 유지했다. 민감정보·키·IMSI·실제 IP는 문서에 포함하지 않았다.
- **최상위 SSOT 가이드 정리 및 통합**:
  - `README.md`: 빠른 시작과 저장소 안내로 축약하고, L3 7종 `p5`/`p1 same-cell 42/42` 현황표와 `@common-signal` 전용 `replay|report|verify` 구분을 반영했다.
  - `E2E-EXECUTION-GUIDE.md`, `CONTROL-GUIDE.md`: 실행 토폴로지/`same-cell` 기준과 `ctl.sh` CLI·`doctor` 범위 역할이 달라 분리 유지했다.
  - `PORTING-GUIDE.md`: `P5-OPERATIONS.md`와 `OTA-OPERATIONS.md`를 `## p5 운영 체크리스트`·`## 차폐 OTA 운영 체크리스트`로 통합하고 기존 두 파일은 1줄 리다이렉트 스텁으로 유지했다(`ctl.sh:98` 잠금으로 `PORTING-GUIDE.md` 경로 유지).
  - `ATTACK-CATALOG.md`, `ATTACK-REFERENCES.md`, `NEW-MODULE-GUIDE.md`, `AGENTS.md`: `CLAIMS-AND-LIMITS.md`를 `ATTACK-CATALOG.md` `## 주장과 한계`로 통합해 기존 파일은 1줄 리다이렉트 스텁으로 남겼고, `L3-06` 위치 오류와 `기존 6개 / 새 7개` 카운트 오류를 바로잡았으며 `AGENTS.md` 중복 이력 장문을 제거했다.
  - `docs/NAMING-CONVENTIONS.md` (신설·갱신): 디렉터리·문서·manifest·`ctl.sh`·스크립트·설정·아티팩트 명명 규칙과 `docs/research/`, 1줄 스텁 3건, 오너 결정 #2·#3 및 코드/lock 예외를 문서화했다.
- **연구·이력 문서 및 아티팩트 인덱스**:
  - 루트 RSS 연구 6종(`comparison-5g.md`, `design.md`, `methodology.md`, `rss-landscape.md`, `rss-theory.md`, `tool-survey.md`)을 `docs/research/`로 `git mv` 이관하고 비봉인 문서 상대 링크를 갱신했다. 봉인된 `artifacts/archive-du-cell-resource-20261026/rss-landscape.md:3`의 구 루트 상대 링크는 봉인 불변 원칙에 따라 그대로 두고 `artifacts/README.md`에 예외를 기록했다.
  - `testbed-checklist.md`·`testbed-limitations.md`를 `docs/history/`로 이동(`git mv`)하고 역사적 기록 안내 배너를 추가했다.
  - `docs/history/README.md` (신설): 2026-10 RSS → 2026-11 플랫폼 → 2026-11-19 `p1` 42/42 흐름과 `docs/research/` RSS 연구 6종 인덱스를 제공한다.
  - `artifacts/README.md` (신설): 루트 `artifacts/` 21개와 `reproducers/*/artifacts/` 11개 디렉터리, 무결성 해시 파일 규칙, 봉인 예외 항목을 정리한 비봉인 인덱스다.
- **L3 공격 7종 모듈 문서 (`25개`: `24개` 수정 + `reproducers/rrc-signaling-storm/docs/REFERENCE.md` 신규 1개)**:
  - 7종 모두 통일된 6단 템플릿(`개요 및 룰 정보` → `동작 요약` → `실행 방법` → `합격 기준` → `한계 및 금지 주장` → `관련 문서 및 근거`)으로 `README.md`를 정비하고 `p1q9-20261119` 6/6 결과를 반영했다.
  - `reproducers/rrc-signaling-storm/README.md`(기존 1,029줄)는 핵심 템플릿으로 축약하고 상세 기술 레퍼런스를 `docs/REFERENCE.md`로 분리했다(`conf/rss.conf.example` 앵커 링크 유지). 2026-10 진단 문서 5종에는 이력 배너를 추가했다.
  - 나머지 6개 모듈의 `USAGE-GUIDE.md`, `PROVENANCE.md`, `DESIGN.md`, `IMPLEMENTATION-PLAN.md`에서 코드 불일치를 수정했다.
- **AN fixture 6종·`reproducers/README.md`·`workloads/normal-ue/`·`rss-storm/` (`19개`)**:
  - `reproducers/README.md`를 공격 1.0 대상 L3 7종과 회귀 전용 AN fixture 6종 표로 분리했다.
  - AN 6종 `README.md`·`PROVENANCE.md`를 콤팩트 템플릿과 `reproducer.json` 고정 URL로 통일했다.
  - `workloads/normal-ue/README.md`를 현행화하고 `docs/*-20261113.md` 4개에 이력 배너를 추가했다(`SAME-CELL-HOT-SWAP-20261113.md` 파일명은 `same-cell-run:704` 잠금에 따라 유지). `rss-storm/README.md`는 호환 안내로 정비했다.

## 2. 새 디렉터리·문서 맵

```text
├── README.md                        # 프론트 도어: 7종 현황표, 빠른 시작, 전체 맵
├── E2E-EXECUTION-GUIDE.md           # 공식 E2E 설치·same-cell 토폴로지·합격 조건 (분리 유지)
├── CONTROL-GUIDE.md                 # ctl.sh CLI/메뉴·doctor 실제 범위·환경변수 (분리 유지)
├── PORTING-GUIDE.md                 # 호스트 선행조건·포팅·p5/차폐 OTA 체크리스트 통합 (ctl.sh:98 잠금)
├── P5-OPERATIONS.md                 # 1줄 리다이렉트 스텁 (-> PORTING-GUIDE.md#p5-운영-체크리스트)
├── OTA-OPERATIONS.md                # 1줄 리다이렉트 스텁 (-> PORTING-GUIDE.md#차폐-ota-운영-체크리스트)
├── ATTACK-CATALOG.md                # L3 7종 + 레거시 uplink-dos + AN 6종 + 주장과 한계 통합
├── CLAIMS-AND-LIMITS.md             # 1줄 리다이렉트 스텁 (-> ATTACK-CATALOG.md#주장과-한계)
├── ATTACK-REFERENCES.md             # 모듈별 고정 레퍼런스 URL 및 자체 구현 범위
├── NEW-MODULE-GUIDE.md              # 신규 모듈 추가 절차·스키마·ctl.sh/lock 제약
├── AGENTS.md (CLAUDE.md -> AGENTS.md) # AI/팀원 필수 작업 규칙
├── NOTICE.md                        # 격리 테스트베드 사용 범위·고지 (무수정)
├── docs/history/DOCS-RESTRUCTURE-20261119.md  # 본 문서 개편 기록
├── docs/
│   ├── NAMING-CONVENTIONS.md        # 표준 명명 규칙, 1줄 스텁·오너 결정 및 코드/lock 예외
│   ├── research/                    # 루트에서 이관한 RSS 연구 6종 (comparison-5g.md 무수정 유지)
│   │   ├── comparison-5g.md
│   │   ├── design.md
│   │   ├── methodology.md
│   │   ├── rss-landscape.md
│   │   ├── rss-theory.md
│   │   └── tool-survey.md
│   └── history/
│       ├── README.md                # 이력·docs/research/ 6종 인덱스
│       ├── testbed-checklist.md     # (구 루트) 2026-10 p5 체크리스트
│       └── testbed-limitations.md   # (구 루트) 2026-10 단일 ZMQ 한계 기록
├── artifacts/
│   └── README.md                    # (신설) 봉인 증거 21+11 디렉터리 비봉인 인덱스 (봉인 예외 3건 기록)
├── reproducers/
│   ├── README.md                    # L3 7종 vs AN 6종 분류 인덱스 (현 단계 평면 구조 유지)
│   ├── <L3 7종>/                    # 통일 6단 README + 동반 문서 (rrc/docs/REFERENCE.md 포함)
│   └── <AN 6종>/                    # 통일 콤팩트 README + 고정 URL PROVENANCE
├── workloads/normal-ue/
│   ├── README.md                    # 독립 virtual RU 5대 + broker 현행 가이드
│   └── docs/*-20261113.md           # 이력 배너 추가 (파일명 유지)
└── rss-storm/README.md              # 과거 봉인 아티팩트·check_sensitive_* 호환 안내 (유지)
```

## 3. 기존 문서와 코드·증거 간 불일치 목록

### 3.1 문서에서 코드 기준으로 수정 완료한 항목

| 영역 | 기존 문서 주장 | 실제 코드·증거 (수정 반영) |
|---|---|---|
| 최상위 (`CLAIMS-AND-LIMITS.md`, `ATTACK-REFERENCES.md`) | `기존 6개 룰`·`새 7개 룰`로 표기해 `L3-06`을 `live_protocol_path_observed=false` 탐지 입력 전용으로 분류, `L3-20 same-cell` 실패 유지 | `L3-06`은 `protocol-result-emulation`·`p5: qualified`·`p1q9` 6/6 통과. live L3는 **7종**(+레거시 `uplink-dos`), AN 회귀 fixture는 **6종**. `L3-20`도 `p1q9` same-cell 6/6 통과 |
| 최상위 (`CONTROL-GUIDE.md`, `PORTING-GUIDE.md`) | `auth-timeout` 설정 환경변수를 `AUTH_TIMEOUT_CONF`로 안내 | `ctl.sh:114,333`과 `auth-stall-cell-run:7`은 **`AUTH_STALL_CELL_CONF`** 사용 (`AUTH_TIMEOUT_CONF`는 레거시 4-cell runner 전용) |
| 최상위 (`README.md`, `E2E-EXECUTION-GUIDE.md`, `P5-OPERATIONS.md`, `CONTROL-GUIDE.md`) | `l3-06` 뒤 `replay/report/verify` 실행 예시; `p1` 설정에 `credentials_file`/`normal-ue setup` 누락; `doctor`가 CU/DU 양쪽 `tcpdump`·`tshark` 및 detector SHA-256을 대조한다고 기술; `active RAISE 1건`으로 기술 | `replay/report/verify`는 `profile.run_root` 7-파일(`@common-signal`) 전용. `reproctl.py`는 CU `tcpdump`+`tshark`·`.deployed-revision` 확인 및 해시 출력, `same-cell doctor`는 DU `timeout`+`tshark` 확인. `ctl.sh doctor` 기본 `all`은 8개 OAI 로컬 설정/바이너리까지 검사. `verify_live_e2e.py:150`은 `RAISE >= 1` 판정 |
| 최상위 (`AGENTS.md`, `README.md`, `PORTING-GUIDE.md`, `NEW-MODULE-GUIDE.md`) | 루트 `reproducer.json` 표기; `rss-storm/`에 위임 스크립트 존재 표기; `profiles/ota.example.json` 직접 수정 안내; `ctl.sh` 동적 manifest 분기 암시 | `reproducers/*/reproducer.json` 13개만 존재. `rss-storm/`은 문서+민감검사 스크립트만 보유(`bin/` 없음). `profiles/ota.json` 복사 필요. `ctl.sh`는 `ATTACKS`/`case` 하드코딩 및 `integration.lock.json` 잠금 |
| L3 `rrc-signaling-storm/` | `rss-build`가 `oai-pucch-null-fix.patch`+`rss-ue-curated.patch` 2개 적용; `ctl.sh same-cell` 누락; `EVIDENCE-CU30`의 `RSS_SHARE_NUE=5`(`-u 6`) 예시 | `bin/rss-build:19-22,80-86`은 패치 4개 적용(`rss-ue-curated`, `oai-stale-rnti-dci`, `oai-msg4-ack-rnti`, `oai-broker-control-gate`). `ctl.sh:517-529` `rss-broker-witness`(`BROKER_WITNESS_MULTI_RU=1`) 반영 및 `RSS_SHARE_NUE == NUM_UES` 제약 주석 추가 |
| L3 `authentication-timeout-exhaustion/` | `PROVENANCE.md` base commit `1c2f4d3c...`; 2개 패치만 기술; 10-UE same-cell "미자격" 표기 | `bin/auth-timeout-build:6`은 `6d6782b4...` 기반 패치 4개 적용(`ru-sharing-w38`, `normal-multi-ru`, `auth-timeout-ue-w38`, `same-cell-ra-gate-w38`). `p1q9-20261119` 6/6 통과 반영 |
| L3 `blind-dos/` | `same-cell` 미승인 유지 및 패치 1개만 기술 | `bin/blind-build:32-35`는 패치 2개(`blind-ue-w38`+`same-cell-ra-gate-w38`) 적용. 2026-11-16 pre-gate p5 한계와 2026-11-19 `p1q9` same-cell 6/6 구분 |
| L3 `uplink-dos/` | `USAGE-GUIDE.md:101-102`에 잘못된 `ctl.sh same-cell run ... -- ...` 문법 기재; L3-21 패치·검증 스크립트 누락 | `ctl.sh:657-680`은 `--` 미지원 → `--profile <p> --mode attack --run-id <id> --enable`로 수정. 3개 패치·`verify_*`·`p1q9` 6/6 반영 |
| L3 `downlink-imsi-extractor/`, `ue-capability-hijacking/` | `same-cell-ra-gate-w38.patch`·`p1q9` 6/6 누락; `ue-capability` clean worktree 선행조건 누락 | 각 2개 패치 및 `ctl.sh setup` 선행조건, `p1q9` 6/6, `downlink-imsi` `UECAP` 복사 주의사항 반영 |
| L3 `nas-counter-desynchronization/` | 잘못된 `ctl.sh same-cell run nas-counter-desync ... -- ...` 문법 및 `same-cell` 미승인만 기술 | `ctl.sh:27`은 `l3-06`/`nas-counter-desynchronization`만 허용 → 올바른 CLI 및 `p1q9` same-cell 6/6 반영 |
| `reproducers/README.md` & AN 6종 | 6개만 나열(`L3-06`·AN 6종 누락); `uplink-imsi-extractor`에 `0/3, 3/3` replay 결과 누락 및 `ctl.sh` ID 불일치 미안내 | L3 7종+AN 6종 분리; AN 6종 replay(`a34b358e...`) 링크 및 `an-02`/`uplink-identifier-exposure` 사용 안내 추가 |
| `workloads/normal-ue/` & `docs/history/` | `SAME-CELL-HOT-SWAP-20261113.md`의 양방향 gain, `auth-timeout` 4 endpoint, `hot-run` 표기; `normal-ue/README.md`의 2개 패치·DU cold-start 표현; `testbed-limitations.md` 단일 포트 한계 및 `./ctl.sh status` | `same_cell_broker.py`(`dl_gate=1.0` 고정, `ul_gate` `0↔1`, `null_source` retire), `auth-timeout` 10슬롯, `normal-ue-build` 9패치, CU 유지·DU 프로세스 cold-start 반영. `testbed-*`는 `docs/history/`로 이동하고 배너 추가 |

### 3.2 코드·설정 자체의 잠긴 불일치 (코드 무수정 원칙에 따라 문서 주의사항으로만 반영)

1. `reproducers/downlink-imsi-extractor/conf/p5-zmq.conf.example:4`: `UECAP` 경로가 `/root/OAI-uplink-dos-w38/...`로 오기돼 있음(`README.md`/`USAGE-GUIDE.md`에 로컬 복사 시 수정 주의 추가).
2. `schemas/reproducer.schema.json:48-56` & `tools/reproctl.py:158`: `environments`가 `{p5, ota}`만 허용해 `p1`/`p4` 상태를 manifest에 직접 기록할 수 없음.
3. `ctl.sh:6-88,108-145,328-374,484-495`: `reproducer.json` 동적 탐색이 아닌 `case` 하드코딩이며 `integration.lock.json:6`에 SHA-256 고정됨.
4. `reproducers/authentication-timeout-exhaustion/reproducer.json:10-14`: `analyze`/`verify`는 direct 4-cell용(`normalize_p5.py`/`verify_evidence.py`)을 가리키지만 `run`은 `bin/auth-stall-cell-run`(`verify_cell_flood.py`)을 호출함.
5. `reproducers/uplink-imsi-extractor/reproducer.json:3-4`: `id`가 `uplink-identifier-exposure`라 `ctl.sh:30`이 폴더명 `uplink-imsi-extractor`를 거부함.
6. `workloads/normal-ue/bin/same-cell-run:700-770`: `SAME_CELL_EXPERIMENTAL_SWITCH` 블록이 `case $ACTION` 뒤에 있어 도달 불가.
7. `tools/reproctl.py:332` vs `uplink-credential-flood-run:77`·`nas-counter-desync-run:79`: `CU_DASHBOARD_ENV` 정규식이 각각 `[A-Za-z0-9._-]` vs `^[a-z0-9][a-z0-9-]{0,31}$`로 상이함.
8. `workloads/normal-ue/bin/normal-ue:260-262` vs `same-cell-run:212-214`: `normal-ue status`는 `oaitun_ue$i`·고정 기본 TUN 게이트웨이 주소를 검사함.
9. `artifacts/p5-default-cleanup-rate-v2-20261030/SHA256SUMS`: 기존 커밋(`d69221e`)부터 `./README.md` 해시 기대값(`26511674...`)과 디스크(`16eab50e...`)가 불일치함.

## 4. 오너 결정 반영 내역

1. **루트 소문자 RSS 연구 문서 6종 `docs/research/` 이관**: `comparison-5g.md`, `design.md`, `methodology.md`, `rss-landscape.md`, `rss-theory.md`, `tool-survey.md`를 `docs/research/`로 `git mv` 이동했다. `docs/research/comparison-5g.md`는 바이트 단위 무수정(`10f91521...`, §8 `TODO(human)` 포함)을 유지하고 비봉인 문서의 상대 링크만 갱신했다. 봉인된 `artifacts/archive-du-cell-resource-20261026/rss-landscape.md:3`의 깨진 상대 링크는 봉인 불변 원칙에 따라 그대로 두고 `artifacts/README.md`에 예외로 기록했다.
2. **`reproducers/` 구조 유지**: 현 단계에서는 `integration.lock.json` 및 `ctl.sh`/`reproctl.py` 보호를 위해 `reproducers/` 평면 구조를 재편하지 않고 유지했다.
3. **`rss-storm/` 디렉터리 유지**: 과거 봉인 아티팩트 호환 안내(`README.md`) 및 `check_sensitive_*.py` 보관용으로 유지했다.
4. **소규모 최상위 문서 통합 및 스텁 유지**: `P5-OPERATIONS.md`와 `OTA-OPERATIONS.md`는 `PORTING-GUIDE.md`(`#p5-운영-체크리스트`, `#차폐-ota-운영-체크리스트`)로 통합하고, `CLAIMS-AND-LIMITS.md`는 `ATTACK-CATALOG.md`(`#주장과-한계`)로 통합했으며, 기존 3개 경로에는 1줄 리다이렉트 스텁을 남겼다. `CONTROL-GUIDE.md`와 `E2E-EXECUTION-GUIDE.md`는 역할이 달라 분리 유지했다.
5. **모듈 내부 이력 문서 유지**: `reproducers/rrc-signaling-storm/docs/` 진단 5종과 `workloads/normal-ue/docs/*-20261113.md`는 이력 배너를 유지한 채 현 위치에 두었다.
6. **코드·설정 불일치(3.2절) 이 브랜치 미수정**: 3.2절의 잠긴 코드·설정 불일치 항목은 이 문서 개편 브랜치에서 수정하지 않고 별도 코드 PR 범위로 남겼다.
7. **봉인 증거 기존 이상 기록 유지**: `artifacts/p5-default-cleanup-rate-v2-20261030/SHA256SUMS`의 `./README.md` 해시 불일치, `artifacts/LEGACY-NAMES.md:32`, `artifacts/archive-du-cell-resource-20261026/rss-landscape.md:3` 등 봉인 증거 관련 이상은 원문을 건드리지 않고 `artifacts/README.md`에만 문서화했다.
8. **로컬 미추적 초안 유지**: `.gitignore` 대상인 `HANDOFF.md`와 `midterm-rss-draft.md`는 미추적 상태 그대로 유지했다.

## 5. 검증 결과 요약

- **1차 개편 커밋 6건 (`docs/restructure-20261119`, base `2db860e`..`04b6455`)**:
  1. `docs: reorganize root guides and add naming conventions` (`657164f`)
  2. `docs: move historical testbed notes and add history and evidence indexes` (`54f4952`)
  3. `docs: unify L3 attack reproducer READMEs and align companion docs with code` (`8ce1080`)
  4. `docs: standardize AN reference fixture docs and update reproducers index` (`64383c9`)
  5. `docs: align normal-ue workload and legacy rss-storm docs with code` (`7677915`)
  6. `docs: add documentation restructure report and owner questions` (`04b6455`)
- **오너 결정 반영 후속 커밋 3건 (`docs/restructure-20261119`, `04b6455..HEAD`)**:
  7. `docs: move RSS research docs to docs/research and document sealed exceptions` (`81a18d6`)
  8. `docs: merge p5/OTA into PORTING-GUIDE and claims into ATTACK-CATALOG with stubs` (`1d9ddae`)
  9. `docs: record owner decisions and post-commit verification in report` (본 보고서 커밋)
- **커밋 후 최종 검증 (clean working tree)**:
  - `git diff --stat 2db860e..HEAD -- ':!*.md'`: 변경 0건(비-Markdown 파일 무수정)
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`: `Ran 31 tests in 2.552s` — `OK`
  - `PYTHONDONTWRITEBYTECODE=1 python3 tools/reproctl.py checkout`: `OK reproducer checkout: <HEAD>` (`integration.lock.json` `reproducer.required_files` 40/40 일치)
  - `PYTHONDONTWRITEBYTECODE=1 python3 tools/reproctl.py validate`: `manifest-validation: ok (13 modules)`
  - `PYTHONDONTWRITEBYTECODE=1 python3 reproducers/rrc-signaling-storm/analysis/check_sensitive_artifacts.py`: `sensitive-artifact-check: ok (436 files)`
  - `docs/research/comparison-5g.md`: SHA-256 `10f91521415a969ce9318d518e4755bf4cfced6c3e7d1942d0036f04b4e52afd` 무수정 유지 (`git mv` 100% rename)
  - 상대 링크 감사(비봉인 101개 `.md` + `artifacts/README.md`, 497개 상대 링크): 깨진 링크 0건(봉인 예외 `artifacts/archive-du-cell-resource-20261026/rss-landscape.md:3`는 `artifacts/README.md`에 기록)

## 6. README 개편

1. **`README.md` 개편 요약**: Best-README-Template 구조에 맞춰 상단 제목·목차·`프로젝트 소개`(`사용 기술` 포함)·`시작하기`(`사전 준비`/`설치`)·`사용법`·`저장소 구조`·`문서 목록`·`한계`·`팀·연계 저장소`·`참고` 순으로 재구성했다. 루트 `README.md`에는 핵심 요약과 주요 명령만 남기고 상세 절차·카탈로그·레퍼런스는 `docs/`로 위임했다.
2. **`docs/`로 이동한 문서 및 인덱스 신설**:
   - `docs/` 이동 5종: `E2E-EXECUTION-GUIDE.md`, `CONTROL-GUIDE.md`, `ATTACK-CATALOG.md`, `ATTACK-REFERENCES.md`, `NEW-MODULE-GUIDE.md`를 `docs/` 아래로 옮기고 각 구 루트 경로에 1줄 리다이렉트 스텁을 유지했다.
   - `CLAIMS-AND-LIMITS.md` 기존 1줄 스텁의 대상을 `docs/ATTACK-CATALOG.md#주장과-한계`로 갱신했다.
   - `docs/README.md`를 신설해 저장소 전체 문서 인덱스를 `실행`·`공격 모듈`·`환경`·`연구`·`이력` 5개 묶음으로 정리했다.
3. **루트에 남긴 문서와 이유**:
   - `README.md`: 저장소 진입점.
   - `AGENTS.md` / `CLAUDE.md`: AI 에이전트 도구가 루트에서 자동 탐색·참조한다.
   - `PORTING-GUIDE.md`: `ctl.sh:98`이 경로를 직접 참조하며 `ctl.sh`가 `integration.lock.json`에 SHA-256으로 잠겨 있다.
   - `NOTICE.md`: 루트 안전 범위 및 별도 소프트웨어 라이선스 미부여 고지다.
   - `docs/history/DOCS-RESTRUCTURE-20261119.md`: 본 문서 개편 기록이다.
   - 구 경로 1줄 리다이렉트 스텁 8종: `E2E-EXECUTION-GUIDE.md`, `CONTROL-GUIDE.md`, `ATTACK-CATALOG.md`, `ATTACK-REFERENCES.md`, `NEW-MODULE-GUIDE.md`, `CLAIMS-AND-LIMITS.md`, `P5-OPERATIONS.md`, `OTA-OPERATIONS.md` (`P5-OPERATIONS.md`·`OTA-OPERATIONS.md`는 이미 루트 `PORTING-GUIDE.md`를 직접 가리켜 이중 스텁을 피한다).
4. **새 오너 결정 질문**:
   - **Q9**: 루트 `LICENSE` 파일 추가 여부 (현재 루트 `LICENSE` 파일이 없고 `NOTICE.md`는 별도 라이선스 미부여를 명시하므로 `README.md`에서 License 섹션을 생략했다).
   - **Q10**: 루트 1줄 리다이렉트 스텁 8종(`E2E-EXECUTION-GUIDE.md`, `CONTROL-GUIDE.md`, `ATTACK-CATALOG.md`, `ATTACK-REFERENCES.md`, `NEW-MODULE-GUIDE.md`, `CLAIMS-AND-LIMITS.md`, `P5-OPERATIONS.md`, `OTA-OPERATIONS.md`)의 유지 기간 및 향후 제거 시점.
   - **Q11**: `README.md` `## 팀·연계 저장소` 섹션에 담당자 이메일이나 이슈 트래커 링크를 추가할지 여부.
