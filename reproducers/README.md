# 공격 재현 모듈

각 하위 디렉터리는 하나의 공격만 다루는 독립 모듈이다.

공통 메뉴와 환경 준비·빌드·실행 명령은 최상위
[통합 컨트롤러 사용 가이드](../CONTROL-GUIDE.md)를 따른다. 컨트롤러는 아래 모듈의 기존
실행기를 위임 호출하며 결과 디렉터리나 라벨 계약을 합치지 않는다.

| 모듈 | 상태 |
|---|---|
| [rrc-signaling-storm](rrc-signaling-storm/) | 동결·사용 가능. 검증 범위와 한계는 모듈 README 참고 |
| [blind-dos](blind-dos/) | 현재 유효 5G-GUTI one-shot 구현 완료. p5 direct 2-cell ZMQ matched control→attack G5 3/3 통과 |
| [uplink-dos](uplink-dos/) | NAS Service Request MAC 단발 변조형 + L3-21 위조 자격증명 실패 플러드 입력 에뮬레이션. 각 matched 3/3 통과 |
| [authentication-timeout-exhaustion](authentication-timeout-exhaustion/) | 2026-11-11 동결. Authentication Response 미전송 기전과 탐지 입력 생성, p5 동시 pre-auth 컨텍스트 6개 확인. 서비스 거부 미관측 |
| [downlink-imsi-extractor](downlink-imsi-extractor/) | 5G-Spector 계열 `Authentication Request → Identity Response(SUCI)` 결과 에뮬레이터. p5 ZMQ matched control→emulation 3/3, 실제 RF overshadowing 미검증 |
| [ue-capability-hijacking](ue-capability-hijacking/) | UE Capability Hijacking 계열의 보안 전 unsolicited `UECapabilityInformation` F1 관측 에뮬레이터. p5 matched control→emulation 3/3 통과 |

새 모듈은 최소한 README, 독립 라벨 계약, 정상 대조군, 유한 실행시간, `runs/`
로컬 보존 정책을 먼저 정한다. 실제 파일이 생기기 전에는 빈 `src/`, `tests/`,
`docs/` 디렉터리를 만들지 않는다.

모듈 완료는 표준·논문·공개 구현 근거, 실제 프로토콜 기전, 탐지 입력과 oracle 정답 분리를
필수로 한다. 서비스 거부와 기지국 전체 마비는 별도 효과 판정이며 필수 완료 조건이 아니다.
