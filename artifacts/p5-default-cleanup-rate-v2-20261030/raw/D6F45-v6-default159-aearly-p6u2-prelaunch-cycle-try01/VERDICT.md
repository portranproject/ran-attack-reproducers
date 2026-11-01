# D6F45 — 기본 cleanup A-early 6×2 prelaunch on/off 판정

판정: **기본 약 2초 cleanup을 바꾸지 않은 상태에서 공격 요청률과 DU provisional-create
률이 cleanup률을 넘고, 공격 중 독립 endpoint의 접속 실패 1건과 공격 종료 뒤 별도
prelaunched endpoint의 완전 회복은 성립했다.** 그러나 **지속 context 포화와 30초 반복
서비스 거부는 성립하지 않았다.** 따라서 이 런은 첫 번째 유효한 on/off 상관 관측이지,
아직 통제 가능한 재현기 승인 결과가 아니다.

- DU는 기본 PRACH 159이며 저장된 설정에 cleanup/RLF/hold32 override가 없다.
- CU는 `max_nof_ues: 200`이고, gNB 소스나 설정을 공격 성공을 위해 바꾸지 않았다.
- 공격은 6 OAI 프로세스 × 2 logical UE의 A-early(`msg4_wait=0`) 60초 구간이다.
- startup sync 8/8, UE·broker exit 0, SIGSEGV 0, forced kill 0이다.
- 공격자 Msg5, 공격 중 SetupComplete, 공격 중 NGAP InitialUEMessage는 모두 0이다.

## 요청률은 cleanup보다 빨랐지만 admission은 평형이었다

같은 공격자 Msg3 first-to-last 60.531647초를 분모로 한 인과 계수는 다음과 같다.

```text
2,183 attacker msg3_tx                         36.064/s
  └─ 2,074 DU UE Create started               34.263/s
       ├─ 2,072 Create success / F1 InitialUL 34.230/s
       │    ├─ 1,096 admitted RRC Setup       18.106/s
       │    │    └─ 1,096 timeout cleanup     18.106/s
       │    └─   976 immediate RRCReject      16.124/s
       └─     2 hard context refusal           0.033/s
```

각 단계의 자체 first-to-last span으로 비교해도 결론은 같다.

| 항목 | 처리율 | cleanup 대비 |
|---|---:|---:|
| UE Msg3 offered | 36.063780/s | 1.992921× |
| DU provisional Create | 34.263801/s | 1.893452× |
| CU admitted Setup | 18.096143/s | 1.000011× |
| timeout cleanup | 18.095942/s | 1.000000× |

따라서 **`offered > cleanup`과 `DU provisional > cleanup`은 통과**한다. 다만 DU Create
2,072건을 전부 지속 admission으로 세면 안 된다. 그중 976건은 DU가 전용 PUCCH 구성을
제공할 수 없다고 표시해 CU가 즉시 `rrcReject`한 transient context다. 실제 미완료 Setup
1,096건은 전부 약 2초 뒤 정리됐고, 생성률은 cleanup률과 다시 평형을 이뤘다.

Setup 수명은 median 1,999.382ms, p90 1,999.788ms다. 기본 cleanup이 실제로 유지됐으며,
과거 hold32처럼 관측창 뒤로 만료를 미룬 결과가 아니다.

## 짧은 창과 점유는 sustained saturation에 미달했다

첫 Setup start에 맞춘 12개 완전한 5초 창의 `admitted start - cleanup`은 다음과 같다.

```text
+3, +1, +85, -37, -50, +2, -4, 0, +75, +21, -34, -10
```

- offered가 cleanup보다 큰 창: 10/12
- DU provisional Create가 cleanup보다 큰 창: 9/12
- admitted Setup start가 cleanup보다 큰 창: 6/12

공격 유입은 bursty했고 모든 짧은 창에서 cleanup을 앞서지 못했다. CU 미완료 Setup 점유는
피크 96에 도달했지만 `>=96`은 6개 구간 합계 3.601874초, 최장 0.792861초다.
`>=90`도 합계 6.012931초, 최장 0.891236초다. 즉 30초 지속 포화가 아니다.

## primary denial은 사실이지만 context 고갈 인과는 아니다

primary endpoint 7은 `17:51:24.221902420Z`에 정상 접속 attempt를 시작했다. 이는 첫 공격자
Msg3 뒤 19.963733초이고, 마지막 공격자 kill까지 40.679308초가 남은 시점이다. 이 UE는
공격창 동안 다음 단계로 전혀 진행하지 못했다.

- UE `msg3_tx`: 0
- DU/CU F1 InitialUL: 0
- RRCSetupComplete / Registration / PDU: 0 / 0 / 0
- ping 송신: 0
- 모든 공격자 kill 뒤 primary의 RRC/Registration/PDU 증가: 0 / 0 / 0

runner의 frozen `attack_window`와 `post_boundary_activity=0`도 이 결과와 일치한다. 다만 이
attempt 시점의 CU 미완료 Setup 점유는 45였고 primary는 Msg3에도 도달하지 못했다. 따라서
이 한 건은 **공격 부하 중 접속 거부/정지 결과**이지만, 실패 원인을 CU/DU context 96 고갈로
특정할 수 없다. 또한 primary가 한 번만 시도한 채 RA 전 단계에 머물렀으므로 “정상 UE를
30초 동안 반복 거부했다”는 증거도 아니다.

## 별도 endpoint의 공격 종료 뒤 회복은 성립했다

recovery endpoint 8은 런 시작 때 미리 띄워 PHY sync만 유지하고, 공격 종료 뒤 처음으로
접속하도록 했다. JSONL에서 `pre_attack_attempts=0`, `pre_phase_attempts=0`이며 primary와
다른 ZMQ endpoint다.

1. 마지막 공격자 kill: `17:52:04.901210484Z`
2. 마지막 in-flight 공격자 Msg4: `17:52:04.984400291Z`
3. 마지막 공격 Setup cleanup: `17:52:06.835760Z`
4. recovery attempt: `17:52:14.213118308Z`
   - 마지막 kill 뒤 9.311908초
   - 마지막 cleanup 뒤 7.377358초
5. recovery Msg3 `0x4e52`: `17:52:14.275678688Z`
6. CU Setup start: `17:52:14.287470Z`
7. CU SetupComplete / InitialUEMessage: `17:52:14.418063Z` / `17:52:14.418102Z`
8. PDU Session setup 성공: `17:52:15.160241Z`
9. 격리 ping: **539/539, loss 0%, 평균 97.305ms**
   - 첫/마지막 reply: `17:52:16.719156Z` / `17:54:04.592638Z`

그러므로 “공격 중 primary 실패 → 공격 종료 뒤 별도 endpoint 서비스 성공”이라는 1회
on/off 결과는 유효하다. 하지만 같은 정상 UE의 반복 probe가 아니고 단일 런이므로, 이것만
으로 공격자가 기지국 마비를 안정적으로 시작·종료한다고 일반화하지 않는다.

## 최종 범위와 다음 합격선

D6F45가 새로 입증한 것은 다음 두 가지다.

1. 기본 cleanup에서 공격의 **제공·provisional 처리율 자체는 cleanup보다 빠르다.**
2. 그 공격 구간에 primary 접속 실패 1건이 있었고, stop 뒤 깨끗한 별도 endpoint는
   Registration·PDU·ping까지 회복했다.

아직 불합격인 항목은 다음과 같다.

- 모든 5초 창의 admitted Setup start > cleanup
- CU/DU 포화 30초
- 독립 정상 witness의 30초 반복 거부
- 공격 stop 뒤 동일 witness 회복
- 동일 조건 3회 반복 성공

다음 반복은 평균 offered를 더 높이는 것보다 5초 창의 burst/stall을 줄이고, 공격 중 fresh
witness를 여러 번 시도시켜 거부 구간을 직접 재야 한다.

## 설정·증거·출처 경계

- `du-config.yaml`: SHA-256
  `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`
- `cu-config.yaml`: 실행 중 원격 설정과 동일, SHA-256
  `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`
- `odu.log.gz`: current-boot DU 원문, SHA-256
  `95c60f5586402724811a769fa57ddb94547a71c846dc89dc82610651a4cadc71`
- `cu-rrc-events.log.gz`: UTC `17:49:25`–`17:54:12` 관련 CU slice, 65,301줄,
  SHA-256 `1f65b7001c67b21c65a06a9d46f2c029f1184c60135ce21328d88e232bf7bf8d`
- `stats.json`: 처리율·5초 창·점유·primary/recovery 시간축의 기계 판독 요약
- 저장 디렉터리 전체 sensitive-artifact scanner: `ok`
- UE 바이너리 SHA-256:
  `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`
- runner / broker SHA-256:
  `245fe0222abd92c370d80b04caac62be2ee6b4d1c5e2c45b0743db3f6541c2c8` /
  `75c8aab23c151caf46198066d70f4f2db294cae2149eed2b8de2e3e9f1b95dfc`

원격 CU 전체 로그는 계속 증가하는 활성 파일이므로 관측 당시 전체 SHA는 고정 원문 해시로
쓰지 않는다. 판정에 사용한 로컬 filtered gzip만 불변 증거로 봉인한다. p5의 CU/DU 프로세스,
설정, 서비스 상태는 이 분석 중 변경하거나 재시작하지 않았다.
