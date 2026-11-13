# 계보와 기여

- 연구·공개 구현: KAUST RRC storm 논문과 `5gattacks/5g-rrc-storm`의 구형 OAI 패치
- 차용: RRCSetupComplete 미전송 기전. 공개 패치의 gNB timer 변경은 제외
- 자체 구현: OAI w38 포팅, runtime rate/ACK/retry 노브, JSONL oracle, DU ACK exact join,
  fail-closed runner, 분석기, 증거 봉인과 p5 기본 cleanup 검증
- 한계: 차폐 OTA, 30초 지속 포화, 기지국 전체 마비는 미입증
