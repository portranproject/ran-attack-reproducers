# p5 기본 cleanup 공격률 재검증 — 서비스 on/off와 지속포화 한계

날짜: 2026-10-30

환경: OCUDU 26.10 CU/DU + OAI 2026.w38 UE + ZMQ 가상 RF

판정: **기본 약 2초 cleanup에서 A-early 서비스 실패→별도 UE 회복은 3/3 반복됐지만,
지속 context 포화·30초 반복 거부·기지국 전체 마비는 재현하지 못했다.**

이 artifact는 hold32 결과를 공격 성공 증거에서 제외한 뒤, gNB의 cleanup/RLF 값을
늘리지 않고 공격자 측 시도율만 높여 다시 검증한 원문이다. D4에서는 공격 제공률이
정리율을 넘었지만 정상 UE도 공격 중 Registration·PDU·ping에 성공했다. 이어서 실행한
D6F25에서는 같은 broker·gNB 안에서 공격 중 정상 서비스 실패와 공격 종료 후 별도
선기동 witness의 Registration·PDU·ping 회복을 확인했다. 다만 두 실행 모두 실제
admission률이 지속 포화에 필요한 수준에 못 미쳤다. 후속 D6F45·D6F46·D6F48은 같은
기본 설정에서 service-off→별도 endpoint recovery-on을 3/3 반복했고, 동일한 8-endpoint
attack-off D6C51은 정상 서비스에 성공했다. 가장 빠른 D6F48도 admission 이후 점유를
지속 포화시키지는 못했다.

## 결론

공격 성공 조건은 단순한 `요청률 > 정리율`도, `admitted > cleanup`의 장시간 유지도 아니다.

```text
N(t+Δ) - N(t) = admitted(t,t+Δ) - cleanup(t,t+Δ)
```

bounded capacity가 차기 전에는 `admitted > cleanup`이어야 점유가 늘지만, 찬 뒤에는
초과 요청이 거절되므로 장시간 평균 `admitted = cleanup`으로 수렴한다. 따라서 포화 뒤에도
`admitted > cleanup`을 요구하는 것은 보존식상 불가능하다. 대신 offered/provisional 부하가
cleanup을 계속 넘는지, 초과분이 overflow 거절로 바뀌는지, 공격 중 정상 서비스가 반복
실패하고 stop 뒤 회복하는지를 함께 본다. D4의 F1 제공률은 48.652/s였지만
`DU is not able to serve the UE`가 1,033건 발생해 실제 RRC Setup 시작은 40.095/s로
줄었다. 워밍업 뒤 생성률 40.026/s와 정리율 39.922/s의 차이는 0.104/s뿐이었고,
24개 5초 창 중 생성률이 정리율보다 큰 창은 12개뿐이었다.

따라서 D4 결과만으로는 “기지국 마비”를 주장하지 않는다. 아래 D6 반복은 더 좁은
**서비스 수준 on/off 상관 3회**를 입증하지만, 30초 fresh-witness 반복 거부와 동일 UE
회복이 없어 “기지국 전체 마비를 공격자가 통제했다”는 최종 주장에는 미달한다.

## D6F45·D6F46·D6F48 — 기본 cleanup 서비스 on/off 3회

- 공격: 6 OAI 프로세스 × 2 logical UE, A-early, 60초, 공격자 Msg5 0
- 설정: DU capacity 96, CU `max_nof_ues: 200`, cleanup/RLF/hold override 없음
- witness: 공격 중 primary endpoint 7, stop 뒤 처음 시도하는 prelaunched endpoint 8
- 원문: `raw/D6F45-v6-default159-aearly-p6u2-prelaunch-cycle-try01/`,
  `raw/D6F46-v6-default159-aearly-p6u2-prelaunch-cycle-try02/`,
  `raw/D6F48-v6-default159-aearly-p6u2-prelaunch-cycle-try03/`

| 런 | Msg3 offered | DU provisional | cleanup | 공격 중 primary | stop 뒤 recovery |
|---|---:|---:|---:|---:|---:|
| D6F45 | 36.064/s | 34.264/s | 18.096/s | service false | service true, ping 539/539 |
| D6F46 | 40.055/s | 38.687/s | 26.930/s | service false | service true, ping 250/251 |
| D6F48 | 77.408/s | 73.338/s | 34.209/s | service false | service true, ping 244/244 |

D6F48은 완전한 5초 창 12/12에서 offered와 DU provisional이 cleanup보다 높았다. F1
4,451건 중 2,373건은 Setup admission 전에 즉시 거절됐고, admitted Setup 2,078건과
timeout cleanup 2,078건은 34.208/s로 평형이었다. 점유 피크는 95/96이었다. primary는
4회 시도 중 두 번 즉시 거절, 한 번 timeout, 마지막은 RRC/InitialUEMessage까지 갔지만
Registration·PDU가 0이었다. 공격 stop 9.295초 뒤 별도 endpoint는 Registration·PDU와
ping 244/244에 성공했다.

정확히 같은 6×2 quiet load와 두 witness를 띄운 8-endpoint D6C51은 load·extra endpoint
시도 0건, primary Registration·PDU·ping 303/303, crash·forced kill 0으로 통과했다.
따라서 endpoint 수만으로 공격군 실패를 설명할 수 없다. 다만 recovery는 primary와 다른
endpoint이고, primary probe도 30초 동안 fresh UE 10개를 반복한 계약이 아니므로 이 결과를
지속 기지국 마비로 확대하지 않는다.

- matched control 원문·판정:
  `raw/D6C51-v6-default159-control-p6u2-primary110-extraquiet8-try01/`

## D6F50 — 기본 cleanup canonical A 기전 확인, denial 실패

- 원문: `raw/D6F50-v6-default159-canonical-p6u2-prelaunch-cycle-try01/`
- 공격: 6 OAI 프로세스 × 2 logical UE, Msg4 ACK 뒤 Msg5 생략, 60초
- exact join: UE canonical 후보 205건 중 current-run DU FAPI HARQ ACK와 전역 유일 조인 149건
- 공격자 Msg5: 0건

Msg3 34.824/s와 DU provisional Create 32.071/s는 cleanup 28.362/s보다 빨랐지만,
F1 1,945건 중 225건이 Setup admission 전에 즉시 거절됐다. admitted Setup은
28.363/s로 cleanup과 평형이었고 점유 피크는 84/96, 96 점유는 0초였다. 공격 중
primary 정상 UE는 RRC·Registration·PDU와 ping 194/195에 성공했다. 따라서 이 런은
v6 바이너리의 canonical A 기전과 exact ACK 조인만 입증하며, 서비스 거부나 공격자
통제성 증거가 아니다.

## D6F25 — 같은 broker·gNB의 공격 중 서비스 실패와 종료 후 회복

- 원문: `raw/D6F25-v4-dual-cycle-default2/`
- matched attack-off 대조: `raw/D6C22-v4-broker6x2-matched/`
- gNB cleanup: 관측 median 1,999ms, p90 2,000ms; hold/RLF override 없음
- 공격: 4 OAI 프로세스 × 2 logical UE, A-early, 공격자 Msg5 0
- witness: 공격 중 primary와 공격 종료 후 recovery를 시작부터 같은 broker에 선기동

공격 관측창 40.737초에서 Msg3 제공은 1,662건(40.80/s), CU가 본 요청은
1,611건(39.55/s)이었다. 실제 RRC Setup 생성은 1,297건(31.84/s), 같은 창의 cleanup은
1,243건(30.51/s)이었다. 제공률과 창 전체 admission은 cleanup을 넘었지만 5초 창별
`start > cleanup`은 5/9에 불과했다. 점유는 peak 83/96, 96 유지 0초였다.

Primary witness `0x484f`는 공격 중 `RRCSetupComplete`·`InitialUEMessage`·인증까지
진행했다. 그러나 DU는 약 0.797초 동안 fallback 자원 배정 실패 175건과 PDSCH 공간
부족을 기록했고, CU는 `UEContextSetupFailure: no-radio-resources-available`로 종료했다.
Registration·PDU·ping은 없었다.

공격 프로세스마다 kill switch는 정확히 한 번이고 이후 새 attempt/retrigger는 0이었다.
같은 실행 안의 별도 recovery witness `0x4c67`은 마지막 kill 뒤 9.33초에 Msg3,
9.47초에 RRC 연결, 10.86초 안에 Registration·PDU와 첫 ping에 도달했다. ping은
295/295였다. 중간 gNB·broker 재시작은 없다.

따라서 D6F25로 주장하는 범위는 다음뿐이다.

> 기본 cleanup을 유지한 ZMQ p5 환경에서, 공격 부하가 정상 UE의 후속 무선자원
> 설정을 실패시켰고 공격 중지 후 같은 gNB에서 별도 정상 UE 서비스가 회복됐다.

“96 지속 포화”, “30초 연속 RRCReject”, “기지국 전체의 지속 마비”, “동일 UE 프로세스
회복”은 주장하지 않는다. dual-witness 사이클도 아직 1회다. 당시 `result.json`은 TUN과
ping을 전역 집계해 primary에도 `attached/ping_ok=true`를 표시했다. Registration/PDU와
`service_ok=false`는 정확하며, 역할별 교정 판정은 `verdict.json`에 있다. runner의 후속
수정은 이 귀속 결함을 고쳤다.

Matched attack-off D6C22는 같은 7-process topology에서 7/7 sync,
Registration·PDU·TUN, ping 323/324, crash 0으로 통과했다.

## 핵심 실행

### D4B1 — 한 OAI 공격 프로세스 6 UE + 독립 정상 witness

- run: `raw/D4B1-two-process-u6-default2/`
- 공격창: `2026-10-30T13:56:56.290661Z`–`13:58:57.004653Z`, 120.714초
- 공격 UE: 6개 RA-only 반복 UE를 한 OAI 프로세스에 배치
- witness: 별도 OAI 프로세스의 full-service UE 1개
- gNB 설정: CU `max_nof_ues: 200`; cleanup/RLF override 없음
- 관측 cleanup: median 1,999.517ms, p90 1,999.846ms

| 항목 | 결과 |
|---|---:|
| 공격 `attempt_start` | 5,970 (49.456/s) |
| F1 Initial UL | 5,873 (48.652/s) |
| DU 선행 거절 | 1,033 (8.558/s) |
| 실제 RRC Setup 시작 | 4,840 (40.095/s) |
| cleanup + 정상 완료 | 4,757 (39.407/s) |
| 공격 Msg5 | 0 |
| 점유 peak | 96 |
| 점유 96 이상 | 1.678초 (1.39%) |
| 점유 96 최장 연속 | 0.885초 |
| CU 200 도달 | 없음 |

정상 witness의 첫 distinct 시도는 거절됐지만 두 번째 시도는 1.03초 뒤 수락됐다.
UE 결과의 `rrc_reject: 3`은 세 번의 독립 시도가 아니라 첫 거절의 DL 복사본 세 개다.
이후 `RRCSetupComplete`·`InitialUEMessage`·Registration·PDU Session이 성공했고,
공격 중 ping은 437/438 성공(loss 0.22831%)이었다.

### R3T4 — 단일 직접 셀의 최대율 진단

- archive: `raw/archives/R3T4-L4-nogates-default2.tar.gz`
- 6 UE, 60초, ACK/RA gate 0, Msg4 wait 1, 기본 cleanup
- 시도 2,839, Msg3 2,767, Msg4 수신 1,850, Msg5 0
- RRC Setup 시작 2,660(44.3/s), 종료 2,566(42.8/s)
- 점유 96 이상 21.4/60초(36%), 최장 연속 1.40초

평균 생성률은 정리율보다 약간 높았지만 burst 사이의 빈틈 때문에 포화를 유지하지
못했다. exact DU ACK join은 `no_match`이므로 이 실행을 canonical A 증거로 세지 않는다.

### D3B2 — 7개 직접 공격 셀 + broker 공격 셀 + 독립 witness

- broker 원문: `raw/D3B2-default2-u8-allcells/`
- 직접 셀 원문: `raw/archives/D3B2-L1..L7-canonical-default2.tar.gz`
- 직접 셀 7개의 시도 합계 46,654; 각 셀 Msg5 0
- broker 공격 시도 6,584; 공격 Msg5 0
- CU RRC Setup 시작 9,696/164초(59.1/s), cleanup 9,651건
- CU 점유 peak 200이지만 200 이상은 총 1.7초, 최장 1.70초
- witness는 거절 뒤 연결되어 Registration·PDU와 ping 449/449에 성공

공격 경로를 여러 셀로 늘려도 시작·정리 burst가 동기화되고 빈 slot의 admission이
정상 UE와 경쟁해 지속 거부가 되지 않았다. 직접 셀 archive의 내부 manifest는 반출
전에 모두 검증했지만 exact DU ACK join은 모두 0이므로 canonical A 증거가 아니다.

## 막힌 이유

1. OAI full-stack PHY가 만든 **제공률** 중 일부는 DU capacity 앞에서 잘려 컨텍스트를
   만들지 못한다.
2. D6F48처럼 제공 부하를 평활화해도 초과분은 admission 전 즉시 거절되고, 실제 admission은
   기본 2초 cleanup과 평형으로 수렴한다.
3. bounded DU가 overflow를 버리므로 높은 offered rate만으로 96개 미완료 Setup을 계속
   점유한다는 보장은 없다.
4. CU admission은 빈 slot이 생긴 순간의 경쟁이므로, 서비스 실패 3회만으로 모든 정상 UE의
   30초 연속 거부를 일반화할 수 없다.

## 해결 방향과 다음 합격 기준

gNB cleanup을 늘리는 방식은 다시 쓰지 않는다. 다음 구현은 공격자 측에서 fill과 overflow,
정상 UE 영향을 동시에 통제해야 한다.

1. OAI full PHY UE를 더 복제하는 대신, UE별 첫 시도를 cleanup 주기 전체에 분산하는
   경량 event-driven/multi-UE 송신 경로 또는 충분한 독립 RF chain을 사용한다.
2. fill 구간에는 `admitted - cleanup > 0`으로 점유가 증가하는지, 포화 구간에는
   offered/provisional 초과분이 지속 overflow 거절로 바뀌는지 확인한다.
3. CU 200 또는 의도한 DU 한도를 30초 이상 유지하거나, 독립 fresh witness의 30초 반복
   서비스 실패로 동등한 고갈 효과를 입증한다.
4. 별도 full-service witness가 10회 이상·30초 이상 연속 거부되고, 공격 중 Msg5·등록·
   PDU·ping 성공이 0이어야 한다.
5. 공격 프로세스만 중지한 뒤 같은 witness가 30초 안에 Registration·PDU·ping 20/20으로
   회복해야 한다.
6. 같은 조건을 세 번 반복하고 canonical A exact DU ACK join을 별도로 확보한다.

이 기준을 모두 통과하기 전에는 이 도구를 “통제 가능한 기지국 마비 재현기”라고 부르지
않는다.

## 소프트웨어·설정 계보

- D6 UE patch: `90068853babfdba3a698f29d4c9b4b34bf8d417985ae08faee1a31ae736f1922`
- D6 UE binary: `6708a4372b898944d3dbbfba95f29bb038aa6fcf913609c6329438818be03efa`
- D6F45·46·48 UE binary: `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`
- D6F50 canonical UE binary: `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`
- curated patch: `90068853babfdba3a698f29d4c9b4b34bf8d417985ae08faee1a31ae736f1922`
- exact ACK RNTI patch: `62cdea20481f9f0c6ba33ce2f5025eb5347af7c5481c90496c6fee4ddf57cd64`
- D6F45·46·48 실행 runner: `245fe0222abd92c370d80b04caac62be2ee6b4d1c5e2c45b0743db3f6541c2c8`
- 8-endpoint matched-control runner: `39a0d968f957f7a301303d8dd9b965384c8d56f4dfe0b3213b079a875ed5a94f`
- 8-endpoint flowgraph: `75c8aab23c151caf46198066d70f4f2db294cae2149eed2b8de2e3e9f1b95dfc`
- D6F25 실행 runner: `93c1cb922a95a32ce06200d178427b6fbf7f8312afe3f6bab9ff7b23d47ed94e`
- 역할별 TUN/ping 귀속 수정 후 runner: `84da7a685f6bf140db816058c411348777a8af04c4f4ecb6434c63b48f9e77c0`
- 6-endpoint flowgraph: `5f73417e94d90c8f6dff3c17dcd62647ac2d9e652fb5864e85ca7e3f17750f9f`
- D6 CU config: `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`
- D6 DU config: `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`
  (둘 다 cleanup/RLF override 없음)
- UE patch: `4ef70618f5fc9d97806f3661b74d842e07ede80bd27bad3c31ffd4551517a1ac`
- UE binary: `c27611938d74648926959b1f9156eafc55d518b1a27d03d0c0056fb70114cb83`
- verified ZMQ plugin: `6360a30ec93a3b1a9c0027eb5bdfd865ed1ed462967f18e6b8263fad6e246be6`
- broker wrapper: `e4a56cb254f13e26ce3cbfcf185fd9e716d76b6c9783e0bb3115375b1191d37f`
- two-endpoint flowgraph: `4a2da46c7aef29bf489e80b5bc4b8041142e4e746396967980fe9b11909d2cdf`
- D4 CU config: `fdbfbe2bfcc50f0798a07b402779b4ad7c3a7dd91f2a6604f1d216295d2ace70`
- D4 lane0 DU config: `f2b2024ff6a5d986f5271cb0f3fe4e9a81c70c2901377fd1f5772054a8f0275f`

`raw/archives.sha256`는 압축 반출한 직접 셀 원문의 해시다. D4의 원래 `du.log`
SHA-256은 `ad1b0456cb3fb0dbd41c117a496fe8760c08c9b81ce0c5f1c4e079ac27ab2d58`이고,
보관본은 `du.log.gz`다.

## 원복과 p5 종료

- CU 설정 원복 SHA-256: `2ab32fc1f27e709b1dd80a4aaf72d61363c96638d064e413cdd539fe3abb15b0`
- 원본 DU 설정 원복 SHA-256: `35ea900e8253013aeec398952d4a6c3c1f407880018d940270b53497700e0b17`
- 임시 공격 DU 인스턴스 7대: 모두 `terminated`
- D6용 임시 `rss-smooth-lane` 인스턴스: 프로세스 정상 종료 후 `stopped`
- 원본 CU·DU 인스턴스 2대: 실험 프로세스 정상 종료 후 모두 `stopped`
- 2026-11-02 AWS 재확인: CU `i-0a9ae984317255dbb`, 원본 DU
  `i-0d2fbb5ef0943021b`, D6 L0 `i-079201da4eb2fa0c0` 모두 `stopped`

## 증거 한계

- D4는 exact DU ACK join, D4 전용 matched control, 동일 조건 3회 반복을 하지 않았다.
- D6 A-early는 서비스 수준 on/off 3회와 8-endpoint control을 확보했지만, 같은 primary의
  회복·30초 fresh-witness 반복 거부·30초 지속 점유는 확인하지 않았다.
- D6F50 canonical A는 exact DU ACK 149건을 확보했지만 공격 중 정상 서비스가 성공해
  denial 증거가 아니다.
- 점유 수치는 CU의 미완료 RRC Setup lifecycle 재구성이며 DU의 모든 내부 자원과 동일한
  값이 아니다.
- ZMQ 결과를 차폐 OTA나 상용 gNB로 일반화하지 않는다.
