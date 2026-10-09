# RRC Signaling Storm 재현 도구 — 공개 도구 조사

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-10-08 |
| 목적 | RRC 시그널링 스톰 **재현(공격) 도구**를 자작하기 전, 기존 공개물로 대체·포크 가능한지 확인 |
| 조사 방법 | 웹 검색 + arxiv/IFIP PDF 원문 추출 + GitHub API로 리포 내용·출처 직접 열람(실행 없음) |
| 결론 | 턴키 공격 코드는 **계열 A(5gattacks, OAI) 하나뿐**. 계열 B(UCD NetsLab, srsRAN)는 **공격 코드 미공개, 데이터셋만 공개** |

---

## 계열 A — 단일 UE 고속 OTA (OAI)

**리포: https://github.com/5gattacks/5g-rrc-storm**

- **출처(신뢰 핵심)**: arxiv [2608.16441](https://arxiv.org/abs/2608.16441) *"Experimental Validation and Mitigation of RRC Storm Attacks in 5G Cellular Networks"* (Abou Hasna, El Falou — KAUST)의 **참고문헌 [12]로 저자 본인이 직접 인용**한 공식 아티팩트. 익명 리포 아님.
- **플랫폼**: OAI nrUE(공격) + OAI gNB(완화). 실측 테스트베드 = Dell Precision 3660 / Ubuntu 24.04 / **USRP B210 2대**.
- **내용물**: 전부 텍스트(바이너리 0). `storm-attack.patch`(14KB)·`storm-mitigation.patch`(23KB), 셸 스크립트, Node/React NMS 대시보드, docker-compose.
  - `*-rfsim.sh` 스크립트 존재 → **SDR·차폐박스 없이 OAI RF 시뮬레이터로 먼저 전 과정 검증 가능**(리스크 저감).
- **공격 패치가 실제로 건드리는 곳**(diff 확인):
  - UE 측: `openair2/RRC/NR_UE/rrc_timers_and_constants.c`, `rrc_UE.c`, `rrc_defs.h`, `openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c` → `attack_rach_timer` 신설, **T300 만료 시 즉시 RACH 재시작** 루프(`handle_t300_expiry`).
  - gNB 측: `gNB_scheduler_RA.c`, `gNB_scheduler_primitives.c` 등도 수정(관측·로깅으로 보임) → **적용 전 두 patch를 읽고 UE-only / gNB 변경을 분리할 것**.
- **신뢰 판정**: 출처·내용 모두 신뢰 가능. 위험 신호 없음.
- **주의점(보안 아님, 실무)**:
  - **라이선스 없음** → 기본값 all-rights-reserved. 포크·재배포 전 저자에게 허가/인용 확인 권장.
  - 0 stars·단독 저자·CI 없음·**특정 OAI 커밋에 라인 단위 고정** → 직접 버전 맞춤·디버깅 각오.
  - README가 "private testbed 전용" 명시 → 차폐 랩 사용과 부합.

---

## 계열 B — 다수 UE ZMQ 가상 RF (srsRAN)

**논문: IFIP Networking 2026 Demo — "Attack Execution and Multi-Layer xApp-based Intrusion Detection in an O-RAN Environment"** (Farah Abed Zadeh, Siniarski, Shen Wang, Liyanage — **UCD NetsLab**)

- **플랫폼**: srsRAN Project gNB + **srsUE** + Open5GS + FlexRIC + **GNU Radio ZeroMQ 멀티플렉서**(다수 UE를 단일 gNB ZMQ 포트에 다중화). 공격 = 다수 srsUE가 PRACH·RRCSetupRequest 폭주.
- **공개물 조사 결과 — 공격 코드 미공개**:
  | 공개 위치 | 실제 내용 | 공격 도구? |
  |---|---|---|
  | [github.com/NetsLab-Demo/armor](https://github.com/NetsLab-Demo) | AI 취약점 스캐너 IDS **데이터셋 노트북** | ❌ |
  | NetsLab-Demo/…5G-ORAN-IDD | 5G O-RAN 침입탐지 **데이터셋** + 분석 노트북(.db는 빈 placeholder) | ❌ |
  | [Kaggle: rrc-signalling-storm-dataset](https://www.kaggle.com/datasets/farahabedzadeh/rrc-signalling-storm-dataset-5g-o-ran-testbed) | 스톰 **트래픽 데이터셋** | ❌ |
  | [netslab.ucd.ie/?p=6218](https://netslab.ucd.ie/?p=6218) | 위 데이터셋 안내 페이지 | ❌ |
- 논문은 "attack scripts·UE config·ZMQ mux·xApp 제공"을 **기여로 선언만** 하고 URL이 없음. 공개 창구를 전부 확인했으나 코드 없음 → **받으려면 저자(madhusanka@ucd.ie) 직접 요청**.
- **데이터셋은 쓸모 있음**: 탐지팀 선학습·검증용, UE팀에는 "정상 스톰 트래픽 형태" 참조 ground truth. (연관 논문: *RadioShield: A PHY-Layer Defense Framework for RRC Signaling Storms in O-RAN*.)

---

## 계열 B를 직접 조립할 때 쓸 srsRAN + ZMQ 다수-UE 뼈대 (공개)

공격 코드는 없어도 가상 RF 다수-UE 환경 자체는 조각으로 재현 가능. 스톰 변조만 얹으면 됨.

| 리포 | 쓸모 |
|---|---|
| [b-akhil-reddy/5G-RAN-srsRAN-Open5gs](https://github.com/b-akhil-reddy/5G-RAN-srsRAN-Open5gs) | srsRAN+Open5GS ZMQ 구동, CSV로 다수 UE |
| [gckopper/5G-testbed](https://github.com/gckopper/5G-testbed) | srsUE + ZMQ 가상 라디오, USRP 2대 겸용 |
| [s5uishida/open5gs_5gc_srsran_sample_config](https://github.com/s5uishida/open5gs_5gc_srsran_sample_config) | 5GC+srsRAN ZMQ 표준 설정 |
| [usnistgov/O-RAN-Testbed-Automation](https://github.com/usnistgov/O-RAN-Testbed-Automation) | Open5GS+srsRAN+FlexRIC 자동 배포 |

---

## 기타 관련(참고만)

| 자료 | 성격 | 관련도 |
|---|---|---|
| [2504.15738](https://arxiv.org/html/2504.15738v1) RRC Signaling Storm Detection in O-RAN | OAI nrUE 변조(T300 무시·Msg5 생략, ~132 Msg3/s). **의사코드만, 코드 미공개** | 방법론 레퍼런스 |
| [2605.14032](https://arxiv.org/pdf/2605.14032) StormShield | 지문(TA/RSSI)+DBSCAN 탐지. 식별자 회전 회피 모델 근거. 공격코드 공개 불명 | 탐지측 레퍼런스 |
| [5G-UE-SecurityTesting](https://github.com/vaggelis-sudo/5G-UE-SecurityTesting) | srsRAN+Open5GS UE 보안 테스트 하네스(NAS/RRC). 스톰 전용 아님 | 구조 참고 |
| [5ghoul](https://github.com/asset-group/5ghoul-5g-nr-attacks) | 변조 gNB→UE 퍼징. **방향 반대** | 낮음 |

---

## 탐지·방어측 핵심 레퍼런스 — 내 재현기가 검증할 대상 (2026-10 추가)

공격 도구가 아니라, 내 스톰이 "밀어봐야 할" 탐지기·팀이 지으려는 방어 구조의 1차 출처. 내 노브(식별자 회전·완료율·rate) 설계와 라벨 포맷이 전부 여기서 역산된다.

| 자료 | 성격 | 내 도구 관점 관련도 |
|---|---|---|
| **RAID** — [arxiv 2511.14921](https://arxiv.org/abs/2511.14921) (2025-11, Waterloo) | Tofino 스위치에 Random Forest 심어 **3.4µs**에 RA 요청 in-network 필터 | 내 스톰을 **정면 탐지**하는 최신 방어기. 노브가 이 초저지연 분류기도 밀어볼 수 있어야. **팀 "near-RT RIC가 답" 차별성에 대한 지연 반론** → 팀 공유 필수 |
| **5G-SPECTOR** — [NDSS'24 PDF](https://www.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf) (MobieXpert/MobiFlow 원전) | L3 공격 탐지 xApp. UE↔RAN 셋업 메시지의 상태·식별자·타이머 추적 | 탐지기가 **정확히 어떤 신호를 읽는지**의 정답지 → 내가 통제해야 할 변조 지점 역산 |
| **Jamming→OCUDU** — [arxiv 2609.18499](https://arxiv.org/abs/2609.18499) (MILCOM'26) | **동일 OCUDU** gNB, E2로 BLER 읽어 xApp가 MCS 제어 폐루프, POWDER OTA | 공격종류만 다름(재밍). OCUDU에서 **E2로 실제 뽑히는 지표·내릴 수 있는 대응**의 레퍼런스 구현 |
| **TeleRAN** — [NDSS FutureG'26 PDF](https://www.ndss-symposium.org/wp-content/uploads/futureg26-40.pdf) | eBPF 커널 필터 + ASN.1 user-space 파서로 메시지 수준 텔레메트리 | 프로젝트 전체 토대. **메시지 수준 텔레메트리가 뭘 보는지 = 내 스톰이 남기는 흔적** |
| **MobiFlow** — [ACM 2022](https://dl.acm.org/doi/pdf/10.1145/3565474.3569070) | NetFlow식 셀룰러 텔레메트리 스트림(탐지기 아님) | "MobiFlow=구조, 탐지는 MobieXpert" 정정의 근거. 라벨/특징 포맷 참고 |

> 넓히기(related-work 채우기용): [IDS in Open RAN 서베이](https://www.researchgate.net/publication/381137844_A_Survey_for_Intrusion_Detection_Systems_in_Open_RAN), [Cross-Layer 융합 탐지 2606.22450](https://arxiv.org/abs/2606.22450), [Open-RAN 이상탐지 테스트베드 2503.10255](https://arxiv.org/abs/2503.10255), [6G-XSec HotNets'24](https://conferences.sigcomm.org/hotnets/2024/papers/hotnets24-198.pdf).

---

## 도구 선택에 주는 결론

1. **턴키는 계열 A뿐** → 1차 bring-up은 5gattacks를 **rfsim으로** 먼저 돌려 공격 동작 자체를 확인.
2. **우리 gNB는 OCUDU(srsRAN)** → 두 경로:
   - **(빠름)** 5gattacks OAI-nrUE 공격기를 OCUDU에 OTA. 변수 = OAI-UE ↔ srsRAN-gNB **interop 마찰**.
   - **(스택일치)** 5gattacks UE 측 핵심(`attack_rach_timer`+T300 훅+Msg5 억제)을 **srsUE로 포팅**. interop 유리, 포팅 품 듦.
3. 선택은 **interop 스모크 테스트**(정상 UE가 OCUDU에 붙나) 결과로 가름 → [methodology.md](methodology.md), [AGENTS.md](AGENTS.md) 참조.

---

## 읽기 순서 (제로베이스, 2026-10)

처음 들어온 사람이 "이 공격·내 도구·검증 대상"을 가장 빨리 잡는 경로. 🔵정독 / ⚪훑기.

**지금 당장 첫 논문 = [sources/2608.16441 (KAUST)](sources/2608.16441_Experimental-Validation-RRC-Storm_OAI_KAUST.pdf).** 내 도구(5gattacks)의 원전, PDF 보유, RACH 기초(§II)부터 실측(§VI)까지 자체완결. 뽑을 것: §II–III 메커니즘 / §V 테스트베드(OAI·B210·rfsim) / §VI 단일 UE로 캡16·90 고갈(0.65s·3.61s, ~25 req/s).

| 단계 | 자료 | 깊이 |
|---|---|---|
| 0 | [AGENTS.md](AGENTS.md) → [methodology.md](methodology.md) §1~2 → [tool-survey.md](tool-survey.md) (내부 문서로 그림) | ⚪ |
| 1 | **2608.16441 KAUST**(첫 논문) → [2504.15738](https://arxiv.org/html/2504.15738v1)(공격+탐지 R1/R2) → `sources/5gattacks_storm-attack.patch`(실코드) | 🔵 |
| 2 | 탐지측: [5G-SPECTOR NDSS'24](https://www.ndss-symposium.org/wp-content/uploads/2024-527-paper.pdf) → StormShield [2605.14032](https://arxiv.org/abs/2605.14032) → RAID [2511.14921](https://arxiv.org/abs/2511.14921) | ⚪ |
| 3 | 팀 토대: [TeleRAN](https://www.ndss-symposium.org/wp-content/uploads/futureg26-40.pdf) → [MobiFlow](https://dl.acm.org/doi/pdf/10.1145/3565474.3569070) → [Jamming→OCUDU 2609.18499](https://arxiv.org/abs/2609.18499) | ⚪ |
| 4 | 이론·변종: [methodology.md §6](methodology.md) 참조(Little/Erlang/RFC4987, 세대차이, 변종표) | ⚪ |

- **3G Gelenbe 논문(ICC2014/TETC2016)은 지금 읽지 말 것.** 원리는 §6.1에 λ·T로 이미 추출됨. 3G 상태기계(DCH 승격)는 우리 5G half-open 변종과 **다른 메커니즘**이라 혼동만. → **논문 집필 때 related-work 인용용으로만** 모델 섹션 스킴.
- 최단 경로: **0→1단계**면 서브태스크 착수 충분. 2~3은 노브·라벨 설계 전, 4는 집필 때.
