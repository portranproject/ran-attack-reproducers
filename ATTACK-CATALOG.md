# 공격 카탈로그

이 문서의 7개 L3 공격이 플랫폼 1.0의 공격 재현 기준 카탈로그다. AN 이상탐지 fixture는
완성 기준에서 제외하고 참고 부록으로만 유지한다. 실행 가능한 최신 상태는
`./ctl.sh coverage`가 `reproducer.json`에서 생성한다. `qualified`는 해당 환경에서 기전,
실측 TeleRAN 입력, production detector, dashboard를 연결한 matched 3/3 증거가 있다는
뜻이고, `pending`은 구현 또는 자격 검증이 남았다는 뜻이다.

| 룰 | 대표 시나리오 | 재현 수준 | p5 | OTA |
|---|---|---|---|---|
| L3-01-V | RRC UE 컨텍스트 고갈 | 실제 프로토콜 | qualified | pending |
| L3-01-O | 인증 응답 미전송형 고갈 | 실제 프로토콜 | qualified | pending |
| L3-20 | 현재 유효 5G-GUTI 재사용형 Blind DoS | 실제 프로토콜 | qualified | pending |
| L3-21 | 무효·위조 자격증명 실패 플러드 | 실제 프로토콜 | qualified | pending |
| L3-24 | 비정상 Identity Response·식별자 노출 | 프로토콜 결과 에뮬레이션 | qualified | pending |
| L3-14 | 보안 전 UE Capability Information | 프로토콜 관측 에뮬레이션 | qualified | pending |
| L3-06 | 요청되지 않은 NAS SecurityModeReject 결과 | 프로토콜 결과 에뮬레이션 | qualified | pending |

## 참고용 AN 이상탐지 fixture

다음 6개는 production detector 회귀용 입력 fixture다. 공격 재현 플랫폼 1.0의 합격·실패에는
포함하지 않는다.

| 룰 | 대표 시나리오 | 재현 수준 | p5 | OTA |
|---|---|---|---|---|
| AN-01 | 인증 동기 실패 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-06a | NAS 카운터 reset 계열 재인증 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-02 | GUTI 불일치 후 상향 식별자 요청 결과 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-04 | 짧은 RRC 연결 반복 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-07 | RRC 거절·해제 투옥 계열 미완료 반복 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |
| AN-08 | TAC 조작·가짜 기지국 복귀 신호 | 탐지 입력 에뮬레이션 | pending | 해당 없음 |

6개 AN 입력 시나리오는 고정된 production detector 기본 설정으로 matched
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

L3-01-V·L3-01-O·L3-20·L3-24·L3-14의 p5 E2E 자격 결과는
[2026-11-17 실제 경로 검증](artifacts/p5-live-e2e-five-20261117/)에 보존한다. L3-21과
L3-06은 각 모듈의 p5 artifact를 따른다.
