# 사용 가이드 — RRC signaling storm 재현기

> 상태: **2026-11-02 동결** (단독 `rss-run` 기준). 정상 UE 5대 통합 E2E 실행은 `./ctl.sh same-cell run rrc-storm` 또는 `./ctl.sh same-cell campaign l3-live`를 사용하며, p1 6/6 결과는 [p1 clean-origin L3 7종 E2E](../../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)에 있다.
>
> 용도: 격리된 팀 소유 ZMQ 테스트베드에서 RRC 분석기의 입력·정답·판정을 분리해 평가
>
> 비용/안전: RF 차폐 또는 가상 RF 안에서만 사용하고, 모든 공격 런에 유한한 `-d`를 둔다.

## 명칭 원칙

이 문서의 시나리오명은 3GPP가 정한 공격 분류명이 아니다. 처음 보는 사람도 중단
지점을 알 수 있도록 3GPP RRC 메시지명으로 동작을 설명한다.

| 현재 이름 | 동작 |
|---|---|
| **RRCSetupComplete 미전송형** | `RRCSetup`을 수신하고 HARQ ACK한 뒤 `RRCSetupComplete`를 보내지 않음 |
| **RRCSetupRequest 후 중단형** | `RRCSetupRequest` 송신이 MAC에서 확인되면 `RRCSetup`을 기다리지 않고 절차를 중단 |
| **RRCSetup HARQ-ACK 억제형** | `RRCSetup`에 대한 HARQ ACK를 억제해 재전송·max-retx 경로를 유발 |

과거 label v1과 봉인 증거의 기계 이름은 재현성을 위해 바꾸지 않는다. 새 문서에서는
아래 이름을 시나리오명으로 사용하지 말고, 기존 자료를 읽을 때만 다음처럼 해석한다.

| 과거 호환 이름 | 현재 설명형 이름 |
|---|---|
| `scenario="A"`, `canonical_a*` | RRCSetupComplete 미전송형. `canonical_a=true`는 DU ACK까지 확인된 양성 |
| `scenario="A_early"`, `canonical_msg3*` | RRCSetupRequest 후 중단형 |
| `scenario="A_no_ack"` | RRCSetup HARQ-ACK 억제형 |
| `Mode A` / `모드 A` | 기본 cleanup 프로필 |
| `Mode B` / `모드 B` | 용량 12·보유 7초 진단 프로필 |

과거 run ID·경로·JSON 필드와 체크섬으로 봉인된 판정문은 수정하지 않는다. 상세 예외는
[과거 증거 명칭표](../../../artifacts/LEGACY-NAMES.md)에 정리했다.

## 1. 이 도구로 할 수 있는 것

이 도구의 운영 목적은 **기지국 마비 시연**이 아니라 다음 두 종류의 분석기 입력과
정답 라벨을 반복 생성하는 것이다.

| 시나리오 | 절차 | 분석 목적 | 현재 검증 수준 |
|---|---|---|---|
| RRCSetupComplete 미전송형 | `RRCSetup` 수신·HARQ ACK 뒤 `RRCSetupComplete` 생략 | 주 분석 시나리오, exact ACK 기반 정답 | 기전 성립. 기본 cleanup에서 서비스 거부는 실패 |
| RRCSetupRequest 후 중단형 | MAC-confirmed `RRCSetupRequest` 뒤 `RRCSetup`을 기다리지 않고 중단 | F1 가시성 경계·고부하 시험 | 최대 부하와 좁은 service-off/on 상관 성립 |
| attack-off | 정상 접속 완료 | 파이프라인·오탐 대조 | Registration/PDU/ping까지 확인 |

현재 가장 강한 기본-cleanup 실측은 다음과 같다.

- RRCSetupRequest 후 중단형 D6F48: attacker `RRCSetupRequest` **77.408/s**, DU provisional Create
  **73.338/s**, cleanup **34.209/s**. 완전한 5초 창 12/12에서 앞의 두 비율이
  cleanup보다 높았다.
- 같은 런의 admitted Setup은 cleanup과 평형이었고, 점유 피크는 **95/96**이었다.
  즉 지속 포화는 아니다.
- RRCSetupRequest 후 중단형 실행 중 primary 서비스 실패와 stop 뒤 **별도** prelaunched UE의
  Registration/PDU/ping 회복은 D6F45·46·48에서 **3/3**이었다.
- 동일한 8-endpoint attack-off D6C51은 Registration/PDU와 ping **303/303**에
  성공했다.
- RRCSetupComplete 미전송형 D6F50은 UE 후보 205건 중 exact DU HARQ ACK와 조인된
  `canonical_a=true` **149건**, 공격자 Msg5 0건을 만들었다. 그러나 공격 중 정상
  UE가 Registration/PDU와 ping **194/195**에 성공했다.

따라서 이 도구는 **RRC storm 분석기 평가용 재현기**로 사용한다. 기본 cleanup에서
30초 지속 포화, 같은 정상 UE의 30초 반복 거부→회복, 기지국 전체 마비, OTA·상용망
DoS는 입증하지 않았다. 인공적으로 정리시간을 늘린 hold32 결과는 진단 자료이며
성공 데이터셋으로 쓰지 않는다.

## 2. 역할과 데이터 격리

한 사람이 여러 역할을 맡더라도 파일 접근 시점은 분리한다.

1. **재현기 운영자**: `rss-run`을 실행하고 raw 정답과 증거를 봉인한다.
2. **분석기 운영자**: F1/eBPF 텔레메트리만 받아 detector를 실행한다.
3. **평가자**: 분석기 출력이 봉인된 뒤에만 ground truth를 열어 채점한다.

분석이 끝날 때까지 분석기에 주면 안 되는 파일은 다음과 같다.

- `run.json`
- `attempts.jsonl`
- `ground_truth*.jsonl`
- OCUDU 내부 DU/CU 진단 로그

분석기에는 opaque `run_id`, cell 식별자, 평가 시작/종료 신호만 전달한다. 시나리오
매핑은 운영자가 따로 보관한다. detector는 경보 창뿐 아니라 normal/unknown으로 판단한
모든 창을 기록한다.

## 3. 사전 게이트

현재 runner는 **ZMQ 전용**이다. `DEVICE`만 바꿔 OTA에서 실행하지 않는다.

운영자는 먼저 `conf/rss.conf`에 OAI·UE 설정·DU 재기동 명령을 채우고 다음을 확인한다.

- `ENABLE=0`을 파일 기본값으로 유지한다.
- CU↔AMF, CU-UP, DU↔CU F1, DU↔UE ZMQ가 준비돼 있다.
- gNB 소스와 기본 cleanup/RLF는 바꾸지 않는다.
- DU ACK 확인 RRCSetupComplete 미전송형 라벨이 필요하면 current-run DU FAPI 로그를 위해 `ODU_LOG`와
  `ODU_SECTOR_ID`를 설정한다. 전체 누적 로그를 나중에 잘라 조인하지 않는다.
- control과 attack의 OAI commit, UE 바이너리, RSS patch, runner, CU/DU 설정 해시를
  보존한다.
- detector git SHA, 설정, threshold, 평가창, capture-drop counter를 공격 전에
  고정한다.
- 서로 다른 호스트의 latency를 평가하려면 측정 전후 clock offset과 uncertainty를
  보존한다. 둘 중 하나라도 없으면 cross-host latency는 `null/unscorable`이다.

```bash
cd /path/to/ran-attack-reproducers/reproducers/rrc-signaling-storm
cp -n conf/rss.conf.example conf/rss.conf
$EDITOR conf/rss.conf
bin/rss-doctor
```

`rss-doctor`에 `[FAIL]`이 하나라도 있으면 실행하지 않는다. 경고는 이유와 수용 여부를
run note에 남긴다.

## 4. 최소 평가 캠페인

아래 네 런은 같은 cell·코어·CU/DU 설정·UE 바이너리에서 수행한다. 명령의 `X101`~
`X104`는 예시이므로 캠페인마다 새 opaque ASCII ID로 바꾸되, 두 번째 글자에 `O`를
쓰지 않는다. 기존 결과 경로는 재사용하거나 덮어쓰지 않는다.

분석기 운영자는 각 명령 전에 F1/eBPF capture와 detector를 시작하고, 종료 뒤 detector 출력의
SHA-256을 먼저 고정한다.

```bash
# 1. 사전 정상 대조: RRC뿐 아니라 Registration/PDU/TUN/ping도 확인
bin/rss-run -e 0 -u 1 -d 30 -n X101

# 2. 주 시나리오: RRCSetup ACK 후 RRCSetupComplete 생략
bin/rss-run -e 1 -u 2 -M 1 -A 1 -r 1 -i 0 -d 120 \
  -n X102

# 3. 선택 시나리오: RRCSetupRequest 후 중단, F1 가시성/고부하 경계 시험
bin/rss-run -e 1 -u 2 -M 0 -A 1 -r 1 -i 0 -d 120 \
  -n X103

# 4. 사후 정상 대조
bin/rss-run -e 0 -u 1 -d 30 -n X104
```

`-i 0`은 무선 경로가 허용하는 최대 속도이지 0ms 주기 보장이 아니다. rate sweep은
사전에 정한 `-i`별로 새 run을 만들고, 설정값이 아니라 JSONL의 wall-clock
`attempt_start`/`msg3_tx`로 실효율을 계산한다. `-r 1`은 gNB의 RRCReject waitTime을
지키는 비교 기준이다.

RRCSetupComplete 미전송형을 분석기 합격 판정의 주 시나리오로 사용한다.
RRCSetupRequest 후 중단형은 별도 변종이며 F1-only 관측에서 두 변종을 항상 구별할 수
있다고 가정하지 않는다.

## 5. 런 산출물과 정답

운영자는 각 run directory에서 최소한 다음을 보존한다.

| 파일 | 의미 |
|---|---|
| `run.json` | 실행 계보·노브·시작 시각 |
| `run_stop.json` | 종료 이유, runner 유효성, label/seal 상태 |
| `attempts.jsonl` | append-only UE raw 정답 이벤트. 탐지기 입력 금지 |
| `ground_truth.jsonl` | `(run_id, ue, seq)`별 정규화 정답 |
| `odu.log`, `du_log_slice.json` | current-run exact DU ACK 조인 증거 |
| `evidence_manifest.json` | 핵심 파일 크기와 SHA-256 |
| `ue.log`, `ue_redaction.json` | 정제된 실행 로그와 민감행 검사 결과 |

종료 직후 운영자가 검증한다.

```bash
RUN_DIR=/root/rss-runs/X102
python3 analysis/evidence_manifest.py verify "$RUN_DIR"

# RRCSetupComplete 미전송형에서 exact DU ACK가 포함된 최종 라벨을 요구할 때
python3 analysis/evidence_manifest.py verify "$RUN_DIR" --require-matched
```

`run_stop.json.valid=true`는 실행·증거가 유효하다는 뜻이지 공격 효과나 DoS 성공을
뜻하지 않는다.

### RRCSetupComplete 미전송형 양성 정답

채점 양성은 `ground_truth.jsonl`의 `canonical_a=true`만 사용한다. 이는 UE scheduler의
ACK tuple과 current-run OCUDU FAPI `UCI.indication`의 유일한 `(RNTI, frame, slot)`
ACK가 exact join된 경우다. `canonical_a=null`은 음성이 아니라 **unknown**이며 FN
분모에 넣지 않는다. `ConRes CE ACKed` 문자열은 ACK 증거가 아니다.

### RRCSetupRequest 후 중단형 양성 정답

UE `msg3_tx`만 있으면 후보일 뿐이다. current-run CU slice의 같은 TC-RNTI
`RRCSetupRequest`와 양쪽에서 유일하게 조인된 `canonical_msg3_only=true`만 최종
양성이다.

```bash
RUN_DIR=/root/rss-runs/X103
CU_RUN_SLICE=/path/to/current-run-cu.log
python3 analysis/export_labels.py \
  "$RUN_DIR/run.json" "$RUN_DIR/attempts.jsonl" "$CU_RUN_SLICE" \
  > "$RUN_DIR/ground_truth-cu.jsonl"
```

현재 manifest replay는 RRCSetupComplete 미전송형의 DU ACK 조인까지만 포함한다.
RRCSetupRequest 후 중단형에서 파생한 artifact는 CU slice, exporter, 출력 파일의
SHA-256을 별도로 보존한다.

## 6. 분석기에 입력할 F1/eBPF 신호

최소 lifecycle은 다음과 같다.

- Initial UL RRC Message Transfer의 `RRCSetupRequest`: 접속 시작
- DL RRC Message Transfer의 `RRCSetup`: setup 발행
- UL RRC Message Transfer의 `RRCSetupComplete`: 정상 완료
- UE Context Release Request/Command/Complete와 `RRCReject`: 미완료 정리·거절

가능하면 gNB-DU/CU UE F1AP ID로 lifecycle을 추적한다. 오프라인 정답 조인은
`(tc_rnti, ue_identity, 검증된 시간 창)`을 함께 쓰며, 시각만으로 1:1 조인했다고
주장하지 않는다.

권장 feature 후보는 다음과 같다. 저장소에는 승인된 운영 threshold가 없으므로 운영자가
정상 대조군으로 보정하고 공격 전에 고정해야 한다.

- `request_rate`, `setup_rate`, `completion_rate`
- delay-aware completion ratio
- open/incomplete context count와 age p50/p95
- timeout/release/reject rate
- F1 객체 생성 실패 또는 empty DU-to-CU container에 따른 reject rate(관측 가능한 경우)

수집은 1초 atomic bin으로 보존하고 5초 rolling window부터 비교할 수 있다. 5초는 D6
실험 비교창이지 검증된 탐지 threshold가 아니다. 분모가 0인 창은 normal이 아니라
unknown으로 둔다.

E2SM-KPM의 `RRC.ConnEstabAtt/Succ`는 노드 단위 보조 신호다. 최소 보고 주기가 1초이고
개별 UE 순서·미완료 수명을 주지 않으므로 이것만으로 RRCSetupComplete 미전송형을
확정하지 않는다.

### 명시해야 할 blind spot

DU capacity 앞에서 F1AP 객체가 생기기 전에 잘린 요청은 F1/CU detector에 보이지 않을
수 있다. D6F48에서도 offered/provisional 초과분 상당수가 Setup admission 전에 즉시
거절됐다. capture drop counter까지 없으면 per-attempt recall이나 전체 coverage를
완전하다고 주장하지 않는다.

## 7. 분석기 출력 계약과 채점

탐지기는 모든 평가창을 `detections.jsonl`에 append-only로 기록한다.

```json
{"schema_version":1,"type":"detection","run_id":"X101","detection_id":"d-17","detector":{"name":"rss-rule","version":"git-sha"},"window_start_ns":1791882034000000000,"window_end_ns":1791882035000000000,"t_decision_ns":1791882035100000000,"decision":"attack","score":0.91,"threshold":0.8,"scope":{"cell":"n78-cell-1","tc_rnti":null},"clock_host":"cu","evidence_ref":"f1-capture:packet-120-190"}
```

필수 항목은 `run_id`, detector 이름·버전, start-inclusive/end-exclusive 평가창, 판단
시각, `attack|normal|unknown`이다. score가 없는 규칙 탐지기는 score와 threshold를
`null`로 둔다.

최소 캠페인 유효 조건은 다음과 같다.

- 사전·사후 control에서 Registration/PDU/TUN/ping 성공
- attack run의 runner·label export·민감정보 scan·manifest 검증 성공
- exact DU ACK로 확인한 최종 양성 라벨이 1개 이상
- detector와 capture가 중단되지 않았고 capture/drop 상태가 기록됨
- crash, 비정상 강제 종료, clock 증거 누락을 숨기지 않음

분석기 출력 파일을 먼저 hash/seal한 뒤 blind를 해제한다. valid attack의 attack 판정과
valid control의 비공격 판정을 비교해 window/run 단위 TP·FP·FN을 계산한다. host 간
latency는 동일 clock이거나 offset+uncertainty 증거가 있을 때만 계산한다. capture gap,
정답 `null`, 분모 0은 억지로 0으로 채우지 않고 unknown/unscorable로 둔다.

## 8. 사용 금지 경로와 금지 주장

- `rss-broker-witness`의 초기 5-UE 개발용 설정은 서비스 acceptance에 쓰지 않는다. 5-UE 대조군 15회 중
  5/5 sync는 5회, 의미상 유효 control은 3회뿐이었고 유효 런의 ping loss도
  0.833333%~93.5484%였다. (참고: 이후 `ctl.sh same-cell` 자격 경로는 `rss-broker-witness`에 `BROKER_WITNESS_MULTI_RU=1`과 `workloads/normal-ue/tools/same_cell_broker.py`의 독립 virtual RU 5개 조합을 적용해 p1 L3-01-V 6/6을 통과했다.)
- 로컬 `BROKER_SAME_WITNESS_CYCLE` 구현은 단위 테스트만 있는 **p5 미실측 초안**이다.
  운영 기능이나 30초 동일-UE 회복 증거로 소개하지 않는다.
- hold32의 CU 200·witness 17/17 거절 결과는 기본 cleanup 공격 성공으로 쓰지 않는다.
- `offered > cleanup`, 높은 attempt 수, `run_stop.valid=true` 중 하나만으로
  지속 포화나 정상 사용자 DoS를 라벨링하지 않는다.
- `RRCSetupComplete`만으로 Registration/PDU 서비스 성공을 주장하지 않는다.
- ground truth를 detector feature나 threshold 튜닝 입력으로 주지 않는다.
- F1-only 결과로 RRCSetupComplete 미전송형과 RRCSetupRequest 후 중단형을 완전히
  구별한다고 주장하지 않는다.
- ZMQ 결과를 OTA, 상용 gNB, 외부망으로 일반화하지 않는다.
- 대응기의 action ACK는 효과가 아니다. 공격이 계속되는 동안 미완료 컨텍스트 감소와
  독립 정상 서비스 회복을 별도로 관측해야 한다.

## 9. 종료와 보존

각 캠페인 뒤에는 다음을 확인한다.

1. UE·DU·broker 자식 프로세스가 남지 않았다.
2. 임시 gNB 설정을 원본 해시로 복구하고 재기동해 읽힌 값을 확인했다.
3. detector 출력, F1 capture, run evidence, clock evidence의 SHA-256을 보존했다.
4. p5를 사용했다면 인스턴스 상태가 실제 `stopped`인지 확인했다.
5. raw 정답과 분석기 입력의 접근 권한을 분리했다.

라벨 필드의 정확한 의미는 [LABEL-CONTRACT.md](LABEL-CONTRACT.md), 상세 옵션·파라미터는
[REFERENCE.md](REFERENCE.md), 실행기 요약은 [../README.md](../README.md), 기본 cleanup 원문은
[기본 cleanup D6 증거](../../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md)를
기준으로 한다.
