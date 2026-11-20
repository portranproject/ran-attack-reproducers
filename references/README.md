# 레퍼런스 도구 (외부 공개 구현)

우리 공격 모듈과 **분리된 네임스페이스**다. 외부 공개 구현을 우리 셀에서 실행해
계측·탐지가 되는지 교차 확인하는 용도이며, `./ctl.sh same-cell` 자격이나 production
detector 판정을 대신하지 않는다.

```bash
./ctl.sh reference list
./ctl.sh reference build ref-rrc-storm --profile p1
./ctl.sh reference doctor ref-rrc-storm --profile p1
./ctl.sh reference run ref-rrc-storm --profile p1 --mode control
./ctl.sh reference run ref-rrc-storm --profile p1 --mode attack --enable
./ctl.sh reference campaign ref-rrc-storm --profile p1 --sets 3 --enable
```

- 목록·원본 커밋·룰 대응·현재 상태의 단일 출처는 `references/manifest.json`이다.
- 빌드 스크립트·브리지·runner는 기존처럼 `reproducers/<모듈>/reference/`에 두고,
  실행·판정 기록만 `references/`가 맡는다.
- `run`은 UE 로그 마커로 기전만 판정한다(`run.json`, `verdict.json`). 탐지 판정은
  별도 `TeleRAN → production detector` 경로에서만 한다.

## 원본에 대해 바꾼 것

원본 소스 수정은 없다. 원본 OAI rfsim UE와 우리 DU ZMQ 사이를 잇기 위해 외부
브리지(`oai-rfsim-zmq-bridge`)만 추가했고, 2026-11-20에 변환을 numpy로 바꿔
23.04 Msps를 따라가게 했다. 상향은 UE가 보낸 최신 블록을 그대로 넘긴다.
