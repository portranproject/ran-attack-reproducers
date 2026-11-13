# 새 7개 룰 production detector 재생 검증

2026-11-12에 새 7개 대표 시나리오의 독립적인 `hello`·`ue_evt`·`kpm2` 입력을 팀
production detector 고정 커밋의 기본 설정에 재생했다. 각 시나리오는 control 1회와
emulation 1회를 한 세트로 묶어 3세트 실행했다.

| 룰 | control 예상 룰 경보 | emulation 예상 룰 경보 | 결과 |
|---|---:|---:|---|
| L3-06 | 0/3 | 3/3 | 통과 |
| AN-01 | 0/3 | 3/3 | 통과 |
| AN-06a | 0/3 | 3/3 | 통과 |
| AN-02 | 0/3 | 3/3 | 통과 |
| AN-04 | 0/3 | 3/3 | 통과 |
| AN-07 | 0/3 | 3/3 | 통과 |
| AN-08 | 0/3 | 3/3 | 통과 |

모든 emulation run에서 예상 룰의 `RAISE`가 정확히 1건 발생했다. 모든 입력은
`period_ms=100`, 연속 seq, gap 없음, UE event timestamp 비역행 검사를 통과했다. detector
출력의 `ALERT RAISE` action과 `kind=attack|anomaly`를 서로 다른 필드로 보존한다.
fixture 시계 기준 탐지 지연은 L3-06 2 ms, AN-01 82 ms, AN-06a 50 ms, AN-02 5 ms,
AN-04 1,300 ms, AN-07 2,100 ms, AN-08 100 ms였고 세 반복에서 동일했다. 이는 offline
replay 지연이며 live 수집·전송 지연이 아니다.

## 고정 계보

- detection commit: `a34b358e585e24aa91b1586da022ad14ef98d3e0`
- detector binary SHA-256: `b28565aacac1a2187f5874732f3b84637326b5b651678fd32efb019f9ead4704`
- production config SHA-256: `9bbb0b5039b05d0aa73c31c4a4e30860042a873ebc48ba8589191f6f61c77c53`
- generator SHA-256: `6c301022229e56b3e9c6c6cadd6767ff300aa5b6004d31740ad016522f9327e0`

원시 42개 run bundle은 로컬 외부 보관하고 Git에는 aggregate 판정만 둔다. 각 로컬 bundle은
`run.json`, `observations.jsonl`, `oracle.jsonl`, `detector.jsonl`, `verdict.json`,
`report.md`, `evidence_manifest.json`으로 봉인됐다.

## 주장 경계

이 결과는 production detector의 입력 계약과 기본 threshold 회귀를 검증한다. p5에서 실제
NAS/RRC 경로가 발생했다거나 RF/MITM/rogue gNB 원인이 관측됐다는 결과가 아니다. 따라서 새
7개 manifest의 p5 상태는 `pending`, OTA 입력형 상태는 `not-applicable`로 유지한다.
