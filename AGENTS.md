# AGENTS.md — RRC Signaling Storm 재현 도구 (RAN 보안 테스트베드)

> 이 디렉토리에서 작업하는 에이전트/팀원용 컨텍스트. 처음 들어오면 이 파일부터 읽을 것.
> 최종 갱신 2026-10-08.

## 이 디렉토리는 무엇인가

팀의 **O-RAN 기지국 침입 탐지·대응(IDS/IPS) 테스트베드** 프로젝트 중,
**"외부자 UE(공격자) 측 — RRC signaling storm 재현 도구 제작"** 서브태스크의 조사·설계 기록.
사용자(이 저장소 주인)가 맡은 역할이 바로 이 UE 공격 도구 부분이다.

- [tool-survey.md](tool-survey.md) — 공개 도구 조사(계열 A/B, 신뢰성 평가, 데이터셋)
- [methodology.md](methodology.md) — 공격 메커니즘·변조 지점·파라미터 명세
- [sources/](sources/) — 1차 자료 원본(논문 PDF 2건, 5gattacks 공격 패치)

관련 배경 자료(팀 전체 설계·조사)는 사용자의 별도 반입 자료(`RAN/` zip: 설계분석·요약·공격표 57건·소스코드 레퍼런스)에 있으며 이 디렉토리에는 미포함.

---

## 팀 프로젝트 (전체 그림)

**주제**: 상용 vRAN의 벤더 종속(클로즈드) CU를 전제로, 기지국 소스 수정 없이 **TeleRAN식 eBPF 텔레메트리 프록시** 위에서 near-RT RIC 기반 **탐지→대응 폐루프**를 만든다. 3-노트북 RF 차폐 테스트베드로 검증.

- **차별성**: eBPF 텔레메트리 자체가 아니라(그건 TeleRAN이 이미 함) **그 방법론 위에 탐지·대응 솔루션을 완성**하는 것. TeleRAN §IV는 "가능성"만, 5GSEC 계열은 "대응 없음". 우리는 실제 공격 재현→탐지→대응→정량평가.
- **스택**: gNB = **OCUDU**(srsRAN 기반). RIC = OSC/FlexRIC(미확정). 코어 = 미확정(Open5GS 등).
- **구성**: 노트북C(공격자 UE) ─RF차폐─ 노트북B(O-DU) ─F1(IP)─ 노트북A(O-CU+RIC+eBPF+대응).

### 대화에서 정리된 핵심 사실(정정 포함)
- **MobiFlow는 탐지기가 아님** — 텔레메트리 구조화 프레임워크. 탐지는 MobieXpert(규칙)/MobiWatch(DL).
- 부족한 건 KPM(카운터)이 아니라 **메시지 수준 텔레메트리**. 표준 E2SM-**RC REPORT**에는 있으나 **OCUDU 미구현**(OAI엔 있음). eBPF는 "CU를 못 고친다(상용 블랙박스)"는 전제에서 정당화됨.
- **대응 딜레마**: 표준 E2로 내릴 실효 대응이 좁음(DU 빼면 사실상 없음, Style 4 미구현). "표준·무수정·실효대응" 셋 중 둘만. 현실적 선택 = 무수정 + (벤더 관리 API 어댑터/코어) 대응.

---

## 내 서브태스크: RRC signaling storm 재현 도구

**목표**: RF 차폐 랩에서 팀 OCUDU gNB를 상대로, 팀 탐지·대응기를 **검증**할 수 있는 통제 가능한 스톰 재현기.
→ "강한 공격"이 아니라 **"파라미터가 통제되는 재현기"**가 설계 목표.

### 확정/파악된 것
- 공격 메커니즘 명확(**Msg1~4 수행 + Msg4 HARQ ack**, **Msg5 생략**, **T300+T302 무력화** + RA 재시작 루프). → [methodology.md](methodology.md) §2
  - ⚠ 정정(2026-10, 2608.16441 §V 실측): Msg1~3만으론 컨텍스트 안 쌓임(gNB가 temp 컨텍스트 즉시 해제). **Msg4 받고 HARQ ack까지** 해야 half-open 축적. RRCReject 후 재시도 막는 **T302**도 꺼야 고갈 유지.
- **턴키 공개 공격 코드 = 계열 A [5gattacks/5g-rrc-storm](https://github.com/5gattacks/5g-rrc-storm) 하나**(OAI, KAUST 논문 공식 아티팩트, 신뢰 가능, rfsim 포함). 계열 B(UCD srsRAN)는 **코드 미공개·데이터셋만**. → [tool-survey.md](tool-survey.md)
- **공격은 표적 벤더 무관** — 표준 Uu(PRACH/RRC)에서 일어나 gNB는 어떤 UE SW인지 구분 못 함. "srsUE vs OAI-nrUE"는 **우리 도구의 베이스 선택(빌드·interop 편의)**일 뿐, 피해자 종속 아님.

### 열린 결정(서브팀이 정할 것)
1. **베이스**: 5gattacks(OAI nrUE, 빠름·완성형) 포크 vs srsUE 포팅(OCUDU와 스택 일치, interop 유리). → interop 테스트로 가름.
2. **RF 경로**: 차폐박스 실 SDR OTA(통합 데모) vs ZMQ 가상 RF(스케일). 병행 가능.
3. 노출 노브(요청률·완료율·**식별자 회전**·패턴)·대조군 설계.
4. 탐지팀과 공유 라벨 포맷 — 나중.

### 미확인/리스크
- **[최우선] interop**: 변조 안 한 정상 UE가 차폐박스에서 **OCUDU gNB에 정상 RRC 연결 되는가.** 안 되면 나머지 무의미. (OAI-UE↔srsRAN-gNB 마찰 가능 → srsUE가 안전.)
- **OCUDU의 RRCSetup 완료 대기 타이머** 값(= 고갈 성립 여부). "3초 PDU 타임아웃"과 **다른 타이머**. OCUDU 소스/설정에서 확인.
- 5gattacks 라이선스 없음 → 포크 전 저자 허가/인용 확인.

### 다음 액션(순서)
1. **interop 스모크 테스트** — 정상 srsUE(또는 OAI-nrUE) ↔ OCUDU 정상 연결 확인. 붙는 스택이 베이스로 유력.
2. 5gattacks를 **rfsim으로 먼저** 돌려 공격 동작 자체 확인(SDR 전).
3. OCUDU 완료 대기 타이머 확인 → 고갈 rate 산정.
4. 베이스 확정 후 노브(특히 식별자 회전) 보강 + half-open 내장 확인 신호.

---

## 작업 원칙(이 프로젝트 한정)
- **격리 전제**: 모든 공격 재현은 RF 차폐 박스 안, 팀 자체 장비 대상. 외부 망 금지. 5gattacks README도 "private testbed 전용".
- **기지국 무수정**: 공격은 UE 측만 변조. OCUDU(gNB)는 건드리지 않음.
- 조사 시 **1차 출처 확인 습관**: 리포 "공개" 주장은 실제 URL·내용까지 열어 확인(계열 B가 "제공한다" 선언만 하고 코드 없던 사례).
