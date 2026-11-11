# 하향 IMSI 추출 계열 식별자 노출 재현기

상태: **p5 ZMQ 프로토콜 결과 에뮬레이션 구현·실측 완료**

이 모듈은 LTE의 **Downlink IMSI Extractor**를 5G SA 테스트베드의 탐지 입력으로
옮긴다. 원형 공격은 정상 기지국의 하향 NAS 메시지를 공격자의 `Identity Request`로
overshadowing하고, 피해 UE가 올리는 `Identity Response`에서 IMSI를 수집한다.

현재 p5 ZMQ에는 실제 RF 신호 경쟁이 없으므로 첫 구현은 5G-Spector 공개 OAI 코드와 같은
방식으로 공격 이후의 프로토콜 결과를 에뮬레이션한다. 정상 `Authentication Request`를 받은
OAI UE가 공격 모드에서 인증 응답 대신 `Identity Response(SUCI)`를 한 번 제출한다. OCUDU와
Open5GS는 수정하지 않는다.

## 원형 공격

LTrack의 LTE 공격 흐름은 다음과 같다.

```text
피해 UE                  정상 eNodeB                 공격자
   │ RRC/Attach Request      │                         │
   │───────────────────────>│                         │
   │                        │ 정상 하향 NAS            │
   │<───────────────────────│<─ 같은 시각·주파수의 ───│
   │        공격자의 Identity Request를 더 강하게 복호 │
   │ Identity Response(IMSI)│                         │
   │───────────────────────>│──────── uplink sniff ──>│
```

논문 구현은 정상 기지국의 하향 전송과 정밀 동기화한 낮은 추가 전력의 surgical
overshadowing을 사용한다. 공격자는 uplink allocation도 조작하여 정상 기지국이 피해자의
응답을 받지 못하게 하고, 별도 uplink sniffer로 IMSI를 수집한다.

## 5G SA에서 달라지는 점

5G UE는 pre-security 상태의 평문 `Identity Request`가 **SUCI**를 요구할 때 이를 처리할 수
있다. 그러나 UE는 `Identity Response`에서 SUPI를 직접 보내지 않고 SUCI를 보낸다.

- protection scheme 0(null-scheme): SUCI가 MSIN을 숨기지 않으므로 MCC·MNC와 결합하면
  IMSI 기반 SUPI가 노출된다.
- protection scheme 1(Profile A): scheme output이 암호화돼 관측자가 SUPI를 복구할 수 없다.
- 따라서 이 모듈에서 항상 성립하는 결과는 **예상하지 않은 평문 SUCI 응답**이다.
- “IMSI/SUPI 추출 성공”은 실험 프로필이 null-scheme이고 응답의 가입자 fingerprint가
  oracle과 일치할 때만 별도로 판정한다.

5G의 SUCI 보호를 우회했다고 주장하지 않는다. null-scheme 결과는 팀 랩 프로필의 설정
조건을 함께 기록한다.

## p5 재현 흐름

```text
OAI 피해 UE                  OCUDU DU/CU                 Open5GS
   │ RRCSetupComplete + Registration Request │              │
   │────────────────────────────────────────>│ InitialUEMessage
   │                                         │─────────────>│
   │                    Authentication Request              │
   │<────────────────────────────────────────│<─────────────│
   │ 공격 모드: 정상 인증 처리 대신                          │
   │ Identity Response(SUCI)                                │
   │────────────────────────────────────────>│─────────────>│
```

이 흐름은 5G-Spector/MobiWatch 공개 자료의 비정상 시퀀스
`Registration Request → Authentication Request → Identity Response`와 같다. 망이 보낸
`Identity Request`가 없는데 같은 UE 연결에서 `Identity Response`가 나타나는 것이 핵심
탐지 신호다.

## 구현 범위

- OAI 2026.w38 UE-only one-shot 패치
- 기본 off, `control`과 명시적 `emulation` 분리
- 실제 OAI NAS encoder로 평문 `Identity Response(SUCI)` 생성
- 같은 RAN/AMF UE NGAP ID의 Registration·Authentication·Identity 메시지 조인
- SUCI protection scheme과 가입자 fingerprint의 사후 oracle 검증
- 정상 대조군, 유한 실행시간, crash/강제 종료 판정
- 실행 원문과 판정 파일의 SHA-256 봉인

구현하지 않는다.

- 실제 RF downlink overshadowing, 시간·주파수 동기화 또는 송신 우위
- 외부망 실행, 임의 가입자 수집 또는 실사용자 추적
- gNB·코어 소스, timer, capacity 변경
- Profile A SUCI 복호화 또는 SUPI 보호 우회
- 탐지 입력에 UE 마커·가입자 원문·Open5GS 내부 oracle 주입

## p5 실측 결과

2026-11-11 `p5-downlink-imsi-final-20261111` matched control→emulation 3세트를
모두 첫 실행에 통과했다.

- control: 인증 응답·등록·PDU·ping 3/3 성공, Identity Response 0건
- emulation: `Authentication Request → Identity Response` 각 1건, 망의 Identity Request
  0건, null-scheme fingerprint 일치 3/3
- emulation의 등록·PDU·ping은 3/3 실패했지만 서비스 효과는 필수 기전과 분리한다.
- 모든 child의 UE/CU/core crash와 forced kill은 0건이었다.
- 실제 RF overshadowing은 실행·관측하지 않았다.

원문 해시와 판정은 [p5 결과](artifacts/p5-zmq-identity-response-20261111/)에 있다.
실행 절차는 [사용 가이드](USAGE-GUIDE.md)를 따른다.

## 완료 판정

| 판정 | 조건 |
|---|---|
| 이론·공개 구현 | LTrack·3GPP·5G-Spector 고정 자료와 현재 변형의 차이를 기록 |
| 정상 대조군 | 정상 Authentication Response, 예상하지 않은 Identity Response 0건, 등록 성공 |
| 기전 재현 | Authentication Request 뒤 Identity Response 정확히 1건, 같은 UE ID 조인, 실제 Identity Request 0건 |
| 식별자 노출 | SUCI 응답과 protection scheme 확인. scheme 0일 때만 oracle fingerprint 일치 |
| 탐지 입력 | N2 시퀀스와 UE·코어 oracle 분리. CU/F1/eBPF 조인은 선택 확장 |
| 서비스 효과 | 별도 선택 지표. 등록 실패나 서비스 손실은 필수 조건이 아님 |

모든 결과에는 다음 두 필드를 고정한다.

```json
{
  "dl_overshadowing_observed": false,
  "identity_response_substitution_emulated": true
}
```

control은 두 번째 값을 `false`로 기록한다.

## 근거와 공개 구현

- [LTrack, USENIX Security 2022 §5](https://www.usenix.org/system/files/sec22-kotuliak.pdf)
  — 하향 `Identity Request` overshadowing과 uplink `Identity Response(IMSI)` 수집 원형
- [AdaptOver, ACM MobiCom 2022](https://arxiv.org/html/2106.05039)
  — surgical downlink/uplink overshadowing 구현과 공격 전제
- [3GPP TS 24.501 §4.4.4.2·§5.4.4](https://www.etsi.org/deliver/etsi_ts/124500_124599/124501/16.12.00_60/ts_124501v161200p.pdf)
  — pre-security SUCI Identity Request 처리와 Identity Response 절차
- [3GPP TS 33.501 §6.12·Annex C](https://www.etsi.org/deliver/etsi_ts/133500_133599/133501/16.08.00_60/ts_133501v160800p.pdf)
  — SUCI 보호, null-scheme과 Profile A/B
- [5GSEC/OAI-5G 고정 커밋](https://github.com/5GSEC/OAI-5G/blob/b631b577cc00929e50947a453dc5d4c2dcdfa887/openair3/NAS/NR_UE/nr_nas_msg_sim.c#L1254)
  — Authentication Request 분기에서 SUCI Identity Response를 만드는 공개 5G 에뮬레이션
- [MobiWatch 공개 데이터](https://github.com/5GSEC/MobiWatch)
  — `Authenticationrequest → Identityresponse` 비정상 시퀀스와 탐지 데이터
- [MobieXpert 공개 규칙](https://github.com/5GSEC/MobieXpert)
  — 망의 직전 Identity Request 없이 나타난 Identity Response 탐지

## 주장 범위

구현 완료 뒤 허용할 주장은 **p5 ZMQ에서 Downlink IMSI Extractor 계열의 5G SA
프로토콜 결과인 예상하지 않은 SUCI Identity Response를 실제 UE→RAN→코어 경로로
에뮬레이션하고 탐지 입력과 oracle을 분리했다**까지다.

null-scheme 실측을 통과한 경우에만 **랩 가입자 프로필의 SUPI가 숨겨지지 않은 SUCI로
노출됐다**고 추가할 수 있다. 실제 RF overshadowing, Profile A 복호화, 상용망 IMSI 추출은
별도 검증 없이는 주장하지 않는다.

실 SDR로 옮길 때는 현재 공격자 UE를 악성 gNB/하향 waveform injector로 바꾸고 정상 gNB
하향과의 동기화, 송신 gain·감쇠 교정, uplink 응답용 독립 수신 경로를 추가해야 한다. 단순히
ZMQ device를 USRP로 교체하는 포팅이 아니다. 구성과 OTA 합격 조건은 [설계 §9](DESIGN.md#9-실제-ota-변형으로-전환할-때)를 따른다.
