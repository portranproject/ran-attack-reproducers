# Label v1 · CSI-DTX RLF 실기 증거 — 2026-10-30

이 디렉터리는 p5 ZMQ 실험의 **식별자 없는 집계와 아래 목록에 적은 원격 원문의
SHA-256**만 보존한다.
UE·DU·CU 원문 로그는 식별자를 포함할 수 있어 저장소로 복사하지 않았다. 원문은 중지된
p5 보존 디스크의 `/root/rss-runs-label-v1-20261030/`(DU)와
`/root/rss-response-rlf20-20261030/`(CU)에 있다.

## 빌드 계보와 발견한 결함

| 항목 | 값 |
|---|---|
| OAI 기준 | `2026.w38`, `1c2f4d3c2e68181cdef9f426d161163147ad4b77` |
| 적용 순서 | clean stock build → 공식 PUCCH 수정 → curated patch |
| 공식 PUCCH 수정 | upstream `3d4b1923b424be974c1dadcc9c48eddbe8428ba0`, local patch SHA-256 `f464e39ca3f99f8528dc2769a05e1d477d1e5e3701280bfe6d972d9d4eae0d7f` |
| 최종 curated patch SHA-256 | `4ad5c85b60e0fba0a70eb1c261950a2b407e0b0c241804dae6604e1d3aac26bc` |
| `nr-uesoftmodem` SHA-256 | `cb0682800f46ddc283aaf62c63ce3a50c128bde0ad37dcbb83ea07d6d24af270` |
| `liboai_zmqdevif.so` SHA-256 | `66b4b95f8feea9491d5fdac99ef354e9265a5aa5cc4f1a93d8e03e7e39d26b71` |
| 변경 범위 | curated patch 11개 파일 + 별도 공식 PUCCH 수정 |

위 SHA-256은 이 보존 실측에 실제 사용한 역사적 patch다. 현재 기본 patch는 이후 UICC
가입자 로그와 direct Milenage 인증 dump 제거 hunk가 추가되어 hash가 다르며, 이 표의 실측 계보를 소급해
바꾸지 않는다.

첫 ACK-on 런 `lv1a-ackon-20261030-01`은 MAC ACK event와 RRC Msg4 event가 같은
`FILE*`에 동시 기록돼 JSON 두 줄이 서로 끼어들었다. exporter가 malformed JSON을
감지해 출력 없이 런을 무효화했다. 공용 JSONL writer 전체를 mutex로 직렬화하고
재빌드한 뒤 아래 유효 런을 수행했다. 무효 런도 원격에 보존했다.
이 최초 무효 런은 이번 manifest에 별도 hash를 싣기 전에 발견한 운영 관측이므로,
재현 가능한 봉인 증거로 세지 않는다.

## 정상 회귀와 ACK 라벨 분리

attack-off `lv1b-20261030-01`은 attach·PDU tunnel과 ping 5/5에 성공했고,
`attempts=0`, `label_export=no_events`, `valid=true`였다.
이 기준선도 이번 manifest의 개별 파일 hash 목록에는 포함하지 않았다.

동일한 단일 UE·2초 시도 간격·20초 공격 조건의 결과는 다음과 같다. ACK event 수는
Msg4 재전송 때문에 시도 수보다 많을 수 있다.

| run | 시도 | scheduled | withheld | UE A 후보 | 최종 A | actual reach | DU ACK/DTX | max-retx | Msg5 |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| `lv1a-ackon-20261030-03` | 10 | 52 | 0 | 10 | 0 (`null` 10) | `msg5_skip` 10 | 65 / 22 | 0 | 0 |
| `lv1n-ackoff-20261030-01` | 10 | 0 | 240 | 0 | 0 (`false` 10) | `msg4_no_ack` 10 | 0 / 475 | 40 | 0 |

두 런 모두 `label_export=ok`, `valid=true`이고 raw JSON 전체가 파싱됐다. 최종 A형은
UE 후보와 DU ACK를 아직 시도별로 자동 조인하지 않으므로 `canonical_a=true`로 만들지
않았다. 표의 DU ACK는 단일 UE 셀 로그의 별도 aggregate evidence다.

## CSI-DTX RLF A/B

기본 `pucch.max_consecutive_kos=100`인 위 ACK-on 런에서는 시도 10개 모두
`100 consecutive undecoded CSIs` RLF를 기록했지만 F1 release request는 0이었다.
RLF 뒤 t310까지 기다리는 동안 기존 CU Setup 타임아웃이 먼저 context를 정리한 결과다.

`max_consecutive_kos=20`만 추가하고 t310=1000ms 및 나머지 설정을 유지한
`rv1a-rlf20-20261030-01`은 다음을 보였다.

| DU 설정 provenance | SHA-256 / 변경 |
|---|---|
| 실험 전·원복 후 | `7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3` |
| RLF20 후보 | `a5b398a5aa87ff2555dee31c95aa83160e3db37053c2422c4b4da8222365f386` |
| 정확한 diff | `cell_cfg.pucch` 아래 `max_consecutive_kos: 20` 한 줄 추가 |

후보 파일은 같은 `du.yaml`에 적용한 뒤 원복해 별도 파일로 보존하지 않았다. 따라서 후보
hash와 한 줄 diff는 실행 중 기록한 operator record이며, 원본 백업과 원복본만 원격
디스크에 남아 있다.

| 항목 | 결과 |
|---|---:|
| canonical A UE 후보 | 20/20 |
| `20 consecutive undecoded CSIs` RLF | 20 |
| RLF timer expiry → release 요청 집계 | 20 |
| F1 Release Request / Command / Complete 집계 | 20 / 20 / 20 |
| CU DU-initiated release 처리 / Setup 취소 집계 | 20 / 20 |
| CU NG release 생략(no NG context) | 20 |
| Msg5 / InitialUEMessage | 0 / 0 |

같은 threshold 20의 attack-off 안전 게이트 `rv1b-rlf20-normal-20261030-01`은
Registration Accept 1, PDU Session Accept 1, ping 20/20, RLF 0, F1 release 0이었다.
이는 한 번의 약 60초 회귀일 뿐 장기·열악 채널의 정상 UE false release를 배제하지 않는다.
단일 UE 직렬 런에서 각 단계 집계가 20건으로 일치해 전체 경로와 부합하지만, 시도별
F1/CU ID를 조인한 20개 인과 체인 증거는 아니다.

## 복구와 주장 경계

- DU 설정은 원본 SHA-256
  `7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3`로 원복했다.
- DU·UE와 CU stack을 종료한 뒤 p5 CU/DU 인스턴스를 중지했다.
- ZMQ radio는 실시간보다 빠르므로 wall-clock 수명을 OTA 값으로 일반화하지 않는다.
- threshold 20은 셀 전체 정적 설정이며 정상 UE false release 위험이 있다.
- 이 결과는 **정적 DU hardening의 ZMQ 실증**이지, 외부 탐지기가 호출한 개별 UE
  actuator나 near-RT RIC 탐지→대응 폐루프가 아니다.
- 차폐 OTA와 장기·채널 열화 정상 UE 안전성은 미검증이다.

manifest에 포함한 원격 원문의 무결성은 [SHA256SUMS.remote](SHA256SUMS.remote)에
기록했다.
