# Blind DoS 구현·검증 계획

상태: **현재 유효 5G-S-TMSI 재사용형의 UE 패치·실행기·판정기 구현과 p5 ZMQ
실측 완료.** 공격 입력은 AMF까지 도달했고 기존 피해 binding 변화와 ping 손실도
관측됐지만, 같은 피해 UE가 사전 고정한 30초 안에 회복하지 않았다. 현재 피해자 값 조건의
G3 도달과 상태 변화는 관측했지만 무작위·만료·다른 UE 값의 특이성 대조는 실행하지 않아
전체 G4는 확정하지 않는다. G5 공격 성공도 아니므로 식별자 수집기·지속형·OTA로 확장하지 않는다.
RRC 재수립 식별자 위조형은 별도 시나리오로 유지하고 이 구현에 섞지 않는다.

이 계획에서 공격 성공 게이트는 **G5**다. G3의 메시지 도달과 G4의 망 상태 변화는
원인 경로를 확인하는 중간 게이트이며, 실제 피해 UE 서비스 중단이 없으면 공격 성공이
아니다. G6와 G7은 각각 현실적인 식별자 획득과 지속 서비스 거부라는 상위 주장이다.

## 1. 먼저 고정할 기전

공격 입력은 `RRCSetupRequest`에 보이는 39-bit Part1만이 아니라 **48-bit
5G-S-TMSI 전체값**이다.

```text
피해 UE 정상 등록
  └─ 현재 5G-GUTI / 48-bit 5G-S-TMSI 할당

공격 UE 1회 접속
  ├─ Msg3  RRCSetupRequest: 5G-S-TMSI 오른쪽 39-bit Part1
  ├─ Msg5  RRCSetupComplete: 왼쪽 9-bit Part2 + 공격자 자신의 NAS Registration Request
  └─ CU: Part1+Part2 복원 → NGAP InitialUEMessage(FiveG-S-TMSI)

AMF
  └─ 그 값으로 기존 UE를 찾고 old/new NG context를 어떻게 처리하는지 관측
```

OAI 2026.w38은 이미 전체값에서 [Part1과 Part2를 각각 만드는
경로](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/2026.w38/openair2/RRC/NR/MESSAGES/asn1_msg.c)를
갖고 있다. 새 ASN.1 생성기를 만들지 않고, 공격 모드에서 이 기존 경로에 전체값을 한 번
넣는다. Msg3만 보내면 식별자가 AMF까지 도달하지 않으므로 Msg5와 Initial NAS까지는
정상 전송하고, NAS `Authentication Request`를 받으면 응답하지 않고 종료한다.

AMF 결과는 버전에 따라 다를 수 있다. Open5GS v2.7.6은 InitialUEMessage의
FiveG-S-TMSI로 기존 UE를 찾은 뒤 연결 중이면
[`HOLDING_NG_CONTEXT`](https://github.com/open5gs/open5gs/blob/v2.7.6/src/amf/ngap-handler.c)로
기존 NG 컨텍스트를 분리하고 새 RAN UE 컨텍스트를 연결한다. holding timer는
[기본 30초](https://github.com/open5gs/open5gs/blob/v2.7.6/src/amf/timer.c)다.
반면 현재 main에는 Registration Request의 가입자 identity와 연결된 NG context가 다르면
이를 탐지하는 [추가 분기](https://github.com/open5gs/open5gs/blob/main/src/amf/amf-sm.c)가
있다. 따라서 특정 release 동작을 전제로 구현하지 않고 **p5 설치 버전의 실제 상태 전이**를
증거로 삼는다. `Known UE`, `Holding NG Context` 한 줄만으로 DoS 성공이라 판정하지 않는다.

## 2. p5 ZMQ 구성

```text
p5 CU 호스트
  Open5GS AMF/UPF + OCUDU CU
  AMF·CU run-slice 로그 + N2/F1 캡처
              │ F1
p5 DU/UE 호스트
  OCUDU DU + GNU Radio ZMQ broker
  ├─ 피해 OAI UE     : 가입자 V, 정상 서비스 측정
  ├─ 공격 OAI UE     : 가입자 A, 1회 표적 요청
  └─ 특이성 대조 UE  : 가입자 C, G4부터 추가
```

- V·A·C는 서로 다른 팀 소유 가입자 프로필을 쓴다. 같은 SUPI 복제는 무효다.
- CU·DU·Open5GS의 타이머·용량·소스는 바꾸지 않는다.
- 처음에는 기존 headless
  [`multi_ue_2ue.py`](../rrc-signaling-storm/tools/multi_ue_2ue.py)로 V+A 경로만 안정화한다.
  현재 유효한 비표적 identity까지 검증하는 G4에서만 같은 패턴의 3-endpoint broker를
  최소 변경으로 추가한다.
- 최종 증거는 별도 UE 프로세스로 만든다. 한 프로세스의 다중 UE는 진단에는 쓸 수 있지만
  피해자 독립성 증거로 쓰지 않는다.

## 3. 가장 작은 구현 범위

### OAI 패치

기준은 clean OAI `2026.w38`와 현재 사용 중인
[PUCCH null 수정](https://github.com/OPENAIRINTERFACE/openairinterface5g/commit/3d4b1923b424be974c1dadcc9c48eddbe8428ba0)만이다.
RRC storm의 curated/full 패치나 과거 A-NAS 패치는 섞지 않는다.

공격 UE 옵션은 아래 일곱 개만 둔다. 독립 실행기는 표적 snapshot 뒤에도 동일 공격 UE와
브로커 그래프를 유지하기 위해 `target_file` 게이트를 사용한다.

| 옵션 | 의미 | 기본값 |
|---|---|---|
| `blind.enable` | 공격 경로 활성화 | `0` |
| `blind.tun_suffix` | 서로 다른 UE의 PDU TUN 이름 분리 | `0` |
| `blind.target_5g_s_tmsi` | 48-bit 전체값, hex | 없음 |
| `blind.target_file` | snapshot 뒤 원자적으로 생성할 표적 파일 | 없음 |
| `blind.target_wait_s` | 표적 파일 대기 제한시간 | `120` |
| `blind.run_id` | run 조인 키 | 필수 |
| `blind.log_file` | 공격자 JSONL | 필수 |

구현 규칙은 다음과 같다.

1. `enable=1`일 때 direct 표적값과 표적 파일 중 정확히 하나만 요구하고,
   `0x000000000000`~`0xffffffffffff` 범위를 검사한다.
2. 최종 Msg3 생성 직전에 기존 `fiveG_S_TMSI` 인자에 표적값을 **한 번만** 넣는다.
3. 기존 OAI 함수가 Part1·Part2를 만들게 하고
   `full == ((part2 << 39) | part1)`을 작은 테스트로 고정한다.
4. 정상 Msg5와 공격자 자신의 NAS Registration Request를 전송한다.
5. NAS Authentication Request를 받으면 이벤트를 기록하고 응답 없이 멈춘다.
6. v1은 1회 시도만 허용한다. 재시도율·스캔·다중 표적 기능은 만들지 않는다.
7. `enable=0`은 stock w38과 같은 경로여야 한다.

기존 5GSEC OAI 포크는 오래된 OAI v2.1.0용이며 라이선스가 명확하지 않으므로 동작
참고만 하고 코드는 복사하지 않는다.

### 독립 실행기

RRC storm의 `rss-run`을 확장하지 않고 Blind DoS 전용 실행기를 둔다. 실제 구현 시 필요한
파일만 만든다.

```text
reproducers/blind-dos/
├── patch/blind-ue-w38.patch
├── bin/blind-build
├── bin/blind-run
├── analysis/export_labels.py
├── conf/blind.conf.example
└── tests/                 # bit split과 attack-off 회귀만
```

실행기는 다음 기존 패턴만 재사용한다: 기본 공격 off, run lock, 유한 실행시간, readiness
확인, 두 단계 SIGINT 종료, 프로세스 crash 기록, 파일 SHA-256, immutable run 디렉터리,
민감정보 검사, clock offset/uncertainty 기록. RRC storm의 시나리오별 라벨·판정기는 재사용하지
않는다.

## 4. 구현·실측 게이트

앞 게이트가 실패하면 뒤 기능을 만들지 않는다.

### G0 — 설치 상태와 불변조건 고정

실험 전 아래 값을 `run.json`에 기록한다.

- p5 Open5GS 정확한 버전·commit/package/image digest와 AMF 설정 hash
- OCUDU commit·CU/DU 설정 hash, OAI commit·binary hash, PUCCH patch hash
- broker hash, V·A·C 프로필의 비밀값 제외 설정 hash와 서로 다른 SUPI임을 나타내는 alias
- CU·DU·AMF·UE 시계 offset과 uncertainty
- AMF가 v2.7.6식 holding인지 최신 identity-mismatch식인지 구분할 로그·소스 서명

이 값을 얻지 못하거나 gNB/core 기본 설정이 바뀌어 있으면 중단한다.

### G1 — 패치 자체 검증

1. clean w38 + PUCCH fix + Blind 패치를 새 worktree에서 빌드한다.
2. 48-bit 경계값과 Part1/Part2 round-trip 테스트를 통과시킨다.
3. `blind.enable=0` 단일 UE direct-ZMQ에서 Registration·PDU session·TUN·ping을 확인한다.
4. 공격 모드 1회 뒤 재시도가 없고 제한시간에 clean 종료되는지 확인한다.

### G2 — 공격 없는 2-UE 기반선

기존 2-endpoint broker에서 V와 A를 **별도 프로세스**로 실행한다. 공격 off 상태로 3회
연속 다음을 만족해야 한다.

- 두 UE sync 성공
- V의 Registration·PDU session·ping 성공
- A 시작·종료가 V 서비스에 영향을 주지 않음
- kernel/UE/broker crash 0, TUN 소유권 모호성 0, clean teardown

이 단계의 서비스 분포를 보고 공격 전 성공 수·실패 연속 수·회복 제한시간을 고정한다.
공격 결과를 본 뒤 threshold를 바꾸지 않는다.

### G3 — 메시지 도달과 identity 복원

서비스 중단 여부와 무관하게 아래 순서로 각각 1회 보낸다.

1. 무작위 48-bit 값
2. V의 이전 등록에서 나온 만료 값
3. V의 현재 등록에 유효한 값

각 run에서 아래 한 줄의 인과 사슬이 exact join되어야 한다.

```text
attacker JSONL(full/Part1/Part2 commit)
  → current-run AMF InitialUEMessage FiveG-S-TMSI
  → 유효 NGAP ID를 가진 identity reach와 기존 피해자 NGAP ID의 상태 변화
```

F1/NGAP pcap은 원문 무결성 자료로 보존하지만 현재 자동 판정기는 이를 ASN.1 decode해
메시지별 조인하지 않는다. 따라서 자동 `exact_join`은 공격자 commit 시각·48-bit 표적값·
AMF InitialUEMessage·기존 피해자 RAN/AMF UE ID 상태 변화의 결합을 뜻한다.

송신 직전과 직후 V의 5G-GUTI가 바뀌면 그 run은 무효다. 이 게이트가 실패하면 Uu
식별자 수집이나 반복 공격을 만들지 않고 인코딩·캡처부터 고친다.

### G4 — 컨텍스트 충돌과 표적 특이성

3-endpoint 구성으로 다음 다섯 조건을 같은 설정에서 비교한다.

| 조건 | 기대 역할 |
|---|---|
| 공격 없음 | 서비스·컨텍스트 기준선 |
| 무작위 값 | 메시지 도달 음성 대조군 |
| 만료 V 값 | 과거 실패의 음성 대조군 |
| 현재 유효 C 값 | 영향이 identity 소유자를 따라가는지 확인 |
| 현재 유효 V 값 | 정규 표적 조건 |

현재값 두 조건에서는 공격 commit 뒤의 identity reach와 identity 소유자의 **기존**
컨텍스트를 구분한다. Open5GS 로그가 identity reach에 기존 NGAP ID를 재사용할 수 있으므로
새 ID 발급은 필수 조건이 아니다. 최소 40초 관측해 v2.7.6 계열의 30초 NG holding
만료까지 포함한다.

판정은 세 층으로 나눈다.

1. `identity reach`: AMF가 현재 UE를 정확히 찾음
2. `network state effect`: 식별자 소유자의 기존 AMF/RAN binding 변경, PDU session
   deactivation 또는 NGAP/F1 UE context release 중 하나 이상이 exact join됨
3. `service impact`: 해당 UE의 사전 고정된 Registration/PDU/ping 판정이 실패함

1이나 2만 관측되면 기전 후보일 뿐 Blind DoS 성공이 아니다. 명시적인 무선 release는
필수 단계가 아니며, 어떤 망 상태 변화든 실제 서비스 손실과 인과 조인되어야 한다.
공격자 자신의 새 컨텍스트가 인증 실패로 정리된 것은 표적 상태 변화로 세지 않는다.

### G5 — 단발 서비스 중단과 회복

G4에서 현재 V 값의 영향은 V에만, 현재 C 값의 영향은 C에만 나타나고 V에는 영향이 없을
때만 matched attack-on/off를 사전에 고정한 N세트 수행한다. N은 기본 3이며
`blind-campaign -R N`으로 3~100 범위에서 실행 전에 고정한다.

- on: 현재 V 값 1회 송신, V의 기존 상태에 대한 exact network-state-effect join,
  V 서비스 손실
- off: 같은 시간·구성에서 공격 송신 0, 같은 망 상태 변화·V 서비스 손실 0
- recovery: 공격 종료 뒤 **같은 V UE**가 Registration·PDU·ping을 회복

각 세트마다 V를 새로 정상 등록하고 현재 5G-S-TMSI를 다시 읽는다. 앞 세트 값을 재사용하지
않는다. 이 조건을 N/N 만족해야 `oracle 보조 단발 Blind DoS 재현기 성공`이라고 부른다.
중간에 유효한 실패가 하나라도 나오면 그 캠페인은 즉시 실패로 끝나며 N을 줄여 합격으로
바꾸지 않는다. broker sync 같은 인프라 무효만 사전 고정한 제한 횟수 안에서 재시도한다.

### G6 — 현실적인 식별자 획득

G5까지 성립한 뒤에만 oracle을 공격 입력에서 제거한다. paging·Uu에서 현재 유효
5G-S-TMSI를 비특권으로 얻을 수 있는지 별도 검증한다. UE·gNB·코어 내부 로그는 이때도
채점용 ground truth로만 남긴다. 획득이 실패해도 G5를 통과했다면 oracle 보조 단발
재현기 결과는 유지하되, 현실적인 공격자 입력 경로는 주장하지 않는다.

### G7 — 지속형과 차폐 OTA

지속형은 G6 뒤 별도 증분이다. 피해 UE가 재접속할 때마다 새 식별자를 다시 얻고,
각 시도와 망 상태 변화를 exact join하면서 사전 고정한 30초 동안 서비스 불능과 공격
중단 뒤 회복을 3회 확인한다. 1회 값을 고속 반복하거나 전체 식별자 공간을 스캔하지
않는다.

OTA는 ZMQ G0~G6를 통과한 뒤 기존
[OTA 안전 게이트](../rrc-signaling-storm/docs/OTA-SMOKE.md)를 적용한다. RF 차폐,
TX-off 기본값, 장비 serial·clock·gain·감쇠·누설 확인을 다시 수행한다. 독립 V/A에 최소
3대, C까지 같은 시간에 유지하려면 4대 SDR가 필요하다.

## 5. run 증거와 무효 조건

각 run은 다음만 보존한다.

```text
run.json
attacker_events.jsonl
victim_service.jsonl
target_snapshot_before.json
target_snapshot_after.json
amf.log / cu.log / du.log          # current-run slice
ngap.pcap / f1ap.pcap              # current-run capture
ground_truth.jsonl
run_stop.json
evidence_manifest.json
```

`target_snapshot`에는 피해 로그가 제공하는 AMF Set ID·AMF Pointer·5G-TMSI,
이를 합친 48-bit 5G-S-TMSI, Part1, Part2, owner role,
RAN UE NGAP ID, AMF UE NGAP ID와 추출 근거 hash를 넣는다. 원시 로그·pcap·가입자 설정은
이미 ignore된 `reproducers/blind-dos/runs/`에만 두고 Git에는 정제된 판정과 SHA-256만
올린다. 탐지기 입력에는 oracle 값과 attacker ground truth를 넣지 않는다.

다음 중 하나면 run 전체를 무효 처리한다.

- p5 버전·설정 hash가 G0와 다름
- V·A·C 중 같은 SUPI 사용
- snapshot과 송신 사이 표적 48-bit 5G-S-TMSI 재할당
- 표적 mapping 부재 또는 identity reach·기존 피해 ID 조인 중복
- UE sync 실패, F1/N2 capture gap, clock uncertainty 초과
- UE·broker·gNB·core crash 또는 강제 kill
- TUN/서비스 측정 주체가 불명확함
- CU·DU·Open5GS 타이머·용량 변경

유효한 실패 결과는 자동 재시도하지 않는다. broker sync 같은 인프라 실패만 새 run ID로
제한 재시도하고 실패 원문도 보존한다.

## 6. 작업 순서와 종료점

| 순서 | 산출물 | 통과해야 다음으로 감 |
|---|---|---|
| 1 | p5 G0 inventory | 완료: 정확한 stack·설정·binary hash 보존 |
| 2 | 최소 OAI patch + bit test | 완료: clean w38 계열 빌드와 attack-off 경로 확인 |
| 3 | 전용 runner + evidence seal | 완료: valid failure와 infrastructure-invalid 분리·자동 봉인 |
| 4 | 고정 2-UE attack-off | 완료: 닫힌 표적 게이트에서 피해 서비스 정상 확인 |
| 5 | 현재 유효 값 전달 | 완료: attacker commit→AMF identity reach 확인 |
| 6 | 현재 피해자 binding·서비스 영향 | binding 변화와 ping 손실 확인, 30초 안 회복 없음 |
| 7 | matched on/off N세트(기본 3, 3~100) | 실행기는 완료. 현 p5는 첫 유효 attack의 회복 미달로 즉시 종료 |
| 8 | Uu 획득, 지속형·OTA | G5 미달로 구현하지 않음 |

가장 중요한 중단점은 G4~G5다. 현재값에서 상태 변화와 서비스 손실이 보여도 표적 특이성,
같은 UE 회복, matched N/N 중 하나가 미달이면 그 결과를 보존하고 상위 주장을 닫는다.
그 경우 식별자 수집기·반복기·OTA 이식은 만들지 않는다.
