# 인증 응답 미전송형 탐지 계약

## 목적

Authentication Response 미전송형 연결 컨텍스트 고갈의 재현 결과를 탐지기에 제공할 때
입력과 사후 정답을 분리한다. 이 계약은 특정 detector나 threshold의 성능을 보장하지 않는다.

## 신뢰 경계

| 구분 | 허용 데이터 |
|---|---|
| 탐지 입력 | CU/F1/N2/eBPF에서 수집한 메시지 종류·방향·RAN UE ID·시각·context 생성/해제 |
| 사후 oracle | UE 원문, `attacker_truth.jsonl`, Open5GS 원문, `contexts.jsonl`, 가입자 fingerprint, `verdict.json` |
| 서비스 효과 | `service.jsonl`의 Registration·PDU·ping 결과 |

탐지 출력이 봉인되기 전에는 oracle을 threshold 선택, 특징 생성, 경보 보정에 사용하지 않는다.
IMSI·SUPI·SUCI 원문과 가입자 키는 탐지 입력과 결과에 남기지 않는다.

## 관측할 메시지 수명

```text
RRCSetupComplete
→ InitialUEMessage / Registration Request
→ Authentication Request
→ Authentication Response 또는 Authentication Failure 없음
→ timeout 또는 context release
```

KPM의 RRC 성공 카운터만으로는 공격 연결도 정상 Setup 성공으로 집계되므로 충분하지 않다.
Authentication Request와 Response/Failure를 구분할 수 있는 F1/N2 NAS 메타데이터 또는
동등한 eBPF 계측이 필요하다. NAS 원문 payload를 보존할 필요는 없다.

## 권장 특징

- 관측창별 `Authentication Request - (Response + Failure)` 미매칭 수
- 활성 pre-auth context 추정치와 피크
- SetupComplete 이후 인증 미완료 context의 수명
- 새 RAN UE context와 `InitialUEMessage` 생성률
- timeout/release 비율과 control 대비 변화량

## 라벨과 시간 경계

- `control`: 같은 가입자·프로세스·시작 간격에서 Authentication Response를 정상 제출한다.
- `attack_mechanism`: UE 정답과 exact join된 Authentication Request에 Response/Failure가 없다.
- `resource_accumulation`: 공격 가입자 수 이상의 pre-auth context가 동시에 존재한다.
- `service_effect`: 별도 witness의 Registration·PDU·ping 실패다. 기전 라벨과 독립이다.

탐지기는 자체 관측 시각만 사용한다. 실행 후 oracle의 context 생성·해제 시각과 조인해
정탐·오탐·탐지 지연과 활성 context 추정 오차를 계산한다.

## detector 출력 최소 필드

```json
{
  "schema": "auth-timeout.detection.v1",
  "run_id": "RUN_ID",
  "detector_id": "NAME@VERSION",
  "window_start_realtime_ns": 0,
  "window_end_realtime_ns": 0,
  "alert_realtime_ns": null,
  "active_pre_auth_estimate": 0,
  "threshold": 0,
  "input_manifest_sha256": "64자리 SHA-256"
}
```

`alert_realtime_ns`는 경보가 없으면 `null`이다. threshold는 control을 보기 전에 고정하거나
별도 학습 집합에서 정하며 attack 결과를 본 뒤 바꾸지 않는다.

## 평가

최소 보고값은 control 오경보 수, attack 정탐 여부, 첫 공격 context부터 경보까지의 지연,
피크 활성 context 추정 오차다. 현재 p5 결과는 탐지 입력과 oracle 생성까지만 검증했으며,
특정 detector의 정탐·오탐·지연 수치는 아직 없다.
