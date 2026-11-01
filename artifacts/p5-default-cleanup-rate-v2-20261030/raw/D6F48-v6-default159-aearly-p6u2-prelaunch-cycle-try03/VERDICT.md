# D6F48 — 기본 cleanup A-early 6×2 prelaunch on/off 3회차 판정

판정: **기본 약 2초 cleanup을 바꾸지 않고, 공격 Msg3 제공률과 DU provisional-create
률이 cleanup률을 모든 완전한 5초 창에서 넘었다.** 공격 중 primary 정상 UE는 RRC까지
완료했지만 Registration·PDU 서비스에는 실패했고, 공격 종료 뒤 별도 prelaunched UE는
Registration·PDU·ping에 성공했다. D6F45·D6F46과 합치면 runner 수준의
`primary service off → separate recovery service on`은 3/3 반복됐다.

그러나 **실제 admitted Setup 생성률은 cleanup과 평형이고, 미완료 Setup 점유는 95가
피크라서 지속 context 포화는 성립하지 않았다.** primary도 30초 동안 fresh UE로 반복
거절된 것이 아니며 recovery는 같은 UE가 아닌 별도 endpoint다. 따라서 이 런은 공격자가
제공 부하와 서비스 실패/회복의 반복 상관을 만들었다는 증거이지, 기지국 전체 마비나 최종
재현기 승인 증거는 아니다.

- 저장된 DU 설정은 기본 PRACH 159이며 cleanup/RLF/hold32 override가 없다.
- CU는 `max_nof_ues: 200`이고 gNB 소스·설정을 공격 성립을 위해 바꾸지 않았다.
- 공격은 6 OAI 프로세스 × 2 logical UE의 A-early(`msg4_wait=0`) 60초 구간이다.
- startup sync 8/8, UE·broker exit 0, SIGSEGV 0, forced kill 0이다.
- 공격자 Msg5, 공격자 SetupComplete, 공격자 NGAP InitialUEMessage는 모두 0이다.

## 제공·provisional 유입은 매 창 cleanup보다 빨랐다

같은 공격자 Msg3 first-to-last 60.691017초를 분모로 한 계수는 다음과 같다. 공격 중
primary의 네 Msg3/F1 경로는 RNTI와 DU UE ID로 제외했다.

```text
4,698 attacker msg3_tx                         77.408/s
  └─ 4,451 DU UE Create / F1 InitialUL         73.339/s
       ├─ 2,078 admitted RRC Setup             34.239/s
       │    └─ 2,078 timeout cleanup           34.239/s
       └─ 2,373 immediate RRCReject            39.100/s
```

각 단계의 자체 first-to-last span으로 비교하면 다음과 같다.

| 항목 | 처리율 | cleanup 대비 |
|---|---:|---:|
| UE Msg3 offered | 77.408490/s | 2.262842× |
| DU provisional Create | 73.338254/s | 2.143859× |
| CU admitted Setup | 34.208396/s | 0.999996× |
| timeout cleanup | 34.208522/s | 1.000000× |

따라서 **`offered > cleanup`과 `DU provisional > cleanup`은 명확히 통과**한다. 다만 F1
4,451건을 모두 지속 admission으로 세면 안 된다. 2,373건은 DU가 전용 자원을 제공할 수
없어 CU가 즉시 `rrcReject`한 transient context다. 실제 미완료 Setup 2,078건은 전부 약
2초 뒤 정리됐고, 생성률은 cleanup률과 평형을 이뤘다.

Setup 수명은 median 1,999.400ms, p90 1,999.784ms다. 기본 cleanup이 실제로 유지됐으며
과거 hold32처럼 만료를 관측창 뒤로 미룬 결과가 아니다.

## 5초 유입 평활화는 성립했지만 지속 포화는 아니었다

첫 attacker Setup start에 맞춘 12개 완전한 5초 창의 차이는 다음과 같다.

```text
offered - cleanup:
+210, +217, +230, +223, +221, +241, +207, +226, +226, +239, +218, +218

DU provisional - cleanup:
+178, +201, +204, +211, +205, +217, +183, +204, +206, +218, +206, +198

admitted Setup start - cleanup:
 +76,   -8,   +7,  -12,   -3,  +14,   -2,   -5,  -16,  +36,  -19,   +9
```

- offered가 cleanup보다 큰 창: **12/12**
- DU provisional Create가 cleanup보다 큰 창: **12/12**
- admitted Setup start가 cleanup보다 큰 창: **5/12**

즉 이전 burst/stall 문제와 달리 공격 제공·provisional 유입은 60초 전 구간에서 평활화됐다.
하지만 bounded DU가 초과 요청을 거절한 뒤 admitted start는 cleanup과 평형으로 수렴했다.

공격자 미완료 Setup 점유 피크는 95다. `>=90`은 13개 구간 합계 0.459548초, 최장
0.099953초이고 96에는 한 번도 도달하지 않았다. primary Setup을 포함해도 피크는 95다.
따라서 30초 지속 포화는 불합격이다.

## primary는 RRC 뒤 NAS 서비스에 실패했다

primary endpoint 7은 첫 공격자 Msg3 뒤 19.974857초에 첫 attempt를 시작했고, 네 차례
Msg3를 보냈다.

1. `0x4bc4`: CU Setup admission 뒤 2초 timeout
2. `0x4c15`: CU immediate `rrcReject`
3. `0x4c5e`: CU immediate `rrcReject`
4. `0x4cad`: RRCSetupComplete·NGAP InitialUEMessage까지 성공

네 번째 시도는 `18:02:37.226803Z`에 RRCSetupComplete, `18:02:37.226833Z`에
InitialUEMessage에 도달했지만 Registration Accept와 PDU Session은 0건이었다. AMF의
UEContextReleaseCommand는 `18:02:38.131902Z`에 왔다. runner가 모든 공격자 kill에서
동결한 attack window에서도 `RRC=1, Registration=0, PDU=0, ping=0`이고, 경계 뒤 primary
활동 증가는 0이다.

따라서 공격 중 **정상 서비스 실패 결과**는 사실이다. 하지만 첫 attempt 시 공격자
미완료 점유는 63, 전체 피크는 95였다. 두 distinct reject도 context 96 고갈이 아니라
`DU is not able to serve` 경로다. primary는 네 번을 약 3초 동안만 시도하고 이후 fresh
접속을 반복하지 않았으므로, 이를 30초 context exhaustion이나 반복 정상 UE 거부로
해석하지 않는다.

## 공격 종료 뒤 별도 endpoint의 완전 회복은 성립했다

recovery endpoint 8은 런 시작 때 미리 PHY sync만 유지하고 공격 종료 뒤 처음 접속했다.
`pre_attack_attempts=0`, `pre_phase_attempts=0`이며 primary와 다른 ZMQ endpoint다.

1. 마지막 공격자 kill: `18:03:13.694070335Z`
2. 마지막 공격자 Msg4 수신: `18:03:13.886928874Z`
3. 마지막 공격 Setup cleanup: `18:03:15.794789Z`
4. recovery attempt: `18:03:22.988694629Z`
   - 마지막 kill 뒤 9.294624초
   - 마지막 cleanup 뒤 7.193906초
5. recovery Msg3 `0x57e4`: `18:03:23.053888844Z`
6. CU Setup start: `18:03:23.065841Z`
7. CU SetupComplete / InitialUEMessage: `18:03:23.178089Z` / `18:03:23.178127Z`
8. PDU Session setup 성공: `18:03:23.929075Z`
9. 격리 ping: **244/244, loss 0%, 평균 97.461ms**

그러므로 이 런의 `attack service off → stop 뒤 service on` 결과는 유효하다. 다만 recovery는
동일 UE 재시도가 아니라 별도 endpoint이고, primary와 같은 가입자 설정을 쓰므로 runner는
primary의 Registration/PDU가 경계와 최종 모두 0인 경우에만 recovery ping을 격리된 것으로
인정했다.

## 3회 반복의 정확한 범위

runner 계약으로 본 D6F45·D6F46·D6F48은 모두 다음을 만족했다.

| 런 | 유효 | 공격 중 primary 서비스 | stop 뒤 recovery 서비스 |
|---|---:|---:|---:|
| D6F45 | true | false | true |
| D6F46 | true | false | true |
| D6F48 | true | false | true |

따라서 별도 endpoint 기준 on/off 상관은 **3/3 반복**됐다. 하지만 각 런의 공격 처리율과
primary 실패 단계가 다르고, 같은 witness 회복·30초 fresh probe 연속 거부·30초 context
포화가 아니므로 기존 최종 승인 게이트를 통과한 것으로 쓰지 않는다. matched control도 이
런 디렉터리의 증거가 아니다.

## 설정·증거·출처 경계

- `du-config.yaml`: SHA-256
  `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`
- `cu-config.yaml`: 원격 활성 설정과 동일, SHA-256
  `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`
- `odu.log.gz`: current-boot DU 원문, SHA-256
  `c5b241442782dcd35e4401ae7e77373e905d8c517e9c38976fadf599c6c4e5af`
- `cu-rrc-events.log.gz`: UTC `18:00:30`–`18:04:20` timestamped CU slice,
  174,845줄, SHA-256
  `36308d32352f874fc3052805e94345c7e2a739ebf66e4ea004da18403217f34f`
- `stats.json`: 처리율·5초 창·점유·primary/recovery 시간축의 기계 판독 요약
- UE 바이너리 SHA-256:
  `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`
- runner / broker SHA-256:
  `245fe0222abd92c370d80b04caac62be2ee6b4d1c5e2c45b0743db3f6541c2c8` /
  `75c8aab23c151caf46198066d70f4f2db294cae2149eed2b8de2e3e9f1b95dfc`

원격 CU 전체 로그는 계속 증가하는 활성 파일이므로 전체 로그의 SHA를 고정 원문 해시로
쓰지 않는다. 판정에 사용한 로컬 timestamp-filtered gzip만 불변 증거로 봉인한다. p5의
CU/DU 프로세스·설정·서비스 상태는 이 분석 중 변경하거나 재시작하지 않았다.
