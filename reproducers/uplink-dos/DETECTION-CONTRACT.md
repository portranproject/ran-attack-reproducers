# Uplink DoS 탐지 계약

## L3-21이 세는 신호

탐지 엔진의 L3-21 “상향 DoS(위조 자격증명)”는 한 셀에서 다음 NAS 실패 메시지를 센다.

- DL: `RegistrationReject`, `ServiceReject`, `AuthenticationReject`
- UL: `AuthenticationFailure`
- 제외: `SecurityModeReject`, AMF 내부 NAS MAC 검증 로그

production 기준은 `window_ms=10000`, `n_fail=5`, `n_fail_frac=0.1`,
`max_conn=96`, `fail_accept_wait_ms=3000`이다. p5의 실제 문턱은
`max(5, ceil(96×0.1))=10`이다. 실패 메시지 뒤 3초 동안
`RegistrationAccept`·`ServiceAccept`·RRC `SecurityModeCommand`가 없었던 서로 다른 연결이
10초 창에 10개 이상이면 branch 1을 RAISE한다.

## 두 재현 시나리오의 관계

기존 단발 NAS 무결성 손상형은 정상 UE 한 대의 `Service Request` MAC을 한 번만 바꾼다.
Open5GS는 무결성 실패 메시지를 조용히 폐기하므로 F1의 Reject 메시지는 0건이고, 건수도
1회뿐이다. 따라서 이 시나리오가 L3-21에 미탐되는 것은 룰 부재가 아니라 변형 불일치다.

무효·위조 자격증명 실패 플러드형은 같은 수정 OAI UE가 서로 다른 10개 RAN 연결에
`RRCSetupRequest → RRCSetup → RRCSetupComplete + RegistrationRequest → RegistrationReject`
순서를 만든다. UE marker는 사후 정답에만 쓰며 탐지기는 실제 F1/N2에서 생성된
`hello`·`ue_evt`·`kpm2`만 받는다.

## 입력과 정답 분리

- 탐지 입력: TeleRAN이 기록한 `observations.jsonl`의 `hello`·`ue_evt`·`kpm2`
- 사후 정답: UE marker, `run.json`, `oracle.jsonl`, `verdict.json`
- 탐지 출력: `detector.jsonl`과 production 엔진 stdout·설정·바이너리 SHA-256

탐지 엔진에는 시나리오 mode와 UE marker를 넣지 않는다. live control은 실패 연결 1개로
같은 메시지 종류를 유지한다. 합성 fixture는 경계 회귀만 위해 9건 무경보와 10건 경보를 쓴다.

## 주장 경계

live 실행은 수정 UE→ZMQ→DU/CU→TeleRAN→production detector 경로를 사용한다. 한 물리 UE가
10개의 새 RAN 컨텍스트를 만드는 것이며 10대의 물리 UE를 뜻하지 않는다. RF 송신 우위와
서비스 거부는 관측하거나 주장하지 않는다. 합성 fixture는 탐지기 경계 회귀 근거일 뿐이다.
