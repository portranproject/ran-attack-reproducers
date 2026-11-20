# p5 단일 셀 공격 hot-swap 검증 (2026-11-13)

> 이 문서는 2026-11-13~16 이력 기록이며, 이후 L3 7종 통합 자격은 [정상 UE README](../README.md) 및 [p1 자격 기록](../../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)이 대체한다. 현행 코드(`tools/same_cell_broker.py`, `bin/same-cell-run`)는 아래 세 지점에서 11-16 절과 다르다: (1) `dl_gate=1.0` 고정이고 `ul_gate`만 `0.0↔1.0` 전환, (2) `auth-timeout`은 `ATTACK_SLOTS=10`, (3) `hot-run` 하위 명령은 없음(`SAME_CELL_EXPERIMENTAL_SWITCH` 분기는 비도달).

## 결론

**모든 공격을 같은 cell ID에서 실행하는 것은 가능하다.** 현재 승인하지 않는 것은 같은
DU·broker·정상 UE를 유지한 채 실행 중인 RF 스트림에 서로 다른 공격 UE 프로세스를 늦게
삽입하는 **무재시작 hot-swap**이다. 공격별 OAI binary·UE 수·endpoint 토폴로지가 달라 전환
시 uplink sample 시간축이 DU와 어긋났고, DU를 재시작하지 않고는 공격 UE baseline과 정상
UE 회복을 함께 만족하지 못했다.

따라서 현재 권장 운영 방향은 다음과 같다. 공격별 정상 UE 5대 결합 자격은 아직 별도 검증이
필요하다.

- 공격 모듈이 바뀌어도 같은 cell ID·PLMN·대시보드 집계 키를 사용한다.
- 모듈 전환 시 broker·UE를 먼저 준비하고 DU를 함께 재시작한다. CU·코어 재시작은 필요 없다.
- 대시보드에는 같은 셀의 연속 실험으로 보이지만 전환 구간의 짧은 gap을 실행 메타데이터로
  표시한다.
- 완전 무재시작 전환은 공통 OAI attack agent 또는 timestamp-aware ZMQ proxy를 별도 개발할
  때 다시 검토한다.

13개 모듈을 모두 RF 셀에 넣어야 하는 것도 아니다. L3-06·AN-01·AN-06a·AN-02·AN-04·AN-07·
AN-08은 `detector-input-emulation`이므로 UE·DU를 실행하지 않는다. 이 7개는 같은 실험의
cell metadata로 재생할 수 있지만, 이를 “같은 셀에 실제 공격을 가했다”고 표현하면 안 된다.

## 검증한 방식과 결과

1. **broker·UE 프로세스 교체**
   - 정상 UE 5대와 대기 공격 슬롯 4개를 같은 broker에 연결했다.
   - 세션 시작은 `normal=5/5`로 통과했으나 대기 UE를 새 프로세스로 교체한 뒤 정상 UE가
     `0/5`가 되었고 120초 안에 회복하지 못했다.
   - GNU Radio REQ source 재생성 뒤 새 UE가 동기화해도 기존 RF 시간축과 합쳐지지 않았다.

2. **런타임 flowgraph 재배선**
   - peer를 교체하지 않고 broker의 source를 다시 연결했다.
   - 실제 경로 변경 전 `lock()/unlock()`만으로도 정상 UE가 재접속 상태로 내려가 제외했다.

3. **정적 selector + DL warmup 후 UL 전환**
   - 모든 경로를 시작 때 고정하고 selector index만 바꿨다.
   - 최종 `p5-unified-v8-20261113/sc-blind-v5`에서 CU PID `5399`, DU PID `39698`은 전환 전후
     유지됐다.
   - Blind 피해·공격 UE는 `Initial sync` 3건, `SIB1 decoded` 2건까지 도달했으나
     `RAR-Msg2 decoded=0`, `Registration Accept=0`으로 victim baseline에 실패했다.
   - 정상 UE 건강 표본은 28개 중 `5/5` 20개였고 이후 `4/5`, `3/5`, `2/5`, `0/5`가 각각
     2개였다. 공격 종료 후 30초 안에 회복하지 못했다.
   - Blind 판정은 `phase_hook_failed`, `infrastructure-invalid`이며 공격 성공 증거가 아니다.

## 증거

원문은 p5 DU에 보존했다.

- 세션: `/root/normal-ue-qualification/persistent/same-cell/p5-unified-v8-20261113/`
- Blind run: `/root/blind-dos-runs-g5/sc-blind-module-v5/`
- `session.json`: `d160a48e7c3d15b7ddbd5a03b5987339db95e09b813480f88c00f8580be37895`
- `broker.log`: `29913bc5285078689707e4ff80354f16a4156ee1a106145356ce5413454ea6f6`
- `normal-health.tsv`: `c219166625cdf577941376babbe6994cd40a888675dd00fabd17f8b4dfe91e4a`
- `phase.stderr`: `e5897e871855b916abb1e666836b019092e3cd1e419620621dd388b8c033bd2c`
- `run_stop.json`: `787af029b01c9613b4e71e3af929152e82838148a962f53bdb858386eb75eaad`

## 남은 선택지

무재시작이 절대 조건이면 기존 runner를 더 감싸는 수준으로는 부족하다. 세 공격 패치를 하나의
상시 OAI UE agent에 통합해 런타임 gate로 전환하거나, OAI ZMQ의 request·timestamp를 이해해
빈 구간과 새 UE sample을 같은 DU 시간축에 맞추는 proxy가 필요하다. 둘 다 공격별 독립 모듈
유지보다 구현·검증 비용과 결합도가 커 현재 1.0 범위에서는 진행하지 않는다.

## 단일 셀 구현 방향 재검토 (2026-11-15)

### 무엇이 실제로 어긋났는가

GNU Radio broker는 복소수 sample 배열을 순서대로 전달할 뿐, 서로 다른 OAI 프로세스의
`openair0_timestamp`를 하나의 공통 시계로 조인하지 않는다. 새 공격 UE는 실행 시점부터 자체
sample cursor를 시작한다. 반면 DU와 정상 UE는 이미 훨씬 앞선 sample을 처리 중이다.

현재 selector 구조는 비선택 attack uplink가 DU와 같은 속도로 계속 소비된다는 보장이 없다.
8초간 downlink를 먼저 공급한 v8 실험도 `Initial sync`와 SIB1까지만 갔고 PRACH/RAR은
성립하지 않았다. 즉 단순 warmup은 주파수·셀 동기를 맞췄을 뿐, attack uplink를 DU의 정확한
slot 위치에 놓지 못했다. 늦은 sample을 미래로 강제로 옮기는 방식도 과거 RU-sharing 실험에서
접속 시도를 급감시켰으므로 해결책으로 쓰지 않는다.

### 우선순위 1 — 공격별 같은 셀 cold-start

가장 작고 검증 가능한 우회는 **공격 모듈 하나를 선택한 뒤 해당 공격 UE·정상 UE·broker를
먼저 준비하고 DU를 함께 시작하는 것**이다.

- cell ID·PLMN·CU·코어·대시보드 집계 키는 모든 모듈에서 동일하게 유지한다.
- 모듈을 바꿀 때만 DU·broker·UE를 재시작하고 CU·코어는 유지한다.
- 공격이 실행되는 동안에는 DU 재시작이 없으므로 정상 대조군→공격→회복을 같은 셀 세션에서
  비교할 수 있다.
- 전환 gap은 숨기지 않고 run metadata와 대시보드에 표시한다.

이 방식은 ZMQ 시간축을 억지로 보정하지 않고 모든 참여자를 sample 0부터 같이 시작시킨다.
RRC storm+정상 UE 5대는 이미 같은 셀에서 실측했다. Blind DoS·상향 DoS·인증 응답 미전송형,
하향 식별자 노출·UE capability는 공격별 cold-start 공존 3/3 자격 검증이 남았다.

### 우선순위 2 — 상시 clocked attack slot

DU 무재시작이 정말 필요하면 timestamp proxy보다 먼저 다음 구조를 시험한다.

1. 사용할 공격 UE를 broker·DU 시작 **전**에 실행한다.
2. attack UE에는 downlink를 처음부터 계속 공급한다.
3. attack uplink도 selector로 끊지 않고 항상 소비한다. standby에서는 고정 이득 `0`, 활성화
   때만 이득 `1`로 바꿔 DU 합산 경로에 넣는다.
4. UE 내부에서는 standby 동안 Random Access 시작만 보류하고, 활성화 때 RA 상태를 초기화해
   새 절차를 시작한다. PHY와 sample cursor는 종료하지 않는다.

핵심은 “나중에 새 stream을 삽입”하는 대신 “처음부터 같은 시계로 흐르던 stream의 기여도만
0→1로 바꾸는 것”이다. 현재 selector의 late insertion보다 변경 범위가 작고, raw sample에서
없어진 timestamp를 사후 추측할 필요도 없다.

먼저 공격 패치가 없는 일반 UE 한 대로 이 gate를 검증한다. 아래 조건을 3/3 통과하기 전에는
Blind DoS 등 공격 모듈을 연결하지 않는다.

- DU·CU·broker PID가 activation 전후 동일
- standby와 activation 전 구간 `channel timeout=0`
- activation 뒤 RAR→RRC→Registration→PDU→ping 성공
- 기존 정상 UE 5/5가 activation 전·중·후 유지
- 종료 뒤 공격 slot만 다시 0으로 만들었을 때 정상 UE 5/5 유지

한계는 공격별 binary를 모두 상시 실행할 CPU 여유와, 공격 상태 기계를 runtime gate로 바꾸는
패치 비용이다. 우선은 **한 세션에 한 공격 binary**로 검증하고, 여러 공격을 한 binary에
합치는 작업은 그 뒤에 판단한다.

### 우선순위 3 — sample-clock ZMQ bridge

공격 UE를 상시 실행할 수 없을 때만 전용 bridge를 검토한다. 일반 GNU Radio selector가 아니라
다음 기능이 필요하다.

- DU stream의 전역 sample counter와 bounded ring buffer 유지
- 새 UE의 첫 downlink sample 위치를 전역 counter에 offset으로 기록
- UE별 송수신 sample 수를 계속 계수하고, uplink를 해당 전역 slot에만 합산
- 늦은 sample 폐기, 빈 구간 zero-fill, buffer overrun을 각각 계측하고 fail-closed 처리
- sample 역행·중복·gap을 run artifact에 기록

현재 ZMQ wire에는 여러 프로세스가 공유하는 명시적 무선 timestamp가 없으므로 bridge는
첫 sample offset과 sample 수로 시간을 추론해야 한다. 이 가정이 OAI의 가변 요청 크기와
PRACH 송신에서도 유지되는지 소스·실측 검증이 필요하다. 따라서 이 방법은 상시 clocked slot보다
구현 위험이 높다.

### OTA에서는 문제가 달라진다

차폐 OTA에서는 DU의 RF 수신 stream이 계속 흐르고, 각 UE가 공중에서 독립적으로 같은 셀의
동기 신호를 잡는다. ZMQ stream 교체 문제는 없어지고 SDR clock·주파수 오차·송신 gain·감쇠가
새 검증 대상이 된다. 따라서 p5 무재시작 proxy를 완성해야만 OTA 단일 셀이 가능한 것은
아니다. 다만 OTA 공존은 아직 실측하지 않았다.

## 결정

1. 플랫폼 기본은 같은 cell ID의 **공격별 cold-start**로 둔다.
2. 완전 무재시작은 일반 UE 상시 clocked slot 3/3을 먼저 증명한 뒤 공격 모듈로 확장한다.
3. sample-clock bridge는 2번이 CPU 또는 패치 충돌로 불가능할 때만 개발한다.
4. detector-input-emulation 7개는 RF 셀에 억지로 넣지 않고 동일 run/cell metadata로 재생한다.

## 2026-11-16 구현 반영

- `same-cell run`을 공격별 one-shot cold-start 경로로 변경했다.
- 공격 UE와 정상 UE를 DU보다 먼저 실행하고, 하나의 broker가 동일 cell stream에 합친다.
- 공격 endpoint는 처음부터 downlink·uplink를 계속 소비한다. broker의 양방향 complex gain을
  standby `0`에서 attack `1`로 바꿀 뿐 stream을 교체하지 않는다.
- Blind DoS 2개, 상향 DoS·하향 식별자·UE capability 각 1개, 인증 응답 미전송형 4개
  endpoint를 지원한다. RRC storm은 이미 별도 same-cell+정상 5 UE 경로로 자격 검증돼 있다.
- 과거 selector 전환은 `hot-run`으로 이름을 바꾸고 기본 비활성을 유지한다.
- 이 반영은 아직 p5 결합 자격 전이다. 공격별 control→attack 3세트가 통과하기 전에는
  `qualified`로 표시하지 않는다.

## 2026-11-16 p5 smoke

- `sc-cap-control-20261116e`: 정상 UE 5대 준비 뒤 UE Capability control이 등록·PDU·ping과
  정상 `Enquiry → Information`을 통과했다.
- `sc-cap-emulation-20261116a`: 같은 구조에서 보안 전 unsolicited Information과 이후 정상
  Information이 분리 관측됐고 module verdict가 통과했다.
- 두 실행 모두 공격 구간의 정상 UE health 표본은 각각 9/9, 10/10이 5/5였다. runner가 대상
  UE를 종료한 뒤 분석하는 teardown 표본 1개씩은 broker 입력 종료로 0/5였으며 공격 구간
  안정성 표본에는 넣지 않는다.
- 이 smoke로 1-slot 양방향 clock gate와 capture readiness 계약은 확인했다. 2-slot Blind DoS,
  4-slot 인증 응답 미전송형, 상향 DoS, 하향 식별자 노출은 아직 p5 미검증이다.
