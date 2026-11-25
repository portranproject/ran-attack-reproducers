# 공격 재현 도구 경계 (2026-11-24 결정)

이 문서는 이 저장소가 **무엇을 하고 무엇을 하지 않는지**를 고정한다. 새 모듈·새 실행기를
추가할 때 이 경계를 먼저 확인한다. 결정 근거는 주인(tazo)의 2026-11-24 지시다.

## 한 줄 정의

> 공격 재현 도구는 **UE 선에서의 조작과 ZMQ broker의 공격 슬롯**까지만 담당한다.
> CU·DU·코어·TeleRAN·탐지 엔진·대시보드는 운영/탐지팀 몫이며, 공격 도구는 그쪽에 직접
> 접근하지 않는다.

## 범위 안 (공격 도구)

| 대상 | 내용 | 현재 구현 위치 |
|---|---|---|
| UE 프로세스 | OAI `nr-uesoftmodem`, UE 설정, UE 패치·런타임 노브 | `reproducers/*/bin/*-run`, `reproducers/*/patch/` |
| UE 정답 라벨 | 공격 ID·시작/종료 시각·셀·공격 UE 식별자(논리 ID)와 그 근거 | 각 runner의 `oracle.jsonl`·`verdict.json` |
| ZMQ broker 공격 슬롯 | DU 하향 복제, UE 상향 합산, 예약 슬롯의 이득 `0/1` | `workloads/normal-ue/tools/same_cell_broker.py` |
| 정상 UE 풀 | 공격 슬롯과 같은 DU·셀의 정상 UE 5대 | `workloads/normal-ue/` |

공격 도구의 출력은 **정답 라벨**이다. "이 시각에 이 셀에서 이 공격이 이 UE로 실행됐다"까지가
출력이고, "탐지기가 맞혔는가"는 운영 도구가 판정한다.

## 범위 밖 (운영/탐지팀)

| 대상 | 왜 밖인가 | 현재 결합 지점(분리 대상) |
|---|---|---|
| CU root SSH 기동 | 공격 도구가 CU에 들어가 TeleRAN·detector·dashboard_sender를 켜고 설정 경로를 바꿨다 | `tools/p5-live-e2e` (CU 접속·`CU_PLATFORM_ROOT`·`CU_LIVE_RUN_ROOT`), `ctl.sh`의 `p5-live-e2e` 호출 |
| 탐지 입력 SHA 비교 | 탐지 엔진 입력 기록과 UE 관측 원문을 비교하는 것은 탐지 파이프라인 검증이다 | `reproducers/*/analysis/verify_live.py`의 `sha256(observations) != sha256(telemetry)` (예: `reproducers/nas-counter-desynchronization/analysis/verify_live.py:83-84`) |
| 공격별 DU·broker·UE cold-start | 공격이 아니라 **실험 운영**의 순서다. 정상 UE 5대를 매번 끊는다 | `docs/E2E-EXECUTION-GUIDE.md:61`, `workloads/normal-ue/bin/same-cell-run`의 run 경로 |
| AN 6종 탐지 입력 재생 | UE·DU를 실행하지 않고 detector 입력만 재생한다. 공격 재현이 아니라 detector 회귀다 | `reproducers/{authentication-sync-failure,nas-counter-reset,uplink-imsi-extractor,short-connection-repeat,rrc-reject-release-imprisonment,tac-manipulation-return}/` |
| 탐지 임계값·대시보드 | 공격 도구가 바꾸면 탐지 평가가 무의미해진다 | 금지 |

## 재배치 계획

1. `tools/p5-live-e2e`와 `tools/verify_live_e2e.py`는 `tools/ops/`로 옮기고, 공격 판정에서
   제거한다. 운영 도구는 탐지 경보를 **관측**할 뿐 공격 라벨을 만들지 않는다.
2. 각 모듈의 `analysis/verify_live.py`에서 탐지 입력 SHA 비교를 분리한다. 모듈 판정은
   UE 관측(오라클)만 사용하고, 탐지 입력 비교는 운영 도구의 별도 검사로 둔다.
3. `same-cell run|campaign`은 "공격 도구"가 아니라 "운영 자격 도구"다. 공격 도구의 공개
   진입점은 `./ctl.sh attack run <module>`이고, 정상 UE 5대는 `./ctl.sh cell up`이 상시
   유지한다.
4. AN 6종과 기존 42/42·3/3 봉인 결과는 삭제하지 않는다. 문서 머리에
   `> 옛 방식(운영 도구 결합) 기록`을 붙이고 새 경계의 근거로 쓰지 않는다.

## 기존 자격 증거의 표시

- `artifacts/p1-clean-origin-live-e2e-20261119/` (42/42), `artifacts/p5-live-e2e-five-20261117/`
  (5종 matched 3/3), 각 모듈의 `artifacts/p5-*`는 **옛 방식 기록**이다. CU SSH 기동과
  탐지 입력 SHA 비교가 포함돼 있다. 수치를 지우지 않되 새 경계의 자격으로 인용하지 않는다.
- 새 경계의 자격은 "정상 UE 5대가 공격 전·중·후 끊기지 않음" + "공격 라벨" + "운영 도구가
  별도로 관측한 탐지 경보"를 분리해 기록한다.

## 금지

- CU·DU·코어·탐지 엔진 소스 수정, 탐지 임계값 변경, detector/대시보드 직접 입력.
- 공격 도구가 CU에 SSH로 들어가 프로세스를 기동·설정 변경하는 것.
- 공격 도구 출력에 탐지 결과를 섞는 것(정답 라벨과 탐지 결과의 분리 유지).
