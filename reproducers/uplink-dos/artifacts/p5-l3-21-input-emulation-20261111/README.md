# p5 참조 기반 L3-21 입력 에뮬레이션 실측

## 결론

2026-11-11 production 탐지 엔진 기본 설정으로 matched `control → emulation` 3세트를
재생했다. control 3회는 L3-21 RAISE 0회, emulation 3회는 모두
`branch=1`, `fails_w=5`, `n_fail=5`, `window_ms=10000` RAISE 정확히 1회였다.

| 항목 | control 3회 | emulation 3회 |
|---|---:|---:|
| 완전한 RRC→등록 거절 컨텍스트 | 각 1개 | 각 5개 |
| RegistrationReject | 각 1건 | 각 5건 |
| 거절 간격 | 0 ms | 각 2,000 ms |
| L3-21 branch 1 RAISE | 모두 0회 | 모두 1회 |
| child 판정 | 3/3 통과 | 3/3 통과 |

## 참조 실측과 주장 경계

p5 live 시험 한 번에서 서로 다른 F1 컨텍스트의 `RegistrationReject` 5건을 2.260초
안에 관측했다. 원문 PCAP SHA-256은
`f3222e81d0cef1904159e724ead95e831a8aefa847761069e8cbdbcc264609e6`이다.

OAI 반복 RRC 재접속은 PHY segfault, RU-sharing 다중 UE는 한 실행에 최대 3개 거절로
불안정했다. 따라서 이 artifact는 live 프로토콜 플러드 성공 근거가 아니라, 실제 p5에서
확인한 신호 모양을 이용한 **탐지 입력 에뮬레이션 3/3** 근거다. 모든 child에
`live_protocol_path_observed=false`, `rf_overshadowing_observed=false`를 고정했다.

## 무결성

- 탐지 엔진 소스: `portranproject/detection` `dev`
  `a34b358e585e24aa91b1586da022ad14ef98d3e0`
- 탐지 엔진 SHA-256:
  `f50ce9bd8149663c7a3f3fddc88d46fbd8edf204649f7d8c72c7414bbb97e067`
- production 설정 SHA-256:
  `9bbb0b5039b05d0aa73c31c4a4e30860042a873ebc48ba8589191f6f61c77c53`
- `campaign.json` SHA-256:
  `48ad8095a727737e601d79049f7037003441dafa1209b5645119300e02d58248`
- child 원문의 SHA-256은 `campaign.json.raw_files_sha256`에 있다.
