# TAC 조작·가짜 기지국 복귀 신호 (AN-08)

미리 알려진 랩 UE 5개가 짧은 창에 mobility registration으로 돌아오는 결과 신호를
재현한다. SigOver 계열의 TAC 조작/가짜 기지국 원인은 현재 1:1 ZMQ에서 만들 수 없으므로
**탐지 입력 에뮬레이션**으로 제한한다.

```bash
./ctl.sh campaign an-08 an-08-matched --profile p5 --enable
```

control은 known UE 5개 중 4개만 복귀하고, emulation은 5개가 복귀한다. production 기본
설정에서 control 0/3, AN-08 RAISE 3/3을 통과했다.
