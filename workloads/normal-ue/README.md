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

공격과 같이 실행할 때는 `same-cell` 세션이 정상 UE 5대와 고정 공격 슬롯 4개를 하나의
broker/셀에 연결한다. 세션 시작 때 broker 연결 뒤 DU만 한 번 재시작하며, 이후 공격 전환은
DU·CU·broker와 대기 UE를 유지한 채 broker의 슬롯 경로만 선택한다. 정상 5대의
Registration·PDU·ping이 모두 성공한 뒤에만 공격 runner의 readiness gate가 열린다.

```bash
./ctl.sh same-cell start -n demo --count 5
./ctl.sh same-cell status
./ctl.sh same-cell run blind -n demo-blind -- /path/to/blind-run attack -n blind-1 -e 1
./ctl.sh same-cell run uplink -n demo-uplink -- /path/to/uplink-run emulation -n uplink-1 -e 1
./ctl.sh same-cell run auth-timeout -n demo-auth -- /path/to/auth-timeout-run attack -n auth-1 -e 1
./ctl.sh same-cell stop
```

각 module의 Git 밖 설정과 `--enable` 안전 조건은 기존과 같다. 각 공격 module runner는
CU/DU를 시작·중지하지 않는 외부 lifecycle 모드로 실행된다. 세션 종료 시에는 PID와
시작시각이 일치하는 정상 UE, 대기 UE, broker, DU만 종료하고 CU·코어는 유지한다.

> p5 hot-swap 자격 검증에서 실행 중인 ZMQ RF 스트림에 서로 다른 OAI 공격 프로세스를
> 전환하면 공격 UE uplink 시간축이 DU와 맞지 않았고 정상 UE도 무재시작 회복하지 못했다.
> 따라서 `same-cell run`은 기본 비활성이며 위 명령은 개발 진입점 예시다. 현재 안전한 다음
> 구현 방향은 같은 셀 설정을 유지하되 공격 모듈이 바뀔 때 DU·broker·UE를 함께 다시 시작하는
> 방식이며, 정상 UE 5대와 각 공격의 결합 자격 검증은 별도로 필요하다.
> 단일 셀 자체가 불가능한 것은 아니다. 무재시작이 필요할 때의 상시 clocked attack slot과
> sample-clock bridge 설계, 검증 순서는
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
- `same-cell run`의 무재시작 전환 코드는 연구용으로 남겨 두되
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
