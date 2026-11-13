# 포팅 가이드

공격 상태기계, oracle, 판정, 공통 artifact 스키마는 backend와 분리한다. 다른 gNB나 OTA로
옮길 때 교체할 부분은 profile, build/run adapter, 로그 parser 세 곳이다.

## p5에서 다른 가상 RF 환경으로

- `profiles/p5.example.json`을 새 이름으로 복사하고 실제 경로와 target allowlist를 채운다.
- detector·telemetry commit과 `period_ms=100`을 유지한다.
- CU/DU 주소와 UE endpoint는 profile의 environment에서 runner에 전달한다.
- 기존 protocol 모듈은 정상 attach·PDU·ping control을 먼저 통과시킨다.

## OTA로

- `profiles/ota.example.json`에 실제 SDR serial 두 개 이상, clock source, gain 상한을 적는다.
- `shielding_confirmed=true`는 케이블·감쇠·차폐를 사람이 확인한 뒤에만 설정한다.
- 정상 UE attach·PDU·ping, 주파수, clock, gain을 먼저 검증한다.
- Uu protocol 모듈만 matched 3회를 수행한다. detector-input-only 모듈은 OTA 결과를 만들지
  않고 `not_applicable`로 유지한다.

## 포팅 완료 조건

동일한 manifest rule ID와 공통 run 구조를 유지하면서 control과 active run이 재현되고,
입력 gap·timestamp 역행·period 불일치가 없으며, detector와 oracle의 조인이 확인돼야 한다.
RF 원인을 직접 관측하지 않은 결과 에뮬레이션은 OTA에서 실행됐더라도 RF 공격 성공으로
승격하지 않는다.
