# Blind DoS 재현 도구 사용 가이드

이 도구는 팀 소유 ZMQ 테스트베드 또는 RF 차폐 환경에서 **현재 유효 48-bit
5G-S-TMSI 재사용형**을 한 번 실행하고, 피해 UE의 실제 서비스 손실까지 독립적으로
판정한다. 외부 망, 전체 식별자 공간 탐색, 다중 표적에는 사용하지 않는다.

## 판정부터 이해하기

`passed`는 공격 메시지가 전송됐다는 뜻이 아니다. 다음 조건이 모두 맞아야 한다.

1. 공격 전 같은 피해 UE의 Registration·PDU session·ping이 정상이다.
2. 공격자 commit 뒤 AMF `InitialUEMessage`에서 표적 5G-S-TMSI와 유효 NGAP ID가 조인된다.
3. 그 identity reach 뒤 기존 피해자의 같은 RAN/AMF UE ID에 상태 변화가 생긴다.
4. 사전에 정한 연속 측정 횟수만큼 같은 피해 UE의 서비스가 실패한다.
5. one-shot 종료 뒤 같은 피해 UE가 제한시간 안에 회복한다.
6. matched control에는 표적 commit·상태 변화·서비스 손실이 없다.

현재 자동 조인은 공격자 JSONL commit, AMF `InitialUEMessage`, 48-bit 표적값,
기존 피해자의 RAN/AMF UE ID와 시각을 사용한다. F1/NGAP pcap도 원문으로 봉인하지만
ASN.1 메시지별 자동 조인에는 아직 사용하지 않는다.

결과 분류는 세 가지다.

| 분류 | 의미 | 자동 재시도 |
|---|---|---|
| `passed` | 해당 control 또는 attack 계약을 모두 만족 | 안 함 |
| `valid-failure` | 실험은 유효하지만 서비스 손실·회복 등 공격 효과 계약이 미달 | 안 함 |
| `infrastructure-invalid` | sync·hook·capture·clock·crash·증거 계약 문제 | 설정한 제한 안에서만 |

`valid-failure`를 반복 실행하거나 N을 줄여 성공으로 바꾸면 안 된다.

## 준비

1. `conf/p5-zmq.conf.example`을 Git 밖의 권한 `0600` 파일로 복사한다.
2. OAI binary·UE profile·broker·CU SSH·DU/CU 설정 경로를 실제 p5 경로로 바꾼다.
3. `CLOCK_*`, `LAB_INVENTORY_SHA256`, 피해자·공격자 profile fingerprint를 채운다.
4. 피해자와 공격자는 서로 다른 팀 가입자이며, CU·DU·Open5GS 타이머·용량·소스가
   기본 inventory와 같은지 확인한다.
5. `ENABLE=0`을 유지한다. 공격은 명령행 `-e 1`이 있을 때만 실행된다.

고정 2-UE 그래프에서는 피해자와 공격자 프로세스를 처음부터 끝까지 유지한다. control도
공격 UE를 `blind.enable=1`로 준비하지만 private 표적 파일을 만들지 않아 Msg3 commit이
0건이다. attack은 피해자 snapshot 뒤 그 파일을 원자적으로 만들어 같은 프로세스의
one-shot만 시작한다. 따라서 프로세스 교체나 broker 재연결이 on/off 차이에 섞이지 않는다.

## 한 phase 실행

먼저 control을 실행한다.

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-run control -n control-001
```

현재 피해 UE 값의 one-shot attack은 두 개의 명시적 스위치가 필요하다.

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-run attack -e 1 -n attack-001
```

각 run은 `run_stop.json`과 `verdict.json`을 읽고, 마지막으로 다음 명령으로 봉인을
재검증한다.

```bash
python3 reproducers/blind-dos/analysis/evidence_manifest.py verify \
  /run/root/attack-001
```

## matched campaign과 `-R N`

기본값은 control→attack 세 쌍이다.

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-campaign -e 1 -n campaign-3 -R 3
```

10/10을 요구하려면 실행 전에 `-R 10`으로 고정한다.

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-campaign -e 1 -n campaign-10 -R 10
```

허용 범위는 3~100이다. `-R 10`은 성공한 세트 열 개를 모을 때까지 무한 재시도한다는
뜻이 아니다. control 또는 attack의 **유효 실패가 하나라도 나오면 즉시 campaign 실패**다.
`INFRA_RETRY_LIMIT`은 인프라 무효 run에만 적용되며 N에 포함되지 않는다. N/N control과
attack이 모두 통과한 경우에만 `campaign_result.json`이 `passed`가 된다.

## 증거 사용

각 run의 핵심 파일은 다음과 같다.

- `run.json`: 고정 threshold·clock·inventory·profile fingerprint
- `attacker_events.jsonl`: 표적 게이트·Msg3 commit·Msg5·NAS 중단 정답
- `victim_service.jsonl`: 공격 전·중·후 Registration·PDU·ping
- `target_snapshot_before.json`, `target_snapshot_after.json`: 표적과 기존 NGAP ID
- `amf.log`, `cu.log`, `du.log`, `ngap.pcap`, `f1ap.pcap`: current-run slice
- `ground_truth.jsonl`: identity reach·기존 피해 컨텍스트 변화·인프라 이벤트
- `verdict.json`, `run_stop.json`, `evidence_manifest.json`: 독립 판정·종료·무결성

탐지기에는 `attacker_events.jsonl`, oracle 표적값, `ground_truth.jsonl`을 입력하지 않는다.
탐지 결과를 먼저 봉인한 뒤 정답과 합쳐 채점한다. 원시 run은 Git에 올리지 않고
정제된 판정·SHA-256·inventory만 `artifacts/`에 게시한다.

## 주장 경계

- `identity_reached`만 있으면 G3 전달 경로 확인이다.
- 기존 피해 binding 변화만 있으면 망 상태 변화이며 서비스 DoS 성공이 아니다.
- matched N/N의 실제 서비스 손실·같은 UE 회복까지 있어야 oracle 보조 단발 G5다.
- 내부 로그 없이 Uu에서 현재값을 획득하지 않았으면 현실적 입력 경로 G6가 아니다.
- 재접속마다 새 값을 얻어 관측창 동안 차단하지 않았으면 지속 Blind DoS G7이 아니다.

무작위 값·만료 값·다른 UE의 현재값은 표적 특이성을 확인하는 대조 입력이다. oracle,
Uu 관측, 추측은 식별자 확보 방식이다. 둘 다 RRC 재수립형·RRC 재개형 같은 별도 절차
변형과 혼동하지 않는다.
