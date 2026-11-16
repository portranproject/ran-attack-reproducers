# 공격별 레퍼런스와 구현 기여

이 문서는 13개 공격 재현 모듈이 **어떤 외부 근거를 어디까지 참고했고, 이 저장소가
무엇을 새로 구현했는지**를 한곳에서 설명한다. 논문에 공격이 나온다는 사실, 공개 코드를
참고했다는 사실, 현재 테스트베드에서 같은 원인을 재현했다는 사실은 서로 다른 주장이다.
따라서 각 모듈의 `재현 수준`과 `한계`를 함께 읽어야 한다.

공통 기반인 OAI·OCUDU·Open5GS는 공격 레퍼런스가 아니라 실행 환경이다. 탐지 임계값과
경보 조건은 논문에서 임의로 가져오지 않고, `integration.lock.json`에 고정한
[production detector](https://github.com/portranproject/detection/tree/a34b358e585e24aa91b1586da022ad14ef98d3e0)의
실제 규칙을 사용한다.

## 실제 프로토콜 또는 프로토콜 결과를 만드는 모듈

### L3-01-V — RRC UE 컨텍스트 고갈

- **레퍼런스**:
  [KAUST RRC storm 연구](https://arxiv.org/abs/2608.16441),
  [공개 OAI 패치](https://github.com/5gattacks/5g-rrc-storm/tree/0e71f7aee24999b66d44e10db4612f96b5219d98),
  [3GPP TS 38.331 보관소](https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/)
- **참고한 부분**: Msg4를 수신하고 HARQ ACK한 뒤 `RRCSetupComplete`를 보내지 않는 공격
  중단점과, 구형 OAI에서 그 분기를 만든 위치를 직접 참고했다.
- **가져오지 않은 부분**: 공개 패치에 함께 있던 gNB timer 변경은 제외했다. 공개 패치를
  현재 OAI에 그대로 적용하지 않았다.
- **이 저장소의 기여**: OAI 2026.w38 포팅, 실행 시 rate·ACK·재시도 노브, JSONL oracle,
  DU HARQ ACK exact join, fail-closed 실행기·분석기·증거 봉인, OCUDU 기본 cleanup 실측을
  새로 구현했다.
- **주장 한계**: 실제 RRC 기전은 재현했지만 기본 cleanup에서 30초 지속 포화와 기지국 전체
  마비는 입증하지 않았다.

### L3-20 — 현재 유효 5G-GUTI 재사용형 Blind DoS

- **레퍼런스**:
  [LTEFuzz](https://syssec.kaist.ac.kr/pub/2019/kim_sp_2019.pdf),
  [5G-Spector](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf),
  [5GSEC/OAI-5G 고정 소스](https://github.com/5GSEC/OAI-5G/tree/b631b577cc00929e50947a453dc5d4c2dcdfa887),
  [Open5GS 상태 전이 issue #4577](https://github.com/open5gs/open5gs/issues/4577),
  [3GPP TS 24.501](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf)
- **참고한 부분**: 피해 UE의 임시 식별자를 재사용하는 공격 개념, 공개 OAI의
  `--blind-dos-attack`·`--RRC-TMSI` 경로, 5G-S-TMSI와 5G-GUTI 구성, 동일 identity가
  Open5GS 상태에 미치는 영향을 참고했다.
- **가져오지 않은 부분**: 공개 공격 코드를 복사하지 않았고 피해자 자격증명, 식별자 스캔,
  gNB·코어 수정도 사용하지 않았다.
- **이 저장소의 기여**: RRC와 NAS 양쪽에 피해자의 **전체 5G-GUTI**를 넣는 w38 one-shot,
  피해자·공격자 분리, 현재 GUTI snapshot, 기존 피해 context exact join, 동일 피해자 PID의
  서비스 손실·회복 판정과 matched 3세트 봉인을 구현했다.
- **주장 한계**: 랩 oracle로 식별자를 공급한 단발 G5 결과다. 비특권 식별자 획득, 지속
  차단, OTA는 미검증이다.

### L3-01-O — 인증 응답 미전송형 연결 컨텍스트 고갈 (NAS 고갈)

- **레퍼런스**:
  [3GPP TS 24.501 §5.4.1.3.7](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf),
  [LTEFuzz](https://syssec.kaist.ac.kr/pub/2019/kim_sp_2019.pdf),
  [5G-Spector](https://www.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf),
  [5GSEC/OAI-5G 인증 분기](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair2/RRC/NR_UE/rrc_UE.c),
  [Buckler](https://arxiv.org/html/2608.30615)
- **참고한 부분**: Registration 뒤 Authentication Request에 답하지 않는 상태 전이,
  T3560 재전송·해제, 공개 OAI의 인증 분기와 선행 연구의 자원 누적 관측을 참고했다.
- **가져오지 않은 부분**: 미등록 IMSI 생성, 가입자 복제, gNB·코어 timer/capacity 변경과
  공개 코드의 PHY 재시작 구현은 가져오지 않았다.
- **이 저장소의 기여**: OAI w38 응답 억제, 서로 다른 랩 UICC 검증, direct 4-cell phase
  driver, OCUDU·Open5GS exact join, CU/F1/N2 입력과 oracle 분리, fail-closed 판정·봉인을
  구현했다.
- **주장 한계**: Authentication Response 미전송과 동시 pre-auth 컨텍스트 6개는
  확인했지만 정상 UE 서비스 거부는 관측하지 못했다.

### L3-21 — 상향 DoS 두 변형

- **레퍼런스**:
  [3GPP TS 24.501 보관소](https://www.3gpp.org/ftp/Specs/archive/24_series/24.501/),
  production detector의 L3-21 규칙, p5에서 수집한 F1 Registration Reject 원문
- **참고한 부분**: NAS 무결성 실패 처리, L3-21이 세는 Reject·AuthenticationFailure의
  종류와 p5 production 문턱 `10초/10건`, 실제 관측한 거절 순서를 사용했다.
- **가져오지 않은 부분**: 공개된 RF 공격 구현을 포팅하지 않았다. RF 송신 우위의 논문
  구현을 현재 모듈의 성공 근거로 사용하지도 않는다.
- **이 저장소의 기여**: 첫 Service Request MAC을 한 번만 변조하는 프로토콜 결과
  에뮬레이터와, 수정 OAI UE가 10개 RAN 연결의 실제 Registration Reject를 만드는 실패
  플러드 runner를 별도로 구현했다. TeleRAN·production detector·대시보드 종단 연동,
  정상 UE 5대 공존, fail-closed 판정·봉인도 새로 만들었다.
- **주장 한계**: RF 원인은 두 변형 모두 미관측이다. 실패 플러드형은 실제 프로토콜
  경로지만 한 물리 UE의 반복 연결이며 물리 UE 10대나 서비스 거부를 뜻하지 않는다.

### L3-24 — 비정상 Identity Response·식별자 노출

- **레퍼런스**:
  [LTrack](https://www.usenix.org/system/files/sec22-kotuliak.pdf),
  [AdaptOver](https://arxiv.org/html/2106.05039),
  [3GPP TS 24.501](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf),
  [3GPP TS 33.501](https://www.etsi.org/deliver/etsi_ts/133500_133599/133501/16.08.00_60/ts_133501v160800p.pdf),
  [5GSEC/OAI-5G Identity Response 코드](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair3/NAS/NR_UE/nr_nas_msg_sim.c#L1254),
  [MobiWatch](https://github.com/5GSEC/MobiWatch),
  [MobieXpert](https://github.com/5GSEC/MobieXpert)
- **참고한 부분**: 하향 Identity Request를 덮어쓰고 상향 Identity Response를 받는 원형,
  5G에서 IMSI 대신 SUCI가 응답되는 차이, 공개 OAI의 Authentication Request 분기와
  비정상 메시지 순서를 참고했다.
- **가져오지 않은 부분**: RF overshadowing과 uplink sniffing 코드는 구현하거나 복사하지
  않았다.
- **이 저장소의 기여**: OAI w38에서 첫 Authentication Response를 SUCI Identity Response로
  한 번 치환하고, 같은 N2 context·Identity Request 부재를 조인했다. null-scheme일 때만
  fingerprint로 노출을 판정하고 민감 원문과 탐지 입력을 분리했다.
- **주장 한계**: 공격 이후의 프로토콜 결과 에뮬레이션이다. RF 원인, Profile A 복호화,
  상용망 IMSI 추출은 주장하지 않는다.

### L3-14 — 보안 전 UE Capability Information 주입

- **레퍼런스**:
  [Shaik 등의 UE Capability Hijacking 연구](https://zenodo.org/records/4671828/files/New%20vulnerabilities%20in%204G%20and%205G%20cellular%20access%20networkprotocols%20%20exposing%20device%20capabilities.pdf),
  [3GPP TS 38.331 보관소](https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/),
  [OAI w38 UE RRC 구현](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/1c2f4d3c2e68181cdef9f426d161163147ad4b77/openair2/RRC/NR_UE/rrc_UE.c),
  [팀 L3-14 규칙](https://github.com/portranproject/detection/blob/a34b358e585e24aa91b1586da022ad14ef98d3e0/src/core/rules/cap_hijack.cpp)
- **참고한 부분**: AS 보안 전 capability 질의·응답이 노출되는 원인, MITM이 응답 내용을
  바꾸는 원형, 표준 메시지 순서와 OAI의 기존 encoder·SRB1 전송 경로를 참고했다.
- **가져오지 않은 부분**: 조사 범위에서 공개된 원 논문의 MITM 공격 코드를 확인하지
  못했다. relay와 capability payload 변조도 구현하지 않았다.
- **이 저장소의 기여**: 기존 표준 encoder를 이용한 opt-in one-shot, 보안 전·선행 질의
  없는 F1 관측 exact join, 이후 정상 capability 흐름 보존, matched 판정·봉인을 구현했다.
- **주장 한계**: 탐지 관측 에뮬레이션이다. MITM, 내용 변조·강등 수락, OTA는 미검증이다.

## production detector 입력만 만드는 모듈

아래 7개는 외부 공격 코드를 가져온 도구가 아니다. 논문·공개 저장소에서 **탐지해야 할
메시지 상태**를 추출하고, production detector의 실제 입력 계약과 임계값에 맞게
`hello`·`ue_evt`·`kpm2` 시퀀스를 독립 작성했다. 모든 결과는
`live_protocol_path_observed=false`, `rf_cause_observed=false`다.

| 룰·모듈 | 레퍼런스 | 참고한 부분 | 이 저장소가 구현한 부분과 한계 |
|---|---|---|---|
| L3-06 NAS 카운터 비동기화 결과 | [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | NAS 보안 상태가 맞지 않을 때 나타나는 SecurityModeReject 계열 순서 | 선행 SecurityModeCommand와 짝이 없는 Reject 입력, 대조군, replay·판정·봉인. 실제 NAS count 변조와 Reject 원인은 미관측 |
| AN-01 인증 동기 실패 | [LTEInspector 고정 소스](https://github.com/relentless-warrior/LTEInspector/tree/033184ce35f2dee31ed1103c1289a57d48579b2a), [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | AuthenticationFailure cause 21과 이후 재인증 흐름 | 정상/이상 시퀀스와 production replay. USIM SQN·코어 SQN을 실제로 어긋나게 하지는 않음 |
| AN-06a NAS 카운터 reset 계열 | [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | 보안 수립 뒤 같은 UE에 AuthenticationRequest·NAS SMC가 다시 나타나는 상태 | same-context 입력, matched campaign·판정·봉인. 실제 counter reset과 UE·AMF 수락은 미관측 |
| AN-02 GUTI 불일치 후 상향 식별자 요청 결과 | [5G-Spector 고정 소스](https://github.com/5GSEC/5G-Spector/tree/63e94b9ad8860298894ed7a94e52f00faea02719), [논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | GUTI 기반 등록 뒤 IdentityRequest가 반복되는 탐지 상태 | 가명화된 반복 입력과 threshold-bound control. RF 공격과 실제 IMSI/SUPI 획득은 미관측 |
| AN-04 짧은 RRC 연결 반복 | [LTEInspector 고정 소스](https://github.com/relentless-warrior/LTEInspector/tree/033184ce35f2dee31ed1103c1289a57d48579b2a)와 팀 AN-04 계약 | 연결 상태 악용 가능성과 같은 임시 식별자의 짧은 lifecycle 반복 | 동일 가명 UE의 연결·서비스·해제 시퀀스와 임계값 대조군. 특정 공격 원인이나 live RRC 반복은 주장하지 않음 |
| AN-07 RRC 거절·해제 투옥 계열 | [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | rogue gNB 계열에서 반복되는 RRC 미완료·release 결과 | 같은 Part1 가명의 미완료 lifecycle 입력과 판정. rogue gNB와 실제 UE 투옥은 미관측 |
| AN-08 TAC 조작·가짜 기지국 복귀 신호 | [SigOver](https://www.usenix.org/conference/usenixsecurity19/presentation/yang-hojoon) | 무선 메시지 overshadowing과 tracking area 조작 뒤의 단말 복귀 등록 결과 | known-UE seed 5개의 mobility registration burst와 대조군. TAC 송출·가짜 기지국·RF 우위·실제 이동 등록은 미관측 |

7개 모듈의 검증은 [production detector replay](artifacts/production-detector-rule-replay-20261112/)에
봉인했다. 각 모듈은 control→emulation 3/3을 통과했지만, 이는 해당 공격의 live p5 또는
OTA 성공을 뜻하지 않는다.

## 평가자에게 설명할 때의 정확한 요약

- 외부 코드를 직접 포팅한 핵심 사례는 RRC UE 컨텍스트 고갈이다.
- Blind DoS와 인증 응답 미전송형은 공개 연구의 공격 지점과 상태 전이를 참고해 현재 OAI와
  OCUDU/Open5GS에 맞는 구현·오케스트레이션·판정기를 새로 만들었다.
- 하향 식별자 노출과 UE capability는 원래 RF/MITM 원인 대신 실제 프로토콜 경로의 결과 또는
  관측을 에뮬레이션했다.
- 상향 DoS는 공개 RF 공격 구현의 포팅이 아니라 표준 처리·p5 원문·production rule에 근거한
  결과 및 탐지 입력 에뮬레이션이다.
- 나머지 7개는 논문 기반 메시지 시퀀스를 production detector에 재생하는 회귀 fixture다.
  실제 공격 UE나 RF 공격으로 설명하면 안 된다.
