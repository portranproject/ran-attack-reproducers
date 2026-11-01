# Base-Station Attack Reproducers

팀 소유 5G/O-RAN 테스트베드에서 기지국 대상 공격을 통제된 조건으로 재현하고,
탐지·대응기의 입력과 정답을 검증하기 위한 도구 모음이다. 공격 모듈마다 구현,
설정, 라벨 계약, 실험 결과를 분리하며 RF 차폐 또는 가상 RF 환경에서만 사용한다.

처음 읽을 문서는 [AGENTS.md](AGENTS.md)다. 각 공격의 실행 명령과 검증 범위는 해당
모듈의 README를 기준으로 한다.

## 재현 도구 상태

| 도구 | 상태 |
|---|---|
| [RRC signaling storm](reproducers/rrc-signaling-storm/) | 2026-11-02 동결. 분석기 입력·정답 생성기로 사용 |
| [Blind DoS](reproducers/blind-dos/) | 준비 단계. 기존 5G-S-TMSI 주입 방식은 실측에서 반증되어 재개 조건부터 재정의 |
| [Upstream DoS](reproducers/upstream-dos/) | 범위 정의 단계. 공격 계층·대상 자원·성공 기준 확정 전에는 구현하지 않음 |

각 도구는 구현·설정·라벨 계약·실험 출력을 서로 섞지 않는다.

```text
reproducers/
├── rrc-signaling-storm/   # 동결된 구현·분석기·문서·테스트
├── blind-dos/            # 기존 접근 반증, 재개 조건 정의 중
└── upstream-dos/         # 공격 범위 정의 중
artifacts/                  # 봉인된 RRC 증거와 게시용 요약
sources/                    # 조사에 사용한 1차 자료 보관본
tool/                       # RRC 초기 역사 구현
rss-storm -> reproducers/rrc-signaling-storm  # 과거 로컬 경로 호환 링크
```

새 공격은 `reproducers/<attack-name>/`에 별도 모듈로 추가한다. 공통 실행 프레임워크는
두 번째 공격에서 실제 중복이 확인되기 전까지 만들지 않는다.

## RRC signaling storm 보존 기록

새 문서는 임의의 A/B 분류 대신 `RRCSetupComplete 미전송형`처럼 중단 지점을 드러내는
설명형 이름을 쓴다. 봉인 증거의 과거 이름은 [명칭표](artifacts/LEGACY-NAMES.ko.md)로만
해석하고 run ID·JSON 필드·체크섬 대상 원문은 바꾸지 않는다.

| 문서 | 내용 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 2026-10-19 당시 구현 계획을 보존한 역사 기록. 현재 상태는 이 README와 `reproducers/rrc-signaling-storm/` 문서가 우선 |
| [AGENTS.md](AGENTS.md) | 공통 저장소 원칙 + RRC 동결 컨텍스트 + 다음 공격 준비 상태 |
| [reproducers/rrc-signaling-storm/README.md](reproducers/rrc-signaling-storm/README.md) | 현재 재현기: 빌드·실행·노브·안전장치·판정법·검증 범위 |
| [reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.ko.md](reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.ko.md) | clean w38 curated 빌드, 정상 회귀, Msg4 ACK-on/off와 독립 broker witness 실측 |
| [reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.ko.md](reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.ko.md) | UE 정답·탐지·대응·효과 판정·시간 동기 계약 v1 |
| [reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md) | 동결된 재현기의 실행 순서·입력 격리·라벨·채점·금지 주장 |
| [reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.ko.md](reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.ko.md) | p5에서 새 exact DU ACK join을 짧게 검증하고 원복하는 실기 게이트 |
| [reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.ko.md](reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.ko.md) | RRCSetupComplete 미전송형에 닿는 대응 경로 감사와 CSI-DTX RLF hardening on/off 비교 |
| [reproducers/rrc-signaling-storm/docs/OTA-SMOKE.ko.md](reproducers/rrc-signaling-storm/docs/OTA-SMOKE.ko.md) | 차폐 OTA inventory·RF 안전·정상 UE 기준선·공격 실행의 fail-closed 게이트 |
| [artifacts/curated-verify-20261030/](artifacts/curated-verify-20261030/) | curated 빌드 계보, 3회 ACK-on/off 요약과 원격 원문 SHA-256 목록 |
| [artifacts/label-v1-rlf20-20261030/](artifacts/label-v1-rlf20-20261030/) | label v1 ACK-on/off, JSONL 동시 기록 결함 수정, CSI-DTX RLF20 실측과 원격 원문 SHA-256 |
| [artifacts/p5-du-ack-join-20261030/](artifacts/p5-du-ack-join-20261030/) | 구버전 패치·바이너리에서 RRCSetupComplete 미전송형 exact DU ACK join 10/10 실측 |
| [artifacts/p5-cu200-3cell-20261030/](artifacts/p5-cu200-3cell-20261030/) | hold32 실험 진단: DU ACK 확인 RRCSetupComplete 미전송형 176건·CU 200 도달·witness 17/17 거부. 기본 정리시간 성공 증거는 아님 |
| [artifacts/p5-msg3-cap96-20261030/](artifacts/p5-msg3-cap96-20261030/) | 실제 DU capacity 96에서 G34 정상 대조군과 G35 hold32 관측창 10.13초 자원 거부 진단 |
| [artifacts/p5-default-cleanup-rate-v2-20261030/](artifacts/p5-default-cleanup-rate-v2-20261030/) | 기본 약 2초 cleanup의 rate-v2 원문. RRCSetupRequest 후 중단형 서비스 off→별도 UE recovery on은 3/3, 동일 8-endpoint control은 정상; 지속 포화·기지국 전체 마비는 불합격 |
| [artifacts/broker-witness-20261030/](artifacts/broker-witness-20261030/) | 5개 별도 UE 프로세스의 attack-on/off 요약과 원격 원문 SHA-256 |
| [artifacts/broker-stability-20261030/](artifacts/broker-stability-20261030/) | 5 UE 시작 경합 계측, 과거 종료 SIGSEGV 주체 확인, 2단계 종료·제한 재시도 검증 |
| [artifacts/broker-sync-sampling-20261030/](artifacts/broker-sync-sampling-20261030/) | 사전 고정 15회 대조군의 sync 시작 분포, 서비스 품질, 종료 건전성 |
| [artifacts/SECURITY-REDACTION-20261030.md](artifacts/SECURITY-REDACTION-20261030.md) | 과거 UE 로그 credential 정제 범위와 키 회전·Git 이력 정리 필요사항 |
| [artifacts/LEGACY-NAMES.ko.md](artifacts/LEGACY-NAMES.ko.md) | 봉인 증거에 남은 과거 시나리오명과 현재 설명형 명칭의 대응표 |
| [artifacts/verify-20261021/README.md](artifacts/verify-20261021/README.md) | OCUDU 기본 설정에서 RRCSetupComplete 미전송형 120초 실측 원문과 판정(4,438 절차, 피크 96/96) |
| [tool-survey.md](tool-survey.md) | OCUDU 공식 UE 연결 예제, 5gattacks 패치, UCD 데모, 다중 UE ZMQ 공개물의 실제 범위 |
| [methodology.md](methodology.md) | RSS 실험 시나리오, RRCSetupComplete 미전송형 절차, F1 관측 경계, 재현기 기록과 단계별 검증 기준 |
| [rss-theory.md](rss-theory.md) | RSS 원리: 단계별 자원 할당, 조작 파라미터, 고갈 동역학, OCUDU 대입 |
| [rss-landscape.md](rss-landscape.md) | RSS 변종 분류, 논문·공개 도구 비교, 재현기 요구사항 |
| [comparison-5g.md](comparison-5g.md) | 5G 기준 기존 연구·공격 도구 비교 요약판. 주장별 원본 대조 여부 표시, 독립 재검색 결과 |
| [testbed-checklist.md](testbed-checklist.md) | 팀 테스트베드 체크리스트(AWS EC2 분리 CU/DU·ZMQ·n78 TDD 30 kHz 20 MHz·OCUDU 26.10·Open5GS·OAI UE) , OCUDU 설정에서 TDD/FDD 읽는 법, 베이스 UE 결정(OAI UE) |
| [design.md](design.md) | RRCSetupComplete 미전송형 재현기 설계: 아키텍처, 상태 기계, 노브, 라벨 스키마, 단계별 계획 |
| [sources/](sources/) | 1차 자료: 논문 PDF 2건 + 5gattacks 공격 패치 |

상태(2026-11-02): RRC storm 구현·실측은 여기서 동결하고 분석기 평가용으로 사용한다. hold32 V4는 계속 진단 자료로만 둔다. 기본 cleanup/RLF·DU 96·CU 200의 D6F45·D6F46·D6F48 RRCSetupRequest 후 중단형에서는 공격 중 primary 서비스 실패와 stop 뒤 별도 UE 회복이 3/3 반복됐다. 가장 빠른 D6F48은 Msg3 77.408/s와 DU provisional 73.338/s가 cleanup 34.209/s를 완전한 5초 창 12/12에서 넘었고, 정확히 같은 8-endpoint attack-off control은 Registration·PDU·ping 303/303에 성공했다. 다만 초과분은 admission 전에 거절돼 실제 Setup 생성은 cleanup과 평형, 점유 피크는 95/96이었다. D6F50의 DU ACK 확인 RRCSetupComplete 미전송형은 exact DU ACK 149건·Msg5 0건으로 기전은 확인했지만 공격 중 정상 서비스가 성공했다. 따라서 **분석기 입력·정답 생성기로는 사용하되 30초 지속 포화·기지국 전체 마비 도구로 부르지 않는다**. 운영 절차는 [사용 가이드](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md)를 따른다.

- [testbed-limitations.md](testbed-limitations.md) — 테스트베드 환경의 한계(팀 공유용): 시간 왜곡·ZMQ 1:1·용량/타이머 비교·운영 함정

민감정보 검사는 유지하지만 과거 랩 credential과 private GitHub 저장은 현재 p5 실험의
차단 조건이 아니다. 외부 공개 배포로 범위가 바뀔 때
`check_sensitive_artifacts.py`와 `check_sensitive_history.py`를 다시 실행하고 키 회전·이력
정리 여부를 검토한다.

## Git 게시 범위

새 원시 실행물은 `artifacts/`, `tool/runs/`, `reproducers/*/runs/`에 로컬 보존하고 Git에
추가하지 않는다. `artifacts/`에서는 검토한 최상위 README·판정문과 SHA-256·campaign
메타데이터만 기본 게시 후보가 된다. 봉인된 기존 증거는 경로와 manifest를 보존하며,
원시 자료를 포함하려고 `git add -f`를 사용하지 않는다.
