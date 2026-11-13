# 계보와 기여

- 연구 근거: LTEInspector와 5G-Spector의 인증 동기 실패 메시지 흐름
- 차용: 외부 공격 코드는 복사하지 않았고 cause 21 조건만 독립 구현
- 자체 구현: 정상/이상 인증 순서, production replay, 공통 oracle·verdict·SHA-256 봉인
- 한계: 실제 USIM SQN과 코어 SQN 비동기화는 미구현
