# 인증 동기 실패 (AN-01)

`AuthenticationFailure`의 5GMM cause 21(synchronization failure)을 실제 production 룰이
보는 형태로 재현한다. control은 정상 인증, emulation은 cause 21 뒤 재인증 성공 흐름이다.
현재는 **탐지 입력 에뮬레이션**이므로 USIM SQN 교란이나 AUTS 검증 성공을 주장하지 않는다.

```bash
./ctl.sh campaign an-01 an-01-matched --profile p5 --enable
```

matched 3세트에서 control 예상 경보 0/3, emulation AN-01 RAISE 3/3을 확인했다. p5 live
경로 자격은 pending이다.
