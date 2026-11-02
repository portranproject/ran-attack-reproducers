# p5 ZMQ 현재 유효 5G-S-TMSI 재사용형 실측

## 결론

`p5-current-tmsi-v3`의 공격 런은 공격자 one-shot과 AMF identity reach, 피해자의 기존
binding 변화를 exact join했고 피해 UE의 ping 손실도 관측했다. 그러나 같은 UE가 사전
고정한 30초 회복 제한 안에 회복하지 않아 캠페인은 `valid-failure`로 끝났다. 따라서 이
결과는 **G5 공격 성공이나 3/3 재현 성공이 아니다.**

또한 무작위 값·만료 값·현재 유효한 다른 UE 값 대조를 수행하지 않았으므로, 관측한 ping
손실을 5G-S-TMSI 충돌에만 특이적인 효과로 확정하지 않는다. 현재 허용 주장은 다음까지다.

- 현재 피해자 값이 공격자 commit 뒤 AMF까지 도달했다.
- 그 identity reach와 기존 피해자 NGAP binding 변화가 현재 런에서 조인됐다.
- 같은 런에서 피해 UE ping이 끊겼지만 Registration·PDU 상태 표시는 유지됐다.
- attack-off 대조군은 71/71 서비스 표본이 정상이었다.
- 공격군은 제한시간 안에 같은 피해 UE의 회복을 입증하지 못했다.

정제된 기계 판정은 [result.json](result.json), 설치 상태는 [inventory.json](inventory.json),
시계 근거는 [clock-sync.json](clock-sync.json)에 있다. 원시 로그·pcap·가입자 설정은 Git에
올리지 않고 팀 p5 증거 저장소에 보존한다.

## 사전 고정 계약

- matched 세트: 3
- 공격 순서: control → attack
- 공격: 현재 피해 UE의 48-bit 5G-S-TMSI를 별도 가입자 OAI UE가 1회 사용
- 관측: 40초
- 공격 전 정상 표본: 20회
- 서비스 손실: Registration·PDU·ping 중 하나가 5회 연속 실패
- 회복: 30초 안에 같은 피해 UE의 Registration·PDU·ping 정상 표본 20회
- 인프라 무효 재시도: 최대 3회, 유효 실패는 재시도하지 않음
- CU·DU·Open5GS 타이머·용량·소스 변경: 없음

N은 실행 전에 `blind-campaign -R N`으로 3~100 범위에서 바꿀 수 있다. `-R 10`은 유효
실패를 버리고 성공한 열 세트를 모으는 옵션이 아니다. 한 세트라도 유효 실패면 즉시 멈춘다.

## 실행 결과

| 단계 | 결과 | 핵심 증거 |
|---|---|---|
| control try01 | `infrastructure-invalid` | 피해 UE 기준선 이전 ZMQ 동기화 실패, 성능 판정에서 제외 |
| control try02 | `passed` | before 20/20, during 31/31, after 20/20 정상; attacker commit 0; crash 0 |
| attack try01 | `valid-failure` | exact join·binding 변화·서비스 손실 있음; 30초 안 회복 없음; crash 0 |
| campaign | `valid-failure` | 첫 유효 공격 실패에서 중단, 완료 matched 세트 0/3 |

공격 런에서는 공격 전 20/20 표본이 정상이었고, commit 뒤 첫 측정인 +1.184초부터
관측·회복 대기 동안 33/33 ping 표본이 실패했다. 마지막 실패 표본은 +73.339초였으며
Registration과 PDU session 상태 검사는 계속 참이었다. 공격자와 망 이벤트의 commit 기준
상대 시각은 다음과 같다.

| 이벤트 | 상대 시각 |
|---|---:|
| `target_msg3_committed` | 0초 |
| `rrc_setup_complete_submitted` | +0.090519초 |
| AMF `identity_reached` | +0.173799초 |
| 기존 피해 binding 변화 | +0.173825초 |
| `authentication_request_withheld` | +0.199463초 |
| 첫 서비스 실패 표본 | +1.184초 |
| 마지막 실패 표본 | +73.339초 |

자동 `exact_join`은 동기화된 시각, 공격자 commit, 표적 48-bit 값, current-run
`InitialUEMessage`, 피해자 snapshot의 RAN/AMF UE ID를 결합한다. Open5GS가 공격 도달
로그에도 기존 NGAP ID를 기록할 수 있으므로 새 ID 발급 자체를 요구하지 않는다. NGAP·F1
pcap은 봉인했지만 ASN.1 메시지별 자동 조인에는 아직 사용하지 않았다.

## 무결성

- campaign 입력: `d18418f61ad6d8110cc79a4a6b68d524af2e185e3268e38e4a6cfc319b100336`
- campaign 이벤트: `2c847e1f84c8a7e30833cb74b2bbeabb4bf2d783a2a2d8c9d886a4ec39c8c79d`
- campaign 결과: `2a86249d33920371b7e442acac2344cc88642bade5b75a77ee467a20f0d00d88`
- control manifest: `0b11b2a6ab09f781e02bde81ba528c2022085181d7cea503a7d4ebba1690c450`
- attack manifest: `e42c2333410e710e523c97b7529b201d2a89b36e77e5caa72f6b672da9503ef6`
- lab inventory: `fe8364bc01d361d190fb2df1bc815fb40dc21296882216d1c75408d610bd1596`
- clock evidence: `bcd028626f0c4b5de709a0f440630e1fa4114b202006cce9f993d82334e8652f`

두 유효 런의 `evidence_manifest.json`은 현재 verifier로 다시 검증해 통과했다. v2 캠페인은
공격군 네 시도가 모두 피해 UE 기준선 전에 실패한 `infrastructure-invalid` 진단이라 성능
근거에서 제외했다.
