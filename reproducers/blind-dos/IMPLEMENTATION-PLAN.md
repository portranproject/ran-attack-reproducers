# Blind DoS 구현·검증 계획

상태: **현재 유효 5G-GUTI 재사용형 구현과 G5 검증 완료.** 이 문서는 구현 범위와
판정 근거를 보존한다. 실행자는 [사용 가이드](USAGE-GUIDE.md)를 먼저 본다.

## 1. 목표와 비목표

목표는 피해 UE의 현재 5G-GUTI를 랩 oracle로 받은 별도 가입자 OAI UE가 한 번 재사용해,
기존 피해 context 변화와 실제 서비스 손실을 만들고 같은 UE 프로세스의 회복까지 반복
검증하는 것이다.

구현 범위에 포함한다.

- OAI 2026.w38 UE-only one-shot 패치
- direct 2-cell ZMQ의 피해 UE·공격 UE 분리
- control→attack matched campaign
- 공격자 이벤트, 피해 서비스, AMF/CU/DU, N2/F1 증거 봉인
- 기존 피해 context 효과와 동일 PID 회복의 fail-closed 판정

구현하지 않는다.

- 식별자 추측·스캔·자동 수집
- 피해자 SIM 자격증명 복제
- gNB·코어 소스나 timer/capacity 변경
- 반복 재표적화에 의한 지속 차단
- 실 SDR OTA 자동 실행

## 2. 확정된 공격 기전

```text
피해 UE(V)
  정상 Registration + PDU session + ping
  └─ 현재 5G-GUTI와 48-bit 5G-S-TMSI 보유

runner
  ├─ V의 현재 5G-S-TMSI·AMF Region·기존 NGAP ID snapshot
  └─ snapshot 뒤 표적 파일을 원자적으로 공개

공격 UE(A, 별도 가입자)
  ├─ Msg3 RRCSetupRequest: 5G-S-TMSI Part1
  ├─ Msg5 RRCSetupComplete: 5G-S-TMSI Part2
  ├─ NAS Registration Request: 피해자의 전체 5G-GUTI
  └─ Authentication Request: 응답하지 않음

AMF
  └─ 기존 V binding/context 상태 변화 → V 서비스 손실

runner
  └─ one-shot 종료 확인 → 같은 V PID 재등록 요청 → 서비스 회복 확인
```

5G-S-TMSI는 `AMF Set ID(10) + AMF Pointer(6) + 5G-TMSI(32)`다. 전체 NAS
5G-GUTI에는 PLMN과 AMF Region ID도 필요하다. RRC의 48-bit 값만 재사용하는 구현으로는
Open5GS가 기대하는 NAS identity collision을 안정적으로 만들 수 없었다. 최종 구현은 plain
NAS Registration Request의 mobile identity도 피해 5G-GUTI로 구성한다.

Open5GS의 상태 전이 근거는
[issue #4577](https://github.com/open5gs/open5gs/issues/4577)이며, 실제 판정은 특정 로그
문자열이 아니라 current-run snapshot·NGAP ID·서비스 관측의 조인으로 한다.

## 3. 테스트베드 구성

```text
p5 CU 호스트
  Open5GS AMF/UPF + OCUDU CU
  ├─ 피해 GUTI/NGAP snapshot
  ├─ AMF·CU current-run log slice
  └─ N2/F1 capture
             │ F1
p5 DU/UE 호스트
  OCUDU DU, 2 ZMQ cells
  ├─ cell 0: 피해 OAI UE, 127.0.0.1:4556/4557
  └─ cell 1: 공격 OAI UE, 127.0.0.1:4558/4559
```

GNU Radio 다중 UE broker/relay는 최종 경로에서 제거했다. relay는 RRCSetupComplete를
지연시켰고 기존 broker는 시작 동기화가 불안정했다. direct 2-cell은 두 UE를 별도
프로세스·별도 cell로 유지하면서 실측이 안정적이었다.

V와 A는 서로 다른 팀 가입자 프로필이다. `provision_profiles.py`가 별도 프로필과 비가역
fingerprint를 만들며, runner는 두 fingerprint가 같으면 프로세스를 시작하지 않는다.

## 4. OAI 패치 범위

기준 commit은 `6d6782b48484efd935c14e834832032743f9b138`다. `bin/blind-build`는
`patch/blind-ue-w38.patch`(SHA-256 `5ee58d5b0009431dbddbba0c08f0dbe25f46c7b4d48f06a9accdb88c06b3697a`)와
same-cell RA gate용 `../authentication-timeout-exhaustion/patch/same-cell-ra-gate-w38.patch`를 함께 적용한다.

| 옵션 | 대상 | 의미 | 기본값 |
|---|---|---|---|
| `blind.enable` | 공격 UE | one-shot 공격 경로 | `0` |
| `blind.amf_region_id` | 공격 UE | 전체 5G-GUTI 복원 | 공격 시 필수 |
| `blind.target_5g_s_tmsi` | 공격 UE | direct 48-bit 표적 | 없음 |
| `blind.target_file` | 공격 UE | snapshot 뒤 공개되는 표적 파일 | 없음 |
| `blind.target_wait_s` | 공격 UE | 표적 게이트 제한시간 | `120` |
| `blind.run_id` | 공격 UE | 이벤트 조인 키 | 공격 시 필수 |
| `blind.log_file` | 공격 UE | exclusive-create JSONL | 공격 시 필수 |
| `blind.recovery_mode` | 피해 UE | reject 뒤 동일 프로세스 유지 | `0` |
| `blind.tun_suffix` | 두 UE | PDU TUN 이름 충돌 방지 | `0` |

공격 상태 기계는 `armed → Msg3 committed → RRCSetupComplete submitted →
authentication request withheld` 한 번만 전진한다. 재전송·T300 경로가 두 번째 공격을
만들면 `retry_blocked`를 기록한다. verifier는 terminal chain이 정확히 한 번인지 확인한다.

회복 신호 handler는 signal-safe하게 eventfd에만 쓴다. worker가 NAS task에 재등록 요청을
보낸다. runner는 `SIGUSR1`을 victim 메인 PID에만 보낸다. 프로세스 그룹에 보내면 OAI가
fork한 TUN command helper까지 죽어 이후 TUN 재구성이 실패한다.

`blind.recovery_mode=1`은 테스트 victim에만 사용한다. Registration Reject가 남긴
`termination_procedure`를 초기화하고 RRC release가 softmodem 전체를 종료하지 않게 한다.
일반 UE와 공격 UE의 기본 종료 동작은 바꾸지 않는다.

## 5. 실행기와 증거 계약

`blind-p5-phase`는 다음 순서만 허용한다.

1. 기존 UE/DU 충돌 검사, DU 2-cell 재시작, CU log/capture 시작
2. 피해 UE와 게이트 대기 공격 UE 시작
3. 피해 Registration·PDU·ping 및 20회 baseline 확인
4. 현재 피해 GUTI·NGAP ID snapshot
5. control은 게이트를 닫고, attack만 표적 파일을 원자적으로 생성
6. 사전 고정한 관측창에서 연속 5회 서비스 실패 검사
7. attack terminal event와 after snapshot 확인
8. 같은 victim PID에 재등록 요청, Registration/PDU count 증가와 ping 20회 확인
9. 추가 공격 이벤트 0건 확인 후 두 UE·DU·수집기 정리

2-cell ZMQ radio clock 때문에 attack terminal 뒤 공격 UE endpoint는 idle 상태로 남겨 둔다.
추가 이벤트가 하나라도 생기면 런은 실패한다.

각 run은 다음 파일을 독립적으로 봉인한다.

- `run.json`, `run_stop.json`, `verdict.json`
- `attacker_events.jsonl`, `victim_service.jsonl`
- before/after target snapshot
- 정제된 AMF·CU·DU log와 N2/F1 pcap
- `ground_truth.jsonl`, `evidence_manifest.json`
- credential scanner 결과

verifier는 raw evidence를 수정할 수 없다. 검증 전후 hash가 다르거나 필수 파일이 없거나
scanner가 실패하면 `infrastructure-invalid`다. 실제 공격 효과가 없는 유효 런은
`valid-failure`이며 재시도하지 않는다. 인프라 무효만 사전 고정한 횟수 안에서 새 run ID로
재시도한다.

## 6. 성공 게이트

| 게이트 | 판정 |
|---|---|
| G3 | 공격자 GUTI commit 뒤 동일 표적의 AMF identity reach와 유효 NGAP ID |
| G4 | before snapshot의 기존 피해 RAN/AMF UE ID에 exact-join된 binding/context 변화 |
| G5 | G4 + 피해 연속 손실 + 동일 PID의 새 Registration/PDU + ping 회복, matched control 정상, N/N |
| G6 | G5 + oracle 없이 공격 시점의 현재 식별자를 비특권 Uu에서 획득 |
| G7 | G6 + 매 재접속 재표적화로 사전 고정 관측창 동안 지속 차단 |

현재 완료 기준은 G5다. 기본 `N=3`, 허용 범위는 3~100이다.

## 7. 최종 p5 판정

캠페인 ID는 `blind-g5-final-20261102`, 실행 순서는 각 세트의 control→attack이다.

- completed/passed set: 3/3
- control: 3/3 첫 시도 통과, 공격 이벤트 0, ping 손실 0
- attack: 3/3 첫 시도 통과, exact join·기존 피해 상태 효과·5회 연속 손실 참
- attack 회복: 세 run 모두 동일 PID, Registration/PDU `1→2`, after ping `20/20`
- crash/forced kill: 전 run 0/0
- 인프라 재시도: 0
- 최종 OAI binary SHA-256:
  `9a532c5e4c678ecbee115b37d03b20d9a79fc5100e6056c9615ba48d0fa9b73c`

정제 결과와 모든 원문 파일의 원격 SHA-256은
[`artifacts/p5-zmq-nas-guti-g5-20261102/`](artifacts/p5-zmq-nas-guti-g5-20261102/)에
보존한다. 이전 `artifacts/p5-zmq-20261102/`는 RRC-only 초기 구현의 G5 미달 기록이며
최종 결과와 합치거나 덮어쓰지 않는다.

## 8. 남은 범위

- G6: oracle 없는 현재 식별자 획득
- G7: 재접속마다 다시 공격하는 지속 차단
- 차폐박스 실 SDR OTA 상호운용
- 다른 Open5GS·AMF 버전의 상태 전이 비교
- 탐지 결과와 대응 actuator를 잇는 폐루프

위 항목은 G5 재현기 완료와 별도다. 현재 결과를 상용망 전체, OTA, 지속 DoS로
일반화하지 않는다.
