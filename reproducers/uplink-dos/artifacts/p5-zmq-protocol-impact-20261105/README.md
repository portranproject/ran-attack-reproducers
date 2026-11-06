# p5 ZMQ Uplink DoS 프로토콜 영향 에뮬레이션 실측

2026-11-05에 direct 1-cell ZMQ에서 실행한 최종 matched campaign의 게시용 증거다.

## 판정

- campaign: `p5-uplink-final-v5-20261105`
- 순서: 각 세트 `control → emulation`
- 요구/완료/통과: `3 / 3 / 3`
- control: 3/3 통과, MAC 변조 0회, impact ping 성공 `5/5·4/5·3/5`
- emulation: 3/3 통과, MAC 변조 각 1회, impact ping 모두 `0/5`
- 세 emulation 모두 Open5GS `NAS MAC verification failed`와 UE `Service Reject` 확인
- child 6개 모두 같은 PID 회복 ping 5회 연속, crash/forced kill 0
- 최종 판정: **uplink DoS의 NAS·서비스 영향 에뮬레이터 성공**

`rf_overshadowing_observed=false`이므로 실제 RF overshadowing 성공 증거가 아니다.

## 계보

- OAI 기준 commit: `6d6782b48484efd935c14e834832032743f9b138`
- UE patch SHA-256: `c6ffa479e9b90fd59ca9b8b104897a6c80ae754e5c05dc1b64acfdf9a2abaa78`
- `nr-uesoftmodem` SHA-256: `61521fe5e70e26146fa3f18a3edc0e38ee2e3bc2bb78ffaaba3a4dc562c6ce39`
- `liboai_zmqdevif.so` SHA-256: `732951603cf228114770452188e74f8b333a6eeb410a750a04507e13f9f04f25`
- runner SHA-256: `4a86d198f60f5ca1b9b15abab1d169e77b7c45727c9b19d228a177b14d0e811a`
- child verifier SHA-256: `2bb15e1d063dd5197050c810a72b0b1c08c3e96f25c1300708a784c68d26c6bf`
- campaign verifier SHA-256: `655cbff882a51fc8814f8835bcfc6f1c40bff3eb3b00135d7ae8098c5084ed7a`
- stack: OCUDU 26.10 CU/DU, Open5GS, OAI 2026.w38 UE, direct 1-cell ZMQ
- CU 실험 프로필: `inactivity_timer 7200 → 2`, 실행 뒤 원본 해시로 원복

## 판정 기준

control은 baseline 5/5, 변조 0회, paging 구간 성공 3/5 이상·연속 손실 2회 이하,
동일 PID 회복 5회 연속을 요구한다. emulation은 baseline 5/5, 변조 정확히 1회,
CU의 두 번째 `InitialUEMessage`, AMF의 `Service request`와 정확한
`NAS MAC verification failed`, UE의 `Service Reject`, ping 5회 연속 손실,
동일 PID 회복 5회 연속을 요구한다.

실행기는 PDU session setup 완료와 CU context `Removed`를 확인한 뒤 다음 단계로 간다.
이 게이트가 없던 개발 중간 run은 PDU setup과 release가 경합해 paging이 사라졌으며 최종
성능 근거에 합산하지 않았다.

## 파일 구성

- `campaign_result.json`: 6개 child의 게시용 판정과 verdict SHA-256
- `REMOTE-HASHES.sha256`: p5에 보존된 각 child 원문 전체의 SHA-256

raw UE·AMF·CU·DU 로그와 가입자 설정은 Git에 복사하지 않았다. 원문은 p5의
`/root/uplink-dos-runs/`에 있으며, campaign 집계 파일 SHA-256은
`c8436164f04cf10754f55773674927f57899b99c42d327ed331f6fda43f7e903`다.

## 주장 경계

이 결과는 공격자의 RF 송신이나 물리 채널 탈취를 구현한 것이 아니다. OAI UE가 정상
계산한 Service Request MAC을 송신 직전에 한 번 변조해, uplink DoS 이후 예상되는
프로토콜·서비스 결과를 실제 망 경로에서 발생시킨 것이다. 실 SDR OTA, RF 출력 우위,
상용망 일반화와 RF 원인 식별은 미검증이다.
