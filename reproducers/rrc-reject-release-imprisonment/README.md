# RRC 거절·해제 투옥 계열 미완료 반복 (AN-07)

같은 5G-S-TMSI Part1의 `RRCSetupRequest`가 완료 없이 release되는 흐름을 반복한다.
control 2회와 emulation 3회로 탐지 경계를 고정했다. rogue gNB가 UE를 실제로 거절·해제
상태에 가두는 원인은 만들지 않는 **탐지 입력 에뮬레이션**이다.

```bash
./ctl.sh campaign an-07 an-07-matched --profile p5 --enable
```

production 기본 설정에서 control 0/3, AN-07 RAISE 3/3을 통과했다.
