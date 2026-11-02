# p5 ZMQ 현재 유효 5G-GUTI 재사용형 G5 실측

2026-11-02에 direct 2-cell ZMQ에서 실행한 최종 matched campaign의 게시용 증거다.

## 판정

- campaign: `blind-g5-final-20261102`
- 순서: 각 세트 `control → attack`
- 요구/완료/통과: `3 / 3 / 3`
- control: 3/3 첫 시도 통과
- attack: 3/3 첫 시도 통과
- 인프라 재시도: 0
- 최종 판정: **G5 통과 — oracle 보조 단발 Blind DoS 재현기 성공**

세 control은 공격 이벤트·표적 상태 효과·ping 손실이 모두 0이었다. 세 attack은 모두
동일 GUTI의 AMF identity reach와 기존 피해 context 변화를 exact join했고, 피해 ping이
연속 5회 실패했다. one-shot 종료 뒤 동일 victim PID에서 Registration과 PDU count가
`1→2`로 증가했고 after ping은 각 20/20이었다. 전 run의 crash와 forced kill은 0이다.

자세한 probe 집계는 [METRICS.json](METRICS.json), campaign 최종값은
[campaign_result.json](campaign_result.json), 실행 순서는
[campaign_events.jsonl](campaign_events.jsonl)에 있다.

## 계보

- OAI 기준 commit: `6d6782b48484efd935c14e834832032743f9b138`
- Blind DoS patch SHA-256:
  `5ee58d5b0009431dbddbba0c08f0dbe25f46c7b4d48f06a9accdb88c06b3697a`
- 최종 `nr-uesoftmodem` SHA-256:
  `9a532c5e4c678ecbee115b37d03b20d9a79fc5100e6056c9615ba48d0fa9b73c`
- stack: OCUDU 26.10 CU/DU, Open5GS, OAI 2026.w38 UE
- radio: 피해 cell 0 + 공격 cell 1의 direct ZMQ
- threshold: baseline 20, 관측 12초, 연속 손실 5, 회복 제한 30초, after 20
- clock: `campaign.json`에 측정 방식·offset·uncertainty와 증거 hash 보존

## 파일 구성

- `campaign.json`: 실행 전에 봉인한 설정·정책·software hash·threshold
- `campaign_events.jsonl`: 6개 child run의 순서·분류·시도 번호
- `campaign_result.json`: 최종 3/3 판정
- `children/*/run.json`: child별 입력·software hash
- `children/*/run_stop.json`: runner가 계산한 최종 분류와 verdict
- `children/*/verdict.json`: 독립 verifier 출력
- `children/*/evidence_manifest.json`: 원격 raw run의 파일 크기·SHA-256
- `children/*/sensitive_artifact_check.txt`: child별 credential scanner 결과
- `REMOTE-HASHES.sha256`: 원격 campaign 디렉터리의 모든 원문 파일 hash

Git에는 raw AMF/CU/DU log, pcap, attacker/victim JSONL을 복사하지 않았다. child manifest와
`REMOTE-HASHES.sha256`이 원격 원문을 식별한다. 따라서 이 정제 디렉터리만으로 child
manifest verify를 다시 실행할 수는 없고, 원격 raw run 보관본이 필요하다.

## 주장 경계

이 결과는 랩 oracle로 현재 5G-GUTI를 얻은 뒤 실행한 **단발** 공격이다. 자연 회복을
측정한 것이 아니라 one-shot 종료 뒤 같은 OAI victim 프로세스에 재등록을 요청했다.
비특권 식별자 획득(G6), 반복 재표적화에 의한 지속 차단(G7), 실 SDR OTA, 다른 AMF
버전과 상용망은 미검증이다.

이전 [`p5-zmq-20261102`](../p5-zmq-20261102/)는 RRC-only 초기 구현의 G5 미달 기록이다.
실패 기록을 수정하거나 최종 캠페인과 합산하지 않았다.
