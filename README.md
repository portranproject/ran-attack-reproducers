# 기지국 공격 재현 도구

팀 소유 5G/O-RAN 테스트베드에서 기지국 대상 공격을 통제된 조건으로 재현하고,
탐지·대응기의 입력과 정답을 검증하기 위한 도구 모음이다. 공격 모듈마다 구현,
설정, 라벨 계약, 실험 결과를 분리하며 RF 차폐 또는 가상 RF 환경에서만 사용한다.

처음 읽을 문서는 [AGENTS.md](AGENTS.md)다. 공통 준비·빌드·실행은
[통합 컨트롤러 사용 가이드](CONTROL-GUIDE.md), 공격별 검증 범위는 해당 모듈의 README를
기준으로 한다.

```bash
./ctl.sh list
./ctl.sh doctor --profile p5
./ctl.sh campaign an-01 --profile p5 --enable
./ctl.sh replay <run-id> --profile p5
./ctl.sh report <run-id> --profile p5
./ctl.sh verify <run-id> --profile p5
```

공격 카탈로그는 [13개 탐지 룰 기준표](ATTACK-CATALOG.md), 각 공격에서 참고한 논문·공개
코드와 자체 구현 범위는 [공격별 레퍼런스와 구현 기여](ATTACK-REFERENCES.md), 새 환경 이관은
[포팅 가이드](PORTING-GUIDE.md), 새 공격 추가는 [새 모듈 가이드](NEW-MODULE-GUIDE.md)를
따른다. 실험실 운용은 [p5 운영](P5-OPERATIONS.md)과 [차폐 OTA 운영](OTA-OPERATIONS.md),
detector·telemetry·dashboard 호환 commit은 `integration.lock.json`에 고정한다.

Markdown 문서는 한국어를 기본으로 하며 파일명에 언어 접미사를 붙이지 않는다. 봉인된
증거 원문만 예외로 보존하고 한국어 안내본을 별도로 둔다. 현재 예외 안내본은
[DU 셀 자원 고갈 보존 기록](artifacts/archive-du-cell-resource-20261026/README.md)과
[CU 90 spike 실험 기록](artifacts/spike-cu90-20261026/EXPERIMENT-NOTES.md)이다.

## 재현 도구 완료 원칙

이 저장소의 필수 목표는 기지국 전체 마비가 아니라 **실재 공격의 기전을 통제된 환경에서
재현하고, 벤더 비종속 탐지기가 평가할 관측과 정답을 만드는 것**이다. 새 공격 모듈은 다음
세 항목을 충족하면 재현 도구 범위를 완료할 수 있다.

1. 표준·논문·공개 구현의 고정 URL로 공격의 실재성과 메시지 흐름을 확인한다.
2. 정상 대조군과 공격군에서 해당 기전이 실제 프로토콜 경로로 발생했음을 원문과 정답으로
   확인한다. RF 원인 대신 결과를 에뮬레이션했다면 이를 명시한다.
3. CU/F1/N2/eBPF 등 탐지 입력과 UE·코어 oracle 정답을 분리하고, 탐지 특징·라벨·시간
   경계를 사용 가이드에 명시한다.

탐지 모델의 정탐·오탐·탐지 지연 평가는 재현 도구 완료 뒤 별도 게이트다. 정상 UE 성능
저하, 서비스 거부, 기지국 전체 마비도 관측됐을 때만 추가 성과로 기록하며 재현 도구 완료의
필수 조건으로 강제하지 않는다. 기본 실험 자원은 CU 1대와 DU 1대다. 서비스 거부만 만들기
위한 다중 인스턴스 증설이나 timer/capacity 완화는 별도 승인 없이는 진행하지 않는다.

## 재현 도구 상태

| 도구 | 상태 |
|---|---|
| [RRC signaling storm](reproducers/rrc-signaling-storm/) | 2026-11-02 동결. 분석기 입력·정답 생성기로 사용 |
| [Blind DoS](reproducers/blind-dos/) | 현재 유효 5G-GUTI 재사용형 구현 완료. p5 direct 2-cell ZMQ에서 matched control→attack G5 3/3 통과 |
| [Uplink DoS](reproducers/uplink-dos/) | 단발 NAS 무결성 손상형 프로토콜 영향 에뮬레이션과 L3-21용 실제 UE 실패 플러드. L3-21은 정상 UE 5대와 같은 셀에서 matched control→attack 3/3 통과, RF overshadowing 미검증 |
| [인증 응답 미전송형 연결 컨텍스트 고갈 (NAS 고갈)](reproducers/authentication-timeout-exhaustion/) | 2026-11-11 기전·탐지 입력 재현기로 동결. p5 direct 4-cell ZMQ에서 6개 동시 pre-auth 컨텍스트 확인, 서비스 거부는 미관측 |
| [하향 IMSI 추출 계열 식별자 노출](reproducers/downlink-imsi-extractor/) | p5 ZMQ 프로토콜 결과 에뮬레이션 완료. 예상하지 않은 SUCI Identity Response와 null-scheme 랩 가입자 노출 matched 3/3, RF overshadowing 미검증 |
| [보안 전 UE Capability Information 주입](reproducers/ue-capability-hijacking/) | UE Capability Hijacking 계열 탐지 관측 에뮬레이터 완료. p5 F1 matched control→emulation 3/3, MITM·내용 변조·강등 수락은 범위 밖 |
| [새 7개 룰 입력 모듈](ATTACK-CATALOG.md) | production detector 기본 설정 matched control→emulation 3/3 통과. p5 live protocol과 RF 원인은 pending |

각 도구는 구현·설정·라벨 계약·실험 출력을 서로 섞지 않는다.

```text
reproducers/
├── rrc-signaling-storm/   # 동결된 구현·분석기·문서·테스트
├── blind-dos/            # 5G-GUTI one-shot 구현·판정기·사용 가이드·G5 결과
├── uplink-dos/           # Service Request MAC 단발 변조 + L3-21 실제 UE 실패 플러드
├── authentication-timeout-exhaustion/ # 인증 응답 미전송형(NAS 고갈) 구현·판정기
├── downlink-imsi-extractor/ # 하향 Identity Response 유도 결과 에뮬레이션·판정기
├── ue-capability-hijacking/ # 보안 전 Capability Information 주입·F1 판정기
├── nas-counter-desynchronization/ # L3-06 입력 에뮬레이션
├── authentication-sync-failure/  # AN-01 입력 에뮬레이션
├── nas-counter-reset/             # AN-06a 입력 에뮬레이션
├── uplink-imsi-extractor/         # AN-02 입력 에뮬레이션
├── short-connection-repeat/       # AN-04 입력 에뮬레이션
├── rrc-reject-release-imprisonment/ # AN-07 입력 에뮬레이션
└── tac-manipulation-return/       # AN-08 입력 에뮬레이션
artifacts/                  # 봉인된 RRC 증거와 게시용 요약
profiles/                   # Git 밖 실제 환경 + 추적되는 p5/OTA 예제
schemas/                    # module/profile/run/verdict/evidence 계약
tools/                      # catalog·replay·report·verify와 공통 입력 생성기
rss-storm/                  # 과거 문서·명령용 호환 안내와 위임 스크립트
```

새 공격은 `reproducers/<attack-name>/`에 별도 모듈로 추가한다. 최상위 `ctl.sh`는 각
모듈의 기존 빌드기·runner를 위임 호출할 뿐, 구현·설정·라벨·실험 원문은 계속 분리한다.

## RRC signaling storm 보존 기록

새 문서는 임의의 A/B 분류 대신 `RRCSetupComplete 미전송형`처럼 중단 지점을 드러내는
설명형 이름을 쓴다. 봉인 증거의 과거 이름은 [명칭표](artifacts/LEGACY-NAMES.md)로만
해석하고 run ID·JSON 필드·체크섬 대상 원문은 바꾸지 않는다.

| 문서 | 내용 |
|---|---|
| [AGENTS.md](AGENTS.md) | 공통 저장소 원칙 + RRC 동결 컨텍스트 + 다음 공격 준비 상태 |
| [reproducers/rrc-signaling-storm/README.md](reproducers/rrc-signaling-storm/README.md) | 현재 재현기: 빌드·실행·노브·안전장치·판정법·검증 범위 |
| [reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.md](reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.md) | clean w38 curated 빌드, 정상 회귀, Msg4 ACK-on/off와 독립 broker witness 실측 |
| [reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.md](reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.md) | UE 정답·탐지·대응·효과 판정·시간 동기 계약 v1 |
| [reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.md](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.md) | 동결된 재현기의 실행 순서·입력 격리·라벨·채점·금지 주장 |
| [reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.md](reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.md) | p5에서 새 exact DU ACK join을 짧게 검증하고 원복하는 실기 게이트 |
| [reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.md](reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.md) | RRCSetupComplete 미전송형에 닿는 대응 경로 감사와 CSI-DTX RLF hardening on/off 비교 |
| [reproducers/rrc-signaling-storm/docs/OTA-SMOKE.md](reproducers/rrc-signaling-storm/docs/OTA-SMOKE.md) | 차폐 OTA inventory·RF 안전·정상 UE 기준선·공격 실행의 fail-closed 게이트 |
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
| [artifacts/LEGACY-NAMES.md](artifacts/LEGACY-NAMES.md) | 봉인 증거에 남은 과거 시나리오명과 현재 설명형 명칭의 대응표 |
| [artifacts/verify-20261021/README.md](artifacts/verify-20261021/README.md) | OCUDU 기본 설정에서 RRCSetupComplete 미전송형 120초 실측 원문과 판정(4,438 절차, 피크 96/96) |
| [tool-survey.md](tool-survey.md) | OCUDU 공식 UE 연결 예제, 5gattacks 패치, UCD 데모, 다중 UE ZMQ 공개물의 실제 범위 |
| [methodology.md](methodology.md) | RSS 실험 시나리오, RRCSetupComplete 미전송형 절차, F1 관측 경계, 재현기 기록과 단계별 검증 기준 |
| [rss-theory.md](rss-theory.md) | RSS 원리: 단계별 자원 할당, 조작 파라미터, 고갈 동역학, OCUDU 대입 |
| [rss-landscape.md](rss-landscape.md) | RSS 변종 분류, 논문·공개 도구 비교, 재현기 요구사항 |
| [comparison-5g.md](comparison-5g.md) | 5G 기준 기존 연구·공격 도구 비교 요약판. 주장별 원본 대조 여부 표시, 독립 재검색 결과 |
| [testbed-checklist.md](testbed-checklist.md) | 팀 테스트베드 체크리스트(AWS EC2 분리 CU/DU·ZMQ·n78 TDD 30 kHz 20 MHz·OCUDU 26.10·Open5GS·OAI UE) , OCUDU 설정에서 TDD/FDD 읽는 법, 베이스 UE 결정(OAI UE) |
| [design.md](design.md) | RRCSetupComplete 미전송형 재현기 설계: 아키텍처, 상태 기계, 노브, 라벨 스키마, 단계별 계획 |

상태(2026-11-02): RRC storm 구현·실측은 여기서 동결하고 분석기 평가용으로 사용한다. hold32 V4는 계속 진단 자료로만 둔다. 기본 cleanup/RLF·DU 96·CU 200의 D6F45·D6F46·D6F48 RRCSetupRequest 후 중단형에서는 공격 중 primary 서비스 실패와 stop 뒤 별도 UE 회복이 3/3 반복됐다. 가장 빠른 D6F48은 Msg3 77.408/s와 DU provisional 73.338/s가 cleanup 34.209/s를 완전한 5초 창 12/12에서 넘었고, 정확히 같은 8-endpoint attack-off control은 Registration·PDU·ping 303/303에 성공했다. 다만 초과분은 admission 전에 거절돼 실제 Setup 생성은 cleanup과 평형, 점유 피크는 95/96이었다. D6F50의 DU ACK 확인 RRCSetupComplete 미전송형은 exact DU ACK 149건·Msg5 0건으로 기전은 확인했지만 공격 중 정상 서비스가 성공했다. 따라서 **분석기 입력·정답 생성기로는 사용하되 30초 지속 포화·기지국 전체 마비 도구로 부르지 않는다**. 운영 절차는 [사용 가이드](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.md)를 따른다.

- [testbed-limitations.md](testbed-limitations.md) — 테스트베드 환경의 한계(팀 공유용): 시간 왜곡·ZMQ 1:1·용량/타이머 비교·운영 함정

민감정보 검사는 유지하지만 과거 랩 credential과 private GitHub 저장은 현재 p5 실험의
차단 조건이 아니다. 외부 공개 배포로 범위가 바뀔 때
`check_sensitive_artifacts.py`와 `check_sensitive_history.py`를 다시 실행하고 키 회전·이력
정리 여부를 검토한다.

## Git 게시 범위

원시 실행물은 `artifacts/`, `reproducers/*/runs/`에 로컬 보존하고 Git에 추가하지 않는다.
`artifacts/`에는 검토한 텍스트 판정·분석 자료와 SHA-256·campaign 메타데이터만 게시한다.
원문은 해시로 식별하며, 원시 자료를 포함하려고 `git add -f`를 사용하지 않는다. 외부 논문과
제3자 코드는 문서의 arXiv·DOI·고정 커밋 URL로 참조하고 저장소에 복사하지 않는다.
