# 짧은 RRC 연결 반복 (AN-04)

같은 가명 5G-S-TMSI가 RRC setup, service accept, release를 짧게 반복하는 이상 신호를
재현한다. control은 2회, emulation은 3회다. 이 신호는 여러 원인에서 나타날 수 있으므로
특정 공격 기전을 단정하지 않는 **탐지 입력 에뮬레이션**이다.

```bash
./ctl.sh campaign an-04 an-04-matched --profile p5 --enable
```

production 기본 설정에서 control 0/3, AN-04 RAISE 3/3을 통과했다.
