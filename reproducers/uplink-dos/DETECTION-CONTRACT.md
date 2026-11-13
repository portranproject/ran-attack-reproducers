# Uplink DoS 탐지 계약

## L3-21이 세는 신호

탐지 엔진의 L3-21 “상향 DoS(위조 자격증명)”는 한 셀에서 다음 NAS 실패 메시지를 센다.

- DL: `RegistrationReject`, `ServiceReject`, `AuthenticationReject`
- UL: `AuthenticationFailure`
- 제외: `SecurityModeReject`, AMF 내부 NAS MAC 검증 로그

production 기본값은 `window_ms=10000`, `n_fail=5`,
`fail_accept_wait_ms=5000`이다. 실패 메시지 뒤 5초 동안
`RegistrationAccept`·`ServiceAccept`·RRC `SecurityModeCommand`가 없었던 서로 다른 연결이
10초 창에 5개 이상이면 branch 1을 RAISE한다.

## 두 재현 시나리오의 관계

기존 단발 NAS 무결성 손상형은 정상 UE 한 대의 `Service Request` MAC을 한 번만 바꾼다.
Open5GS는 무결성 실패 메시지를 조용히 폐기하므로 F1의 Reject 메시지는 0건이고, 건수도
1회뿐이다. 따라서 이 시나리오가 L3-21에 미탐되는 것은 룰 부재가 아니라 변형 불일치다.

무효·위조 자격증명 실패 플러드형은 서로 다른 5개 연결에
`RRCSetupRequest → RRCSetup → RRCSetupComplete + RegistrationRequest → RegistrationReject`
순서를 만들고 수락 메시지를 넣지 않는다. `kpm2` 시계를 마지막 거절 뒤 5초 이상 진행해
fail-accept gate도 실제 룰 코드로 평가한다.

## 입력과 정답 분리

- 탐지 입력: `detector-input.jsonl`의 `hello`·`ue_evt`·`kpm2`
- 사후 정답: `observations.jsonl`, `run.json`, `verdict.json`
- 탐지 출력: `l3-21-verdict.json`에 보존한 실제 엔진 stdout과 엔진·설정 SHA-256

탐지 엔진에는 p5 PCAP 해시, 시나리오 mode, 사후 정답을 넣지 않는다. control은 실패 연결
1개로 같은 메시지 종류를 유지하되 임계값 아래에 둔다.

## 주장 경계

에뮬레이션은 실제 p5 F1에서 확인한 메시지 순서와 시간 범위를 바탕으로 하지만 live UE나
코어를 실행하지 않는다. 따라서 L3-21 탐지 검증에는 쓸 수 있으나 live 프로토콜 공격,
서비스 거부, RF overshadowing 성공 근거로 쓰지 않는다.
