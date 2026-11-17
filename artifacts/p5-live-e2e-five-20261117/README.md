# p5 실제 경로 E2E 자격 검증 — L3 5종

2026-11-17 p5에서 기존 공격 runner를 그대로 실행하면서 다음 전체 경로를 검증했다.

```text
OAI UE → ZMQ → OCUDU DU/CU → TeleRAN → production detector → dashboard
```

고정 구성은 production detector `766f5569d0ddb425c14bf210a31c38ac60eceef9`,
TeleRAN `7550153a58a993942303bd3d4a6cd635b664468b`, 보고 주기 100 ms다.
각 룰은 `control → attack/emulation` 세 세트를 수행했다.

인증 고갈 자격용 OAI UE는 base `1c2f4d3c2e68181cdef9f426d161163147ad4b77`,
Authentication Response 미전송 패치 `bc8f29473155494ada7c07c16e095f99b96e2d82989c9bc6aa9a3d7f57817e07`,
source diff `1eb34bae6bce86ed6f9089b0252f61410b8ca81fc65ca058f4b3b6f0297eb781`,
binary `ae0d4640bcb9882acab60e4bf033240fb7bb65b158d43fa70ede4afb02fb814a`로
고정했다. RRC runner의 자격 실행본은
`548eb2a53dfe1e2217a36aa3ad36d3fea1d018b13fa244cc6d2fe0700d24ab02`다.

| 룰 | 시나리오 | 재현 수준 | 대조군 | 공격·에뮬레이션 | 결과 |
|---|---|---|---:|---:|---|
| L3-01-V | RRCSetupComplete 미전송형 | 실제 프로토콜 | 3/3, 경보 0 | 3/3, 경보 1 | 통과 |
| L3-01-O | Authentication Response 미전송형 | 실제 프로토콜 | 3/3, 경보 0 | 3/3, 경보 1 | 통과 |
| L3-20 | 현재 유효 5G-GUTI 재사용형 | 실제 프로토콜 | 3/3, 경보 0 | 3/3, 경보 1 | 통과 |
| L3-24 | 비정상 Identity Response | 프로토콜 결과 에뮬레이션 | 3/3, 경보 0 | 3/3, 경보 1 | 통과 |
| L3-14 | 보안 전 UE Capability Information | 프로토콜 관측 에뮬레이션 | 3/3, 경보 0 | 3/3, 경보 1 | 통과 |

모든 실행은 다음 조건을 함께 만족했다.

- 기존 모듈의 기전 판정 통과
- TeleRAN `hello.period_ms=100`, 연속된 sequence, gap 0, KPM 존재
- production detector 기본 설정에서 예상 룰만 대조군 0건·활성군 1건 RAISE
- dashboard sender 성공, 수락 1건 이상·거절 0건
- 실행별 `evidence_manifest.json`의 크기와 SHA-256 재검증 통과

원시 telemetry·F1/N2·가입자 설정은 p5의 `/root/ran-live-e2e/<run-id>/`에만 보존한다.
Git에는 식별자나 credential을 포함하지 않는 [캠페인 요약](campaign.json)과 원격 봉인
파일의 SHA-256만 둔다.

## 주장 경계

- L3-24와 L3-14는 원 논문의 RF/MITM 원인이 아니라 그 뒤의 프로토콜 결과·관측을
  UE에서 만든 에뮬레이션이다.
- 서비스 거부와 기지국 마비는 이 자격의 필수 조건이 아니며 별도 성과로 일반화하지 않는다.
- 실 SDR OTA와 상용망 일반화는 검증하지 않았다.
