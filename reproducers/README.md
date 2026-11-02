# 공격 재현 모듈

각 하위 디렉터리는 하나의 공격만 다루는 독립 모듈이다.

| 모듈 | 상태 |
|---|---|
| [rrc-signaling-storm](rrc-signaling-storm/) | 동결·사용 가능. 검증 범위와 한계는 모듈 README 참고 |
| [blind-dos](blind-dos/) | 현재 유효 5G-GUTI one-shot 구현 완료. p5 direct 2-cell ZMQ matched control→attack G5 3/3 통과 |
| [upstream-dos](upstream-dos/) | 작업명. 공격 계층과 대상 자원 정의 중 |

새 모듈은 최소한 README, 독립 라벨 계약, 정상 대조군, 유한 실행시간, `runs/`
로컬 보존 정책을 먼저 정한다. 실제 파일이 생기기 전에는 빈 `src/`, `tests/`,
`docs/` 디렉터리를 만들지 않는다.
