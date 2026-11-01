# 5G RRC 시그널링 스톰: 기존 연구·공격 도구 비교 (검증 표시판)

> 작성 2026-10-16. [rss-landscape.md](rss-landscape.md)의 조사를 **5G 기준으로 좁혀** 다시 정리하고, 주장마다 원본과 대조했는지 표시한 요약판이다. 세부 근거와 각주 번호는 rss-landscape.md를 따른다.

## 0. 읽는 법

### 범위
- **5G NR**을 대상으로 한 연구·코드만 본문에 둔다. LTE에서만 실험한 자료는 계보상 필요한 것만 §5에 따로 둔다.
- 우리 과제의 조건은 **외부자 UE 1대 + 무수정 gNB(OCUDU)**이다. 봇넷·가짜 기지국·코어 장악이 필요한 공격은 범위 밖이다.

### 신뢰 표시

| 표시 | 뜻 |
|---|---|
| ✅ | 2026-10-15~16에 원본(PDF·패치·소스 파일)을 직접 열어 대조했고 일치했다 |
| 📄 | rss-landscape.md에 출처 위치(절·줄 번호)와 함께 기재돼 있으나 이번에 재확인하지 않았다. arXiv는 작업 환경에서 접속이 막혀 있었다 |
| 🔍 | 추론 또는 미확인. 실험 전에는 사실로 쓰지 않는다 |

**조사 범위의 한계**: 공개 도구를 비교한 초판 조사에서는 공격·탐지 도구를 **실행하지 않았고**, 기능 판단은 논문과 코드 판독에 근거했다 ([rss-landscape.md](rss-landscape.md) §2.2, §2.4). 이후 본 프로젝트의 OAI w38 RRCSetupRequest 후 중단형과 RRCSetup HARQ-ACK 억제형은 p5 ZMQ에서 별도로 실측했으며, 아래 표는 그 결과를 구분해 적는다.

---

## 1. 분류 기준: "공격 UE가 접속 절차의 어디서 멈추는가"

### 표준 메시지명에 기반한 설명형 이름을 쓴다
이 문서의 이름은 3GPP 공식 공격 분류명이 아니다. 대신 처음 보는 사람도 중단 지점을 알 수 있도록 **RRCSetupComplete 미전송형**, **RRCSetupRequest 후 중단형**, **RRCSetup HARQ-ACK 억제형**, **NAS Authentication Response 미전송형**, **UE 재시작 반복형**, **RRCResume 반복형**, **PRACH 반복형**처럼 표준 메시지명과 반복 동작을 그대로 쓴다.

### 기준 자체는 문헌에 근거가 있다

| 근거 | 내용 | 신뢰 |
|---|---|---|
| KAUST §V-B | 선행 연구 방식(Msg1–3 반복)으로는 컨텍스트가 쌓이지 않았고, Msg4의 HARQ ACK까지 보내야 쌓였다고 직접 비교한다. 멈추는 위치가 공격 성패를 가른다는 실험 증거 | ✅ |
| 3GPP TR 33.861 KI#5 | 위협을 "AS 보안 전의 반복 접속"과 "AS 보안 후의 재수립·resume 반복"으로 나눈다 | 📄 |
| OCUDU 소스 | `RRCSetupComplete`(Msg5)가 와야 CU가 AMF로 NGAP InitialUEMessage를 보낸다. Msg5 전에 멈추면 코어에 보이지 않는다 | 📄 |

멈추는 위치가 바뀌면 ① 묶이는 자원, ② 묶이는 시간, ③ **관측 위치**(DU만 / F1 / 코어까지)가 함께 바뀐다. 탐지기 검증이 목적인 우리에게는 ③이 결정적이라 이 기준을 쓴다.

### 이 기준만으로 갈리지 않는 축
같은 중단 지점이라도 아래는 별개의 축이다. rss-landscape.md 표 3은 이것들을 따로 행으로 둔다.
- **위장 신원**: 무작위 identity vs 피해 UE의 5G-S-TMSI(→ Blind DoS)
- **접속 이유**: `establishmentCause`를 emergency 등으로 위조
- **규모·분산**: UE 1대 vs 다수, 여러 DU로 분산(RAID)
- **시작 상태**: RRC_INACTIVE에서 resume 반복(RRCResume 반복형), 재수립 반복

---

## 2. 5G 변종 지도

```
Msg1 → Msg2 ─┬→ Msg3 ─┬→ Msg4(+HARQ ACK) ─┬→ Msg5 → 인증요청 ─┬→ 등록 완료 ─┬→ ...
             │        │                   │                    │              │
      [PRACH 반복형] [RRCSetupRequest 후 중단형] [RRCSetupComplete 미전송형] [NAS Authentication Response 미전송형] [UE 재시작 반복형]
```

| 변종 | 묶이는 자원 | 코어에 보이나 | UE 1대로 가능한가 | 공개 코드 |
|---|---|---|---|---|
| **PRACH 반복형**: Msg3 전 중단 | DU의 RA 자원(프리앰블, TC-RNTI) | ❌ | 부분적 📄 | 없음 |
| **RRCSetupRequest 후 중단형**: Msg3 직후 재시작 | OCUDU p5에서 capacity 96 점유 확인. 기본 CSI-DTX RLF에서는 지속 거부 실패, 실험 전용 hold 프로필에서 probe 11/11 자원 거절 ✅ | ❌ | ✅ ✅ | salam 포크 + 본 프로젝트 OAI w38 |
| **RRCSetup HARQ-ACK 억제형**: Msg4 ACK 억제 | Msg4 재전송·max-retx까지 DU 자원 사용. p5 ACK-on/off 비교 3회에서 ACK 0·max-retx 38~40 확인 ✅ | ❌ | ✅ ✅ | 본 프로젝트 OAI w38 |
| **RRCSetupComplete 미전송형**: Msg5 생략 | DU·CU 컨텍스트가 CU 타임아웃까지 유지 | ❌ | ✅ ✅(KAUST OTA) | **5gattacks** |
| **NAS Authentication Response 미전송형**: 인증 무응답 | 기지국 컨텍스트 + 코어 인증 상태 | ✅ | ✅ 📄 | 5GSEC NR 브랜치 |
| **Blind DoS** | 피해 UE 한 대의 연결(표적형) | ✅ | 피해 UE의 TMSI가 필요 📄 | 5GSEC `--RRC-TMSI` |
| **UE 재시작 반복형**: 재부팅 반복 | 전체 절차(정상 접속과 같음) | ✅ | ❌ 다수 UE 필요 📄 | 공개 확인 못함 |

현재 변종 구현 목표 가운데 RRCSetupRequest 후 중단형과 RRCSetup HARQ-ACK 억제형은 p5 ZMQ 실측까지 완료했다. RRCSetupRequest 후 중단형의 지속 거부 성공은 capacity를 바꾸지 않은 실험 전용 hold 프로필 결과이며, 기본 운영값이나 차폐 OTA 결과로 일반화하지 않는다.

---

## 3. 공개 공격 코드 (5G NR)

코드가 실제로 공개된 것은 아래 4개이며 **전부 OAI 기반**이다. OCUDU(srsRAN 계열) 대상 공개 공격 코드는 찾지 못했다.

| | **5gattacks/5g-rrc-storm** | **salam-ai-learning/5g-rrc-storm-attack** | **5GSEC/OAI-5G** (`nr.attack.v2.1.0`) | **5GSEC/MobiDojo** |
|---|---|---|---|---|
| 저장소 실재 | ✅ (`main`) | ✅ (`storm_attack`) | ✅ (커밋 `b631b577`) | 📄 |
| 중단 지점 | **RRCSetupComplete 미전송형** ✅ | RRCSetupRequest 후 중단형 📄 | **NAS Authentication Response 미전송형**, Blind DoS ✅ | 5GSEC 공격 재사용 📄 |
| 기반 | OAI `92980ceb` ✅ | Firecell 계열 OAI로 추정 🔍 | OAI v2.1.0 📄 | OAI rfsim 📄 |
| 재시도 방식 | `RRCSetup` 수신 후 `attack_rach_timer` **10 ms** 뒤 재요청 ✅ | Msg3 뒤 바로 프리앰블 생성 📄 | 인증 요청 수신 후 `usleep(bts_delay)` 뒤 RA 재시작 ✅ | 📄 |
| 거절 처리 | `RRCReject`를 받아도 즉시 재요청, T302 처리 주석 처리 ✅ | 📄 | 📄 | 📄 |
| 신원 바꾸기 | OAI 기본 난수 📄 | 매번 다른 Msg3(커밋 메시지) 📄 | 레벨 5 이상이면 IMSI 1바이트가 100값 순환 ✅. 난수 시드 `srand(_ra_restart_counter+1)` 고정 ✅ | 📄 |
| 속도 노브 | ❌ 빌드 상수 ✅ | ❌ 빌드 상수 📄 | 실행 시작 인자 `--bts-attack`(레벨), `--bts-delay`(기본 188 ms) ✅ | ❌ 📄 |
| **gNB도 변경** | ⚠️ UL failure 타이머 30000/10000 → 5000/1000 ms ✅ | ⚠️ UL failure 트리거 2 → 2700 ms 📄 | 확인 안 함 | — |
| 라이선스 | **없음**. README가 private testbed 전용 명시 ✅ | OAI Public License 📄 | OAI Public License 📄 | Apache-2.0 📄 |
| 우리에게 | **RRCSetupComplete 미전송형 직접 참고(UE 쪽만)** | RRCSetupRequest 후 중단형 참고 | CLI 노브 설계 참고, NAS Authentication Response 미전송형 대조군 | 실행 환경 참고 |

**짚어 둘 점**
- **gNB 변경 동봉**: 5gattacks와 salam 패치는 피해자인 gNB의 타이머도 바꾼다. 논문 수치가 공격 효과인지 gNB 설정 효과인지 섞이므로, 우리는 **UE 쪽 변경만** 가져온다.
- **속도 노브 부재**: 실행 중에 시도율을 바꿀 수 있는 공개 도구가 없다. 탐지기를 여러 공격 강도로 시험하려면 이 노브가 필요하다.
- **5GSEC 레벨**: NR 코드의 공격 분기는 `bts_attack >= 5`일 때만 동작한다 ✅(`rrc_UE.c` 846, 1528행). 5G-Spector artifact 위키의 예시 `--bts-attack 1`이 반복 공격이 되는 방식은 VM의 `run_attack.sh`를 열어야 알 수 있다 🔍.

---

## 4. 5G 논문

### ① RRCSetupComplete 미전송형 계열: Msg5 생략을 실험한 논문 (우리와 가장 가까움)

| | **KAUST** (arXiv 2608.16441, 2026) | **StormShield** (ACM WiSec 2026) | **Nguyen 등** (IEEE ISCC 2025) |
|---|---|---|---|
| 중단 지점 | RRCSetupComplete 미전송형 ✅ | RRCSetupComplete 미전송형 📄 | RRCSetupRequest 후 중단형 📄 |
| 환경 | OAI gNB+UE, **B210 2대 OTA**, 상용폰 Nothing Phone (3a) ✅ | OAI + NVIDIA Aerial, USRP X410·Foxconn RU OTA 📄 | OAI **rfsim**, VM 📄 |
| 공격률 | 약 25 req/s ✅ | MUE당 45.7 Msg3/s 📄 | 132.07 Msg3/s (rfsim) 📄 |
| 피해 | 16 UE 한도 0.65초, 90 UE 한도 3.61초에 포화. 대기 5초. 이후 `RRCReject`, 폰 접속 실패 ✅ | 📄 | 약 150 ms 만에 불가용 📄 |
| 탐지 | 시간 창 안의 `N_Msg5 / N_Msg4` 비율이 임계 아래로 떨어지면 탐지 ✅ | (TA, RSSI) 지문, 정확도 97.6%, 106.5 ms 📄 | Msg 비율 임계(0.5), 약 90 ms 📄 |
| 대응 | 미완료 연결이 가장 많은 TA 버킷의 컨텍스트 즉시 해제, 그 버킷 신규 시도에 짧은 완료 타이머 ✅ | 차단 목록으로 reject 📄 | 탐지만 📄 |
| gNB 수정 | ⚠️ 예 (gNB RRC 내부) ✅ | ⚠️ 예 (OAI gNB·FlexRIC 확장) 📄 | 아니오 (xApp) 📄 |
| 코드 | 5gattacks ✅ | 없음 📄 | 없음 📄 |

KAUST는 **"25 × T개의 컨텍스트를 점유"**라는 식을 본문에 직접 쓴다 ✅. 쌓이는 미완료 컨텍스트 수 ≈ 시도율 × 대기 시간(Little의 법칙)이며, 우리 재현기의 시도율 노브가 이 식의 λ에 해당한다.

### ② 5G SA의 L3 공격 탐지 (NAS Authentication Response 미전송형·Blind DoS 포함)

| | **6G-XSec** (ACM HotNets 2024) | **Dayaratne 등** (arXiv 2025) |
|---|---|---|
| 공격 | 5G SA BTS DoS(인증 단계 정지), Blind DoS 등 📄 | Blind DoS. Resume·재수립으로도 가능하다고 서술 📄 |
| 환경 | OAI 5G SA CU/DU, B210, OSC RIC. F1AP·NGAP pcap → MobiFlow 📄 | 6G-XSec 데이터 증강 📄 |
| 탐지 | 오토인코더·LSTM + LLM 설명 📄 | 제로샷 LLM xApp 📄 |
| 코드 | 5GSEC/MobiWatch 📄 | 🔍 |

이 계열의 탐지 근거는 "Msg5와 등록 요청은 왔는데 인증 응답이 없다"이다. **RRCSetupComplete 미전송형은 Msg5가 오지 않으므로 이 규칙들의 대상이 아닐 것이다** 🔍. RRCSetupComplete 미전송형에는 Msg5/Msg4 비율 같은 별도 지표가 필요하다.

### ③ 그 밖의 5G 논문

| 논문 | 요약 | 우리와의 관계 | 신뢰 |
|---|---|---|---|
| **UCD 데모** (IFIP Networking 2026 Demo) | 동기화된 bash 스크립트로 srsUE 15개를 재부팅 반복(UE 재시작 반복형). XGBoost Radio IDS 99.43%, Network IDS 97.88%이며 이 값은 "prior experimental deployments"에서 나왔다고 명시 | UE 재시작 반복형 참고. 스크립트 URL은 찾지 못함 | ✅ (PDF) |
| **RAID** (arXiv 2511.14921) | Msg3를 초당 1만–5만 건 버스트. 여러 DU로 분산하면 DU에선 무해해 보이다가 F1에서 합쳐져 스톰이 된다 | UE 1대 속도로는 불가능한 규모라 범위 밖. **F1 관측 위치의 근거**로는 유용 | 📄 |
| **Beyond Static Thresholds (EVT)** (ACM MSWiM 2025) | 실제 사업자 RRC 카운터에 공격을 합성해 적응 임계 학습 | 분석기 운영자 임계 설계 참고 | 📄 |
| **Tabiban 등** (IEEE ComMag 2024) | RSS 개관. OAI 분리형이 패킷 약 2.5배, 15 UE 재부팅 시 정상 UE 재등록 지연 125초 | 배경 | 📄 |
| **Bogucka 등** (IEEE ComMag 2025) | Amarisoft OTA, TA별 KPI profile xApp으로 reject 정책 | 저속 완료 접속이 대상이라 RRCSetupComplete 미전송형 차단 근거는 아님 🔍 | 📄 |
| **Hoffmann·Kryszkiewicz** (INFOCOM WS 2023) | IIoT 시뮬레이션, TA별 KPI profile 탐지 | 탐지 아이디어 참고 | 📄 |
| **3GPP TR 33.861** (2020) | KI#5에서 반복 접속 위협을 다루지만 "no normative work is needed" 결론 | 대응이 구현에 맡겨졌다는 근거 | 📄 |

---

## 5. LTE 기반 참고 (5G 범위 밖, 계보상 필요한 것만)

| | 왜 남기나 | 주의 |
|---|---|---|
| **LTEFuzz** (IEEE S&P 2019) | "BTS resource depletion"이라는 이름과 NAS Authentication Response 미전송형 공격을 처음 정의. 약 20/s 📄 | LTE, 상용 펨토셀 |
| **5G-Spector** (NDSS 2024) | 탐지기(MobiFlow + MobieXpert P-BEST)와 공격 포크의 출처. 팀 3단계 "P-BEST"의 원류 | 논문 평가와 artifact VM은 **LTE**(OAI 2023.w23) ✅. 공격 포크에는 NR 브랜치도 있다(§3) ✅ |
| **Buckler** (arXiv 2026) | eBPF로 vRAN에 핫픽스를 넣는 방식. 우리 eBPF 관측과 접근이 가깝다 | 실험은 **LTE 설정** 📄. 규칙이 `SetupComplete` 이후를 보므로 RRCSetupComplete 미전송형은 대상이 아님 🔍 |

2026-10-16 재검색에서 3G/LTE 시그널링 DoS 논문(Qian NDSS 2012, Gorbil·Gelenbe SECRYPT 2015, Escudero-Andreu 2019)도 나왔지만, 5G 기준이 아니고 메커니즘(데이터 트래픽으로 RRC 상태 전환 유발)도 RRCSetupComplete 미전송형과 달라 넣지 않았다.

---

## 6. 빠진 자료가 없는가

rss-landscape.md는 초판 검색어를 기록하지 않았다고 스스로 밝힌다(§2.1). 그래서 2026-10-16에 아래 검색어로 독립 재검색했다.

- `RRC signaling storm attack 5G gNB incomplete RRC connection detection paper`
- `5G RRC connection exhaustion DoS attack RRCSetupComplete malicious UE OpenAirInterface srsRAN`
- `github RRC flooding attack 5G UE srsUE OAI storm/flood/exhaustion attack tool`
- `O-RAN xApp L3 attack detection 2025 2026 MobiWatch/SPOTLIGHT/signaling storm dataset RRC`

**결과**: 5G 대상 논문은 KAUST, StormShield, Nguyen, EVT, RAID, UCD 데모가 나왔고 **모두 이미 수록돼 있었다**. 5G NR 대상 공격 코드도 새로 나온 것이 없었다. 따라서 "주요 검색 경로에서 추가로 나온 5G 단일 UE 공격 연구·도구는 없다"까지 말할 수 있고, "이것이 전부다"라고 말할 수는 없다.

---

## 7. 비교 결론

| 기존 연구·도구의 상태 | 우리 재현기의 위치 |
|---|---|
| RRCSetupComplete 미전송형 공개 코드는 5gattacks 하나이고, 재시도가 10 ms 빌드 상수다 ✅ | **시도율·완료율·identity 정책을 조절할 수 있는 RRCSetupComplete 미전송형 재현기** |
| 공개 공격 코드는 전부 OAI 대상이다 | **OCUDU 대상** 검증 (효과는 미확인 🔍) |
| 공개 패치가 gNB 타이머도 함께 바꾼다 ✅ | **UE만 변조**, gNB 무수정 |
| RRCSetupComplete 미전송형 탐지·대응 논문(KAUST ✅, StormShield 📄)은 gNB를 수정한다 | 무수정 gNB + eBPF 관측 (팀 전체 차별점) |
| NAS Authentication Response 미전송형 계열 탐지 규칙은 Msg5 이후를 본다 | RRCSetupComplete 미전송형 전용 지표 필요 → 계측팀의 "RRC 요청 지표 vs 완료 지표" |

### 아직 확인하지 않은 것 (우선순위순)
1. OCUDU에서 RRCSetupComplete 미전송형이 실제로 컨텍스트를 쌓는지, 대기 시간 실제값 🔍
2. StormShield·Nguyen 수치 (arXiv 접속 가능한 환경에서 재확인) 📄
3. 5G-Spector VM의 `run_attack.sh`와 `--bts-attack 1`의 반복 방식 🔍
4. 5gattacks 저작자의 재사용 허가 (라이선스 없음) ✅

---

## 8. 내 판단

<!-- TODO(human): 위 비교를 보고, 우리 재현기의 베이스를 무엇으로 정할지와 그 이유를 2~3문장으로 쓴다. -->
