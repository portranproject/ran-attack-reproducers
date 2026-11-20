# 계보와 기여

- 연구·공개 구현: LTEFuzz, 5G-Spector/OAI-5G, Buckler와 3GPP 24.501
- 차용: Authentication Request에 응답하지 않는 상태 전이 개념
- 자체 구현: OAI w38 응답 억제, 다중 UICC fingerprint, direct 4-cell phase driver,
  OCUDU/Open5GS exact join, fail-closed 판정·증거 봉인
- 현재 OAI 호환 구현: `bin/auth-timeout-build`는 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 4개 패치(`ru-sharing-w38.patch`, `workloads/normal-ue/patch/normal-multi-ru.patch`, `auth-timeout-ue-w38.patch`, `same-cell-ra-gate-w38.patch`)를 적용한다. `bin/auth-stall-cell-run`의 한 셀 2프로세스×5 UE + 정상 UE 5대 same-cell 경로는 `p1q9-20261119`에서 6/6 통과했다(`artifacts/p1-clean-origin-live-e2e-20261119/README.md`).
- 2026-11-17 p5 단독 E2E 보존 이력(`p5-live-e2e-five-20261117`): 당시 자격용 UE 바이너리는 OAI base `1c2f4d3c2e68181cdef9f426d161163147ad4b77`, 패치
  `bc8f29473155494ada7c07c16e095f99b96e2d82989c9bc6aa9a3d7f57817e07`, 바이너리
  `ae0d4640bcb9882acab60e4bf033240fb7bb65b158d43fa70ede4afb02fb814a`였다.
- 한계: p1/p5 E2E 3/3 모두 정상 UE 서비스 거부는 미관측(`not_observed`)이며 실 SDR OTA는 미검증이다.
