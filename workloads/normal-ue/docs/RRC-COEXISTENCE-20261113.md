# 정상 UE 5대와 RRC storm 공존 실측 (2026-11-13)

## 결론

p5의 같은 DU·셀에서 정상 UE 5대를 먼저 Registration·PDU·ping 5/5로 만든 뒤 RRC storm을
60초 실행했다. 이미 연결된 5대는 두 변형 모두 RRC Reject·release 없이 서비스를 유지했다.

RRC storm은 기존 `RRC_CONNECTED` UE를 직접 끊는 공격이 아니라 새 RRC 접근에 필요한
자원을 압박한다. 따라서 공격 전에 붙어 있던 UE와 공격 중 새로 접속하는 UE를 분리해서
판정해야 한다.

## 구성

- 공격: OAI 6프로세스 × 2 logical UE
- 정상: OAI 1프로세스 × 5 logical UE, UE별 독립 virtual RU
- broker: 공격 6개와 정상 5개, 총 11 ZMQ endpoint를 같은 DU·셀로 합산
- DU capacity 96, CU max 200, 기본 cleanup 유지
- 정상 UE 5/5 연결 뒤 공격을 시작하기 위해 공격 시작을 90초 지연

## 이미 연결된 정상 UE 5대

| 공격 변형 | 공격 attempt / Msg3 | 정상 Registration/PDU | 정상 RRC Reject/release | ping | 결과 |
|---|---:|---:|---:|---:|---|
| RRCSetupRequest 후 중단형 | 3,062 / 3,060 | 5/5 | 0/0 | 891/891 | 5대 유지 |
| RRCSetupComplete 미전송형 | 1,287 / 1,282 | 5/5 | 0/0 | 885/886 | 5대 유지 |

두 실행 모두 정상 UE의 ZMQ channel timeout과 crash marker는 0이었다. 후자의 ping 손실
1개는 0.113%이며 RRC release·재등록으로 이어지지 않았다.

## 공격 중 새로 접속한 정상 UE 5대 비교

RRCSetupRequest 후 중단형을 먼저 시작하고 10초 뒤 정상 UE 5대의 접속을 허용했다.

- 4대는 Registration·PDU·ping에 성공했다.
- 1대는 관측 종료까지 TUN을 만들지 못했다.
- 실패 UE에 명시적 `RRCReject`는 없었다.
- 해당 UE는 Msg3 전에 잘못된 RAPID의 RAR을 반복 수신해 random access에서 멈췄다.
- 공격 종료 뒤 약 40초 관측에서도 자동 회복하지 않았다.

따라서 이 단일 표본의 정확한 표현은 `RRC Reject 1/5`가 아니라
**`기존 연결 5/5 유지, 공격 중 신규 접속 4/5 성공·1/5 pre-RRC 실패`**다.

## 증거

원문은 p5 DU의 `/root/normal-ue-qualification/coexist-runs/`에 보존했다.

- 기존 연결·RRCSetupRequest 후 중단형 `result.json` / `normal5-monitor.tsv`:
  `57241dcb4ba6457d8c2e296a53470a8e61fecefd347d568a72ba2aedabfe91a6` /
  `073b400eb31f4751297bba24af3acaa6fbd52bb0093e551f605d2b137fb5a71e`
- 기존 연결·RRCSetupComplete 미전송형 `result.json` / `normal5-monitor.tsv`:
  `40dee19c10a7412414a522416d9ff098293556f43fc9b796cee7534df4b55378` /
  `f40243467d0915677f4220ddf4721a7bd44811759241604997d4e3791e6797ee`
- 신규 접속 비교 `result.json` / `fresh5-monitor.tsv` / `du.log`:
  `b0a3032fe691e16235422c4fab9984d47d5538a4d8e57f59ae0b5acd644d8e18` /
  `93d0e0ba98a1db955c3b97dea4e7bad0e212551dfe43ca17b0c8808569826abc` /
  `ac5496110162cd3a1f9f0b36026c83b66957bf86791e21fffea09c0473dca8df`

각 실행은 단일 표본이다. 서비스 영향의 반복성·확률을 주장하려면 같은 순서로 matched
control→attack을 최소 3세트 반복해야 한다.
