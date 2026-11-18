# Authentication Response 미전송형 연결 컨텍스트 고갈 (NAS 고갈)

상태: **p5 실제 UE→RAN→TeleRAN→production detector matched 3/3 통과 — 한 셀의 서로 다른 랩 가입자 10명, 서비스 거부는 미관측**

최종 실측 요약과 원격 원문 해시는
[p5 다중 UE 한계 실측](artifacts/p5-zmq-multiue-limit-20261111/)에 보존했다. 최초 2가입자
smoke는 [초기 기전 실측](artifacts/p5-zmq-mechanism-smoke-20261111/)에 남겨 두었다.

이 모듈은 공격 UE가 정상 `Registration Request`를 보낸 뒤 AMF의
`Authentication Request`에 응답하지 않아 미인증 RRC·NGAP·5GMM 컨텍스트를 점유하는
공격을 재현한다. 문헌의 `BTS resource depletion`을 5G SA 테스트베드에 옮기는 것이며,
상위 분류는 **NAS 고갈 계열**이다.

`NAS 고갈`은 넓은 분류명이고, 이 모듈의 정확한 변형명은
**Authentication Response 미전송형 연결 컨텍스트 고갈**이다. ngKSI cause #71이나
동기화 실패를 반복해 인증 벡터 생성을 증폭하는 변형은 다루지 않는다.

## 공격 절차

```text
공격 UE          OCUDU DU/CU                 Open5GS
   │ RRC Setup       │                          │
   │────────────────>│                          │
   │ RRCSetupComplete + Registration Request   │
   │────────────────>│ InitialUEMessage         │
   │                 │─────────────────────────>│
   │                 │      Authentication Request
   │<────────────────│<─────────────────────────│
   │                 │                          │
   │  응답하지 않음   │ 미인증 연결 상태 유지     │
   │                 │                          │
   │  다음 공격 연결 또는 다음 공격 UE 시작      │
```

공격 UE는 `Authentication Response`와 `Authentication Failure`를 모두 보내지 않는다.
3GPP TS 24.501 §5.4.1.3.7에 따라 AMF는 T3560 만료 때 Authentication Request를
재전송하고, 다섯 번째 만료에서 인증 절차와 N1 NAS 연결을 종료한다. 실제 보유시간은
AMF의 T3560보다 먼저 동작하는 RAN·NGAP 정리 정책이 있으면 더 짧아질 수 있다.

동시 점유량은 대략 다음 관계를 따른다.

```text
동시 미인증 컨텍스트 ≈ 연결 생성률 × 실제 컨텍스트 보유시간
```

하나의 SUPI를 여러 프로세스에서 동시에 반복하면 Open5GS가 기존 컨텍스트로 병합하거나
즉시 정리할 수 있으므로, 첫 구현은 팀이 보유한 **서로 다른 가입자 프로필**을 사용한다.
각 프로필이 자연 timeout 뒤 재접속한 컨텍스트는 새 NGAP ID로 따로 추적한다. 미등록 IMSI를
임의 생성하거나 정상 가입자의 식별자를 복제하는 방식은 기본 시나리오에 포함하지 않는다.

## 구현 범위

- OAI 2026.w38 UE-only 패치
- 한 ZMQ 무선을 공유하는 OAI 다중 UICC UE의 입력·출력 동기화
- 공격 모드에서만 `Authentication Request`의 정상 NAS 처리 생략
- 서로 다른 공격 가입자 프로필과 독립 정상 witness 프로필 검증
- 유한한 공격 UE 수·실행시간·관측시간
- 공격 UE 정답 JSONL, CU·AMF 원문, witness 서비스 결과의 exact join
- 고정 순서 `control → attack` 실행과 선택적 서비스 영향 campaign
- 실행 원문 SHA-256과 판정 결과 봉인

구현하지 않는다.

- gNB·코어 소스, timer, capacity 변경
- 외부 망 실행, 식별자 스캔, 가입자 자격증명 복제
- 미등록 IMSI를 무제한 생성하는 공개 코드의 동작을 그대로 가정
- 실 SDR OTA 자동 실행
- 탐지 입력에 UE 정답이나 AMF oracle 주입

OAI의 최소 개입 지점은 기존 Blind DoS 패치에서 이미 검증한
`FGS_AUTHENTICATION_REQUEST` 분기다. 새 모듈은 표적 5G-GUTI 처리와 피해 UE 회복 코드를
가져오지 않고, 정상 공격 가입자의 인증 응답 억제와 반복 실행만 독립적으로 구현한다.

`analysis/normalize_p5.py`는 OCUDU의 `rrcSetupComplete → NGAP UE context →
InitialUEMessage → AMF-UE-NGAP-ID → NGAP context release`와 Open5GS의
`InitialUEMessage → SUCI`를 RAN/AMF UE NGAP ID로 조인한다. Authentication Request 수신과
Response 제출·억제는 해당 NAS handler에서 남긴 UE 마커를 가입자 fingerprint·건수로
교차검증한다. SUCI 원문은 정규화 결과에 남기지 않는다.

2026-11-11 p5의 OAI w38 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에서
인증 미응답 패치(`bc8f2947...`), 공유 무선 패치(`c2e91eb6...`)와 ZMQ queue wakeup을
빌드했다. direct 4-cell ZMQ에서 공격자 3프로세스×2 UICC와 witness를 분리하고, ZMQ 재연결
상태가 시도 사이에 남지 않도록 각 시도마다 DU와 UE 세트를 재기동한다. 최종 정상 대조군은
공격자 컨텍스트 30개 exact join과 baseline·impact 5회·recovery 5회의
Registration/PDU/ping을 모두 통과했다.

프로세스당 10 UICC 진단은 120초 안에 11/20명만 인증했고 약 85만 건의 ZMQ channel
timeout이 발생했다. 프로세스당 4 UICC도 반복 phase timeout으로 무효였다. 따라서 현재 p5
단일 DU에서 반복 가능한 구성은 3프로세스×2 UICC이며, 이 진단 런은 성능 근거로 쓰지 않는다.
별도 ZMQ broker로 프로세스를 분리한 8·14 UE와 3셀 6·9 UE 확장도 정상 대조군 또는 반복
인증을 통과하지 못했다. 미검증 broker 코드는 운영 도구에서 제외했다.

2026-11-17 자격 검증은 위 4-cell 자원 누적 실험을 억지로 확장하지 않고, 정상 UE 풀에서
검증된 **shared virtual RU** 구조를 사용한다. `auth-stall-cell-run`이 서로 다른 랩
가입자 10명을 2개 OAI 프로세스×5 UE로 실행하고, GNU Radio broker가 프로세스별 2개 endpoint를 한
DU·셀에 합친다. 공격군은 10명 모두 Authentication Response를 미전송하고 대조군은 10명
모두 정상 제출한다. gNB·코어·detector는 수정하지 않는다.

이 경로로 실제 F1/N2→TeleRAN→production detector→dashboard를 함께 실행한 결과,
대조군 L3-01-O 경보 0건과 공격군 RAISE 1건을 matched 3/3 반복했다. 입력 보고 주기
100 ms, sequence 연속, gap 0, KPM 존재, dashboard 거절 0건도 매 실행 확인했다. 공통 결과와
봉인 해시는 [p5 E2E 자격 요약](../../artifacts/p5-live-e2e-five-20261117/)을 따른다.

## 완료 판정

숫자 코드 대신 무엇이 확인됐는지 분리해서 기록한다.

### 1. 이론·공개 구현 근거 확인 — 완료

- 3GPP TS 24.501의 Authentication Request 무응답 및 T3560 동작을 확인했다.
- LTEFuzz의 BTS resource depletion, 5GSEC/OAI-5G의 공개 OAI 구현, Buckler의
  SetupComplete 이후 Authentication Response 부재 실험과 현재 변형의 관계를 아래 고정
  자료로 기록했다.
- 공개 구현과 현재 OAI w38 패치가 동일한 파일·코드라고 주장하지 않는다. 공개 자료의
  공격 지점과 메시지 흐름을 현재 UE-only 구현에 옮겼다.

### 2. 기전·자원 누적 재현 — 완료

- 각 공격 UE가 자신의 가입자 프로필로 `Registration Request`를 보낸다.
- 같은 흐름의 `RRCSetupComplete → InitialUEMessage → Authentication Request`를 RAN/AMF
  UE NGAP ID로 조인한다.
- `Authentication Response`와 `Authentication Failure`는 0건이고 UE의
  `authentication_request_withheld` 정답과 일치한다.
- 자연 timeout/release까지의 컨텍스트 수명을 측정하며 gNB·코어 소스·timer·capacity는
  대조군과 동일하다.
- p5 attack에서 서로 다른 가입자 6명의 pre-auth 컨텍스트가 동시에 존재했고 crash와
  forced kill은 0건이었다.

### 3. 탐지 입력 준비 — 완료

- CU/F1/N2 메시지 수명과 current-run 시간 경계를 탐지 입력으로 제공한다.
- UE 마커, Open5GS 내부 로그, 가입자 fingerprint와 정규화 결과는 탐지 출력 봉인 뒤에만
  비교하는 oracle로 분리한다.
- 권장 특징과 입력 금지 항목은 [탐지 계약](DETECTION-CONTRACT.md)과 사용 가이드에 고정했다.

production detector 기본 설정에서 이 변형의 정탐은 3/3, 대조군 예상 공격 경보는 0/3이다.
이는 해당 p5 표본의 규칙 검증 결과이며 운영망 정확도로 일반화하지 않는다.

### 선택 효과 판정 — 서비스 거부 미관측

최종 attack은 Response 억제 30건, exact join된 컨텍스트 30개와 피크 동시 6개를 만들었다.
그러나 정상 witness의 Registration·PDU session·ping이 5/5 성공했으므로 서비스 거부와
기지국 마비는 성립하지 않았다. 이 결과는 재현 도구 완료를 막지 않지만 DoS 성공으로
부르지 않는다.

기존 `verdict.json`의 `passed`는 보수적인 서비스 거부 게이트를 유지한다. 재현기 기전은
`mechanism_reproduced`, 자원 누적은 `resource_accumulation_observed`, 서비스 영향은
`witness_denial_observed`를 각각 읽는다. 봉인된 스키마와 과거 판정을 소급 변경하지 않는다.

## 운영 경계

기전·자원 누적 분석은 direct 4-cell, production L3-01-O 자격 검증은 한 셀 10 UE 경로를
사용한다. 20가입자·5-lane 분산 진단은 정식 증거로 봉인되지 않았으며 운영 코드와 성능
주장에 포함하지 않는다. 서비스 거부만 만들기 위한 추가 인스턴스 증설이나 gNB·코어
timer/capacity 변경은 진행하지 않는다.

## 탐지 관측 계약

파일 단위 입력·oracle 경계와 detector 출력 스키마는
[DETECTION-CONTRACT.md](DETECTION-CONTRACT.md)를 따른다.

권장 탐지 특징은 다음 메시지 수명이다.

```text
RRCSetupComplete
→ Registration Request
→ Authentication Request
→ Authentication Response/Failure 없음
→ timeout 또는 Release
```

- 동시에 살아 있는 pre-auth RNTI 수
- `Authentication Request - (Response + Failure)` 미매칭 수
- SetupComplete 뒤 인증 미완료 컨텍스트의 수명
- 짧은 시간에 생성되는 새 RNTI와 InitialUEMessage 비율
- 정상 witness의 등록 성공률과 등록 지연

| 구분 | 사용 데이터 |
|---|---|
| 탐지 입력 | CU/F1/N2/eBPF에서 얻은 메시지 종류·방향·RAN UE ID·시각·context lifecycle |
| 사후 정답 | `attacker_truth.jsonl`, UE 원문, Open5GS 원문, `contexts.jsonl`, `verdict.json` |
| 효과 판정 | witness의 Registration·PDU·ping과 `service.jsonl` |

공격 UE JSONL과 Open5GS 내부 로그는 정답·oracle이다. 탐지기 출력이 봉인되기 전에는
탐지 입력으로 제공하지 않는다. KPM의 RRC 성공 카운터만으로는 공격 연결도 정상
`RRCSetupComplete`로 집계될 수 있으므로 F1/N2 메시지 수준 조인이 필요하다. 최소 탐지
출력은 관측창, 경보 시각, 활성 pre-auth 추정치, threshold와 입력 원문 해시를 포함해야 한다.

## 근거와 구현 레퍼런스

- [3GPP TS 24.501 §5.4.1.3.7](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf)
  — Authentication Request 무응답 때 T3560 재전송과 최종 N1 NAS 연결 해제
- [LTEFuzz, IEEE S&P 2019 §VI-A](https://syssec.kaist.ac.kr/pub/2019/kim_sp_2019.pdf)
  — Authentication Request 뒤 새 Random Access를 시작하는 BTS resource depletion 원형
- [5G-Spector, NDSS 2024](https://www.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf)
  — 5G 공격 재현, transient UE 집계 탐지, 공개 실험 절차
- [5GSEC/OAI-5G 고정 커밋](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair2/RRC/NR_UE/rrc_UE.c)
  — OAI v2.1.0 기반 Authentication Request 감지와 Random Access 재시작 구현
- [Buckler §5.3·§6.3](https://arxiv.org/html/2608.30615)
  — SetupComplete 뒤 Authentication Response가 없는 연결의 집계·해제와 Open5GS 실험
- [기존 p5 컨텍스트 보유 조사](../../artifacts/archive-du-cell-resource-20261026/findings/anas-completed-context-hold.md)
  — OCUDU의 RAN/NGAP 정리 정책과 동일 SUPI 반복 시 주의점

## 주장 범위

현재 허용 주장은 **p5 한 셀에서 서로 다른 랩 가입자 10명의 Authentication Response
미전송을 실제 UE 경로로 만들고, 실제 TeleRAN→production detector에서 L3-01-O를
matched 3/3 검출했다**까지다. 기존 witness 5/5가 정상 등록돼 서비스 거부는 성립하지
않았다. 실 SDR OTA, 상용망 일반화와 외부 망 영향은 별도 검증 없이는 주장하지 않는다.
