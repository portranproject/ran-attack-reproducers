# NAS 카운터 reset 계열 재인증 (AN-06a)

이미 NAS·AS 보안을 수립한 같은 UE context에 `AuthenticationRequest`와 NAS
`SecurityModeCommand`가 다시 나타나는 신호를 만든다. 이는 detector가 보는 **입력
에뮬레이션**이며 NAS count를 실제로 reset하거나 replay protection을 우회하지 않는다.

```bash
./ctl.sh campaign an-06a an-06a-matched --profile p5 --enable
```

control은 재인증 없음, emulation은 재인증·SMC one-shot이다. production 기본 설정에서
control 0/3, AN-06a RAISE 3/3을 통과했다.
