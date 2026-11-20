# 계보와 기여

- 연구·상태 근거: 5G-GUTI 재사용 흐름과 Open5GS issue #4577
- 차용: 외부 공격 구현 복사 없이 identity/GUTI 상태 전이만 참고
- 자체 구현: 전체 GUTI encoding, 피해자·공격자 분리, one-shot orchestration, exact context
  join, 동일 피해자 PID의 서비스 손실·회복 판정, matched 3세트 봉인, `same-cell-ra-gate-w38.patch`
  기반 사전 clock·GUTI gate, 다중 InitialUEMessage 중 피해자 IMSI·target S-TMSI와 일치하는 live mapping 선택
- 한계: 식별자 비특권 획득(G6), 지속 차단(G7), OTA는 미검증. 2026-11-16 pre-gate p5 단일 셀에서는
  독립 ZMQ 상향 시간축 불일치로 실패했으나, `same_cell_broker.py` + `same-cell-ra-gate-w38.patch`
  통합 경로는 `p1q9-20261119` same-cell 6/6을 통과했다(`artifacts/p1-clean-origin-live-e2e-20261119/README.md`).
