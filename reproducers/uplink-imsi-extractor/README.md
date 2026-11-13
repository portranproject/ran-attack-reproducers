# GUTI 불일치 후 상향 식별자 요청 결과 (AN-02)

5G-GUTI로 시작한 연결 뒤 `IdentityRequest`가 반복되는 5G-Spector 계열 결과 신호를
재현한다. control 4건과 emulation 5건으로 production threshold 경계를 고정했다. 실제
rogue gNB, GUTI 변조, IMSI/SUPI 획득은 수행하지 않는 **탐지 입력 에뮬레이션**이다.

```bash
./ctl.sh campaign an-02 an-02-matched --profile p5 --enable
```

`observations.jsonl`에는 실제 식별자 대신 가명 5G-S-TMSI만 사용한다.
