# AGENTS.md — RRC Signaling Storm 재현 도구 (RAN 보안 테스트베드)

> 이 디렉토리에서 작업하는 에이전트/팀원용 컨텍스트. 처음 들어오면 이 파일부터 읽을 것.
> 최종 갱신 2026-10-09.

## 이 디렉토리는 무엇인가

팀의 **O-RAN 기지국 침입 탐지·대응(IDS/IPS) 테스트베드** 프로젝트 중,
**"외부자 UE(공격자) 측 — RRC signaling storm 재현 도구 제작"** 서브태스크의 조사·설계 기록.
사용자(이 저장소 주인)가 맡은 역할이 바로 이 UE 공격 도구 부분이다.

- [tool-survey.md](tool-survey.md) — OCUDU 공식 UE 연결 경로와 공개 공격 코드·다중 UE 자료의 실제 범위
- [methodology.md](methodology.md) — RSS 실험 시나리오·관측 경계·재현기 기록·OCUDU 검증 기준
- [rss-theory.md](rss-theory.md) — RSS 원리: 단계별 자원 할당·조작 파라미터·고갈 동역학·OCUDU 대입
- [rss-landscape.md](rss-landscape.md) — 변종 분류·논문·공개 도구 비교, 기존 문서와 다른 점
- [design.md](design.md) — A형 재현기 설계: 아키텍처·상태 기계·노브·라벨 스키마·단계별 계획
- [sources/](sources/) — 1차 자료 원본(논문 PDF 2건, 5gattacks 공격 패치)

관련 배경 자료(팀 전체 설계·조사)는 사용자의 별도 반입 자료(`RAN/` zip: 설계분석·요약·공격표 57건·소스코드 레퍼런스)에 있으며 이 디렉토리에는 미포함.

---

## 팀 프로젝트 (전체 그림)

**주제**: 상용 vRAN의 벤더 종속(클로즈드) CU를 전제로, 기지국 소스 수정 없이 **TeleRAN식 eBPF 텔레메트리 프록시** 위에서 near-RT RIC 기반 **탐지→대응 폐루프**를 만든다. 3-노트북 RF 차폐 테스트베드에서 OCUDU로 검증하되, 이는 상용 블랙박스 CU에서의 동작을 직접 입증하지는 않는다.

- **차별성 목표**: TeleRAN식 텔레메트리 위에서 실제 공격 재현→탐지→조치→정량평가를 연결하는 것. TeleRAN은 텔레메트리 가능성을 보였지만 RSS 대응 폐루프는 실증하지 않았다. 우리 차별성도 조치 효과를 확인한 뒤에만 성과로 주장한다.
- **스택**: gNB = **OCUDU**(srsRAN 기반). RIC = OSC/FlexRIC(미확정). 코어 = 미확정(Open5GS 등).
- **구성**: 노트북C(공격자 UE) ─RF차폐─ 노트북B(O-DU) ─F1(IP)─ 노트북A(O-CU+RIC+eBPF+대응).

### 대화에서 정리된 핵심 사실(정정 포함)
- **MobiFlow는 탐지기가 아님** — 텔레메트리 구조화 프레임워크. 탐지는 MobieXpert(규칙)/MobiWatch(DL).
- [OCUDU E2SM-KPM](https://docs.ocudu.org/knowledge_base/e2sm_kpm_metrics/)에는 `RRC.ConnEstabAtt/Succ` 등 **노드 단위 카운터**가 있다. [KPM 최소 보고 주기는 1초](https://docs.ocudu.org/tutorials/near-rt-ric/)이며, A형의 UE별 메시지 순서·미완료 수명 검증에는 F1 메시지 수준 텔레메트리가 더 필요하다. [TeleRAN](https://www.csl.sri.com/users/gehani/papers/FutureG-2026.eBPF.pdf)은 무수정 CU 관측의 근거지만 RSS 탐지→대응 폐루프를 실증한 자료는 아니다.
- **대응은 별도 성립 조건**: 현 OCUDU 소스의 E2 제어는 [DU slice PRB quota](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/e2/e2sm/e2sm_rc/e2sm_rc_control_action_du_executor.cpp)와 [CU handover](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/e2/common/e2_cu_cp_factory.cpp)를 포함하지만 A형 미완료 UE 차단은 입증되지 않았다. A형은 `RRCSetupComplete` 전이라 [NGAP InitialUEMessage도 전송되지 않으므로](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/rrc/ue/procedures/rrc_setup_procedure.cpp) 코어의 직접 대응 대상이 아니다. 벤더 관리 API도 실제 인터페이스·효과 확인 전에는 가설이다.

---

## 내 서브태스크: RRC signaling storm 재현 도구

**목표**: RF 차폐 랩에서 팀 OCUDU gNB를 상대로, 팀 탐지·대응기를 **검증**할 수 있는 통제 가능한 스톰 재현기.
→ "강한 공격"이 아니라 **"파라미터가 통제되는 재현기"**가 설계 목표.

### 확정/파악된 것
- **RSS는 여러 절차의 묶음**이며 A/B 등은 우리의 실험 시나리오 이름이다. 1차 대상은 **A형 초기접속 미완료**: Msg4 수신·HARQ ACK 후 `RRCSetupComplete`(논문 약칭 Msg5)를 생략한다. KAUST의 OAI 실측 조건이며 OCUDU 효과는 미확인. → [methodology.md](methodology.md) §2~3
- [5gattacks/5g-rrc-storm](https://github.com/5gattacks/5g-rrc-storm)은 A형의 직접적인 공개 OAI 패치지만 구형 OAI 커밋용이다. 패치에는 **gNB UL failure 타이머 변경**도 있어 UE 부분과 분리해야 한다. 런타임 rate·완료율 노브는 없다. UCD/srsUE 데모의 재시작 스크립트·15 UE mux는 조사 범위에서 찾지 못했으나, 공식 srsRAN **3 UE ZMQ 브로커**는 공개돼 있다. → [tool-survey.md](tool-survey.md)
- **공격 진입점은 표준 Uu(PRACH/RRC)**다. 다만 UE 구현별 무선 동작과 상호운용성이 달라 OCUDU에서 같은 효과가 난다고 단정할 수 없다. [OCUDU 공식 OAI UE 튜토리얼](https://docs.ocudu.org/tutorials/oaiue/)은 OAI `2026.w25` 이상과 ZMQ 정상 접속 사례를 제시한다. 우리 차폐 OTA·분리형 CU/DU 및 구형 공격 패치 조합은 별도 시험이 필요하다.

### 열린 결정(서브팀이 정할 것)
1. **베이스**: 팀 셀이 TDD면 [OCUDU 공식 튜토리얼](https://docs.ocudu.org/tutorials/oaiue/)의 최신 OAI UE로 정상 연결을 확인한 뒤 구형 5gattacks의 UE 동작을 참고해 이식. srsUE는 15 kHz SCS/FDD/최대 20 MHz이므로 FDD 셀에서만 별도 후보.
2. **RF 경로**: 차폐박스 실 SDR OTA(통합 데모) vs ZMQ 가상 RF(스케일). 병행 가능.
3. 노출 노브(시도 간격·완료율·초기 UE identity 정책·패턴)와 실제 관측값·대조군 설계.
4. 탐지팀과 공유 라벨 포맷 — 나중.

### 미확인/리스크
- **[최우선] interop**: 공식 OAI UE↔OCUDU ZMQ 사례는 있으나, 차폐박스 **OTA·팀 CU/DU 분리 배치**의 정상 접속과 5gattacks 패치의 최신 OAI 포팅 성공은 미확인이다. srsUE는 FDD 설정에서만 후보.
- **OCUDU의 RRCSetup 완료 대기 시간 계산**은 소스에서 확인(`t300 + rrc_procedure_guard_time_ms`). 설치본의 로드된 값, 실제 DU/F1 해제 시각, 먼저 걸리는 용량 한도는 미확인.
- **폐루프 게이트**: 무수정 gNB에서 접근 가능한 대응 수단, A형에 닿는 대상 범위, 조치 후 미완료 컨텍스트 감소와 정상 UE 유지가 아직 입증되지 않았다. 그 전까지 A형은 탐지 검증 시나리오다.
- 5gattacks 라이선스 없음 → 포크 전 저자 허가/인용 확인.

### 다음 액션(순서)
1. **interop 스모크 테스트** — 팀 RF 설정에 맞는 정상 UE↔OCUDU 연결 확인. TDD라면 최신 OAI UE의 공식 ZMQ 경로부터, 차폐 OTA와 분리형 배치를 차례로 확인.
2. 5gattacks의 **OAI gNB↔OAI UE rfsim**은 구형 패치의 A형 동작 참고 시험으로 사용 가능하다. 이것은 최신 OAI UE·OCUDU interop 시험과 별개.
3. OCUDU 설치본의 로드된 설정과 미완료 UE 생성~해제, 정상 UE 영향 실측.
4. 베이스 확정 후 A형 요청 간격부터 제어. 탐지팀의 실제 대응 수단과 효과가 확인되어야 A형 폐루프를 주장한다. B형 UE 재시작 반복은 별도 구현·라벨로 확대.

---

## 작업 원칙(이 프로젝트 한정)
- **격리 전제**: 모든 공격 재현은 RF 차폐 박스 안, 팀 자체 장비 대상. 외부 망 금지. 5gattacks README도 "private testbed 전용".
- **기지국 무수정**: 공격은 UE 측만 변조. OCUDU(gNB)는 건드리지 않음.
- 조사 시 **1차 출처 확인 습관**: 리포 "공개" 주장은 실제 URL·내용까지 열어 확인(계열 B가 "제공한다" 선언만 하고 코드 없던 사례).
