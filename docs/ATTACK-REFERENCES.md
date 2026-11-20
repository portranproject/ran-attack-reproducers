# 공격별 레퍼런스와 구현 기여

이 문서는 13개 재현 모듈이 어떤 외부 근거를 어디까지 참고했고 이 저장소가 무엇을 새로 구현했는지 정리한다. 논문에 공격이 나온다는 사실, 공개 코드를 참고했다는 사실, 현재 테스트베드에서 같은 원인을 재현했다는 사실은 서로 다른 주장이다.

공통 기반인 OAI·OCUDU·Open5GS는 공격 레퍼런스가 아니라 실행 환경이다. 탐지 임계값과 경보 조건은 `integration.lock.json`에 고정한 [production detector](https://github.com/portranproject/detection/tree/766f5569d0ddb425c14bf210a31c38ac60eceef9)의 실제 규칙을 따른다.

## 실제 프로토콜 또는 프로토콜 결과를 만드는 모듈 (L3 7종 + 레거시 `uplink-dos`)

### L3-01-V — RRC UE 컨텍스트 고갈

- **레퍼런스**: [KAUST RRC storm 연구](https://arxiv.org/abs/2608.16441), [공개 OAI 패치](https://github.com/5gattacks/5g-rrc-storm/tree/0e71f7aee24999b66d44e10db4612f96b5219d98), [3GPP TS 38.331 보관소](https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/)
- **참고한 부분**: Msg4 수신·HARQ ACK 뒤 `RRCSetupComplete`를 보내지 않는 중단점과 구형 OAI 패치 위치.
- **비도입 부분**: gNB timer 변경은 제외하고 공개 패치를 그대로 복사하지 않았다.
- **자체 구현**: OAI 2026.w38 포팅, rate·ACK·재시도 노브, JSONL oracle, DU HARQ ACK exact join, `same-cell` broker 게이트, fail-closed 판정·봉인.
- **주장 한계**: 실제 RRC 기전과 TeleRAN·detector 검출은 재현했지만 기본 cleanup에서 30초 지속 포화와 기지국 전체 마비는 미입증이다.

### L3-01-O — 인증 응답 미전송형 연결 컨텍스트 고갈 (NAS 고갈)

- **레퍼런스**: [3GPP TS 24.501 §5.4.1.3.7](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf), [LTEFuzz](https://syssec.kaist.ac.kr/pub/2019/kim_sp_2019.pdf), [5G-Spector](https://www.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf), [5GSEC/OAI-5G 인증 분기](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair2/RRC/NR_UE/rrc_UE.c), [Buckler](https://arxiv.org/html/2608.30615)
- **참고한 부분**: Registration 뒤 Authentication Request 미응답 상태 전이, T3560 재전송·해제, 공개 OAI 인증 분기 및 자원 누적 관측.
- **비도입 부분**: 미등록 IMSI 생성, 가입자 복제, gNB·코어 timer/capacity 변경, 공개 코드 PHY 재시작 구현.
- **자체 구현**: OAI w38 응답 억제, 서로 다른 랩 UICC 10명(`2×5` 독립 virtual RU) 동시 억제, OCUDU·Open5GS exact join, 탐지 입력과 oracle 분리, fail-closed 봉인.
- **주장 한계**: 기전과 동시 pre-auth 컨텍스트 점유 및 검출은 확인했지만 정상 UE 서비스 거부는 미관측이다.

### L3-20 — 현재 유효 5G-GUTI 재사용형 Blind DoS

- **레퍼런스**: [LTEFuzz](https://syssec.kaist.ac.kr/pub/2019/kim_sp_2019.pdf), [5G-Spector](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf), [5GSEC/OAI-5G 고정 소스](https://github.com/5GSEC/OAI-5G/tree/b631b577cc00929e50947a453dc5d4c2dcdfa887), [Open5GS 상태 전이 issue #4577](https://github.com/open5gs/open5gs/issues/4577), [3GPP TS 24.501](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf)
- **참고한 부분**: 피해 UE 임시 식별자 재사용 개념, 공개 OAI `--blind-dos-attack`·`--RRC-TMSI` 경로, 5G-S-TMSI·5G-GUTI 구성, Open5GS 상태 영향.
- **비도입 부분**: 공개 공격 코드 복사, 피해자 자격증명·식별자 스캔, gNB·코어 수정.
- **자체 구현**: RRC와 plain NAS 양쪽에 피해자 전체 5G-GUTI를 주입하는 w38 one-shot, 피해자·공격자 분리, 현재 GUTI snapshot, 기존 피해 context exact join, `same-cell` RA·GUTI 게이트, 서비스 손실·회복 판정.
- **주장 한계**: 랩 oracle로 식별자를 공급한 단발 결과다. 비특권 식별자 획득, 지속 차단, OTA는 미검증이다.

### L3-21 — 상향 DoS 두 변형 (실제 UE 실패 플러드 + 레거시 단발 MAC 변조)

- **레퍼런스**: [3GPP TS 24.501 보관소](https://www.3gpp.org/ftp/Specs/archive/24_series/24.501/), production detector L3-21 규칙, p5 F1 Registration Reject 실측 원문
- **참고한 부분**: NAS 무결성 실패 처리, L3-21 집계 대상(Reject·AuthenticationFailure)과 문턱(`10초/10건`), 관측된 거절 순서.
- **비도입 부분**: 공개 RF 송신 우위 공격 코드는 포팅하거나 성공 근거로 쓰지 않았다.
- **자체 구현**: 첫 Service Request MAC 1비트 단발 변조 에뮬레이터(`uplink-dos`), 10개 RAN 연결에서 실제 Registration Reject를 만드는 실패 플러드 runner(`uplink-credential-flood`), `same-cell` 정상 UE 5대 공존 및 종단 봉인.
- **주장 한계**: 두 변형 모두 RF 원인은 미관측이다. L3-21 실패 플러드는 1대 UE의 반복 연결이며 물리 UE 10대나 서비스 거부를 뜻하지 않는다.

### L3-24 — 비정상 Identity Response·식별자 노출

- **레퍼런스**: [LTrack](https://www.usenix.org/system/files/sec22-kotuliak.pdf), [AdaptOver](https://arxiv.org/html/2106.05039), [3GPP TS 24.501](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf), [3GPP TS 33.501](https://www.etsi.org/deliver/etsi_ts/133500_133599/133501/16.08.00_60/ts_133501v160800p.pdf), [5GSEC/OAI-5G Identity Response 코드](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair3/NAS/NR_UE/nr_nas_msg_sim.c#L1254), [MobiWatch](https://github.com/5GSEC/MobiWatch), [MobieXpert](https://github.com/5GSEC/MobieXpert)
- **참고한 부분**: 하향 Identity Request overshadowing 뒤 상향 Identity Response 수집 원형, 5G SUCI 응답 차이, 공개 OAI Authentication Request 분기.
- **비도입 부분**: RF overshadowing 및 uplink sniffing 코드.
- **자체 구현**: OAI w38에서 첫 Authentication Response를 SUCI Identity Response로 one-shot 치환, 동일 N2 context 및 Identity Request 부재 조인, null-scheme fingerprint 판정, 탐지 입력·민감 원문 분리.
- **주장 한계**: RF 이후 결과 에뮬레이션이다. RF 원인, Profile A 복호화, 상용망 IMSI 추출은 주장하지 않는다.

### L3-14 — 보안 전 UE Capability Information 주입

- **레퍼런스**: [Shaik 등의 UE Capability Hijacking 연구](https://zenodo.org/records/4671828/files/New%20vulnerabilities%20in%204G%20and%205G%20cellular%20access%20networkprotocols%20%20exposing%20device%20capabilities.pdf), [3GPP TS 38.331 보관소](https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/), [OAI w38 UE RRC 구현](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/1c2f4d3c2e68181cdef9f426d161163147ad4b77/openair2/RRC/NR_UE/rrc_UE.c), [팀 L3-14 규칙](https://github.com/portranproject/detection/blob/766f5569d0ddb425c14bf210a31c38ac60eceef9/src/core/rules/cap_hijack.cpp)
- **참고한 부분**: AS 보안 전 capability 노출 원인, MITM 변조 원형, 표준 메시지 순서와 OAI encoder·SRB1 전송 경로.
- **비도입 부분**: MITM relay와 capability payload 내용 변조(조사 범위에서 원 논문 MITM 코드 미확인).
- **자체 구현**: 기존 표준 encoder 기반 opt-in one-shot, 보안 전·선행 질의 없는 F1 관측 exact join, 이후 정상 capability 흐름 보존.
- **주장 한계**: 탐지 관측 에뮬레이션이다. MITM, 내용 변조·강등 수락, OTA는 미검증이다.

### L3-06 — 요청되지 않은 NAS SecurityModeReject 결과

- **레퍼런스**: [5GReasoner](https://syed-rafiul-hussain.github.io/wp-content/uploads/2019/10/5GReasoner.pdf), [5G-Spector 논문](https://dev.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf)
- **참고한 부분**: invalid NAS SMC 반복 → UE SecurityModeReject → MITM drop → UE·AMF 상향 NAS counter divergence 원형과 L3-06 메시지 관측 계보.
- **비도입 부분**: 외부 공격 코드는 복사하지 않았으며 MITM relay와 invalid SMC 주입은 구현하지 않았다.
- **자체 구현**: OAI w38 UE가 요청되지 않은 NAS `SecurityModeReject`를 one-shot으로 실제 `UE → ZMQ → DU/CU → TeleRAN → production detector` 경로에 송신하고 동일 context의 선행 SMC 부재를 검증한다(`p5` live 3/3 및 `p1` same-cell 3/3 통과).
- **주장 한계**: 프로토콜 결과 에뮬레이션이다. MITM, invalid SMC 실제 수신, 8-bit NAS counter wrap, 서비스 거부는 미관측이다.

## production detector 입력만 만드는 모듈 (AN 6종)

아래 6개는 외부 공격 코드를 가져온 도구가 아니다. 논문·공개 저장소에서 탐지해야 할 메시지 상태를 추출하고 production detector 입력 계약과 임계값에 맞게 `hello`·`ue_evt`·`kpm2` 시퀀스를 `tools/generate_rule_signal.py`로 독립 작성했다. 모든 결과는 `live_protocol_path_observed=false`, `rf_cause_observed=false`, `service_denial_observed=false`다.

| 룰·모듈 | 레퍼런스 | 참고한 부분 | 자체 구현과 한계 |
|---|---|---|---|
| AN-01 인증 동기 실패 | [LTEInspector 고정 소스](https://github.com/relentless-warrior/LTEInspector/tree/033184ce35f2dee31ed1103c1289a57d48579b2a), [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | AuthenticationFailure cause 21과 재인증 흐름 | 정상/이상 시퀀스 생성·replay. 실제 USIM/코어 SQN 비동기화는 미수행 |
| AN-06a NAS 카운터 reset 계열 | [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | 보안 수립 뒤 동일 UE의 AuthenticationRequest·NAS SMC 재등장 | same-context 입력, matched 판정·봉인. 실제 counter reset과 수락은 미관측 |
| AN-02 GUTI 불일치 후 상향 식별자 요청 결과 | [5G-Spector 고정 소스](https://github.com/5GSEC/5G-Spector/tree/63e94b9ad8860298894ed7a94e52f00faea02719), [논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | GUTI 등록 뒤 IdentityRequest 반복 탐지 상태 | 가명화된 반복 입력과 threshold-bound control. RF·실제 IMSI 획득은 미관측 |
| AN-04 짧은 RRC 연결 반복 | [LTEInspector 고정 소스](https://github.com/relentless-warrior/LTEInspector/tree/033184ce35f2dee31ed1103c1289a57d48579b2a), 팀 AN-04 계약 | 동일 임시 식별자의 짧은 연결 lifecycle 반복 | 연결·서비스·해제 시퀀스와 임계값 대조군. live RRC 반복·원인은 미주장 |
| AN-07 RRC 거절·해제 투옥 계열 | [5G-Spector 논문](https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf) | rogue gNB 계열의 반복 RRC 미완료·release 결과 | 동일 Part1 가명의 미완료 lifecycle 입력과 판정. rogue gNB·투옥은 미관측 |
| AN-08 TAC 조작·가짜 기지국 복귀 신호 | [SigOver](https://www.usenix.org/conference/usenixsecurity19/presentation/yang-hojoon) | overshadowing·TAC 조작 뒤 단말 복귀 등록 결과 | known-UE seed 5개 mobility registration burst와 대조군. TAC 송출·RF 우위는 미관측 |

6개 AN fixture의 offline detector replay(`a34b358e...`) 검증은 [production detector replay](../artifacts/production-detector-rule-replay-20261112/README.md)에 봉인했다. 이는 해당 공격의 live p5 또는 OTA 성공을 뜻하지 않는다.

## 평가자 요약

- 외부 코드를 직접 포팅한 핵심 사례는 `L3-01-V` RRC UE 컨텍스트 고갈이다.
- `L3-20` Blind DoS, `L3-01-O` 인증 응답 미전송형, `L3-21` 실패 플러드는 공개 연구·표준·실측 원문에 맞춰 OAI w38 구현·오케스트레이션·판정기를 새로 만들었다.
- `L3-24`, `L3-14`, `L3-06`, 레거시 `uplink-dos`는 원래 RF·MITM 원인 대신 실제 프로토콜 경로의 결과 또는 관측을 UE에서 재현했다.
- AN 6종은 논문 기반 메시지 시퀀스를 detector에 재생하는 회귀 fixture이며 실제 공격 UE나 RF 공격이 아니다.

## 레퍼런스 도구 실행 (외부 공개 구현, 2026-11-20)

우리 재현 모듈과 섞지 않기 위해 `./ctl.sh reference` 네임스페이스로 분리했다. 목록·원본
커밋·룰 대응의 단일 출처는 [`references/manifest.json`](../references/manifest.json)이고,
사용법은 [`references/README.md`](../references/README.md)에 있다.

### 공개 공격 구현이 실제로 있는 것

| ID | 원본(고정 커밋) | 대응 룰 | 성격 | 이번 상태 |
|---|---|---|---|---|
| `ref-rrc-storm` | [5gattacks/5g-rrc-storm](https://github.com/5gattacks/5g-rrc-storm/tree/0e71f7aee24999b66d44e10db4612f96b5219d98) + OAI `92980ce` | L3-01-V | OAI NR UE 패치: RRCSetup 수신 뒤 T300을 멈추고 `RRCSetupComplete`를 보내지 않은 채 반복 RA | 빌드 성공, 셀 sync 미달 |
| `ref-blind-dos` | [5GSEC/OAI-5G](https://github.com/5GSEC/OAI-5G/tree/b631b577cc00929e50947a453dc5d4c2dcdfa887) | L3-20 | `--blind-dos-attack`·`--RRC-TMSI` | 빌드 미완료, rfsim 가드로 공격 분기 비활성 |

5G-Spector는 공격 구현이 아니라 O-RAN nRT-RIC 기반 L3 탐지 서비스다. 고정 커밋
[`63e94b9a`](https://github.com/5GSEC/5G-Spector/tree/63e94b9ad8860298894ed7a94e52f00faea02719)의
공개 저장소에는 README·Vagrantfile·그림만 있고 공격 코드가 없다. 따라서 **공개 공격
구현 없음**으로 기록한다.

5GSEC/OAI-5G의 다른 플래그(`bts-attack`, `dnlink-dos`, `uplink-dos`, `rep-conn`,
`auth-sync`, `null-cipher-integ`, `dnlink-imsi-extr`, `uplink-imsi-extr`, `rrc-911`)는
LTE EMM/RRC 경로이거나 NR RRC에서 rfsim 가드로 막혀 있어, 우리 5G L3 룰(L3-06·L3-14·
L3-21·L3-24 등)에 그대로 대응하는 5G 구현은 없다. 있는 것만 위 표에 올렸다.

### 그대로 쓴 것과 붙이기 위해 바꾼 것

- 원본 소스는 수정하지 않았다. `ref-rrc-storm`은 원본 커밋과 원본 `storm-attack.patch`를
  그대로 적용해 `nr-uesoftmodem`만 빌드한다. control은 같은 OAI 커밋을 패치 없이 빌드한
  바이너리다(원본에는 공격 on/off 노브가 없다).
- 원본 UE는 rfsim(TCP, int16 complex)만 말하고 우리 DU는 ZMQ(complex float)만 말한다.
  외부 브리지 `reproducers/rrc-signaling-storm/reference/bin/oai-rfsim-zmq-bridge`가 두
  RF 인터페이스만 변환한다. 2026-11-20에 순수 파이썬 샘플 루프가 23.04 Msps를 따라가지
  못하는 문제를 numpy 변환으로 바꾸고, 상향을 UE가 보낸 0.5 ms 블록 단위로 넘기도록
  고쳤다. 공격 로직·메시지 내용은 건드리지 않았다.
- 실행·기록은 `reproducers/rrc-signaling-storm/reference/bin/reference-run`이 맡고,
  `run.json`·`verdict.json`에 UE 로그 마커와 바이너리·설정 SHA-256만 남긴다.

### p1 결과 (2026-11-20)

- 빌드: 성공. 원본 패치 UE `5814a864…`, 무패치 control `9a268619…`.
- 셀 접속: 브리지가 DU ZMQ에서 DL 샘플을 받아 rfsim UE로 전달하는 단계까지 확인했다.
  UE는 45초 안에 초기 sync에 실패했고(`synch Failed` 반복), 변환·상향 블록 수정 뒤에도
  같은 지점에서 막혔다.
- 따라서 **control 1 + attack 1의 production detector 판정은 실행하지 못했다.**
  2026-11-19 p1hold의 우리 도구 7종 RAISE 1·CLEAR 1과의 비교표도 만들지 않았다.
  이 결과를 p4·OTA 자격으로 쓰지 않는다.

실행 명령은 아래와 같다(레퍼런스 전용, 우리 자격 경로와 무관).

```bash
./ctl.sh reference list
./ctl.sh reference build ref-rrc-storm --profile p1
./ctl.sh reference doctor ref-rrc-storm --profile p1
./ctl.sh reference run ref-rrc-storm --profile p1 --mode control
./ctl.sh reference run ref-rrc-storm --profile p1 --mode attack --enable
```
