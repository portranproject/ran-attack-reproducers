# 탐지·대응 평가 라벨 계약 v1

이 계약은 재현기의 **정답(ground truth)**, 탐지기의 입력과 출력, 대응 요청·ACK,
효과 판정을 분리한다. 정답 파일은 채점 단계에서만 열며 탐지기 입력으로 주지 않는다.
현재 확인되지 않은 F1 필드나 대응 인터페이스를 있는 것처럼 만들지 않는다.

이 문서의 절차명은 3GPP 공격 분류명이 아니라 표준 RRC 메시지명에 기반한 설명형
이름이다. label v1과 봉인 증거의 호환성을 위해 다음 기계 값은 바꾸지 않는다.

| 과거 label v1 값·필드 | 현재 설명형 명칭 |
|---|---|
| `scenario="A"`, `canonical_a*` | RRCSetupComplete 미전송형 |
| `scenario="A_early"`, `canonical_msg3*` | RRCSetupRequest 후 중단형 |
| `scenario="A_no_ack"` | RRCSetup HARQ-ACK 억제형 |

## 1. UE 정답 정규화

`attempts.jsonl`은 실행 중 append-only로 기록하고 종료 뒤 불변 증거로 취급할 raw
event다. 같은 시도의 identity, TC-RNTI와 도달점이 여러 줄에 나뉘므로 다음 명령으로
시도당 한 줄인 `ground_truth.jsonl`을 만든다.

```bash
python3 analysis/export_labels.py RUN_DIR/run.json RUN_DIR/attempts.jsonl \
  > RUN_DIR/ground_truth.jsonl

# 이번 run만 담은 gNB slice가 있을 때만 세 번째 인자로 준다.
# RRCSetupComplete 미전송형은 DU FAPI, RRCSetupRequest 후 중단형은 CU RRC 행을 사용한다.
python3 analysis/export_labels.py RUN_DIR/run.json RUN_DIR/attempts.jsonl \
  RUN_DIR/gnb-run-slice.log > RUN_DIR/ground_truth.jsonl
```

두 인자 호출은 기존처럼 동작한다. 세 번째 인자에는 전체·과거 gNB 로그를 주지 않는다.

exporter는 `(run_id, ue, seq)`로만 묶는다. `seq`는 UE별 순번이므로 단독 조인 키가
아니다. `attempt_id`는 `RUN_ID:UE:SEQ`다. 다른 run id, 잘못된 JSON, 잘못된 UE·seq·
시각은 일부 결과를 내지 않고 전체 실패한다.

출력의 최소 공통 필드는 다음과 같다.

```json
{
  "schema_version": 1,
  "type": "attempt",
  "source": "ue_ground_truth",
  "run_id": "X001",
  "attempt_id": "X001:0:17",
  "ue": 0,
  "seq": 17,
  "ue_identity": "0x1a2b3c4d5e",
  "tc_rnti": "0x4601",
  "intended_reach": "msg5_skip",
  "actual_reach": "msg4_ack_unknown",
  "msg4_ack_state": "unknown",
  "du_ack_state": "unknown",
  "msg5_action": "skipped",
  "canonical_a_ue": null,
  "canonical_a": null,
  "canonical_a_evidence": "missing_ue_ack_event",
  "canonical_msg3_ue": false,
  "canonical_msg3_only": false,
  "canonical_msg3_evidence": null,
  "msg3_tx_evidence": null,
  "cu_msg3_evidence": null,
  "timestamps": {
    "attempt_start_ns": 1791882034819000000,
    "msg3_tx_ns": null,
    "msg4_rx_ns": 1791882034828000000,
    "msg4_ack_scheduled_ns": null,
    "msg4_ack_withheld_ns": null,
    "rrc_reject_ns": null,
    "msg5_submitted_ns": null,
    "attempt_end_ns": null,
    "retrigger_ns": null
  }
}
```

분류 우선순위는 고정한다.

| 순서 | raw evidence | `actual_reach` | `canonical_a` |
|---:|---|---|---|
| 1 | `rrc_reject` | `rrc_reject` | `false` |
| 2 | `msg5_submitted` | `msg5_submitted` | `false` |
| 3 | ACK scheduled와 withheld가 모두 있음 | `inconclusive` | `null` |
| 4 | Msg4 수신 + ACK withheld | `msg4_no_ack` | `false` |
| 5 | Msg4 수신 + ACK scheduled + Msg5 skipped + 유일한 exact DU ACK | `msg5_skip` | `true` (`canonical_a_ue=true`) |
| 6 | Msg4 수신 + ACK scheduled + Msg5 skipped + DU ACK 없음/모호함 | `msg5_skip` | `null` (`canonical_a_ue=true`) |
| 7 | 과거 `actual_reach=msg5_skip`, ACK event 없음 | `msg4_ack_unknown` | `null` |
| 8 | `attempt_end.actual_reach=no_msg4` | `no_msg4` | `false` |
| 9 | 그 밖 또는 마지막 미종결 시도 | `unknown` | `null` |

`canonical_a_ue=true`는 **UE scheduler 쪽 후보 판정**일 뿐이다. `du_ack_state`는 이
후보에만 조인한다. UE `msg4_ack_scheduled`의 `(rnti, frame, slot)`과 OCUDU FAPI
`UCI.indication`의 `(rnti, SFN, slot)`이 정확히 같고 그 tuple에 `PUCCH format 0/1`
`harq_ack=ack` 행이 하나뿐이며 UE 쪽에서도 run 전체에 그 tuple을 기록한 시도가
하나뿐일 때 `du_ack_state="ack"`, `canonical_a=true`,
`canonical_a_evidence="ue_scheduler+ocudu_fapi"`로 승격한다. `du_ack_evidence`에는
source, DU slice SHA-256, 행 번호, sector ID, RNTI, frame, slot을 기록한다.

DTX·NACK·누락·중복 tuple은 음성 정답이 아니므로 `canonical_a=null`을 유지한다.
`ConRes CE ACKed`, PUSCH, PUCCH 2/3/4는 ACK 증거로 쓰지 않는다. FAPI HARQ 후보
행이 파싱되지 않거나 값이 범위를 벗어나면 일부 결과를 내지 않고 export 전체를
실패시킨다. 기존 `msg4_rx.actual_reach=msg5_skip`만으로는 ACK을 증명하지 못한다.
`msg5_submitted`도 PDCP 제출 증거이지 무선 송신·gNB 수신 증거로 확대하지 않는다.

### RRCSetupRequest 후 중단형 (`MSG4_WAIT=0`) 판정

MAC scheduler의 유효 `msg3_tx`가 있고 공격 UE가 Msg4·Msg5에 도달하지 않은 시도는
`canonical_msg3_ue=true`인 **UE 후보**다. UE 이벤트만 있으면 최종
`canonical_msg3_only=null`이다. current-run CU slice의
`ue=N c-rnti=0x....: Rx SRB0 CCCH UL rrcSetupRequest`와 TC-RNTI로 조인하고,
UE run 전체와 CU slice에서 각각 정확히 한 번일 때만
`canonical_msg3_only=true`, `canonical_msg3_evidence="ue_mac+ocudu_cu_rrc"`로
승격한다. `msg3_tx_evidence`에는 MAC의 TC-RNTI·frame·slot·source를,
`cu_msg3_evidence`에는 CU 행 번호·slice SHA-256·UE ID·TC-RNTI를 둔다.

중복 TC-RNTI는 `null`로 남기고 malformed CU 후보는 일부 결과를 만들지 않고 export
전체를 실패시킨다. ordinary probe처럼 정상 완료가 목표인 UE나 `rrc_reject`,
`msg5_submitted`에 도달한 시도는 RRCSetupRequest 후 중단형 공격 정답이 아니다. RRCSetupComplete 미전송형의 FAPI ACK
조인과 RRCSetupRequest 후 중단형의 CU RRC 조인은 서로 대체하지 않는다.

전체 DU 로그는 SFN 순환과 RNTI 재사용 때문에 오조인될 수 있다. `rss-run`은 gNB
readiness 뒤 `ODU_LOG`의 inode·offset·prefix SHA-256을 기록하고, UE 종료 뒤 같은
파일에 append된 완전한 행만 `odu.log`로 봉인한다. rotation·truncate·prefix 변경은
조인을 건너뛰고 최종 RRCSetupComplete 미전송형 판정을 unknown으로 남긴다. `du_log_slice.json`의 SHA-256과
`run_stop.json`의 `du_ack_join` 상태를 함께 보존한다.

OCUDU는 이 `UCI.indication`을 FAPI debug에서만 기록하고 기본 `fapi_level`은
warning이다. `ODU_LOG`와 함께 `ODU_SECTOR_ID`를 명시하고 run.json에 기록한다.
모든 FAPI 후보 행에 `Sector#N`이 있어야 하며 다른 sector 행은 export 전체를
실패시킨다. 단일 sector DU 로그에 `log.fapi_level: debug`를 설정하고 정상 대조군에서
`rss-doctor`가 최근 PUCCH 0/1 HARQ 행을 확인한 뒤 사용한다. `du_ack_join=matched`만
하나 이상의 최종 RRCSetupComplete 미전송형 조인을 뜻한다. `no_match`는 slice 캡처는 성공했지만 exact ACK가
없었다는 뜻이며 ACK 실패의 음성 정답은 아니다.

이 DU HARQ 조인은 F1/CU lifecycle 조인을 대신하지 않는다. F1과의 조인은 가능한
경우 `(tc_rnti, ue_identity, 시각 창)`을 사용한다. 값이 없으면
채우지 않으며 시각만으로 1:1 조인했다고 주장하지 않는다. IMSI·가입자 키·NAS 원문은
이 export에 넣지 않는다.

## 2. 탐지기 입력과 출력

탐지기에는 F1/eBPF 텔레메트리만 준다. `run.json`, raw `attempts.jsonl`,
`ground_truth.jsonl`, OCUDU 내부 진단 로그는 채점 전까지 분리한다. 실험 보존본은
runner가 종료 시 만드는 `evidence_manifest.json`으로 봉인하고 다음 명령으로
run ID·파일 크기·SHA-256·DU 조인 증거를 다시 검사한다. manifest 자체의 악의적
교체까지 막는 전자서명은 아니므로 보존 위치의 접근 통제는 별도다.

```bash
python3 analysis/evidence_manifest.py verify RUN_DIR
python3 analysis/evidence_manifest.py verify RUN_DIR --require-matched
```

`--require-matched`는 봉인된 `attempts.jsonl`, `run.json`, `odu.log`를 기록된
exporter와 같은 SHA-256의 코드로 다시 변환하고, 결과가 `ground_truth.jsonl`과 정확히
같을 때만 성공한다. 일반 verify와 seal도 실행 중인 checkout의 현재
`check_sensitive_artifacts.py`로 run 디렉터리 전체를 다시 검사한다. 따라서 검증에
사용하는 checkout을 신뢰해야 하며, 과거 matched run은 당시 exporter가 있는 checkout에
최신 scanner를 함께 반영한 뒤 검증해야 한다.

현재 `evidence_manifest.py`의 matched replay는 봉인된 `odu.log`를 쓰는 RRCSetupComplete 미전송형의
FAPI ACK 조인까지만 포함한다. 원격 CU slice로 나중에 만든 RRCSetupRequest 후 중단형
`ground_truth-cu.jsonl`은 별도 derived artifact이며 원본 run manifest가 그 결론까지
봉인했다고 쓰지 않는다. CU slice·exporter·derived 결과의 SHA-256을 별도로 보존한다.

탐지기는 경보만이 아니라 판단한 모든 평가 창을 `detections.jsonl`에 남긴다.

```json
{"schema_version":1,"type":"detection","run_id":"X001","detection_id":"d-17","detector":{"name":"rss-rule","version":"git-sha"},"window_start_ns":1791882034000000000,"window_end_ns":1791882035000000000,"t_decision_ns":1791882035100000000,"decision":"attack","score":0.91,"threshold":0.8,"scope":{"cell":"n78-cell-1","tc_rnti":null},"clock_host":"cu","evidence_ref":"f1-capture:packet-120-190"}
```

필수 의미는 `run_id`, detector 이름·버전, 평가 창, 판단 시각, `attack|normal|unknown`
판정이다. score와 threshold가 없는 규칙 탐지기는 두 값을 `null`로 둔다. 실제
텔레메트리에 없는 UE 식별자나 TA를 합성하지 않는다.

## 3. 대응 요청·ACK

확정되지 않은 조치 이름을 enum으로 만들지 않는다. 실제 설치본에서 호출한 인터페이스,
동작과 대상만 `actions.jsonl`의 append-only event로 기록한다.

```json
{"schema_version":1,"type":"action_requested","run_id":"X001","action_id":"a-3","detection_id":"d-17","interface":"verified-interface-name","action":"verified-action-name","target":{"kind":"verified-target-kind","ref":"lab-target"},"t_ns":1791882035200000000,"clock_host":"cu"}
{"schema_version":1,"type":"action_ack","run_id":"X001","action_id":"a-3","t_ns":1791882035250000000,"clock_host":"cu","status":"accepted","error":null}
```

요청 실패도 `action_failed`로 남긴다. ACK는 명령 수락일 뿐 효과가 아니다.

## 4. 효과 판정

`verdict.json`은 raw 정답·탐지·조치·CU 컨텍스트·독립 정상 UE 측정을 모두 봉인한 뒤
offline evaluator가 만든다. 최소 필드는 다음과 같다.

```json
{
  "schema_version": 1,
  "type": "verdict",
  "run_id": "X001",
  "valid": false,
  "verdict": "inconclusive",
  "reason": "response interface not verified",
  "attack_continued_after_action": null,
  "detection": {"first_observable_ns": null, "first_decision_ns": null, "latency_ns": null},
  "response": {"request_ns": null, "ack_ns": null, "effect_ns": null},
  "contexts": {"source": null, "pre": null, "post": null},
  "normal_service": {"source": null, "pre": null, "post": null},
  "thresholds": null
}
```

`effective`는 실행 전에 고정한 threshold가 있고, 공격이 계속되는 동안 미완료
컨텍스트가 감소하며 독립 정상 UE 서비스가 회복된 경우에만 가능하다. action ACK만
있거나 공격 kill switch와 효과 창이 겹치면 `inconclusive`다. 정상 고부하 대조군에서
오차단이 있으면 서비스 보존 성공을 주장하지 않는다.

## 5. 시계와 지연의 성립 조건

각 호스트의 동기 방식, 기준 호스트, offset, uncertainty, 측정 전·후 시각과 raw
증거 SHA-256을 run evidence에 보존한다. `offset_ns`와 `uncertainty_ns` 중 하나라도
없으면 UE↔CU, detector↔responder 같은 **호스트 간 latency는 `null`이며
`unscorable`**이다. UTC 모양의 timestamp나 NTP/PTP 설정 존재만으로 동기됐다고
간주하지 않는다.

동일 호스트의 순서는 그대로 보존할 수 있지만, 서로 다른 호스트의 시각 조인은
TC-RNTI·UE identity·프로토콜 순서와 함께 검증한다. 캡처 drop counter가 없으면
`capture_loss_pct`도 `null`로 두며 포착률을 완전하다고 주장하지 않는다.
