# NAS 카운터 비동기화 결과 (L3-06)

이 모듈은 연구에서 다루는 NAS counter desynchronization 계열이 탐지기에 남기는 결과인
`SecurityModeReject`를 재현한다. 현재 구현은 선행 `SecurityModeCommand`와 짝이 맞지 않는
reject를 control에 한 건만 추가하는 **탐지 입력 에뮬레이션**이다. 실제 NAS count 변조,
live UE→RAN→코어 경로, 서비스 거부는 관측하지 않았다.

```bash
./ctl.sh run l3-06 control l3-06-control --profile p5
./ctl.sh run l3-06 emulation l3-06-emulation --profile p5 --enable
./ctl.sh campaign l3-06 l3-06-matched --profile p5 --enable
```

production detector matched 3/3 결과는 최상위
`artifacts/production-detector-rule-replay-20261112/`에 있다. 이 모듈을 protocol 재현으로
승격하려면 OAI UE의 송수신 NAS count를 통제해 실제 정상 코어와 동일 결과를 만들어야 한다.
