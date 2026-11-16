# 계보와 기여

- 연구 근거: uplink RF overshadowing 뒤 잘못된 NAS credential/무결성 결과와 3GPP NAS 처리
- 차용: RF 공격 코드는 사용하지 않음
- 자체 구현: Service Request MAC one-bit one-shot, AMF 로그 조인, 서비스 영향·회복 판정,
  OAI의 등록 실패 반복 패치, TeleRAN·production detector·대시보드 종단 runner, 정상 UE
  5대 same-cell 수명주기, fail-closed 판정과 matched 3세트 봉인
- 한계: RF 우위는 미관측. L3-21은 한 물리 UE가 만든 10개 RAN 연결이며 서비스 거부와
  실 SDR OTA는 검증하지 않음
