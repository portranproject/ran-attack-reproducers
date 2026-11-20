# 현재 유효 5G-GUTI 재사용형 Blind DoS (L3-20)

별도 가입자 OAI UE가 피해 UE의 현재 유효 5G-S-TMSI(RRC)와 전체 5G-GUTI(NAS `Registration Request`)를 한 번 재사용해 기존 피해자 AMF 컨텍스트와 서비스를 교란하는 one-shot 프로토콜 재현 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-20` |
| `reproducer.json` id | `blind-dos` |
| `ctl.sh` ID / 별칭 | `blind-dos` (`blind`) |
| 재현 수준 (`reproduction_level`) | `protocol` |
| active 모드 (`active_mode`) | `attack` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` direct 2-cell G5 3/3 + E2E 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 표적 게이트를 열지 않는다.

## 동작 요약

```text
피해 UE (V)                  OCUDU DU/CU / Open5GS               공격 UE (A, 별도 가입자)
   │ 정상 등록·PDU·ping          │                                     │
   │<───────────────────────────>│                                     │
   │                             │◄─ Msg3/Msg5(피해 5G-S-TMSI)         │
   │                             │◄─ RegistrationRequest(피해 5G-GUTI) │
   │   기존 AMF context 변화/손실 │◄─ AuthenticationRequest 무응답      │
```

- **control** (`-e 0`): 표적 게이트를 닫아 공격 이벤트를 0건으로 유지하며 피해 UE 정상 서비스를 확인한다.
- **attack** (`-e 1`): 랩 oracle로 피해 UE의 현재 5G-S-TMSI·AMF Region ID를 읽은 뒤 공격 UE가 `RRCSetupRequest`/`RRCSetupComplete`/plain NAS `Registration Request`에 피해자 5G-GUTI를 넣어 1회 송신하고, `Authentication Request`에는 응답하지 않는다.
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/blind-build`가 2개 패치(`patch/blind-ue-w38.patch`, `../authentication-timeout-exhaustion/patch/same-cell-ra-gate-w38.patch`)를 적용한다. OCUDU·Open5GS 소스와 timer/capacity는 수정하지 않는다.

## 실행 방법

### 통합 컨트롤러 (`ctl.sh`)

```bash
./ctl.sh setup blind-dos --profile p1
./ctl.sh doctor blind-dos --profile p1

# 단발 및 matched 3세트 캠페인 (p5 direct 2-cell)
./ctl.sh run blind-dos control blind-ctrl-01 --profile p5
./ctl.sh run blind-dos attack blind-atk-01 --profile p5 --enable
./ctl.sh campaign blind-dos blind-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./ctl.sh same-cell run blind-dos --profile p1 --mode control --run-id sc-blind-ctrl-1
./ctl.sh same-cell run blind-dos --profile p1 --mode attack --run-id sc-blind-atk-1 --enable
```

### 직접 실행 (`bin/`)

`ctl.sh` 설정 예제는 `conf/p5-zmq.conf.example`을 복사한 `conf/blind.conf`(`BLIND_CONF`)를 사용한다(`conf/blind.conf.example`도 보관돼 있다).

```bash
OAI=/root/OAI-blind-dos-w38 bin/blind-build
BLIND_CONF=conf/blind.conf bin/blind-run control -n control-001 -e 0
BLIND_CONF=conf/blind.conf bin/blind-run attack -n attack-001 -e 1
BLIND_CONF=conf/blind.conf bin/blind-campaign -e 1 -n blind-g5-camp -R 3
```

`SIGUSR1` 회복 신호는 반드시 victim **메인 PID에만** 보낸다(프로세스 그룹 전송 시 OAI TUN 보조 프로세스까지 종료됨).

## 합격 기준

- **control**: 공격 이벤트 0건, `target_owner_state_effect=false`, `victim_service_loss=false`, `L3-20` 경보 0건.
- **p5 direct 2-cell G5 (`attack`)**: terminal chain(`target_gate_opened → target_msg3_committed → nas_guti_selected → rrc_setup_complete_submitted → authentication_request_withheld`) 1회, `exact_join=true`, `target_owner_state_effect=true`, `victim_service_loss=true`(5회 연속 ping 손실), `same_victim_recovery=true`(동일 PID 재등록/PDU `1→2`, 회복 ping 20/20), crash/forced kill 0건.
- **same-cell E2E**: TeleRAN 100 ms / gap 0 / KPM 존재, production `L3-20` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, 정상 UE 5대 전후 ping 5/5 성공.
- **campaign**: 고정 순서 `control → attack` 3세트 모두 통과.

## 한계 및 금지 주장

- **oracle 보조 단발 G5 범위**: 비특권 무선 식별자 획득(G6)과 재접속마다 반복 차단하는 지속 DoS(G7)는 미구현이다.
- **정상 UE 5대 서비스 거부 미관측**: `p1q9-20261119` same-cell E2E에서 공격 중·후 정상 풀 5대는 서비스를 유지했으며(`service_denial` `not_observed`), 이는 direct 2-cell의 피해자 단발 손실과 구분한다.
- **과거 p5 pre-gate same-cell 한계**: broker/RA gate 적용 전 2026-11-16 p5 단일 셀에서는 독립 ZMQ 프로세스 시간축 불일치로 실패한 바 있다([한계 기록](artifacts/p5-same-cell-limit-20261116/README.md)). 이후 `same_cell_broker.py` + `same-cell-ra-gate-w38.patch` 통합 경로는 `p1q9-20261119`에서 6/6 통과했다.
- **OTA·상용망 미검증**: 실 SDR 차폐 OTA와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [사용 가이드](USAGE-GUIDE.md), [구현·검증 계획](IMPLEMENTATION-PLAN.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 E2E 자격: [p5 L3 5종 E2E](../../artifacts/p5-live-e2e-five-20261117/README.md)
- 모듈 세부 증거: [p5 direct 2-cell G5 실측](artifacts/p5-zmq-nas-guti-g5-20261102/README.md), [p5 pre-gate same-cell 한계](artifacts/p5-same-cell-limit-20261116/README.md)
