# 새 모듈 추가 가이드

1. `reproducers/<설명형-id>/`를 만들고 한국어 README와 `reproducer.json`을 둔다.
2. 표준·논문·공개 구현의 원문 URL로 메시지 흐름과 변형을 고정한다.
   `PROVENANCE.md`에는 레퍼런스별로 참고한 부분, 가져오지 않은 부분, 자체 구현, 주장 한계를
   구분해 적고 [통합 레퍼런스 문서](ATTACK-REFERENCES.md)에 한 행 또는 절을 추가한다.
3. 수정 UE로 실제 기전을 만들 수 있는지 먼저 판단하고, 불가능할 때만 결과 또는 탐지 입력
   에뮬레이션으로 낮춘다.
4. control과 attack/emulation의 차이를 최소화하고 `--enable`, duration, UE 수 상한을 둔다.
5. 관측 입력과 UE·코어 oracle을 분리하고 가명 식별자와 monotonic timestamp로 조인한다.
6. `./ctl.sh campaign <id> --profile p5 --enable`로 matched 3세트를 수행한다.
7. `./ctl.sh validate`, 전체 테스트, 민감정보 검사를 통과시킨 뒤 증거 해시와 한계를 문서화한다.

manifest 스키마는 [reproducer.schema.json](schemas/reproducer.schema.json)이다. 기존 OAI runner를
공통 코드로 옮기지 말고 manifest가 모듈 내부 진입점을 가리키게 한다. production detector의
입력만 필요한 모듈은 `commands.run`과 `commands.campaign`을 `@common-signal`로 지정하고
`tools/generate_rule_signal.py`에 독립적인 control/emulation 신호를 추가한다.

완료 판정에는 고정 근거, 통제 대조군, input/oracle 분리, production detector 결과,
SHA-256 봉인이 모두 필요하다. `qualified` 표시는 해당 p5 또는 OTA 환경에서 이 조건을
충족한 증거가 있을 때만 사용한다.
