# 계보와 기여

- 연구·상태 근거: 5G-GUTI 재사용 흐름과 Open5GS issue #4577
- 차용: 외부 공격 구현 복사 없이 identity/GUTI 상태 전이만 참고
- 자체 구현: 전체 GUTI encoding, 피해자·공격자 분리, one-shot orchestration, exact context
  join, 동일 피해자 PID의 서비스 손실·회복 판정과 matched 3세트 봉인
- 한계: 식별자 비특권 획득, 지속 차단, OTA는 미검증
