# 하향 IMSI 추출 계열 탐지 계약

## 목적

망이 요청하지 않은 `Identity Response(SUCI)`를 탐지할 수 있도록 입력과 사후 정답을
분리한다. 특정 detector나 threshold의 성능을 미리 보장하지 않는다.

## 신뢰 경계

| 구분 | 허용 데이터 |
|---|---|
| 탐지 입력 | 기본은 정규화된 `observations.jsonl`: N2 메시지 종류·방향·RAN/AMF UE ID·시각·NAS 보안 상태. CU/F1/eBPF와 조인 가능 |
| 사후 oracle | UE 마커, Open5GS 원문, 가입자 fingerprint, `verdict.json` |
| RF 원인 | 현재 입력 없음. `dl_overshadowing_observed=false` |

원시 N2 pcap에는 null-scheme SUCI가 포함될 수 있으므로 제한 접근 전처리 입력으로만 두고
Git이나 일반 detector 입력에 넣지 않는다. SUPI·IMSI·SUCI scheme output 원문과 가입자
키는 `observations.jsonl`·detector 출력·게시 artifact에 남기지 않는다. detector 출력이
봉인된 뒤 oracle fingerprint와 비교한다.

## 관측 시퀀스

```text
정상 identification:
Registration Request → Identity Request(SUCI) → Identity Response(SUCI)

하향 추출 계열 에뮬레이션:
Registration Request → Authentication Request → Identity Response(SUCI)
                                          └─ 직전/해당 context의 Identity Request 없음
```

단순히 `Identity Response`가 존재한다는 이유만으로 경보하면 정상 identification을 오탐한다.
같은 UE context의 이전 하향 NAS 메시지와 NAS 보안 상태를 함께 사용해야 한다.

## 권장 특징

- 동일 RAN/AMF UE ID에서 `Identity Response` 직전 메시지 종류
- 해당 context의 `Identity Request - Identity Response` 짝 불일치
- pre-security 평문 `Authentication Request → Identity Response` 전이
- SUCI protection scheme ID와 null-scheme 사용 비율
- 동일 셀·관측창에서 예상하지 않은 Identity Response 수
- context release 또는 registration 실패까지의 시간

null-scheme은 개인 식별자 노출 심각도를 높이지만 공격 여부 자체의 충분조건은 아니다.
정상망도 가입자 식별이 필요할 때 합법적으로 SUCI Identity Request/Response를 수행할 수 있다.

## 라벨

- `control`: 정상 Authentication Response와 등록 성공
- `protocol_impact`: Authentication Request 뒤 예상하지 않은 Identity Response
- `identity_exposure`: SUCI가 평문 NAS로 전송됨
- `null_scheme_exposure`: SUCI scheme 0과 oracle fingerprint 일치
- `rf_overshadowing`: 현재 항상 false
- `service_effect`: 별도 선택 지표

## detector 출력 최소 필드

```json
{
  "schema": "downlink-imsi.detection.v1",
  "run_id": "RUN_ID",
  "detector_id": "NAME@VERSION",
  "ran_ue_ngap_id": 0,
  "amf_ue_ngap_id": 0,
  "window_start_realtime_ns": 0,
  "window_end_realtime_ns": 0,
  "alert_realtime_ns": null,
  "observed_transition": "AuthenticationRequest>IdentityResponse",
  "identity_request_seen": false,
  "suci_protection_scheme": null,
  "input_manifest_sha256": "64자리 SHA-256"
}
```

## 평가

최소 보고값은 control 오경보, emulation 정탐, Authentication Request부터 경보까지의 지연,
정상 identification 대조군과의 구분 여부다. RF 원인 탐지는 현재 평가 범위가 아니다.
