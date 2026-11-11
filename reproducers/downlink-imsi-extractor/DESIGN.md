# 하향 IMSI 추출 계열 재현기 설계

## 1. 설계 목표

탐지기가 다음 비정상 메시지 수명을 관측할 수 있는 반복 가능한 입력을 만든다.

```text
RRCSetupComplete
→ Registration Request
→ Authentication Request
→ Identity Response(SUCI)
→ release 또는 registration 실패
```

같은 UE 연결에 대해 망이 보낸 `Identity Request`가 없어야 한다. 실제 RF 원인을 만들지
않으므로 메시지 결과와 RF 원인을 별도 필드로 판정한다.

## 2. 신뢰 경계

| 구성요소 | 역할 | 신뢰·변경 범위 |
|---|---|---|
| OAI UE | 피해 UE와 에뮬레이션 지점 | UE NAS handler만 변경 |
| OCUDU DU/CU | 실제 RRC·F1·NGAP 전달 | 소스·timer·capacity 무수정 |
| Open5GS | 예상하지 않은 Identity Response 처리 | 소스 무수정, 로그는 oracle |
| 실행기 | control/emulation, 수집, 종료 | 유한 실행·중복 실행 차단 |
| 판정기 | 메시지 조인·합격 판정 | 실행기와 독립적으로 원문 재검사 |
| detector | 기본 N2 관측, 선택적 CU/F1/eBPF 조인 | UE·Open5GS oracle 접근 금지 |

## 3. UE 패치

OAI 2026.w38 `openair3/NAS/NR_UE/nr_nas_msg.c`에는 이미 다음 구현이 있다.

- `generateIdentityResponse()`
- `nas_fill_5gs_mobile_identity()`
- `fill_suci()`와 protection scheme 0/1 처리
- NAS downlink의 `FGS_AUTHENTICATION_REQUEST` 분기

따라서 새 encoder나 별도 NAS 구조체를 만들지 않는다. 공격 모드의 첫 Authentication
Request에서만 기존 `generateIdentityResponse(..., FGS_MOBILE_IDENTITY_SUCI)`를 호출하고,
이후 재전송은 정상 처리하지 않고 관측 종료까지 유지한다.

런타임 노브는 두 개만 둔다.

- `OAI_DOWNLINK_IMSI_EMULATE=1`: 시작부터 에뮬레이션
- `OAI_DOWNLINK_IMSI_TRACE=1`: control의 Authentication Response 제출 마커

패치는 다음 정답 마커를 남긴다. 원문 SUCI·SUPI는 마커에 쓰지 않는다.

```text
DOWNLINK_IMSI_EXTRACTOR event=identity_response_substituted
ue=N identity_type=suci protection_scheme=N
identity_response_submitted=true dl_overshadowing_observed=false
```

## 4. 실행 상태 기계

```text
준비
 ├─ 기존 UE/DU 실행 없음 확인
 ├─ CU·Open5GS 준비 및 로그 경계 기록
 └─ NGAP packet capture 시작
      ↓
UE 시작
      ↓
Registration Request
      ↓
Authentication Request
 ├─ control: Authentication Response → Registration/PDU/ping
 └─ emulation: Identity Response(SUCI) 1회 → 관측 → 자연 release
      ↓
원문 수집 → 독립 판정 → manifest 봉인 → 원복
```

control과 emulation은 같은 OAI binary, UE 프로필, DU/CU/core 설정을 사용한다. 다른 것은
에뮬레이션 환경 변수뿐이다.

## 5. 판정 데이터

각 run은 최소한 다음 파일을 만든다.

| 파일 | 용도 |
|---|---|
| `run.json` | mode, 고정 버전, 시각 경계, 원인/에뮬레이션 플래그 |
| `ue.log` | 사후 ground truth와 protection scheme |
| `cu.log` | RRC/NGAP context와 망 관측 경계 |
| `amf.log` | Registration·Authentication·Identity 처리 oracle |
| `ngap.pcap` | 가입자 식별자를 포함할 수 있는 제한 접근 N2 원문·기전 증거 |
| `observations.jsonl` | 가입자 원문을 제거한 기본 detector 입력 |
| `process.json` | crash·forced kill |
| `verdict.json` | 단일 실행 판정 |
| `evidence_manifest.json` | 핵심 파일 SHA-256 |

`verdict.json`은 다음 축을 분리한다.

- `control_healthy`
- `protocol_impact_reproduced`
- `unexpected_identity_response_observed`
- `suci_observed`
- `null_scheme_identity_exposure_observed`
- `dl_overshadowing_observed` — 항상 `false`
- `service_effect_observed` — 선택 효과

## 6. exact join

기전 합격에는 문자열 건수만 사용하지 않는다.

1. CU의 RRC UE index와 RAN UE NGAP ID를 조인한다.
2. AMF UE NGAP ID가 설정된 동일 context를 찾는다.
3. 그 context에서 Registration Request와 Authentication Request를 확인한다.
4. 이후 Identity Response가 있고, 그 전에 망의 Identity Request가 없음을 확인한다.
5. UE one-shot 정답 마커의 실행시간 경계와 일치시킨다.

원문 가입자 식별자는 SHA-256 fingerprint로만 oracle에 남기고 detector 입력에서는 제거한다.

## 7. 실패 조건

- control에 Identity Response 치환 마커가 존재
- emulation에 치환 마커가 0건 또는 2건 이상
- 실제 망 Identity Request가 관측돼 정상 identification 절차와 구분할 수 없음
- Identity Response가 다른 RAN/AMF UE ID에 조인됨
- SUCI protection scheme을 판정하지 못함
- null-scheme이 아닌데 IMSI/SUPI 추출 성공으로 판정
- CU·DU·Open5GS crash 또는 강제 종료
- raw 가입자 식별자·키가 게시용 artifact에 포함

## 8. 구현 순서

1. OAI w38 one-shot 패치와 정적 빌드 마커 검사
2. 정규화기·독립 판정기·단위 테스트
3. p5 direct 1-cell control smoke
4. p5 direct 1-cell emulation smoke
5. NGAP exact join과 SUCI scheme 확인
6. matched control→emulation 3세트
7. 사용 가이드·실측 artifact·상위 인덱스 갱신 후 동결

실제 RF downlink overshadowing은 별도 OTA 모듈로 취급한다. ZMQ 에뮬레이션 합격을 OTA
성공으로 승격하지 않는다.

## 9. 실제 OTA 변형으로 전환할 때

p5 direct ZMQ는 UE와 DU가 전용 socket으로 연결되므로 두 송신 신호의 전력 경쟁과 capture
effect를 만들 수 없다. 실제 RF 공격은 현재 UE 패치의 device만 USRP로 바꾸는 포팅이
아니며 별도 설계가 필요하다.

- 정상 gNB 송신 USRP와 피해 UE를 유지한다.
- 현재의 공격자 UE 역할은 정상 하향 프레임을 추적하는 **악성 gNB/하향 waveform
  injector**로 교체한다.
- 공격자 송신기는 정상 하향 NAS와 시간·주파수·자원 위치를 맞춘 Identity Request를
  차폐박스 안에서 송신해야 한다.
- 피해 UE의 Identity Response를 독립적으로 확인할 uplink sniffer 또는 동시 수신 가능한
  별도 SDR 채널이 필요하다.
- 감쇠·송신 gain·clock·trigger·timing offset을 사전 고정하고 정상군과 attack-on을 같은
  조건으로 반복한다.

OTA 성공은 공격자 RF 송신 원문, 피해 UE의 실제 Identity Request 수신, 정상 gNB가 해당
요청을 생성하지 않았다는 증거, 공격자의 uplink Identity Response 수신이 모두 조인될 때만
인정한다. scheme 0일 때만 SUPI/IMSI 노출을 추가 판정하며 Profile A 응답은 SUCI 관측으로만
기록한다.
