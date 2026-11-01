# D6F46 — 기본 cleanup A-early 6×2 prelaunch on/off 2회차 판정

판정: **기본 약 2초 cleanup을 바꾸지 않고 공격 Msg3 제공률과 DU provisional-create
률이 cleanup률을 각각 1.487배, 1.437배 넘었다. 공격 중 primary는 서비스에 실패했고,
공격 종료 뒤 별도 prelaunched endpoint는 Registration·PDU·ping까지 회복했다.** 다만
**admitted Setup은 cleanup과 평형이었고, 96 점유 최장 구간은 0.167초뿐이다.** primary의
두 번째 시도는 RRC와 core까지 도달했으므로 이 런도 30초 지속 기지국 마비나 context
고갈 단일 인과를 입증하지 않는다.

- DU boot 원문은 PRACH index 159, `max_consecutive_kos=100`, `t310=1000ms`, capacity
  96을 기록한다. hold32·cleanup/RLF 완화는 없다.
- CU 설정은 `max_nof_ues: 200`이다.
- 공격은 6 OAI 프로세스 × 2 logical UE의 A-early(`msg4_wait=0`) 60초 구간이다.
- startup sync 8/8, UE·broker exit 0, SIGSEGV 0, forced kill 0이다.
- 공격자 Msg5·SetupComplete·NGAP InitialUEMessage는 모두 0이다.

## 제공·provisional 유입은 cleanup보다 빨랐다

공격자 UE RNTI를 current-boot DU/CU lifecycle에 조인했다. 같은 공격자 Msg3
first-to-last 60.667127초를 분모로 하면 다음과 같다.

```text
2,430 attacker msg3_tx                         40.055/s
  ├─    83 DU Create 전 미도달                  1.368/s
  └─ 2,347 DU UE Create success / F1 InitialUL 38.687/s
       ├─ 1,634 admitted RRC Setup             26.934/s
       │    └─ 1,634 timeout cleanup           26.934/s
       └─   713 immediate RRCReject            11.753/s
```

각 단계의 자체 first-to-last span으로 비교한 값은 다음과 같다.

| 항목 | 처리율 | cleanup 대비 |
|---|---:|---:|
| UE Msg3 offered | 40.054641/s | 1.487389× |
| DU provisional Create | 38.686615/s | 1.436588× |
| CU admitted Setup | 26.929383/s | 0.999996× |
| timeout cleanup | 26.929503/s | 1.000000× |

따라서 사용자가 요구한 **`offered > cleanup`과 `DU provisional > cleanup`은 재현**됐다.
그러나 2,347개를 모두 지속 admission으로 세면 안 된다. 713개는 전용 PUCCH 자원을
받지 못해 CU가 즉시 `rrcReject`한 transient context다. 실제 admitted Setup 1,634개는
모두 median 1,999.380ms 뒤 정리되어 장기 평균에서는 cleanup과 평형을 이룬다. 유한한
capacity에서 포화 뒤 accepted start가 release보다 계속 클 수는 없고, 초과 유입은 reject로
분기된다는 점을 그대로 보여준다.

## 5초 창은 개선됐지만 지속 포화는 아니다

첫 Setup start에 맞춘 12개 완전한 5초 창의 `admitted start - cleanup`은 다음과 같다.

```text
+1, 0, +6, +74, +2, -24, +2, +7, +5, +3, -17, +6
```

- offered가 cleanup보다 큰 창: 11/12
- DU provisional Create가 cleanup보다 큰 창: 10/12
- admitted Setup start가 cleanup보다 큰 창: 9/12

D6F45보다 유입은 평활해졌지만 모든 짧은 창에서 cleanup을 앞서지는 못했다. 미완료 Setup
점유는 피크 96에 도달했으나 `>=96`은 2개 구간 합계 0.171550초, 최장 0.167468초다.
`>=90`도 합계 0.542358초, 최장 0.352422초다. 30초 sustained saturation 합격선과는
거리가 크다.

## primary는 서비스 실패했지만 두 번째 시도는 core까지 갔다

primary endpoint 7은 첫 공격자 Msg3 뒤 19.951초부터 두 번 시도했다. 첫 시점의 공격자
미완료 Setup 점유는 81이었다.

1. `17:56:24.657568Z`, RNTI `0x4745`
   - DU가 dedicated PUCCH를 할당하지 못했고 CU missing-container 경로로 즉시 reject
   - UE에는 같은 RRCReject가 재전송되어 JSONL에 5회 관측됨
2. `17:56:25.666934Z`, RNTI `0x477a`
   - RRCSetupComplete 1회, CU InitialUEMessage `17:56:26.513551Z`
   - UEContextSetupResponse까지 도달했으나 Registration Accept와 PDU Accept는 0
   - CU는 `17:56:28.300899Z` release command를 보내고 `17:56:28.987930Z`에 완료

runner가 모든 attacker kill 시점에 동결한 attack window에서도 Registration/PDU/ping은
`0/0/0`이고, 경계 뒤 primary의 RRC/Registration/PDU 추가 활동도 없다. 따라서 **공격 중
정상 UE 서비스 실패 결과는 사실**이다. 첫 시도의 직접 원인은 DU 자원 압력이다. 하지만
두 번째 시도는 RRC와 core까지 통과한 뒤 서비스가 끝났으므로, 전체 실패를 context 96 고갈
하나로 설명할 수 없다. 두 번의 시도는 “30초 동안 반복 거부” 증거도 아니다.

## 공격 종료 뒤 별도 endpoint 회복은 성립했다

recovery endpoint 8은 시작 때 PHY sync만 유지했고, `pre_attack_attempts=0`,
`pre_phase_attempts=0`인 채 공격자 종료 뒤 처음 접속했다.

1. 마지막 attacker kill: `17:57:05.318708Z`
2. 마지막 attacker Setup cleanup: `17:57:07.325672Z`
3. recovery attempt: `17:57:14.585466Z`
   - 마지막 kill 뒤 9.266758초
   - 마지막 cleanup 뒤 7.259794초
4. Msg3 `0x4f58`: `17:57:14.651728Z`
5. CU Setup / InitialUEMessage: `17:57:14.661373Z` / `17:57:14.834795Z`
6. PDU Session setup 성공: `17:57:15.574825Z`
7. 격리 ping: **250/251, loss 0.398406%, 평균 96.033ms**

따라서 D6F46은 D6F45에 이어 두 번째로 `공격 중 service_ok=false → stop 뒤 별도 endpoint
service_ok=true`를 관측했다. 이는 공격자가 부하의 on/off를 통제했다는 반복 상관 증거를
강화하지만, 같은 정상 UE의 회복도 아니고 primary 실패 인과도 혼합되어 있어 아직 승인
결과로 부르지 않는다.

## 합격선 대비 결론

이번 런이 통과한 항목:

1. 기본 cleanup/RLF 보존
2. aggregate offered 및 DU provisional rate > cleanup
3. 공격창 primary 서비스 실패
4. stop 뒤 별도 endpoint Registration·PDU·ping 회복
5. 유효 종료와 원문 보존

아직 불합격인 항목:

- 모든 5초 창의 admitted Setup start > cleanup
- CU/DU 포화 30초
- 독립 정상 witness의 30초 반복 거부
- 공격 stop 뒤 동일 witness 회복
- 동일 조건 3회 전체 합격

그러므로 D6F46을 **기본 cleanup에서 두 번째 서비스-level on/off 관측**으로는 사용해도 되지만,
“기지국을 30초간 마비시키는 통제 가능한 공격”으로 인용하면 안 된다.

## 설정·증거 경계

- `du-config.yaml`: SHA-256
  `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`
- `cu-config.yaml`: SHA-256
  `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`
- `odu.log.gz`: current-boot DU 원문, SHA-256
  `4a4f20225ac7f106fcad06339b47828f85509b61a21300cf7b648b572253d647`
- `cu-rrc-events.log.gz`: UTC `17:56:03`–`17:57:20` CU slice, 75,900줄,
  SHA-256 `dc557d2cf71f743e89085a038fbb2a7e115e054fcfc9c293b1101ceb1ed40187`
- UE binary SHA-256:
  `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`
- runner / broker SHA-256:
  `245fe0222abd92c370d80b04caac62be2ee6b4d1c5e2c45b0743db3f6541c2c8` /
  `75c8aab23c151caf46198066d70f4f2db294cae2149eed2b8de2e3e9f1b95dfc`

원격 CU 전체 로그는 계속 증가하는 활성 파일이므로 고정 원문 해시로 쓰지 않는다. 판정에
사용한 filtered gzip만 불변 증거로 봉인한다. 이 분석은 p5 프로세스·설정·서비스를 변경하거나
재시작하지 않았다.
