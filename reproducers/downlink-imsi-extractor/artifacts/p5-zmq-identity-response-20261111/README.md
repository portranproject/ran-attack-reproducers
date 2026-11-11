# p5 ZMQ 식별자 응답 치환 실측

2026-11-11 p5 direct 1-cell ZMQ에서 같은 OAI UE 바이너리·가입자·OCUDU/Open5GS
설정을 사용한 `control → emulation` 세 세트를 실행했고 모두 첫 실행에서 통과했다.

| 항목 | control 3회 | emulation 3회 |
|---|---:|---:|
| Registration Request | 3/3 각 1건 | 3/3 각 1건 |
| Authentication Request | 3/3 각 1건 | 3/3 각 1건 |
| Authentication Response | 3/3 각 1건 | 3/3 0건 |
| Identity Request | 3/3 0건 | 3/3 0건 |
| Identity Response | 3/3 0건 | 3/3 각 1건 |
| null-scheme fingerprint 일치 | 해당 없음 | 3/3 |
| 등록·PDU·ping | 3/3 성공 | 3/3 실패 |
| crash·forced kill | 0 | 0 |

N2 pcap에서 control은 `0x41 → 0x56 → 0x57`, emulation은
`0x41 → 0x56 → 0x5c`로 exact join했다. `0x5b Identity Request`는 모든 실행에서
0건이었다.

[RESULTS.json](RESULTS.json)은 각 child의 판정, 원격 원문 크기와 SHA-256을 보존한다.
원시 `ngap.pcap`, UE/CU/AMF 로그는 null-scheme 가입자 식별자를 포함하므로 Git에는 넣지
않았다. 원격 봉인 원문은 실행 당시 p5 DU의
`/root/downlink-imsi-tool/runs/p5-downlink-imsi-final-20261111-*`에 있으며 결과 파일의 해시로
대조한다.

## 주장 경계

이 결과는 **실제 UE→RAN→코어 경로에서 예상하지 않은 SUCI Identity Response와
null-scheme 랩 가입자 노출을 반복 재현**했다는 증거다. RF overshadowing을 송신하거나
관측하지 않았으므로 실제 무선 하향 탈취 성공, Profile A 복호화, 상용망 IMSI 추출로
일반화하지 않는다.
