# p5 L3-06 실제 RAN 경로 자격

2026-11-17 수정 OAI UE가 만든 요청되지 않은 NAS `SecurityModeReject`를
`UE → ZMQ → OCUDU DU/CU → TeleRAN 100 ms 계측 → production detector → dashboard`로
검증했다. detector는 고정 commit
`766f5569d0ddb425c14bf210a31c38ac60eceef9`의 기본 설정을 사용했다.

| 세트 | control | emulation |
|---|---|---|
| 1 | Reject 0, L3-06 경보 0 | Reject 1, 선행 NAS SMC 0, L3-06 경보 1 |
| 2 | Reject 0, L3-06 경보 0 | Reject 1, 선행 NAS SMC 0, L3-06 경보 1 |
| 3 | Reject 0, L3-06 경보 0 | Reject 1, 선행 NAS SMC 0, L3-06 경보 1 |

6개 실행 모두 `mechanism`, `detection_input`, `detector_result`가 `pass`였다. control은
Registration·PDU·ping에 성공했다. TeleRAN 원문과 detector input recorder의 SHA-256도
각 실행에서 일치했다. 대시보드는 control 10/11/11줄, emulation 22/21/21줄을 수락하고
거절 0줄이었다.

이 결과가 입증하는 것은 **L3-06 결과 신호를 실제 RAN·계측 경로로 통제 가능하게
재현하고 탐지했다**는 점이다. 원 공격의 MITM, 잘못된 SMC 실제 수신, reject 차단,
8-bit NAS sequence wrap, 이후 서비스 거부는 관측하지 않았다.

원문은 p5 DU의 `/root/nas-counter-desync-raw/`, 정제된 실행 결과는
`/root/nas-counter-desync-runs/`에 보관한다. Git에는 가입자·패킷 원문을 넣지 않고
[정제 결과](RESULTS.json)와 원격 증거 manifest 해시만 둔다.

개발 중 첫 캠페인은 control 1회 뒤 DU가 runner 잠금 FD를 상속해 중단됐다. DU 시작 시
잠금 FD를 닫도록 수정했으며, 최종 `l3-06-live-final-v2-20261117` 캠페인이 3/3을 통과했다.

별도 same-cell 진단은 5개 정상 UE+1개 L3-06 UE와 4+1 control 모두 공격 슬롯 활성화 뒤
정상 풀 ping health가 회복되지 않아 미승인이다. broker의 warmup 없는 전환 결함은 수정했지만,
정상 UE 보존 실패는 남았다. 이 결과를 direct 1셀 자격에 포함하지 않는다.
