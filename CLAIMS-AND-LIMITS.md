# 주장과 한계

| 범위 | 현재 주장 | 주장하지 않는 것 |
|---|---|---|
| 기존 6개 룰 | 각 모듈 README에 봉인된 p5 기전·결과·입력 재현 | 상용망 일반화, 미관측 RF 원인 |
| L3-21 | 정상 UE 5대 same-cell의 실제 UE 실패 플러드와 production detector matched 3/3 | RF 송신 우위, 물리 UE 10대, 서비스 거부 |
| L3-20 same-cell | oracle의 피해자 mapping 선택 로직만 회귀 검증 | 단일 셀 p5 공격 성공; 현재 독립 ZMQ UE 시간축으로 victim RA 실패 |
| 새 7개 룰 | 연구 기반 입력과 production detector matched 3/3 | p5 live 메시지 경로, 실제 공격 효과 |
| 서비스 영향 | 개별 verdict에서 관측된 경우만 기록 | 재현 성공과 기지국 마비의 동일시 |
| OTA | profile·doctor·계약 준비 | 실 SDR matched 3/3 완료 |

공통 `verdict.json`은 기전, 탐지 입력, 탐지 결과, 서비스 영향을 독립 상태로
보존한다. 상태값은 `pass`, `fail`, `not_observed`, `not_applicable`, `inconclusive`뿐이다.
입력 에뮬레이션 실행은 `live_protocol_path_observed=false`, `rf_cause_observed=false`,
`service_denial_observed=false`를 강제한다.
