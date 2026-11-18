# 정상 UE 워크로드

공격 슬롯과 같은 DU·셀 ID를 사용하는 지속 정상 UE 풀이다. 기본 5 logical UE는 하나의
OAI 프로세스 안에서 UE별 독립 virtual RU/ZMQ endpoint 5개를 사용한다. GNU Radio broker가
이 endpoint들과 공격 endpoint의 하향 신호를 복제하고 상향 신호를 합친다.

```bash
./ctl.sh normal-ue setup --profile p5
./ctl.sh normal-ue doctor --profile p5             # 기본 5대
./ctl.sh normal-ue start --profile p5 --count 5
./ctl.sh normal-ue status --profile p5
./ctl.sh normal-ue stop --profile p5
```

공격과 같이 실행할 때는 `same-cell run`이 해당 공격에 필요한 UE와 정상 UE 5대를 하나의
broker/셀에서 함께 cold-start한다. 공격 UE는 DU보다 먼저 시작해 downlink와 uplink sample을
계속 소비하되, 정상 UE 5/5가 준비될 때까지 broker가 공격 슬롯의 uplink 이득을 0으로
유지한다. downlink는 계속 공급해 공격 UE의 sample clock을 DU와 맞춘다. RRC storm은 전용
gate를, 나머지 live L3 모듈은 공통 RA gate를 사용해 broker의 uplink 활성화 확인 뒤에만
첫 RA를 시작한다. Blind DoS의 공격 UE는 기존 target gate를 사용하므로 공통 gate는 피해 UE에만
적용한다. 준비 뒤
같은 stream의 이득과 UE 동작만 바꾸므로 실행 중 새 ZMQ stream을 삽입하지 않는다.

```bash
./ctl.sh same-cell doctor --profile p5
./ctl.sh same-cell run downlink-imsi --profile p5 --mode control --run-id id-control-1
./ctl.sh same-cell run downlink-imsi --profile p5 --mode emulation --run-id id-emulation-1 --enable
./ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable
```

공개 same-cell 대상은 L3-01-V·L3-01-O·L3-20·L3-21·L3-24·L3-14·L3-06이다. 공격별
내부 runner나 wrapper를 직접 호출하지 않는다. AN fixture와 legacy uplink MAC 단발 변조형은
이 자격 범위가 아니다.

각 module의 Git 밖 설정과 `--enable` 안전 조건은 기존과 같다. phase 종료 시에는 PID와
시작시각이 일치하는 정상 UE, 공격 runner, broker, DU만 종료하고 CU·코어·dashboard는
유지한다. 다음 phase는 같은 CU·DU 인스턴스와 같은 셀 식별자에서 DU·broker·UE 프로세스를
cold-start한다. 따라서 한 실행 중 RF stream을 갈아 끼우는 방식이 아니다.

> 과거 selector 기반 hot-swap은 p5 자격 검증에 실패했다. 공개 사용법에서는 제거했으며
> 과거 실험 기록으로만 보존한다. 현재 `run`은 공격별 cold-start와 상시 clocked attack
> slot을 사용한다. UE Capability
> control·emulation은 각각 1회, L3-21 실패 플러드는 control→attack 3/3이 정상 UE 5대와
> 함께 통과했다. Blind DoS는 배경 1대·2대에서도 피해 UE RA가 실패해 미승인이다. 다른
> 공격의 p5 결합 자격은 아직 필요하다. 설계와 과거 실패 근거는
> [hot-swap 검증 기록](docs/SAME-CELL-HOT-SWAP-20261113.md)을 따른다.

- `start` 뒤 supervisor는 수동 `stop` 전까지 계속 실행한다.
- UE·broker·runner가 종료되면 5초 뒤 새 generation으로 다시 시작한다.
- logical UE는 1초 위상차로 첫 접속하고, 실패 시 5초 주기로 계속 재시도한다.
- `start`는 권한 `0600` 임시 설정에 UE 수와 같은 `RUs`·`cells`·`zmq` 항목을 만든다.
  각 UE는 독립 endpoint를 쓰고 broker에서만 합쳐진다. 가입자 원문과 임시 설정은 Git에 넣지 않는다.
- 정상 워크로드용 OAI에는 `patch/normal-probe-phase.patch`를 적용한다. 공격 UE와 TUN 이름이 충돌하지 않도록 same-cell
  실행용 binary에는 `patch/normal-tun-suffix.patch`도 적용한다.
- `status`의 `healthy`는 요청 수만큼 TUN과 gateway ping이 모두 성공한 경우다.
- same-cell 자격은 공격 전과 종료 직전 정상 UE 5대의 Registration·PDU·gateway ping을
  각각 기록한다. 공격 중 저하는 별도 효과이며 종료 직전 5/5가 아니면 정상 UE 동반 자격에
  실패한다.
- 공격 runner가 목표 이벤트 생성을 완료하면 컨트롤러가 해당 uplink slot을 먼저 닫고 정상
  UE 5/5 회복을 확인한 뒤 공격 UE 종료를 허가한다. 공격 UE가 먼저 사라져 broker 전체가
  멈추는 종료 효과를 서비스 영향으로 오판하지 않는다.
- 인증 미응답형은 같은 UE 프로세스에 재등록을 요청해 radio clock을 유지한다. 15 UE가 다시
  수렴할 수 있도록 회복 관측은 240초, runner 종료 허가는 300초까지 기다리며 망 timer는 바꾸지 않는다.
- p5 cold-start에서 5/5 수렴까지 12.7~62.3초가 걸렸으므로 시작 직후의 `degraded`는
  최종 실패가 아니다.

## p5 자격 현황

2026-11-18 실측에서 current p5 OAI가 `--zmq.[1]...` indexed CLI option을 거부했지만,
OAI config의 `RUs`·`cells`·`zmq` 배열은 독립 virtual RU socket 5/5를 만들었다. 반대로
단일 shared RU는 channel timeout 약 9만 건과 서비스 1/5로 실패했다. 따라서 독립 RU
구조로 복원하며 Registration·PDU·ping 5/5와 전체 캠페인을 다시 봉인한다.
L3-21은 2026-11-16 정상 UE 5대가 모든 attack 표본에서 5/5를 유지한 채 matched 3/3을
통과했다. Blind DoS는 같은 날 배경 1대·2대 모두 정상 풀은 유지했지만 피해 UE가 180초
안에 등록하지 못해 미승인이다. Blind DoS·L3-01-O·L3-06을 포함한 새 L3 7종 cold-start
통합 경로는 구현됐지만, p5에서 control→active 3/3과 dashboard 전송을 새로 봉인하기 전까지
**구현됐으나 미자격**이다. 기존 개별 자격은 유지하지만 정상 UE 5대 same-cell 자격으로
일반화하지 않는다. 실 SDR OTA는 아직 승인 범위가 아니다.

반복 실행별 결과와 증거 해시는 [p5 자격 검증](docs/P5-QUALIFICATION-20261113.md)에 남겼다.
5 UE 불안정성의 코드 원인과 비교 실험은
[RU-sharing 원인 분석](docs/RU-SHARING-ROOT-CAUSE-20261113.md)에 기록했다.
같은 셀에서 RRC storm과 공존시킨 결과는
[RRC 공존 실측](docs/RRC-COEXISTENCE-20261113.md)에 기록했다.
