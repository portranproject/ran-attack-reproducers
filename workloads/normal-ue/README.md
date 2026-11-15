# 정상 UE 워크로드

공격 슬롯과 같은 DU·셀 ID를 사용하는 지속 정상 UE 풀이다. 기본 5 logical UE는 하나의
OAI 프로세스에서 실행하지만, UE마다 독립 virtual RU와 ZMQ endpoint를 사용한다. GNU Radio
broker가 모든 endpoint의 하향 신호를 복제하고 상향 신호를 합쳐 같은 DU·셀에 넣는다.

```bash
./ctl.sh normal-ue setup --profile p5
./ctl.sh normal-ue doctor --profile p5             # 기본 5대
./ctl.sh normal-ue start --profile p5 --count 5
./ctl.sh normal-ue status --profile p5
./ctl.sh normal-ue stop --profile p5
```

공격과 같이 실행할 때는 `same-cell run`이 해당 공격에 필요한 UE와 정상 UE 5대를 하나의
broker/셀에서 함께 cold-start한다. 공격 UE는 DU보다 먼저 시작해 downlink와 uplink sample을
계속 소비하되, 정상 UE 5/5가 준비될 때까지 broker가 공격 슬롯의 상·하향 이득을 0으로
유지한다. 준비 뒤 같은 stream의 이득만 1로 바꾸므로 실행 중 새 ZMQ stream을 삽입하지 않는다.

```bash
./ctl.sh same-cell run blind -n demo-blind --count 5 -- /path/to/blind-run attack -n blind-1 -e 1
./ctl.sh same-cell run uplink -n demo-uplink --count 5 -- /path/to/uplink-run emulation -n uplink-1 -e 1
./ctl.sh same-cell run auth-timeout -n demo-auth --count 5 -- /path/to/auth-timeout-run attack -n auth-1 -e 1
./ctl.sh same-cell run downlink-imsi -n demo-id --count 5 -- /path/to/downlink-imsi-run emulation -n id-1 -e 1
./ctl.sh same-cell run ue-capability -n demo-cap --count 5 -- /path/to/ue-capability-run emulation -n cap-1 -e 1
```

각 module의 Git 밖 설정과 `--enable` 안전 조건은 기존과 같다. 각 공격 module runner는
CU/DU를 시작·중지하지 않는 외부 lifecycle·prestart 모드로 실행된다. 실행 종료 시에는 PID와
시작시각이 일치하는 정상 UE, 공격 runner, broker, DU만 종료하고 CU·코어는 유지한다.

> 과거 selector 기반 hot-swap은 p5 자격 검증에 실패해 `hot-run` 진단 경로로만 남겼다.
> 기본 `run`은 공격별 cold-start와 상시 clocked attack slot을 사용한다. UE Capability
> control·emulation은 p5에서 각각 1회 정상 UE 5대와 함께 통과했다. Blind DoS·상향 DoS·
> 인증 응답 미전송형·하향 식별자 노출의 p5 결합 자격은 아직 필요하다. 설계와 과거 실패
> 근거는
> [hot-swap 검증 기록](docs/SAME-CELL-HOT-SWAP-20261113.md)을 따른다.

- `start` 뒤 supervisor는 수동 `stop` 전까지 계속 실행한다.
- UE·broker·runner가 종료되면 5초 뒤 새 generation으로 다시 시작한다.
- logical UE는 1초 위상차로 첫 접속하고, 실패 시 5초 주기로 계속 재시도한다.
- `start`는 가입자 설정을 복사한 권한 `0600` 임시 설정에 UE 수만큼 `RUs`와 `cells`를
  생성한다. 가입자 원문과 임시 설정은 Git에 넣지 않는다.
- 정상 워크로드용 OAI에는 `patch/normal-probe-phase.patch`와
  `patch/normal-multi-ru.patch`를 적용한다. 후자는 UE 수와 RU 수가 같으면 불안정한
  custom RU-sharing 집계기를 우회한다. 공격 UE와 TUN 이름이 충돌하지 않도록 same-cell
  실행용 binary에는 `patch/normal-tun-suffix.patch`도 적용한다.
- `status`의 `healthy`는 요청 수만큼 TUN과 gateway ping이 모두 성공한 경우다.
- p5 cold-start에서 5/5 수렴까지 12.7~62.3초가 걸렸으므로 시작 직후의 `degraded`는
  최종 실패가 아니다.
- `same-cell hot-run`의 과거 selector 전환 코드는 연구용으로 남겨 두되
  `SAME_CELL_EXPERIMENTAL_SWITCH=1` 없이는 실행되지 않는다.

## p5 자격 현황

2026-11-13 독립 virtual RU 구조의 cold-start 3회 모두 정상 UE 5/5가 등록·PDU·개별
gateway ping을 통과했다. 세 실행의 ZMQ channel timeout과 crash marker는 모두 0이었고,
종료 후 UE·broker·TUN 잔존도 0이었다. 따라서 p5 기본 5대 정상 배경 트래픽 용도로 승인한다.
실 SDR OTA와 정상 풀을 유지한 live 공격 전환은 아직 승인 범위가 아니다.

반복 실행별 결과와 증거 해시는 [p5 자격 검증](docs/P5-QUALIFICATION-20261113.md)에 남겼다.
5 UE 불안정성의 코드 원인과 비교 실험은
[RU-sharing 원인 분석](docs/RU-SHARING-ROOT-CAUSE-20261113.md)에 기록했다.
같은 셀에서 RRC storm과 공존시킨 결과는
[RRC 공존 실측](docs/RRC-COEXISTENCE-20261113.md)에 기록했다.
