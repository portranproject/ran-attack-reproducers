# RRC Signaling Storm — 공격 메커니즘·재현 명세

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-10-08 |
| 범위 | 공격자 UE 관점. 프로토콜 메커니즘 + 재현 도구가 가져야 할 변조 지점·파라미터 |
| 근거 | arxiv 2504.15738, 2605.14032(StormShield), 2608.16441(+ 5gattacks 패치 실측), 팀 조사 docs |

---

## 1. 메커니즘 — 왜 자원이 묶이나

5G 접속은 Random Access + RRC 4-way:

```
UE                                   gNB
 │── Msg1 (PRACH preamble) ─────────▶│
 │◀─ Msg2 (RAR, TC-RNTI 할당) ────────│
 │── Msg3 (RRCSetupRequest) ─────────▶│  ← gNB가 여기서 UE 컨텍스트·무선자원 할당, 완료 대기 타이머 시작
 │◀─ Msg4 (RRCSetup, ContentionRes) ──│
 │── Msg5 (RRCSetupComplete) ────────▶│  ← 정상 UE는 여기서 연결 완성
```

**스톰의 핵심 = Msg5를 의도적으로 생략.** gNB는 Msg3 시점에 이미 자원을 잡고 Msg5를 기다림 → Msg5가 안 오면 타이머 만료까지 "half-open" 상태로 묶임. 타이머 만료 속도보다 빠르게 쌓으면 최대 연결 수 고갈 → 정상 UE 접속 불가. **SYN flood의 셀룰러 버전.**

### 보고된 고갈 속도(설정 의존, 참고)
| 수치 | 출처 |
|---|---|
| 단일 변조 UE ~132 Msg3/s (7ms 프레임당 1개) | 2504.15738 |
| 1 MUE·45.7 Msg3/s에서 gNB 컨텍스트 ~326ms 만에 고갈 | StormShield 2605.14032 |
| **공격자 UE 1대**·~25 req/s·대기 5s → ~125 동시 half-open. gNB 캡 **16→0.65s**, **90→3.61s**에 완전 고갈(RRCReject)→실폰 DoS 입증 | 2608.16441 |

> ⚠ **"90 UE" 오독 주의**: 2608.16441의 90은 *공격자 수*가 아니라 *gNB가 설정한 최대 UE 수용량*(= 고갈 대상 캡). **공격자는 OAI UE 1대.** OAI 기본 softmodem은 모놀리식(CU/DU 미분리)이라 그 캡 = gNB 단일 컨텍스트 풀.

---

## 2. 변조 지점 (5gattacks 패치로 확인된 실제 구현)

개념 "2곳"은 실제론 **코어 개입 3 + 드라이버**:

0. **Msg4 수신 + 하위계층 HARQ ack은 유지** — 2608.16441 §V 명시: Msg1~3만 돌리고 Msg4를 무시하면 gNB가 temp 컨텍스트를 금방 풀어 **half-open이 안 쌓임**. Msg4(ContentionRes)를 받고 **HARQ ack까지 해야** 지속 컨텍스트가 할당됨. → 재현기는 "Msg1~4+ack 후 Msg5만 생략"이 정확(CLAUDE.md의 "Msg1~3 수행"은 부정확).
1. **Msg5 억제** — RRCSetupComplete 전송 지점을 막음.
2. **T300 + T302 무력화** — T300 만료 시 포기·백오프 무시(재시작용). 추가로 gNB가 과부하로 **RRCReject**를 쏘면 정상 UE는 **T302** 걸고 재시도 중단하는데, 그것도 비활성화해야 고갈 상태가 유지됨(2608.16441).
3. **RA 재트리거 드라이버 루프** — 5gattacks는 `attack_rach_timer`를 신설하고 **T300 만료를 즉시 RACH 재시작으로 연결**(`handle_t300_expiry`). 목표 rate로 반복. OTA에선 Msg4 ack 전송 여유를 위해 **재시작 직전 짧은 타이머** 추가(즉시 재시작은 하위계층 미처리로 불안정).
   - 건드린 파일: UE 측 `rrc_timers_and_constants.c`, `rrc_UE.c`, `rrc_defs.h`, `nr_ra_procedures.c`.

전부 **UE 측**. gNB(= 우리 OCUDU)는 공격을 위해 건드릴 필요 없음 → 팀 "기지국 무수정" 원칙과 부합.

### srsUE로 포팅 시 대응 지점(개념)
- RRC 연결 완료 콜백 직전에서 Msg5 송신 억제.
- T300 타이머 만료 핸들러를 재시작 루프로 치환.
- rate 노브를 거는 타이머 1개 추가.
→ 상세 파일 매핑은 interop 테스트 후 `storm-attack.patch`를 줄 단위로 떠서 작성(미완).

---

## 3. 재현 도구가 노출해야 할 파라미터(노브)

단순 DoS가 아니라 **탐지기를 평가**하는 재현기가 목적 → 통제 가능해야 함.

| 노브 | 용도 |
|---|---|
| **요청률** (Msg3/s) | 저~고강도 스윕. 탐지 지연·임계 보정 |
| **완료율 주입** (0~100% Msg5 전송) | R1/R2를 중간값으로 → 임계 0.5 부근 민감도 시험 |
| **식별자 회전 on/off** (매 RA 새로 시작) | 쉬운 케이스(임계로 잡힘) vs 어려운 케이스(지문 필요) 구분. StormShield 회피 모델 재현 |
| **버스트/지속·램프업** | 시간 패턴 변주 |
| **정상 고부하 대조군** (Msg5까지 완성하는 다수 정상 접속) | 탐지기가 "공격 vs 붐비는 셀"을 구분하는지. **필수** — R2가 공격 시 0, 고부하 시 1 근처로 갈리는 지점 |

이 노브들이 곧 탐지팀 평가 데이터셋 라벨(공격/정상/고부하·강도·식별자패턴)이 됨.

### 식별자(RNTI) 주의
- TC-RNTI는 gNB가 Msg2에서 부여 → 공격자가 못 고름.
- **매 RA를 새로 시작하면 RNTI가 자연히 회전**, 연결 재시도면 고정. 이 차이가 지문 탐지 필요성을 가름.

---

## 4. 탐지측 특징(공격기가 만들어야 할 신호의 반대편)

재현 품질 판단용으로 알아둘 것:
- **R1 = Msg5/Msg3, R2 = Msg5/Msg4**, 임계 **0.5**, 625ms(또는 ~1025ms) 윈도, ~90ms 탐지 (2504.15738).
- StormShield: TA·RSSI 물리 지문 + DBSCAN 군집 + 동적 블록리스트.
- → 공격기가 **완료율·식별자 회전**을 조절할 수 있어야 이 탐지기들을 제대로 밀어볼 수 있음.

---

## 5. 성립 전제 — OCUDU에서 실제로 먹히는지

**OCUDU = srsRAN Project 리브랜드**(BSD-3로 Linux Foundation 이관, OCUDU 26.04). → 타이머·한도를 srsRAN_Project 소스/config로 직접 확인 가능.

### 5.1 half-open 타이머 — 소스에서 확정 (2026-10)
파일 `lib/rrc/ue/procedures/rrc_setup_procedure.cpp`:
```cpp
procedure_timeout = context.cell.timers.t300 + context.cfg.rrc_procedure_guard_time_ms;
transaction = event_mng.transactions.create_transaction(procedure_timeout);
send_rrc_setup();              // Msg4
CORO_AWAIT(transaction);       // Msg5(RRCSetupComplete) 대기
// timeout → rrc_ue.on_ue_release_required(cause_protocol_t::unspecified)  // 컨텍스트 해제
```
- **half-open 컨텍스트 수명 = gNB측 t300 + rrc_procedure_guard_time_ms.** 만료 시 UE 컨텍스트 자동 해제 → 고갈은 "영구"가 아니라 **"유지하려면 계속 밀어야" 하는 steady-state**.
- 기본값: t300 **1000ms**(허용 100·200·300·400·600·1000·1500·2000), rrc_procedure_guard_time_ms **1000ms**(config_ref; 소스 구조체 리터럴은 `{500}` → 로드되는 값 확인). ⇒ **기본 수명 ≈ 2000ms.**
- 이게 §1의 "완료 대기 타이머"의 실체. "PDU 세션 3초 / inactivity 5초"는 **등록 이후 타이머라 무관**(확인됨).

### 5.2 고갈 성립 — 자원·설정 의존 (⚠ 정정)
한 RA 사이클이 묶는 자원이 층마다 다르고, 바인딩 상한은 config에 달림:

| 자원 | 위치 | 수명 | 단일 UE로 고갈? |
|---|---|---|---|
| PRACH CB 프리앰블(~64/RO) | DU/PHY | 순간(RO당) | ✗ 충돌은 **동시 다수 UE** 필요. 단일은 부하만 |
| 스케줄러 grant(PDCCH/PUSCH) + 메시지 처리 | DU/MAC | 짧음(사이클당) | △ rate 의존, 단독으론 거의 거부 안 남 |
| **UE 컨텍스트 슬롯 = RNTI + DU UE + CU-CP UE**(F1 양단 동시 점유) | DU 스케줄러 캡 **∧** CU-CP | ≈ 2s | **캡에 달림**(아래) |

- 컨텍스트 바인딩 상한 = **min(DU 스케줄러 max-UE, `cu_cp.max_nof_ues`)**. `max_nof_ues` 기본 8192는 CU-CP 테이블값일 뿐 — **실제 병목은 더 작은 DU 스케줄러 max-UE**(랩 config 보통 32·64·128·256, "128 초과 미검증").
- 단일 변조 UE 정상상태 ≈ rate × 수명(RA 재시작마다 새 TC-RNTI→새 컨텍스트, gNB는 동일 UE인지 모름). 측정 rate: **25/s**(2608.16441, OAI) ~ **132/s**(2504.15738). 수명: OAI **5s** / OCUDU 기본 **~2s** → 대략 **수십~수백 동시 half-open**.
  - **KAUST 실증(2608.16441): 공격자 1대로** gNB 캡 16→**0.65s**, 90→**3.61s** 완전 고갈(~25/s × 5s ≈ 125 > 캡). **작은 캡이면 단일 UE로 충분.**
  - 캡이 CU-CP `max_nof_ues` 8192처럼 크면 단일로 불가(≈ **4096/s → 다수 UE**). UCD가 다수-UE mux를 쓴 건 그 방식 선택(대규모·라벨 다양성)이지 단일이 원천 불가라서가 아님.

**타겟 층 — 단일/다중 공통 (CU 용어 주의):**
- RSS는 **RRC 공격** → half-open 컨텍스트는 **CU-CP**(제어평면) 자원이 본질. **매 사이클 DU 하위계층(RA/스케줄러/RNTI)도 공동 부하**.
- **CU = CU-CP**(제어평면·RRC·half-open = **타겟**) **+ CU-UP**(사용자평면·PDCP/GTP-U = **제외**). "RSS가 CU를 친다" = **CU-CP를 친다**가 정확.
- **CU-UP·코어(AMF)는 구조적 제외** — Msg5 생략 → NGAP InitialUEMessage 미발생(등록·PDU 세션 이전). **다수 UE로도 불가.**
- ⇒ **UE 수는 속도·먼저 포화되는 캡만 바꿀 뿐, 타겟 층(CU-CP + DU)은 안 바뀜.**
- ⇒ "단일 vs 다수"는 별개 공격이 아니라 **바인딩 자원 크기 차이**. 재현기는 목표 자원·캡을 노브로 명시하고, **실측(5.3-3)으로 수명·캡 확정 후 rate 산정**.

### 5.3 남은 확인 (당신 OCUDU 박스에서)
1. 로드된 `gnb.yaml`의 실제 값: **t300 · rrc_procedure_guard_time_ms · max_nof_ues**.
2. 더 낮은 병목 후보: DU/cell 단 UE 상한, PRACH occasion 수, TC/C-RNTI 풀 크기.
3. **실측 ground truth**: 변조 UE 1대로 Msg4만 받고 Msg5 생략 → gNB 로그에서 *RRC Setup 송신~release* 간격 측정(= 실제 수명). 그 값으로 5.2 rate 재산정.

---

## 6. 이론 근거 · RSS 변종 지형 (2026-10 추가)

### 6.1 이론 계보 — "왜 터지나"의 수식
- **원전(큐잉/마르코프)**: Abdelrahman & Gelenbe, "Signalling Storms in 3G Mobile Networks" ([ICC 2014, arXiv 1405.2735](https://arxiv.org/pdf/1405.2735)) — 단일 UE 시그널링을 **마르코프 체인**으로, 최악부하 파라미터 도출. / Gorbil·Abdelrahman·Pavloski·Gelenbe, "Modeling and Analysis of RRC-Based Signalling Storms in 3G Networks" ([IEEE TETC 2016](https://www.researchgate.net/publication/273166586)) — RRC를 **개/폐 큐잉망**으로, 제어·사용자평면 혼잡 예측. "DDoS와 달리 **제어평면 직격**".
- **우리 변종(half-open)의 정확한 수학**: 유한 용량 손실계. 점유 = λ·T (**Little's law** — KAUST "25×T"가 이것). 캡 초과 시 차단 = **Erlang-B / M·M·c·c**. 공격 원형 = **TCP SYN flood** ([RFC 4987](https://www.rfc-editor.org/rfc/rfc4987)).
- **O-RAN 착지**: Tabiban et al., "Signaling Storm in O-RAN" ([IEEE Comm Mag 2023](https://rboutaba.cs.uwaterloo.ca/Papers/Journals/2023/TabibanCommMag23.pdf)).

### 6.2 세대 차이 — 3G 이론을 5G에 그대로 쓰면 안 되는 이유 ⚠
Gelenbe 이론은 **3G/4G RRC 상태기계** 기반. 원리(제어평면 고갈·큐잉 모델)는 전이되지만 메커니즘·비용구조가 다름:

| 세대 | RRC 상태 | 스톰 주 메커니즘 | 전이 비용 |
|---|---|---|---|
| 3G(UMTS) | IDLE·PCH·FACH·DCH (4) | **강제 승격**(트래픽 주입→DCH), 타이머 강등 | IDLE→DCH ~23 msg (비쌈) |
| 4G(LTE) | IDLE·CONNECTED (2) | 연결 setup/release 반복 | 재establish ~7 msg |
| **5G(NR)** | IDLE·**INACTIVE**·CONNECTED (3) | **setup flood(half-open) 주력** + INACTIVE resume 저가 반복 | resume ~3 msg (쌈) |

- 5G 신규 표면: ① **RRC_INACTIVE**(컨텍스트 보존, RRCResume가 Msg3로 올라감 → 저가 재진입 = 새 변종), ② **CU/DU/RU 분리**(F1/E1/E2가 새 스톰 표적), ③ 2-step RACH·빔/SSB·슬라이싱.
- **우리 RSS = 초기접속 half-open 변종** — 전 세대 공통이나 5G 분리형에선 CU-CP+DU 동시 점유(§5.2).
- 5G 전용 이론: Gelenbe 그룹 "[Mitigating Signalling Storms in 5G](https://www.researchgate.net/publication/384069206)"(5G판 timeout 모델) / 변종 "[Detection of RRC inactivity timer based signalling storm attack on 5G and B5G](https://www.sciencedirect.com/science/article/pii/S1389128626002987)"(Computer Networks 2026).

### 6.3 RSS 변종 지형 — 우리 위치 (정식 taxonomy 논문 없음; Ettiane 2021/Tabiban 2023이 최근접)

| # | 변종 | 메커니즘 | 주 타겟 | 우리와 관계 |
|---|---|---|---|---|
| 1 | RACH/PRACH flood | Msg1·무효 프리앰블 폭주 | DU/PHY | 다중-UE 노브로 인접 |
| **2** | **RRC setup storm (half-open)** | **Msg3+Msg5 생략, RNTI 회전** | **CU-CP(+DU)** | ★ **우리 재현기** |
| 3 | RRC state-cycling | setup/release·승강 반복 | 제어평면 | Gelenbe 3G/4G 이론 대상 |
| 4 | RRC_INACTIVE / Resume storm | RRCResume·inactivity 타이머 조작 | CU-CP | 5G 신규. 노브 확장 후보 |
| 5 | Identity-abuse | 도청 5G-TMSI로 위조 setup→피해자 보안컨텍스트 drop | CU-CP/코어 | 식별자 회전 노브와 연결 |
| 6 | Registration/NAS storm | 다수 등록 폭주 | **AMF/코어** | 범위 밖(Msg5 완성 필요) |
| 7 | Paging storm | 저율 다수 페이징 유발 | 공유 무선자원 | 범위 밖 |
| 8 | O-RAN 고유 | E2 구독 flood·eCPRI 주입·RU 교란 | RIC/FH/RU | 팀 방어 설계 참고 |

참고 서지: Ettiane et al. "Toward securing the control plane of 5G... DoS" ([JISA 2021](https://www.sciencedirect.com/science/article/abs/pii/S2214212621001587)) / "Investigating Security Vulnerabilities in 5G Control and User Planes" ([MDPI 2025](https://www.mdpi.com/2624-800X/6/1/37)) / "From Description to Detection: LLM-based Blind DoS Detection" ([arXiv 2510.06530](https://arxiv.org/pdf/2510.06530)) / "Beyond Static Thresholds: Adaptive RRC Storm Detection with EVT" ([arXiv 2511.01391](https://arxiv.org/pdf/2511.01391)).
