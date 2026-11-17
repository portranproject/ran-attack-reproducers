# 차폐 OTA 운영

OTA는 장비를 연결했다고 자동으로 qualified가 되지 않는다. 다음 순서를 모두 통과해야 한다.

현재 공통 OTA run adapter는 구현되지 않았다. `./ctl.sh setup|run|campaign --profile ota`는
p5용 ZMQ 설정을 잘못 실행하지 않도록 실패한다. 아래 항목은 adapter 구현 뒤의 승인 절차다.

1. `profiles/ota.json`에 공격 UE와 O-DU SDR의 서로 다른 serial, clock source, gain 상한을
   기록한다.
2. RF 케이블·감쇠기·차폐박스가 외부 송신을 막는지 사람이 확인하고 그때만
   `shielding_confirmed=true`로 바꾼다.
3. `./ctl.sh doctor --profile ota`로 inventory, credential 권한, detector·telemetry,
   `period_ms=100`을 확인한다.
4. 공격 기능을 끈 정상 UE의 attach·Registration·PDU·ping과 telemetry gap 0을 먼저
   통과시킨다.
5. Uu protocol 모듈만 matched control→attack/emulation 3세트를 실행하고, 매 set 뒤
   정상 회복을 확인한다.
6. p5와 OTA의 메시지 흐름, input gap, detector latency 차이를 report에서 비교한다.

RF 원인이 없는 detector-input 모듈은 OTA를 실행하지 않고 `not_applicable`로 둔다. 결과
에뮬레이션 모듈은 OTA에서 동작해도 RF overshadowing/MITM을 별도 계측하지 않았다면
`rf_cause_observed=false`를 유지한다. 현재 실제 SDR inventory와 차폐 확인이 제공되지 않아
모든 OTA 실측 자격은 pending이다.
