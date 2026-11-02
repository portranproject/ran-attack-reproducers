# Blind DoS 재현 도구

상태: **현재 유효 5G-S-TMSI 재사용형의 패치·실행기·판정기 구현과 p5 ZMQ 1차 실측
완료.** 같은 등록 수명의 현재값은 공격자 commit과 AMF identity reach, 기존 피해 binding
변화와 피해 UE ping 손실까지 만들었지만, 같은 UE가 사전 고정한 30초 안에 회복하지 않아
유효 실패로 끝났다. 따라서 현재 OCUDU/Open5GS p5 결과는 현재 피해자 값 조건의 G3
도달·상태 변화·서비스 손실 관측이고, 무작위·만료·다른 UE 값 대조를 포함한 전체 G4나
N/N 회복까지 요구하는 G5 서비스 DoS 성공은 아니다.

실행 명령은 [사용 가이드](USAGE-GUIDE.md), 테스트베드 구현 순서·합격 게이트는
[구현·검증 계획](IMPLEMENTATION-PLAN.md)을 따른다.

## 무엇을 Blind DoS로 보는가

이 모듈에서 Blind DoS는 공격자가 피해 UE의 장기 가입자 자격증명(SUPI·인증 키)을
가지지 않은 채, 인증 전 임시 식별자를 재사용해 망의 피해 UE 컨텍스트를 충돌·해제시키는
**표적형 서비스 거부**다. 다수의 미완료 컨텍스트로 용량을 소진하는 RRC signaling
storm과는 목표와 합격 기준이 다르다.

- 피해자는 별도 가입자 프로필을 쓰는 팀 소유 정상 UE다.
- 공격자는 자기 OAI UE로 표준 Uu 절차만 시작하며 gNB·코어를 수정하지 않는다.
- 피해 UE와 같은 SIM 자격증명을 복제하는 방식은 공격자 권한 가정이 달라 제외한다.
- 한 번의 컨텍스트 해제와 반복적인 서비스 불능은 별도 성능 등급으로 판정한다.

**단발 공격 효과 판정**은 별도 가입자인 공격 UE가 피해 UE의 현재 유효 5G-S-TMSI를 한 번
재사용했을 때, 그 송신과 exact join된 망 상태 변화 때문에 정상 서비스 중이던 피해 UE의
사전 고정된 Registration·PDU·ping 판정이 실패하는 것이다. 같은 구성의 attack-off에서는
실패하지 않고 공격 종료 뒤 같은 피해 UE가 회복해야 한다. 이 효과를 사전에 정한 N개의
matched on/off 세트 모두에서 재현한 G5를 **재현 도구의 공격 성공**, 즉 `oracle 보조
단발 Blind DoS 재현기 성공`으로 판정한다. N의 기본값은 3이고 실행 전 3~100 범위에서
고정할 수 있다. 식별자 도달이나 컨텍스트 binding 변화만으로는 성공이 아니다.

코드의 판정식을 줄이면 다음과 같다.

```text
attack 통과 = 인프라 정상
            ∧ 표적 식별자 유지
            ∧ 공격 송신과 기존 피해 컨텍스트 변화의 exact join
            ∧ 같은 피해 UE의 서비스 손실
            ∧ 공격 뒤 같은 피해 UE의 서비스 회복

campaign 성공 = 위 attack 통과 ∧ matched control 정상 을 N/N 세트에서 모두 만족
```

공격자의 새 컨텍스트가 인증 실패로 정리된 것, 공격 메시지가 AMF에 도달한 것, 표적과
무관한 다른 UE가 잠깐 실패한 것은 위 식을 만족하지 않는다.

[3GPP TS 38.331](https://www.etsi.org/deliver/etsi_ts/138300_138399/138331/18.01.00_60/ts_138331v180100p.pdf)의
`RRCSetupRequest`는 초기 UE identity로 `ng-5G-S-TMSI-Part1` 또는 난수를 운반한다.
5G-S-TMSI는 gNB가 발급하는 무선 식별자가 아니라 **AMF가 할당한 5G-GUTI에서 가져오는
48-bit 단축 식별자**다. gNB 쪽 셀 임시 식별자인 C-RNTI와는 발급 주체와 수명이 다르다.
그러나 공격 입력은 Part1만이 아니라 **48-bit 5G-S-TMSI 전체값**이다. 정상 setup에서는
Msg3가 오른쪽 39-bit Part1, Msg5가 왼쪽 9-bit Part2를 운반하고 CU가 둘을 복원해
NGAP InitialUEMessage로 AMF에 전달한다.
[Blind DoS 탐지 연구](https://arxiv.org/abs/2510.06530)가 다루는 가설은 이 식별자에
피해 UE 값을 넣고, 피해자 인증 키 없이 등록 절차를 진행하다 멈춰 기존 컨텍스트에 영향을
주는 경로다. 첫 구현은 정상 Msg5·Initial NAS까지 보낸 뒤 NAS Authentication Request에
응답하지 않는 one-shot으로 고정한다. AMF가 그 전에 연결을 정리하는 버전은 제한시간에
종료하고 그 상태 전이를 그대로 기록한다.

## 공격 변형과 대조군을 섞지 않는다

여기서 `5G-S-TMSI 재사용형`의 **재사용**은 피해 UE의 현재 임시 식별자를 공격 UE의
초기 접속 메시지에 복사한다는 뜻이다. 식별자를 어떻게 알아냈는지는 별도 축이다.

- **절차 변형**: `RRCSetupRequest`, `RRCReestablishmentRequest`,
  `RRCResumeRequest` 중 어느 상태와 메시지를 충돌시키는가
- **입력 확보 방식**: 랩 oracle, 비특권 Uu 관측, 부분 정보 추측·탐색 중 무엇을 쓰는가.
  현재 도구는 정확한 현재값을 oracle로 받는 방식만 구현하며, 추측·전수 탐색은 하지 않는다.
- **대조 입력**: 무작위 값, 만료 값, 현재 유효한 다른 UE 값, 공격 없음. 이들은 같은
  공격 경로의 인과성과 표적 특이성을 검증하는 대조군이지 새 공격 변형이 아니다.

따라서 oracle 값을 Uu 관측값으로 바꾸는 것은 공격 절차의 새 변형이 아니라 현실적인
입력 획득 여부를 올리는 G6이고, 값을 추측해 우연히 맞히는 것도 별도 기전으로 세지 않는다.
현재 구현 범위는 아래 표의 첫 행 하나뿐이다.

| 분류 | 설명형 이름 | 식별자·절차 | 현재 위치 |
|---|---|---|---|
| 첫 구현 | **현재 유효 5G-S-TMSI 재사용형** | `RRCSetupRequest`·`RRCSetupComplete`에서 피해자의 현재값 재사용 | AMF 도달·기존 binding 변화·ping 손실 확인, 제한시간 안 회복 없음 |
| 대조군 | **무작위·만료·현재 유효한 다른 UE 값** | 같은 setup 경로에서 입력만 교체 | 공격 변형이 아니라 도달·신선도·표적 특이성 대조군 |
| 별도 변형 | **RRC 재수립 식별자 위조형 표적 축출** | `(PCI, C-RNTI, shortMAC-I)`를 쓰는 `RRCReestablishmentRequest` | OCUDU 단발 축출은 실증, 지속 차단은 미실증 |
| 후보 변형 | **RRC 재개 식별자 위조형** | 피해자의 I-RNTI와 `resumeMAC-I`를 싣는 `RRCResumeRequest` | MAC 검증 전 상태 변화가 있는지 미확인이고 현재 OCUDU 경로도 미추적·미실측 |
| 관련 조사 후보 | **NAS 5G-GUTI 위조형** | NAS Registration Request의 GUTI를 이용하는 코어 경로 | UE의 RRC 임시 식별자 재사용과 위협 경계가 달라 현재 Blind DoS 변형 분류에서 보류 |

자기 식별자나 무작위 식별자로 NAS Authentication Response를 계속 생략하는 방식은 특정
피해자를 겨냥한 Blind DoS가 아니라 자원 소진형 공격이다. 첫 구현에서 Authentication
Response를 생략하는 것은 공격을 무한히 진행하지 않기 위한 **종료 지점**이지 별도 변형이
아니다. 자기 I-RNTI로 Resume를 반복하는 방식도 표적 축출이 아니라 signaling load다.
RRC signaling storm과 피해자 SIM 복제도 이 모듈의 Blind DoS에 포함하지 않는다.

RRC 재개 경로는 규격상 I-RNTI뿐 아니라 키로 계산하는 `resumeMAC-I`도 운반하므로 단순한
5G-S-TMSI 재사용과 같은 공격으로 취급할 수 없다. NAS 5G-GUTI 관련형도
[Open5GS 이슈 #4577](https://github.com/open5gs/open5gs/issues/4577)의 소스 분석상 관련
상태 변화 가능성이 제기됐을 뿐, 이 p5의 UE-only Uu 경로에서 실측한 결과가 아니다.
따라서 현재 변형 수에는 포함하지 않는다.

2026-10-22 실험은 피해 UE를 다시 등록한 뒤 앞선 등록에서 배운 값을 주입했다. AMF가
등록마다 새 5G-GUTI를 발급해 세 run의 값이 모두 달랐고, 공격 중 피해 UE 가용성은
96.0%와 99.6%였지만 실제 주입은 4건과 1건이었다. 따라서 이 결과로 말할 수 있는 것은
**해당 만료 식별자 실험 구성에서 차단을 관측하지 못했다**는 것까지다.
근거는 [변종 비교](../../rss-landscape.md)와
[보존된 실험 기록](../../artifacts/archive-du-cell-resource-20261026/findings/coverage-the-remaining-lever.md)을
따른다.

별도로 `(PCI, C-RNTI, shortMAC-I)`를 담는 `RRCReestablishmentRequest` 위조에서는
`shortMAC-I=0`인데도 최근 생성된 정상 UE 컨텍스트가 해제되는 OCUDU 실측이 있다.
그러나 축출 120건 모두 컨텍스트 생성 후 7.16초 안에 발생했고, 36.6회/s로 2,232건을
스윕한 run의 피해 UE 가용성도 99.3%였다. 이를 현재 유효 5G-S-TMSI 재사용형의 성공이나
지속 Blind DoS로 합산하지 않는다. 상세는
[재수립 축출 기록](../../artifacts/archive-du-cell-resource-20261026/findings/ocudu-reest-unauthenticated-release.md)을
따른다.

## 첫 검증 가설과 절차

첫 질문은 하나다.

> 피해 UE의 현재 등록을 유지한 채 그 등록에 유효한 48-bit 5G-S-TMSI를 별도 공격 UE가
> 재사용하면, 공격자가 피해자 인증에 성공하지 않아도 exact join된 망 상태 변화로 피해
> UE의 실제 서비스가 중단되는가?

가장 작은 실험은 다음 다섯 조건을 같은 설정에서 비교한다.

1. **공격 없음**: 피해 UE의 Registration·PDU session·ping 기준선을 확인한다.
2. **무작위 식별자**: 공격 메시지 도달 자체의 영향을 분리한다.
3. **만료 식별자**: 기존 실패를 음성 대조군으로 재현한다.
4. **현재 유효한 다른 UE 식별자**: 별도 팀 UE의 값을 넣고 영향이 식별자 소유자를
   따라가는지 확인한다.
5. **현재 유효한 피해 UE 식별자**: 피해 UE를 재등록시키지 않고 같은 등록 수명의 값을
   즉시 넣는다.

처음에는 UE·코어 로그에서 읽은 값을 실험용 oracle로만 쓴다. 이 입력으로 G3~G5를
판정할 수 있지만 현실적인 공격자 식별자 획득을 입증하지는 않는다. 현재 유효 값에서만
정확한 피해자 컨텍스트 충돌과 서비스 영향이 반복돼야 그다음에 Uu에서 비특권으로 값을
관측할 수 있는지 검증한다.
각 송신 직전·직후 AMF의 전체 5G-GUTI→UE 컨텍스트 매핑, RRC에 넣은 48-bit
5G-S-TMSI와 파생된 Part1·Part2, 그 사이 재할당 유무를 ground truth로 남긴다. 메커니즘이
실패하면 식별자 수집기나 광범위 스캐너는 만들지 않는다.

## 합격 기준

| 게이트 | 필요한 증거 | 판정·허용 주장 |
|---|---|---|
| **G3 식별자 도달** | 공격자 commit과 current-run AMF InitialUEMessage의 표적 48-bit 값·유효 NGAP ID가 조인 | 전달 경로 확인. 공격 성공 아님 |
| **G4 표적 망 상태 변화** | 현재값에서만 식별자 소유자의 기존 binding 변경, PDU session deactivation 또는 UE context release가 exact join되고 대조군에는 같은 변화가 없음 | identity 충돌 기전 확인. 서비스 DoS 성공 아님 |
| **G5 단발 서비스 중단 재현** | G4의 변화와 피해 UE 서비스 손실이 사전 고정한 attack-on N/N에서 인과 조인되고, matched attack-off에는 없으며 같은 UE가 공격 종료 뒤 Registration·PDU·ping 회복. N 기본값 3, 허용 범위 3~100 | **oracle 보조 단발 Blind DoS 재현기 성공** |
| **G6 현실적 입력 확인** | G5 + UE·gNB·코어 내부값 없이 공격 시점에도 유효한 식별자를 Uu에서 획득 | 비특권 공격자 입력 경로까지 확인 |
| **G7 지속 서비스 거부** | G6 + 매 재접속의 인과 조인 + 사전 고정한 관측창 동안 서비스 불능 + 중단 후 회복을 3회 | 지속 Blind DoS |

각 상위 등급은 하위 등급의 조건을 모두 포함한다. 한 번의 release, 같은 SUPI 사용,
mixed in-process probe, 만료 식별자 실패는 상위 등급의 증거가 아니다. oracle 입력으로도
G5를 만족하면 단발 재현기 성공으로 판정할 수 있지만, G6 전에는 현실적인 식별자 획득을,
G7 전에는 지속 서비스 거부를 주장하지 않는다. 명시적인 무선 release는 유일한 성공
경로가 아니다. 식별자 소유자의 기존 binding 변경이나 PDU session 해제만 발생하더라도
실제 서비스 손실과 exact join되면 G5의 망 상태 변화로 인정한다. 공격자 자신의 새
컨텍스트가 인증 실패로 정리된 것은 표적 상태 변화로 세지 않는다.

현재 자동 판정의 `exact_join`은 공격자 commit 뒤 같은 표적과 유효 NGAP ID를 가진 AMF
identity reach가 먼저 있고, 이어서 snapshot에 있던 피해자의 기존 RAN/AMF UE ID 상태
변화가 생긴 경우만 참이다. Open5GS가 identity reach에도 기존 ID를 기록할 수 있으므로
새 ID 발급 자체를 필수 조건으로 두지 않는다.
F1/NGAP pcap은 current-run 원문으로 봉인하지만 ASN.1 메시지별 자동 조인에는 아직 쓰지
않는다.

## 최소 라벨과 관측점

- 공격자 정답: `run_id`, 시퀀스, 메시지 종류, 48-bit 5G-S-TMSI와 Part1·Part2,
  전체 GUTI의 변환 근거, 식별자 소유자 role,
  출처(`oracle`·`uu_observed`·`stale`·`random`), 송신 시각
- 피해·대조 UE 정답: Registration·PDU session·ping 상태, 현재 GUTI·Part1, 재할당,
  disconnect·recovery 시각
- 망 관측: Initial UL RRC, NGAP InitialUEMessage, CU·DU UE ID, RAN UE NGAP ID,
  AMF UE NGAP ID, release cause, NGAP·F1의 UE Context Release Request/Command/Complete 시각
- 컨텍스트 관계: 공격자의 새 컨텍스트와 식별자 소유자의 기존 컨텍스트를 별도 role로
  기록하고 old/new linkage를 남긴다.
- 조인 키: 동기화된 시각 + cell/PCI + 임시 식별자 + CU·DU UE ID + 두 NGAP UE ID

탐지기 입력에는 공격자 정답과 oracle 값을 넣지 않는다. detector 출력이 봉인된 뒤에만
ground truth와 합쳐 채점한다.

## 안전 경계와 다음 작업

모든 실험은 팀 장비와 ZMQ 또는 RF 차폐 환경에서만 수행한다. 피해 UE와 식별자 특이성
대조 UE는 모두 별도 팀 가입자다. 첫 구현은 allowlist된 단일 UE를 한 번 겨냥하는 모드와
유한 실행시간만 둔다. 전체 C-RNTI·식별자 공간 스캔은 기본 기능으로 만들지 않는다.

소스 추적으로 OAI의 Part1/Part2 생성, OCUDU의 NGAP 전달, Open5GS의 버전별 컨텍스트
처리 차이를 확인했고 G0 inventory와 p5 ZMQ 실측을 마쳤다. ping 손실은 있었지만 회복과
표적 특이성 대조가 미달이라 식별자 수집기·지속형·OTA 확장은 중단한다. 실행 원문은 Git
밖에 보존하고 Git에는
[정제된 결과와 무결성 정보](artifacts/p5-zmq-20261102/README.md)만 올린다.
