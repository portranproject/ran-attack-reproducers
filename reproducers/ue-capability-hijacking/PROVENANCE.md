# 계보와 기여

- 연구 근거: Shaik 등의 보안 전 UE Capability Hijacking 연구
- 차용: 보안 전 capability 평문성·질의/응답 순서 개념
- 자체 구현: OAI w38 표준 encoder 기반 unsolicited one-shot, F1 same-context 조인,
  이후 정상 capability 흐름 보존, matched 3세트 판정·봉인
- 한계: MITM relay, payload 변조, 강등 수락, OTA는 미검증
