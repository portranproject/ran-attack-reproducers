# AGENTS.md — 기지국 공격 재현 도구 모음 (RAN 보안 테스트베드)

> 이 디렉토리에서 작업하는 에이전트/팀원용 컨텍스트. 처음 들어오면 이 파일부터 읽을 것.
> 최종 갱신 2026-11-02.

## 이 디렉토리는 무엇인가

팀의 **O-RAN 기지국 침입 탐지·대응(IDS/IPS) 테스트베드**에서 사용할 기지국 공격
재현 도구 모음이다. 각 공격은 `reproducers/<attack-name>/`의 독립 모듈이며 구현,
설정, 라벨 계약, 실행 원문을 다른 공격과 섞지 않는다.

- `reproducers/rrc-signaling-storm/`: 구현·실측 완료 후 2026-11-02 동결
- `reproducers/blind-dos/`: 기존 5G-S-TMSI 방식 반증, 재개 조건 정의 중
- `reproducers/upstream-dos/`: 공격 계층·대상 자원·성공 기준 정의 중

아래 장문의 실측 기록은 첫 번째 모듈인 RRC signaling storm의 보존 컨텍스트다.

- [tool-survey.md](tool-survey.md) — OCUDU 공식 UE 연결 경로와 공개 공격 코드·다중 UE 자료의 실제 범위
- [methodology.md](methodology.md) — RSS 실험 시나리오·관측 경계·재현기 기록·OCUDU 검증 기준
- [rss-theory.md](rss-theory.md) — RSS 원리: 단계별 자원 할당·조작 파라미터·고갈 동역학·OCUDU 대입
- [rss-landscape.md](rss-landscape.md) — 변종 분류·논문·공개 도구 비교, 기존 문서와 다른 점
- [design.md](design.md) — RRCSetupComplete 미전송형 재현기 설계: 아키텍처·상태 기계·노브·라벨 스키마·단계별 계획
- [reproducers/rrc-signaling-storm/](reproducers/rrc-signaling-storm/) — 현재 OAI UE 패치·실행기·분석기·회귀 테스트·실험 기록
- [reproducers/blind-dos/](reproducers/blind-dos/) — 기존 5G-S-TMSI 주입 방식의 반증을 출발점으로 한 Blind DoS 재검토 공간
- [reproducers/upstream-dos/](reproducers/upstream-dos/) — 상향링크 DoS의 공격 계층·대상 자원·성공 기준을 확정할 준비 공간
- [reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.ko.md](reproducers/rrc-signaling-storm/docs/CURATED-VALIDATION-20261030.ko.md) — clean curated 빌드·정상 회귀·Msg4 ACK·독립 broker witness 실측
- [reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.ko.md](reproducers/rrc-signaling-storm/docs/LABEL-CONTRACT.ko.md) — UE 정답·탐지·대응·효과 판정·시간 동기 계약
- [reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md) — 동결된 재현기의 실행·입력 격리·라벨·채점 가이드
- [reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.ko.md](reproducers/rrc-signaling-storm/docs/P5-DU-ACK-JOIN.ko.md) — 새 exact DU ACK join의 p5 승인·정상 대조·합격·원복 절차
- [reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.ko.md](reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.ko.md) — 기존 E2/core 경로가 RRCSetupComplete 미전송형에 닿지 않는 이유와 CSI-DTX RLF hardening 실측
- [reproducers/rrc-signaling-storm/docs/OTA-SMOKE.ko.md](reproducers/rrc-signaling-storm/docs/OTA-SMOKE.ko.md) — 실 SDR inventory·RF 안전·정상 UE 1→2대·matched control·attack-on 게이트
- [artifacts/broker-witness-20261030/](artifacts/broker-witness-20261030/) — 독립 일반 UE attack-on/off 요약과 원격 원문 SHA-256
- [artifacts/broker-stability-20261030/](artifacts/broker-stability-20261030/) — 5 UE 시작 경합·종료 SIGSEGV 원인·2단계 종료·제한 재시도 검증
- [artifacts/broker-sync-sampling-20261030/](artifacts/broker-sync-sampling-20261030/) — 사전 고정 15회 대조군의 sync 시작 분포·서비스 품질·종료 건전성
- [artifacts/label-v1-rlf20-20261030/](artifacts/label-v1-rlf20-20261030/) — label v1 ACK-on/off·JSONL 결함 수정·CSI-DTX RLF20 실측과 원격 원문 SHA-256
- [artifacts/p5-du-ack-join-20261030/](artifacts/p5-du-ack-join-20261030/) — 구버전 패치·바이너리의 RRCSetupComplete 미전송형 exact DU ACK join 10/10 실측
- [artifacts/p5-cu200-3cell-20261030/](artifacts/p5-cu200-3cell-20261030/) — hold32 진단 자료. DU ACK 확인 RRCSetupComplete 미전송형·CU 200 도달은 입증하지만 기본 정리시간의 공격 성공 증거는 아님
- [artifacts/p5-msg3-cap96-20261030/](artifacts/p5-msg3-cap96-20261030/) — 실제 DU capacity 96의 RRCSetupRequest 후 중단형 G34 정상 대조와 G35 hold32 관측창 진단
- [artifacts/p5-default-cleanup-rate-v2-20261030/](artifacts/p5-default-cleanup-rate-v2-20261030/) — 기본 약 2초 cleanup의 R3/D3/D4와 D6 3회 on/off 원문·matched control·지속포화 한계
- [artifacts/verify-20261021/](artifacts/verify-20261021/) — OCUDU 기본 설정 RRCSetupComplete 미전송형 120초 실측 원문과 해시
- [artifacts/LEGACY-NAMES.ko.md](artifacts/LEGACY-NAMES.ko.md) — 봉인 증거의 과거 시나리오명과 현재 설명형 이름의 대응표
- [sources/](sources/) — 1차 자료 원본(논문 PDF 2건, 5gattacks 공격 패치)

관련 배경 자료(팀 전체 설계·조사)는 사용자의 별도 반입 자료(`RAN/` zip: 설계분석·요약·공격표 57건·소스코드 레퍼런스)에 있으며 이 디렉토리에는 미포함.

---

## 팀 프로젝트 (전체 그림)

**주제**: 상용 vRAN의 벤더 종속(클로즈드) CU를 전제로, 기지국 소스 수정 없이 **TeleRAN식 eBPF 텔레메트리 프록시** 위에서 near-RT RIC 기반 **탐지→대응 폐루프**를 만든다. 3-노트북 RF 차폐 테스트베드에서 OCUDU로 검증하되, 이는 상용 블랙박스 CU에서의 동작을 직접 입증하지는 않는다.

- **차별성 목표**: TeleRAN식 텔레메트리 위에서 실제 공격 재현→탐지→조치→정량평가를 연결하는 것. TeleRAN은 텔레메트리 가능성을 보였지만 RSS 대응 폐루프는 실증하지 않았다. 우리 차별성도 조치 효과를 확인한 뒤에만 성과로 주장한다.
- **현재 실측 스택**: gNB = **OCUDU 26.10**(srsRAN 기반), UE = **OAI 2026.w38**, 코어 = Open5GS, RIC = FlexRIC, RF = AWS p5 세트의 ZMQ 가상 RF.
- **최종 목표 구성**: 노트북C(공격자 UE) ─RF차폐─ 노트북B(O-DU) ─F1(IP)─ 노트북A(O-CU+RIC+eBPF+대응). 이 OTA 구성은 아직 검증 전이다.

### 대화에서 정리된 핵심 사실(정정 포함)
- **MobiFlow는 탐지기가 아님** — 텔레메트리 구조화 프레임워크. 탐지는 MobieXpert(규칙)/MobiWatch(DL).
- [OCUDU E2SM-KPM](https://docs.ocudu.org/knowledge_base/e2sm_kpm_metrics/)에는 `RRC.ConnEstabAtt/Succ` 등 **노드 단위 카운터**가 있다. [KPM 최소 보고 주기는 1초](https://docs.ocudu.org/tutorials/near-rt-ric/)이며, RRCSetupComplete 미전송형의 UE별 메시지 순서·미완료 수명 검증에는 F1 메시지 수준 텔레메트리가 더 필요하다. [TeleRAN](https://www.csl.sri.com/users/gehani/papers/FutureG-2026.eBPF.pdf)은 무수정 CU 관측의 근거지만 RSS 탐지→대응 폐루프를 실증한 자료는 아니다.
- **대응은 별도 성립 조건**: 현 OCUDU 소스의 E2 제어는 [DU slice PRB quota](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/e2/e2sm/e2sm_rc/e2sm_rc_control_action_du_executor.cpp)와 [CU handover](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/e2/common/e2_cu_cp_factory.cpp)를 포함하지만 이 변종의 미완료 UE 차단은 입증되지 않았다. RRCSetupComplete 미전송형은 `RRCSetupComplete` 전이라 [NGAP InitialUEMessage도 전송되지 않으므로](https://gitlab.com/ocudu/ocudu/-/blob/main/lib/rrc/ue/procedures/rrc_setup_procedure.cpp) 코어의 직접 대응 대상이 아니다. 벤더 관리 API도 실제 인터페이스·효과 확인 전에는 가설이다.

---

## 공격 모듈: RRC signaling storm (동결)

**목표**: RF 차폐 랩에서 팀 OCUDU gNB를 상대로, 팀 탐지·대응기를 **검증**할 수 있는 통제 가능한 스톰 재현기.
→ "강한 공격"이 아니라 **"파라미터가 통제되는 재현기"**가 설계 목표.

### 확정/파악된 것
- **RSS는 여러 절차의 묶음**이다. 이 저장소는 임의의 A/B 분류 대신 3GPP 메시지명에 기반한 설명형 이름을 쓴다. 1차 대상은 **RRCSetupComplete 미전송형**으로, Msg4 수신·HARQ ACK 후 `RRCSetupComplete`(논문 약칭 Msg5)를 생략한다. KAUST의 OAI 실측 조건이고 OCUDU 26.10·ZMQ에서는 미완료 절차와 자원 압력을 확인했지만, 차폐 OTA 효과는 미확인이다. → [methodology.md](methodology.md) §2~3
- [5gattacks/5g-rrc-storm](https://github.com/5gattacks/5g-rrc-storm)은 RRCSetupComplete 미전송형의 직접적인 공개 OAI 패치지만 구형 OAI 커밋용이다. 패치에는 **gNB UL failure 타이머 변경**도 있어 UE 부분과 분리해야 한다. 런타임 rate·완료율 노브는 없다. UCD/srsUE 데모의 재시작 스크립트·15 UE mux는 조사 범위에서 찾지 못했으나, 공식 srsRAN **3 UE ZMQ 브로커**는 공개돼 있다. → [tool-survey.md](tool-survey.md)
- **공격 진입점은 표준 Uu(PRACH/RRC)**다. OAI w38 공격 UE↔OCUDU 26.10 분리형 CU/DU의 직접 ZMQ 경로와 GNU Radio 5 UE broker의 별도 프로세스 일반 witness 경로를 p5에서 실측했다. 후자는 동작하지만 시작 동기화와 서비스 결과가 불안정하다. 차폐 OTA 상호운용은 여전히 미검증이다.
- **RRCSetupComplete 미전송형 코어 동작은 성립했다.** 보존된 2026-10-21 120초 런에서 시작 4,438건(37.0/s), `rrcSetupComplete=0`, `InitialUEMessage=0`, 피크 96/96을 gNB 로그로 확인했다. 단, 96의 최장 연속 점유는 0.45초이므로 "지속 포화" 증거가 아니다. → [검증 원문](artifacts/verify-20261021/README.md)
- **기본 DU 정리 정책에서는 정상 UE 완전 거부가 아니었다.** 최고 수락률 43.0/s가 필요한 44.9/s보다 4.4% 낮아 평균 점유가 약 92에 머물렀다. 원인은 Msg3-only UE의 CSI-DTX 100회 뒤 `t310`으로 이어지는 약 2.86초 해제였다. capacity 96은 유지하고 RLF/guard만 관측창 뒤로 미룬 실험 프로필의 G35에서는 96개를 유지한 채 정상 probe 11/11이 CU까지 도달하고 모두 DU 자원 부족으로 거절됐다. 이는 10.13초 hold32 관측창 진단이며 기본 cleanup의 공격 성공이 아니다. → [capacity-96 진단](artifacts/p5-msg3-cap96-20261030/README.md)
- **현재 기본 패치**는 `reproducers/rrc-signaling-storm/patch/rss-ue-curated.patch`(`90068853...`)이며, exact ACK RNTI 보정 패치(`62cdea20...`)까지 적용한 p5 v6 UE 바이너리는 `6b4f254f...`다. RRCSetupComplete 미전송형·지연 witness·Msg4 ACK·반복 RA 노브와 직렬화된 JSONL 정답 로거를 포함한다. `rss-run`은 증거를 봉인하고, `bin/rss-cu200`은 인공 hold32에서 4셀 control과 3공격셀+1 witness 실행을 같은 계약으로 묶는 진단 도구다. 과거 full/archive 패치는 기본 빌드에 쓰지 않는다. → [기본 cleanup 재검증](artifacts/p5-default-cleanup-rate-v2-20261030/README.md)
- **독립 일반 witness 경로는 기술적으로 성립했다.** 통제된 saturation profile(DU 상한 12, PRACH 64, CU cap 200)에서 대조군 r21은 attach 6초·Registration/PDU 성공, 공격군 r2는 서비스 실패, 공격군 r3은 공격 294회에도 attach 50초·Registration/PDU 성공이었다. 따라서 독립 witness 실행은 입증됐지만 정상 서비스 거부는 결정적으로 재현되지 않았다.
- **15회 고정 대조군 표본에서도 broker는 안정 서비스 증거로 쓸 수 없었다.** 60초 sync·60초 관측에서 30초 이내 5/5 sync는 5회, 31~60초 sync는 0회, 0/5 clean timeout은 10회였다. 유효 대조군은 3회, load UE activity가 섞인 의미상 무효 런은 2회였고, 유효 런의 ping loss는 0.833333~93.5484%, attach는 1~36초였다. 15회 모두 clean teardown·kernel SIGSEGV 0이었다. 현재 표본은 fast-success/stuck-0/5 이봉형이므로 30초를 운영값으로 유지하되 percentile 보장은 하지 않는다. → [고정 표본 기록](artifacts/broker-sync-sampling-20261030/README.md)
- **Msg4 ACK 억제는 단일 UE ZMQ 경로에서 3회 반복 성립했다.** 같은 1 UE·2초 간격·10회 시도에서 `MSG4_ACK=1`은 DU ACK 64~65건·DTX 18~20건·max-retx 0건, `MSG4_ACK=0`은 UE 억제 230~240건·DU ACK 0건·DTX 456~477건·max-retx 38~40건이었다. 모두 Msg5와 crash는 0건이었다. OCUDU의 `ConRes CE ACKed` 문자열은 모든 런에서 10건이어서 실제 ACK 증거로 쓰지 않는다.
- **hold32 V4는 최종 성공 증거에서 강등했다.** exact DU ACK와 조인된 `canonical_a=true` 176건, CU 점유 200, witness 17/17 거부는 사실이지만 기본 약 2초 정리시간을 32초로 늘리고 첫 만료 전에 끝냈다. 공격률이 기본 해제율을 이겼다는 증거가 아니므로 현재 목표는 기본 cleanup/RLF·CU 200·DU 96을 유지한 sustained denial 재검증이다. → [V4 진단](artifacts/p5-cu200-3cell-20261030/README.md)
- **기본 cleanup rate-v2 재검증도 sustained denial에는 실패했다.** D4의 공격 제공률은 48.652/s로 정리율 39.407/s보다 높았지만 8.558/s가 컨텍스트 생성 전에 거절됐다. 실제 생성률은 40.095/s였고 워밍업 뒤 생성 40.026/s 대 정리 39.922/s로 평형이었다. 점유 96 최장 구간은 0.885초였고 독립 정상 witness는 첫 distinct 시도만 거절된 뒤 Registration·PDU와 ping 437/438에 성공했다. 공격자 처리율 개선은 확인했지만 통제 가능한 서비스 거부는 성립하지 않았다. → [실패 분석과 원문](artifacts/p5-default-cleanup-rate-v2-20261030/README.md)
- **기본 cleanup RRCSetupRequest 후 중단형의 서비스 수준 on/off는 3/3 반복됐다.** D6F45·D6F46·D6F48은 gNB cleanup/RLF·DU 96·CU 200을 바꾸지 않은 6프로세스×2UE 공격에서 모두 공격 중 primary 서비스 실패와 stop 뒤 별도 prelaunched UE의 Registration·PDU·ping 회복을 보였다. D6F48은 Msg3 77.408/s, DU provisional Create 73.338/s, cleanup 34.209/s였고 완전한 5초 창 12/12에서 offered·provisional이 cleanup보다 높았다. 초과분 2,373건은 Setup admission 전에 즉시 거절돼 admitted Setup은 cleanup과 평형이었고 점유 피크는 95/96이었다. 정확히 같은 8-endpoint attack-off D6C51은 quiet load·extra UE 시도 0건, primary Registration·PDU·ping 303/303으로 통과했다. 따라서 좁은 on/off 상관은 반복됐지만 30초 지속 포화·fresh-witness 반복 거부·동일 UE 회복·기지국 전체 마비는 입증되지 않았다. → [D6 원문과 판정](artifacts/p5-default-cleanup-rate-v2-20261030/README.md)
- **기본 cleanup의 DU ACK 확인 RRCSetupComplete 미전송형은 기전만 성립하고 denial에는 실패했다.** D6F50은 UE 후보 205건 중 current-run DU FAPI HARQ ACK와 exact join된 양성 149건, 공격자 Msg5 0건을 만들었다. Msg3 34.824/s와 DU provisional 32.071/s는 cleanup 28.362/s를 넘었지만 admitted Setup은 cleanup과 평형, 점유 피크는 84/96이었고 공격 중 정상 UE가 Registration·PDU·ping 194/195에 성공했다. 기전 증거와 서비스 영향 증거를 분리한다. → [D6F50 판정](artifacts/p5-default-cleanup-rate-v2-20261030/README.md)
- **4셀 정상 대조와 원복을 확인했다.** 공격 전 최종 바이너리 control 네 셀 모두 `RRCSetupComplete`에 도달했고 C3는 Registration·PDU Session·TUN까지 성공했다. 실험 뒤 CU·DU 설정을 보존한 원본으로 복구하고 p5 CU·DU 인스턴스를 중지했다.
- **새 runner는 run 전체 증거를 자동 봉인한다.** `run.json`에 UE full commit과 binary·RSS patch·runner/exporter/redactor/scanner hash를 남기고, 종료 시 `evidence_manifest.json`에 핵심 산출물의 크기·SHA-256을 기록한다. seal과 verifier는 실행 checkout의 현재 scanner로 run 디렉터리 전체를 다시 검사한다. G34·G35의 manifest verify도 통과했다.
- **CSI-DTX RLF 정적 hardening은 p5 ZMQ에서 성립했다.** `pucch.max_consecutive_kos=20` 한 항목만 바꾼 단일 UE 직렬 RRCSetupComplete 미전송형 20회에서 RLF→F1 Release Request/Command/Complete 각 단계 집계가 20건씩 일치했고, 같은 설정의 약 60초 attack-off 회귀는 ping 20/20·RLF 0이었다. 설정은 원본 SHA-256으로 원복했다. 시도별 F1/CU ID 조인 증거는 아니며, 셀 전체 정적 설정의 실증이지 탐지기가 호출한 actuator나 near-RT RIC 폐루프가 아니다. → [대응 경로 감사](reproducers/rrc-signaling-storm/docs/RESPONSE-PATH-AUDIT.ko.md)
- **2026-11-02에 RRC storm 서브태스크를 동결했다.** 현재 결과는 분석기 입력·정답 생성기로 사용한다. 기본 cleanup에서 30초 지속 포화, 같은 정상 UE의 30초 반복 거부→회복, 기지국 전체 마비는 미달 상태로 닫는다. 로컬 `BROKER_SAME_WITNESS_CYCLE`은 이 기준을 검사하는 단위 테스트까지 있으나 p5 미실측 초안이므로 운영 기능·성능 근거에서 제외한다. → [사용 가이드](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md)

### 동결 후 팀 결정(RRC storm 구현 범위 밖)
1. 실제 빌드·기본 회귀·3회 Msg4 ACK-on/off를 확인한 w38을 데모 기준선으로 고정할지, 최신 OAI로 옮길지. 버전 이관은 별도 브랜치로 한다.
2. ZMQ 스케일 실험과 차폐박스 실 SDR OTA 통합 데모를 어떤 순서와 장비 구성으로 운영할지.
3. label v1의 남은 F1/CU lifecycle 조인 필드·시계 증거·효과 threshold를 분석기 운영 계약으로 승인할지.
4. 이 변종의 미완료 UE에 탐지 뒤 동적으로 닿는 actuator와 정상 UE 보존 기준.

### 미확인/리스크
- **독립 witness attack-on/off 재현성**: 별도 프로세스 일반 witness는 성립했지만 공격군 서비스 결과가 갈렸고, 15회 고정 대조군도 fast sync 5회·clean timeout 10회, 유효 3회에 그쳤다. 유효 대조군 ping loss도 0.833333~93.5484%였다. 30초 sync 제한은 현재 표본에서 운영상 유지하지만 percentile 보장이 아니며, broker 결과로 정상 사용자 DoS나 서비스 보존을 단정하지 않는다. 과거 종료 SIGSEGV는 UE에 INT를 두 번 보내는 종료로 해소됐고 15회 모두 clean teardown이었다.
- **mixed probe의 증거 한계**: 같은 프로세스·ZMQ 무선의 probe는 연결과 PDU까지 성공했지만 channel timeout 157,990건과 약 10.5% out-of-order 공유 TX가 남았다. 진단용일 뿐 정상 UE 서비스 보존 증거로 쓰지 않는다. `RSS_SHARE_NUE` 부분 배치는 타임스탬프 역행과 crash를 만들므로 실행기가 이제 `NUM_UES`와 같은 값만 허용한다.
- **OTA interop**: ZMQ 분리형 CU/DU와 broker witness는 검증됐지만 차폐박스 실 SDR OTA의 독립 정상 UE witness는 미검증이다. 현재 runner·build·doctor는 ZMQ 전용이고, 실제 SDR 모델/serial·clock·gain 상한·감쇠/배선·서로 다른 두 가입자 profile이 확정되지 않아 `DEVICE`만 바꿔 OTA를 실행하면 안 된다. `analysis/validate_ota_inventory.py`는 G0 manifest의 누락·중복·비밀값만 fail-closed 검사하며 실물 대조나 송신 승인을 대신하지 않는다.
- **Msg4 ACK 효과 범위**: 최초와 재전송 HARQ-ACK이 DTX가 되고 max-retx 폐기로 끝나는 것은 실측했다. 스케줄러 압력의 정량 효과와 정상 UE 서비스 영향은 아직 주장하지 않는다. OCUDU의 `ConRes CE ACKed` 로그 문자열은 실제 ACK 판정에 사용하지 않는다.
- **CU200 hold32 진단 범위**: V4의 거부는 기본 약 2초 cleanup을 32초로 늘린 뒤 첫 만료 전에 끝낸 결과다. 기본 cleanup에서 공격 유입률이 해제율을 이기는 서비스 거부나 차폐 OTA 결과로 일반화하지 않는다. 전체·과거 DU 로그는 SFN 순환과 RNTI 재사용 때문에 exporter에 직접 주지 않고, sector가 확인된 current-run slice만 사용한다.
- **rate-v2 병목**: D6F48은 offered·DU provisional이 cleanup을 12/12 완전 5초 창에서 넘었지만 53.3%가 Setup admission 전에 즉시 거절됐다. bounded capacity가 찬 뒤에는 `admitted = cleanup`으로 수렴하는 것이 보존식상 정상이라, admitted가 cleanup보다 계속 커야 한다는 기준은 쓰지 않는다. fill 구간의 점유 증가와 포화 뒤 overflow 거절, 독립 정상 UE의 반복 서비스 실패를 함께 판정해야 한다.
- **과거 credential 노출**: 현재 작업 트리의 추적 로그는 정제됐지만 과거 Git blob에는 랩 값이 남아 있다. 사용자는 LLM 노출과 private GitHub 저장을 이 작업의 차단 사유로 보지 않으므로 p5 실험·개발은 계속한다. 다만 외부 공개 배포로 범위가 바뀌면 키 회전·이력 정리 여부를 다시 검토한다. → [정제 기록](artifacts/SECURITY-REDACTION-20261030.md)
- **폐루프 게이트**: 정적 CSI-DTX RLF 설정은 RRCSetupComplete 미전송형 컨텍스트를 조기 해제했지만 셀 전체에 항상 적용된다. 탐지 결과가 호출할 동적 actuator, 조치 후 미완료 컨텍스트 감소, 장기·열악 채널 정상 UE 유지가 아직 입증되지 않았다. 그 전까지 RRCSetupComplete 미전송형은 탐지 검증과 정적 hardening 실험으로만 보고한다.
- 5gattacks 라이선스 없음 → 포크 전 저자 허가/인용 확인.

### 마감 상태와 사용
1. 사용자는 [사용 가이드](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md)에 따라 RRCSetupComplete 미전송형을 주 시나리오, RRCSetupRequest 후 중단형을 별도 가시성·부하 시나리오로 사용한다.
2. 보존 artifact와 manifest는 수정하지 않고, detector 출력이 봉인될 때까지 UE ground truth를 입력에서 분리한다.
3. 다음 공격 재현 도구는 이 결과를 덮어쓰지 말고 별도 디렉터리·시나리오 이름·라벨 계약으로 시작한다.
4. RRC storm을 다시 열 경우에만 30초 fresh-witness 반복 실패, 같은 witness 회복, 3회 반복, exact DU ACK를 재개 합격 기준으로 사용한다. hold32는 계속 금지한다.

---

## 작업 원칙(이 프로젝트 한정)
- **격리 전제**: 모든 공격 재현은 RF 차폐 박스 안, 팀 자체 장비 대상. 외부 망 금지. 5gattacks README도 "private testbed 전용".
- **기지국 무수정**: 공격은 UE 측만 변조. OCUDU(gNB)는 건드리지 않음.
- 조사 시 **1차 출처 확인 습관**: 리포 "공개" 주장은 실제 URL·내용까지 열어 확인(UCD 데모가 "제공한다"고만 쓰고 코드는 없던 사례).
