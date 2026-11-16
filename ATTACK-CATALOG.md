# 공격 카탈로그

이 문서의 13행이 플랫폼 1.0의 탐지 룰 기준 카탈로그다. 실행 가능한 최신 상태는
`./ctl.sh coverage`가 `reproducer.json`에서 생성한다. `qualified`는 해당 환경의 기존
증거가 있다는 뜻이고, `pending`은 구현 또는 자격 검증이 남았다는 뜻이다.

| 룰 | 대표 시나리오 | 재현 수준 | p5 | OTA |
|---|---|---|---|---|
| L3-01-V | RRC UE 컨텍스트 고갈 | 실제 프로토콜 | qualified | pending |
| L3-01-O | 인증 응답 미전송형 고갈 | 실제 프로토콜 | qualified | pending |
| L3-20 | 현재 유효 5G-GUTI 재사용형 Blind DoS | 실제 프로토콜 | qualified | pending |
| L3-21 | 무효·위조 자격증명 실패 플러드 | 실제 프로토콜 | qualified | pending |
| L3-24 | 비정상 Identity Response·식별자 노출 | 프로토콜 결과 에뮬레이션 | qualified | pending |
| L3-14 | 보안 전 UE Capability Information | 프로토콜 관측 에뮬레이션 | qualified | pending |
| L3-06 | NAS 카운터 비동기화 결과 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-01 | 인증 동기 실패 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-06a | NAS 카운터 reset 계열 재인증 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-02 | GUTI 불일치 후 상향 식별자 요청 결과 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-04 | 짧은 RRC 연결 반복 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-07 | RRC 거절·해제 투옥 계열 미완료 반복 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-08 | TAC 조작·가짜 기지국 복귀 신호 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |

새 7개 입력 시나리오는 고정된 production detector 기본 설정으로 matched
control→emulation 3/3을 통과했다. 이는 live p5 프로토콜이나 RF 원인의 관측이 아니다.
세부 증거는 [production detector replay](artifacts/production-detector-rule-replay-20261112/)에
있다.

## 재현 수준 해석

1. `protocol`: 수정 UE와 정상 gNB·코어 사이에서 원인 기전을 실제 메시지 경로로 만든다.
2. `protocol-result-emulation`: 현재 토폴로지에서 만들 수 없는 RF/MITM 원인 뒤의 결과를
   실제 UE→RAN→코어 경로에 만든다.
3. `protocol-observation-emulation`: 탐지가 보는 프로토콜 관측은 live 경로에 만들지만 원래
   공격의 전체 원인·효과는 만들지 않는다.
4. `detector-input-emulation`: 공개 연구 또는 p5 관측에 근거한 입력만 production detector에
   재생한다. live 경로와 RF 원인, 서비스 거부는 모두 false다.

서비스 거부 여부는 별도 판정 차원이다. 서비스 거부가 없더라도 기전 또는 탐지 입력 검증을
실패로 덮어쓰지 않는다.
