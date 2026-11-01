# Blind DoS 재현 도구

상태: **준비 단계 — 기존 5G-S-TMSI 주입 방식은 반증됨.**

2026-10-22 실측에서는 AMF가 등록 때마다 새 5G-GUTI를 발급해, 공격자가 앞서 확인한
5G-S-TMSI가 주입 시점에는 이미 만료됐다. 해당 방식은 정상 UE 차단으로 이어지지
않았으므로 그대로 재구현하지 않는다. 근거와 수치는
[변종 비교](../rss-landscape.md)와
[보존된 실험 기록](../artifacts/archive-du-cell-resource-20261026/findings/coverage-the-remaining-lever.md)을
따른다.

구현은 다음 조건을 먼저 확정한 뒤 시작한다.

- 공격 시점에도 유효한 표적 식별자를 합법적으로 확보할 수 있는 팀 소유 UE 실험 절차
- 정확한 프로토콜 중단 지점과 공격 성공·실패 기준
- 독립 정상 UE 대조군, 공격 중 영향, 공격 중단 뒤 같은 UE 회복 기준
- RRC storm과 분리된 라벨 계약과 run ID

모든 실험은 팀 장비와 ZMQ 또는 RF 차폐 환경에서만 수행한다. 실행 원문은
`blind-dos/runs/`에 로컬 보존하며 Git에는 요약과 무결성 정보만 올린다.
