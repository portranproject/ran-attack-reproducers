# 계보와 기여

- 연구·상태 근거: 5G-GUTI 재사용 흐름과 Open5GS issue #4577
- 차용: 외부 공격 구현 복사 없이 identity/GUTI 상태 전이만 참고
- 자체 구현: 전체 GUTI encoding, 피해자·공격자 분리, one-shot orchestration, exact context
  join, 동일 피해자 PID의 서비스 손실·회복 판정과 matched 3세트 봉인. same-cell용으로
  다중 InitialUEMessage 중 피해자 IMSI·target S-TMSI와 일치하는 live mapping 선택을 추가
- 한계: 식별자 비특권 획득, 지속 차단, OTA는 미검증. same-cell은 독립 ZMQ UE 상향
  시간축 불일치로 피해자 RA가 실패해 미승인
