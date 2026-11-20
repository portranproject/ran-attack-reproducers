# 계보와 기여

- 연구 근거: SigOver의 무선 메시지 overshadowing과 tracking area 조작 결과
  - https://www.usenix.org/conference/usenixsecurity19/presentation/yang-hojoon
- 차용: RF 공격 구현은 가져오지 않고 알려진 UE mobility burst 결과만 독립 구현했다.
- 자체 구현: known-UE seed, mobility sequence, threshold-bound control, replay·판정·봉인
- 한계: TAC 송출, rogue gNB, RF 우위, 실제 UE 이동 등록은 미관측
