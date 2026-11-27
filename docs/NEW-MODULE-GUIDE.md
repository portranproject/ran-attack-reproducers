# 새 모듈 추가 가이드

새 공격 모듈을 추가할 때는 기존 모듈과 구현·설정·라벨 계약을 분리해 `reproducers/<설명형-id>/` 아래에 둔다. 디렉터리·문서·ID 규칙은 [명명 규칙](NAMING-CONVENTIONS.md)을 따른다.

## 추가 절차

1. `reproducers/<설명형-id>/`를 만들고 한국어 `README.md`, `PROVENANCE.md`, `reproducer.json`을 작성한다.
2. 표준·논문·공개 구현의 고정 URL로 메시지 흐름을 확인하고, `PROVENANCE.md`에 참고 범위·비도입 부분·자체 구현·주장 한계를 구분한다. [ATTACK-REFERENCES.md](ATTACK-REFERENCES.md)에도 해당 모듈 항목을 추가한다.
3. 수정 OAI UE로 실제 프로토콜 기전(`protocol`)을 만들 수 있는지 먼저 판단하고, 현재 토폴로지에서 불가능할 때만 `protocol-result-emulation`, `protocol-observation-emulation`, `detector-input-emulation` 중 하나로 낮춘다.
4. `control`과 `attack`/`emulation`의 차이를 최소화하고 `--enable` 게이트, `max_duration_s`, `max_ues` 상한을 둔다.
5. 탐지 입력(F1/N2/TeleRAN)과 UE·코어 oracle을 분리하고 가명 식별자 및 단조 타임스탬프로 조인한다.
6. `./tools/ctl.sh validate`, 단위 테스트, 민감정보 검사(`reproducers/rrc-signaling-storm/analysis/check_sensitive_artifacts.py`)를 통과시킨다.
7. `./tools/ctl.sh campaign <id> --profile <env> --enable` 또는 `./tools/ctl.sh same-cell run`으로 matched 3세트를 실행한 뒤 증거 SHA-256과 한계를 문서화한다.

## 스키마 및 `tools/ctl.sh` 제약

- manifest 스키마는 [reproducer.schema.json](../schemas/reproducer.schema.json)이다. `tools/reproctl.py`는 `manifest["module"]`이 모듈 디렉터리 이름과 같아야 하며(`reproctl.py:145`), `commands` 진입점이 모듈 내부 실제 파일이거나 `@common-signal`이어야 통과한다.
- `environments` 필드는 현재 스키마상 `p5`와 `ota`만 허용한다(`p1` 등 추가 환경 자격은 `artifacts/`에 별도 봉인한다).
- production detector 입력만 필요한 fixture는 `commands.run`·`commands.campaign`을 `@common-signal`로 두고 `tools/generate_rule_signal.py`에 control/emulation 생성기를 추가한다.
- **중요 (`tools/ctl.sh` 및 lock 제약)**: 현재 `tools/ctl.sh`는 `reproducer.json`을 동적 탐색하지 않고 `ATTACKS` 배열과 `case` 문(`tools/ctl.sh:6-88,108-145,328-374,484-495`)으로 모듈을 분기한다. 또한 `tools/ctl.sh`와 `tools/reproctl.py`는 `integration.lock.json`에 SHA-256이 고정돼 있으므로, 신규 모듈을 `tools/ctl.sh`에 연결하려면 `tools/ctl.sh`와 `integration.lock.json` 갱신이 함께 필요하다.

`qualified` 표시는 해당 환경에서 고정 레퍼런스·대조군·input/oracle 분리·production detector 결과·SHA-256 봉인이 모두 확인된 뒤에만 부여한다.
