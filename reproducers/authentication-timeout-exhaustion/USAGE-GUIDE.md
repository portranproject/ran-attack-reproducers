# Authentication Response 미전송형 연결 컨텍스트 고갈(NAS 고갈) 사용 가이드

## 1. 현재 상태

OAI UE 패치, 다중 UICC 가입자 중복 검사, OCUDU·Open5GS 로그 조인, direct multi-cell ZMQ
phase driver, 단일·캠페인 판정과 SHA-256 봉인을 구현했다. p5에서 정상 대조군과 인증 응답
미전송 기전, 공격자 6명의 동시 pre-auth 컨텍스트를 확인했다. 이 부하에서는 witness 서비스
거부가 발생하지 않았다. 별도 한 셀 10 UE 경로는 실제 TeleRAN→production detector
matched 3/3을 통과했다. 서비스 거부는 완료 조건으로 요구하지 않는다.

## 2. 전제

- 팀 소유 p5 ZMQ 또는 RF 차폐 환경에서만 실행한다.
- OCUDU·Open5GS 소스, timer, capacity는 수정하지 않는다.
- OAI 기준 커밋은 `6d6782b48484efd935c14e834832032743f9b138`이다.
- 공격자마다 서로 다른 정상 테스트 가입자를 사용한다.
- `runs/`, 가입자 설정, 키, 실제 `auth-timeout.conf`는 Git에 올리지 않는다.
- 기본 자원은 CU 1대+DU 1대다. 서비스 거부를 만들기 위한 분산 DU 증설은 운영 범위가 아니다.

## 3. UE 빌드

```bash
git -C /root/OAI worktree add --detach /root/OAI-auth-timeout-w38 \
  6d6782b48484efd935c14e834832032743f9b138
OAI=/root/OAI-auth-timeout-w38 ./bin/auth-timeout-build
```

`OAI_AUTH_TIMEOUT_WITHHOLD=1`일 때만 Authentication Request 처리를 생략한다. 환경변수가
없거나 `1`이 아니면 기존 OAI 동작 그대로 Authentication Response를 보낸다.

## 4. 가입자 manifest

공격자 설정 하나 이상에 합계 두 개 이상의 `uiccN`과 별도 witness 설정을 입력한다. 출력에는
IMSI 원문이 아니라 SHA-256 fingerprint, 프로세스 번호, UE 번호와 설정 파일 해시만 남는다.

```bash
python3 analysis/profile_manifest.py \
  --attacker /root/auth-timeout-secrets/attacker-01.conf \
  --attacker /root/auth-timeout-secrets/attacker-02.conf \
  --witness /root/auth-timeout-secrets/witness.conf \
  --output /root/auth-timeout-secrets/profiles.manifest.json
```

IMSI가 중복되거나 `uiccN` 번호가 0부터 연속되지 않거나 각 section의 IMSI가 정확히 하나가
아니면 중단한다. witness 설정은 `uicc0` 하나만 허용한다.

## 5. p5 phase driver 계약

기본 `PHASE_DRIVER`는 `bin/auth-timeout-p5-phase`다. 공격자 프로세스 N개와 witness를
서로 다른 direct ZMQ endpoint로 실행하며, 각 공격자 설정의 UICC 수를 `--num-ues`로
전달한다. 시도 사이에는 DU·UE 세트를 재기동한다. 실행기는
다음 환경변수를 전달한다.

- `AUTH_TIMEOUT_RUN_DIR`, `AUTH_TIMEOUT_RUN_ID`, `AUTH_TIMEOUT_MODE`
- `AUTH_TIMEOUT_WITHHOLD`: control `0`, attack `1`
- `AUTH_TIMEOUT_ATTACKER_COUNT`, `AUTH_TIMEOUT_ATTACKER_PROCESS_COUNT`, `AUTH_TIMEOUT_START_INTERVAL_MS`
- `AUTH_TIMEOUT_REGISTRATION_LIMIT_MS`

driver는 gNB·코어 소스·timer·capacity를 바꾸지 않고 다음 원문을 run 디렉터리에 만든다.
attack은 run 전용 arm 파일이 존재하는 동안만 Response를 억제하고 recovery 전에 해제한다.

| 파일 | 필수 내용 |
|---|---|
| `attacker_truth.jsonl` | 가입자 fingerprint별 억제 횟수와 Response 제출 여부 |
| `contexts.jsonl` | fingerprint, RAN/AMF UE NGAP ID, RRC·InitialUE·Auth Request, Auth Response/Failure 수, 생성·해제 시각 |
| `service.jsonl` | 같은 witness 프로필의 baseline, impact 5회, recovery 5회 등록·PDU·ping 결과와 시각 |
| `process.json` | crash와 forced kill 수 |
| `ue.log`, `cu.log`, `amf.log` | 판정 전 원문 |

각 공격 UE 로그와 `cu.log`, `amf.log`를 모은 뒤 다음처럼 exact join 결과를 만든다.

```bash
python3 analysis/normalize_p5.py "$AUTH_TIMEOUT_RUN_DIR" \
  --attacker-log "$AUTH_TIMEOUT_RUN_DIR/attacker-01.log" \
  --attacker-log "$AUTH_TIMEOUT_RUN_DIR/attacker-02.log" \
  --attacker-log "$AUTH_TIMEOUT_RUN_DIR/attacker-03.log"
```

`--attacker-log`은 가입자별이 아니라 공격자 **프로세스별** 하나이며, 순서는 manifest의
`process_index`와 같아야 한다. 정규화기는 로그 안의 `ue=N` 마커를 각 UICC fingerprint에
다시 연결한다. 실제
OCUDU 로그 형식의 CU UE ID·RAN UE NGAP ID·AMF UE NGAP ID와 Open5GS의 SUCI를 조인하며,
하나라도 없거나 중복되면 `attacker_truth.jsonl`과 `contexts.jsonl`을 만들지 않는다.
나머지 필드 계약은 `tests/test_export_labels.py`와 `analysis/export_labels.py`를 따른다.
driver가 실패하거나 필수 원문이 없으면 실행기는 판정하지 않는다.

## 6. 설정과 실행

```bash
cp conf/auth-timeout.conf.example conf/auth-timeout.conf
chmod 600 conf/auth-timeout.conf
```

먼저 정상 대조를 실행한다.

```bash
AUTH_TIMEOUT_CONF=conf/auth-timeout.conf \
  ./bin/auth-timeout-run control -n smoke-control -e 0
```

공격은 명시적으로 켠다.

```bash
AUTH_TIMEOUT_CONF=conf/auth-timeout.conf \
  ./bin/auth-timeout-run attack -n smoke-attack -e 1
```

서비스 영향까지 별도로 평가할 때만 고정 순서 3세트 campaign을 사용한다.

```bash
AUTH_TIMEOUT_CONF=conf/auth-timeout.conf \
  ./bin/auth-timeout-campaign -n auth-timeout-YYYYMMDD -e 1
```

캠페인은 재현 도구 완료의 필수 절차가 아니다. 실행할 경우 각 세트의 control 서비스 표본에서
`max(10초, control 최장 정상 등록시간 × 3)`을 계산해 바로 다음 attack의 `-t` 값으로
고정한다. attack 결과를 보고 제한시간을 변경하지 않는다.

### production L3-01-O 한 셀 자격 실행

`auth-stall-cell-run`은 OAI 프로세스별 shared virtual RU 2개를 broker로 한 DU·셀에 합친다. 실제
가입자 설정 목록은 Git 밖에 두고 예제 설정을 복사해 경로만 채운다.

```bash
cp conf/auth-stall-cell.conf.example conf/auth-stall-cell.conf
chmod 600 conf/auth-stall-cell.conf

AUTH_STALL_CELL_CONF=conf/auth-stall-cell.conf \
  ./bin/auth-stall-cell-run control -n auth-cell-control -e 0

AUTH_STALL_CELL_CONF=conf/auth-stall-cell.conf \
  ./bin/auth-stall-cell-run attack -n auth-cell-attack -e 1
```

공격 runner는 gNB·코어·detector를 수정하지 않으며, 공격 모드에서 각 UE의
Authentication Response 제출만 생략한다. 공통 `tools/p5-live-e2e`로 감싸면 같은 실행
시간창의 F1/N2를 TeleRAN과 production detector에 전달하고 dashboard 수락까지 채점한다.

## 7. 판정 읽기

`verdict.json`은 세 수준을 분리한다.

- `mechanism_reproduced=true`: Authentication Request 조인, Response/Failure 미전송 확인
- `resource_accumulation_observed=true`: 공격자 수 이상의 pre-auth 컨텍스트 동시 점유
- `witness_denial_observed=true`: 선택 효과인 정상 witness 서비스 거부 확인

기전·탐지 입력 재현에는 앞의 두 값과 crash/forced kill 0을 사용한다. 기존 최상위
`passed`는 세 번째 서비스 거부까지 요구하는 보수적 게이트이므로 `false`여도 앞의 두 기전
필드가 자동으로 무효가 되지는 않는다. `evidence_manifest.json`은 원문 해시,
`<campaign>-campaign.json`은 선택적인 서비스 영향 3세트 판정이다.

## 8. 탐지 입력 분리

정식 입력·oracle·출력 필드 계약은 [탐지 계약](DETECTION-CONTRACT.md)을 따른다.

탐지기에는 CU/F1/N2/eBPF 텔레메트리의 메시지 종류·방향·RAN UE ID·시각·context
lifecycle만 입력한다. UE의 `attacker_truth.jsonl`, Open5GS 원문, 가입자 fingerprint,
`contexts.jsonl`, `verdict.json`은 탐지 출력이 봉인된 뒤 정답 비교에만 사용한다.

권장 탐지 특징은 다음과 같다.

- 관측창별 `Authentication Request - (Response + Failure)` 미매칭 추정치
- `RRCSetupComplete` 뒤 인증 완료 이벤트가 없는 context의 동시 수와 수명
- 새 RAN UE context·`InitialUEMessage` 생성률과 timeout/release 비율
- control 대비 pre-auth context 피크와 상위 percentile 수명 변화

탐지 출력에는 관측 시작·종료 시각, 경보 시각, threshold, 활성 context 추정치와 입력 원문
SHA-256을 남긴다. 이후 oracle과 조인해 정탐·오탐·탐지 지연을 채점한다. production
detector 기본 설정의 p5 표본에서는 공격 3/3 정탐, 대조군 예상 공격 경보 0/3이었다.

## 9. 운영 범위

- 검증된 기본 프로필: direct 4-cell, 공격자 3프로세스×2 UICC, witness 1프로세스
- 확인 결과: Response 억제 30건, exact context 30개, 피크 동시 6개
- production 자격 프로필: 한 셀 2프로세스×5 UE, L3-01-O matched 3/3
- 미관측: 정상 witness 서비스 거부, 기지국 전체 마비
- 제외: 정식 증거로 봉인되지 않은 20가입자·5-lane 분산 진단

탐지 입력 계약의 결함을 수정하는 경우가 아니면 서비스 거부를 만들기 위한 추가 증설이나
timer/capacity 변경으로 이 모듈을 다시 열지 않는다.
