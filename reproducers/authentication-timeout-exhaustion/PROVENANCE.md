# 계보와 기여

- 연구·공개 구현: LTEFuzz, 5G-Spector/OAI-5G, Buckler와 3GPP 24.501
- 차용: Authentication Request에 응답하지 않는 상태 전이 개념
- 자체 구현: OAI w38 응답 억제, 다중 UICC fingerprint, direct 4-cell phase driver,
  OCUDU/Open5GS exact join, fail-closed 판정·증거 봉인
- 현재 OAI 호환 구현: config 배열 기반 UE별 독립 virtual RU, 한 셀 2프로세스×5 UE 실행기.
  정상 UE 5대 same-cell 경로는 복원 뒤 p5 재자격 중
- 자격용 UE 계보: OAI base `1c2f4d3c2e68181cdef9f426d161163147ad4b77`, 패치
  `bc8f29473155494ada7c07c16e095f99b96e2d82989c9bc6aa9a3d7f57817e07`, 바이너리
  `ae0d4640bcb9882acab60e4bf033240fb7bb65b158d43fa70ede4afb02fb814a`
- 한계: production L3-01-O matched 3/3은 통과했지만 정상 UE 서비스 거부는 미관측
