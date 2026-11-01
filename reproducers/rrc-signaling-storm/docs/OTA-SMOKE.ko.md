# 차폐 OTA 상호운용 스모크 게이트

이 문서는 팀 소유 RF 차폐 테스트베드에서 정상 UE 기준선을 먼저 확인한 뒤 RRCSetupComplete 미전송형
재현기를 올리는 **실행 순서와 중단 조건**만 정한다. 장비별 명령과 RF 수치는 팀
inventory가 확정된 뒤 채운다. 현재 `rss-run`·`rss-build`·`rss-doctor`는 ZMQ 전용이며,
`DEVICE`만 바꿔 이 절차를 실행하지 않는다.

## 현재 블로커

다음 값이 모두 실물과 대조되기 전에는 G1 이후로 진행하지 않는다.

- DU와 UE endpoint별 SDR 모델, local serial, 호스트, RF port·채널·안테나
- DU/OCUDU와 OAI UE의 hardware backend 및 driver·firmware 버전
- clock source, time source, master clock rate, sample rate
- endpoint별 TX/RX gain 상한
- cable·attenuator·combiner 연결도와 각 감쇠값
- 차폐 밖 누설 합격 임계값, 계측기, 측정 위치·절차
- 코어에 별도 등록된 attack/witness 가입자 alias와 서로 다른 profile임을 확인한 기록
- 독립 정상 witness가 쓸 SDR·프로세스·RF 경로

IMSI, K, OPc 같은 가입자 비밀값은 산출물에 기록하지 않는다. serial도 공유 산출물에는
alias 또는 hash만 두고, 실제 값은 접근 제한된 inventory에 둔다.

## G0 manifest 검사

템플릿을 로컬 전용 파일로 복사해 비밀값 없는 초안을 채운다. 그 초안과 실물을 서로
다른 두 사람이 대조한 뒤 `physical_crosscheck_complete`, 승인자·승인 시각을 기록하고
마지막으로 validator를 실행한다. 실제 inventory는 `.gitignore` 대상이며 저장소에
올리지 않는다.

```bash
cp conf/ota-inventory.example.json conf/ota-inventory.json
# 두 사람이 실물 대조하고 승인 필드를 기록한 뒤:
python3 analysis/validate_ota_inventory.py conf/ota-inventory.json
```

검사기는 RF 장비를 탐색하거나 송신하지 않는다. 필수값·세 endpoint 역할·서로 다른
serial hash·DU↔attack/witness RF 경로와 감쇠 합계·누설 기준·서로 다른 가입자 alias·
독립 witness·서로 다른 승인자 2명을 확인한다. `IMSI`, `K`, `OPc`, raw serial 같은
키가 어디에든 있으면 값은 출력하지 않고 실패한다.

exit 0은 **manifest 구조가 완전하다**는 뜻뿐이다. 실물과의 2인 대조를 자동 입증하지
않고 G1 TX-off의 장치 발견·driver·firmware·clock lock 확인도 대신하지 않는다.

## Fail-closed 게이트

| 게이트 | 작업 | 통과 증거 | 즉시 중단 조건 |
|---|---|---|---|
| G0 inventory | 초안 작성 → 필수값·소유권 2인 실물 대조 → 승인 기록 → validator 최종 통과 | 누락 없는 inventory, 서로 다른 승인자·시각 | validator 실패, 값 누락, 장비/가입자 소유권 불명 |
| G1 TX-off | 송신을 비활성화한 채 model·serial·driver·clock lock 탐색 | endpoint별 발견값과 inventory 일치 | 예상 밖 장치, serial 중복, clock unlock |
| G2 RF 안전 | 차폐 닫힘·배선·감쇠를 확인하고 승인된 최소 gain으로 누설 측정 | 임계값·실측값·계측기·위치·gain 기록 | 차폐 열림, 감쇠 불일치, 누설 임계 초과 |
| G3 UE1 baseline | attack off, 정상 UE 1대 | sync, RRCSetupComplete, Registration, PDU, ping, F1 가시성 | crash, 가입 실패, 예상 밖 외부 RF |
| G4 UE2 baseline | 서로 다른 profile·독립 RF의 정상 UE 2대 동시 실행 | 두 UE 각각 Registration/PDU/ping, subscriber distinct 확인 | 한 UE가 다른 UE를 대체, 공유 profile/경로 |
| G5 matched control | 공격 바이너리·배치 그대로 `ENABLE=0` 반복 | 사전 고정 횟수의 유효 control, 시계·캡처 품질 | control 불안정, clock/capture 근거 없음 |
| G6 attack on | G5와 같은 설정에서 RRCSetupComplete 미전송형만 활성화 | 정답 라벨, 미완료 컨텍스트, 독립 witness 서비스 | 누설/온도/장치 오류, stop 조건 도달 |

한 게이트의 실패를 다음 게이트의 공격 결과로 재분류하지 않는다. G3~G5가 안정적이지
않으면 G6는 실행하지 않는다. 누설 임계 초과 시 UE와 DU 송신을 먼저 중지하고, 로그
수집은 그 뒤에 한다.

## 실행 기록

각 run은 `run_id`와 다음 값을 함께 남긴다.

- software: OAI·OCUDU commit, patch와 binary SHA-256, driver·firmware version
- cell: band, ARFCN/frequency, duplex, SCS, bandwidth/PRB, TDD pattern
- endpoint: 장비 alias, serial hash, RF port/channel, clock/time source와 lock 상태
- radio: sample/master-clock rate, TX/RX gain, cable·attenuator path
- safety: shield closed, leakage threshold/result/unit/instrument/location, gate verdict/reason
- subscriber: attack/witness alias, `distinct_profiles` boolean, witness assignment
- time: host별 sync method, offset, uncertainty, 측정 시각과 evidence SHA-256
- capture: source, 시작·종료, drop/loss와 계산 근거
- verdict: gate, valid/invalid, stop reason, 정상 UE 단계별 결과

정답 JSONL은 탐지기 입력으로 주지 않고 채점 단계에서만 조인한다. `(run_id, ue, seq)`와
시각 창을 기본 attempt key로 쓰며, 가능한 경우 TC-RNTI·초기 UE identity를 추가한다.
시계 offset 또는 uncertainty가 없으면 호스트 간 탐지·대응 지연은 `unscorable`이다.

## G6 사전 고정 항목

공격 실행 전에 다음을 manifest에 고정한다.

- control/attack 실행 수와 순서, adaptive extension 금지 여부
- 공격 노브와 유일하게 바뀌는 변수
- 최대 지속시간·시도 수·점유 상한·온도·누설 stop 조건
- 정상 UE 성공 기준과 허용 손실·지연 기준
- 미완료 컨텍스트의 pre/during/post 관측 창
- 대응을 시험한다면 action 요청·ACK가 아니라 컨텍스트 감소와 정상 UE 회복 기준

현재 승인된 수치가 없으므로 이 문서는 gain, 감쇠, 누설 임계값을 예시로도 제공하지
않는다. 실제 값이 확정되면 별도 OTA runner/doctor가 model·serial을 고정하고 G0~G2가
실패한 상태에서는 송신 프로세스를 시작하지 않도록 구현한다.
