# L3 공격 7종 E2E 실행 가이드

이 문서는 다른 팀원이나 AI가 **검증된 실행 경로만** 사용하도록 고정한 운영 기준이다.
공격 이론과 개별 판정 기준은 각 모듈 README를 따르며, 여기서는 배포·토폴로지·실행 진입점만
정한다.

## 반드시 지킬 것

1. ZIP·파일 복사본이 아니라 Git clone을 사용한다.
2. 공격 전에 `./ctl.sh doctor --profile <환경>`을 통과한다.
3. 공식 runner가 없거나 doctor가 실패하면 중단한다. OAI 바이너리를 직접 실행하거나
   `/tmp` 수동 스크립트로 대체하지 않는다.
4. control을 먼저 통과한 뒤 active 모드를 실행한다. active에는 `--enable`을 붙인다.
5. CU·DU EC2 인스턴스는 그대로 재사용한다. runner가 공격별 DU **프로세스와 설정**을
   시작·정리할 수 있지만 인스턴스를 생성·삭제하지 않는다.

`doctor`는 Git checkout, 최소 자격 커밋, 추적 파일 변경 여부, 핵심 runner 해시,
detector·telemetry 고정 버전을 검사한다. 하나라도 다르면 그 환경은 자격 검증 대상이 아니다.

## 처음 설치하거나 업데이트할 때

```bash
git clone https://github.com/portranproject/ran-attack-reproducers.git
cd ran-attack-reproducers
git switch main
git pull --ff-only
git status --short
```

`git status --short` 출력은 비어 있어야 한다. p4는 다음처럼 profile을 만든다.

```bash
cp profiles/p4.example.json profiles/p4.json
chmod 600 profiles/p4.json
# p4의 CU·DU 주소, 허용 대상, credential 경로를 채운다.
./ctl.sh doctor --profile p4
```

실제 profile, 가입자 설정, SSH key는 Git 밖에 두고 권한을 `0600` 이하로 둔다.

## 자격 토폴로지와 공격 runner

모든 자격 실행은 **CU 인스턴스 1대와 DU 인스턴스 1대**를 순차 재사용한다. Blind DoS의
2-cell은 DU 두 대가 아니라 동일 DU 프로세스의 논리 셀 두 개다.

| 룰 | 공격 runner 진입점 | 자격 토폴로지 | 금지·미승인 경로 |
|---|---|---|---|
| L3-01-V | `ctl.sh campaign rrc-storm` | 1 DU·1 cell | 임의 timer/capacity 완화 |
| L3-06 | `ctl.sh campaign l3-06` | direct 1-cell | 정상 UE same-cell |
| L3-24 | `ctl.sh campaign downlink-imsi` | direct 1-cell | RF 원인 재현 주장 |
| L3-14 | `ctl.sh campaign ue-capability` | direct 1-cell | MITM·내용 변조 주장 |
| L3-21 | `ctl.sh campaign uplink-credential-flood` | 한 UE가 10개 실패 연결 생성 | 단발 MAC 변조를 L3-21로 주장 |
| L3-01-O | `ctl.sh campaign auth-timeout` | 한 셀, 2 OAI 프로세스×5 UE, endpoint 10개 | 한 프로세스 `--num-ues 10` |
| L3-20 | `bin/blind-run`·`bin/blind-p5-phase` | direct 2-cell, victim·attacker 동시 실행 | 순차 재사용·same-cell |

L3-01-O production 자격은 일반 기전 runner인 `auth-timeout-run`이 아니라 반드시
`auth-stall-cell-run`을 사용한다. 컨트롤러가 이 runner로 matched 3세트를 고정한다.

```bash
AUTH_STALL_CELL_CONF=/etc/ran-reproducer/auth-stall-cell.conf \
  ./ctl.sh campaign auth-timeout auth-matched-3 --enable
```

Blind DoS는 모듈의 `p5-zmq.conf.example`을 환경에 맞춰 만든 뒤 기존 campaign을 사용한다.
설정의 phase command는 공식 `blind-p5-phase`를 가리켜야 하며 direct 2-cell DU 설정을
사용해야 한다.

```bash
BLIND_CONF=/etc/ran-reproducer/blind.conf \
  reproducers/blind-dos/bin/blind-campaign -n blind-matched-3 -e 1
```

위 campaign은 공격 기전의 matched 3세트다. **TeleRAN→detector→dashboard까지 포함한 E2E
자격은 아니다.** E2E에서는 control과 active 각각을 `tools/p5-live-e2e`로 감싸고, 실제 runner가
생성할 `CHILD_DIR`을 정확히 넘긴다. 다음은 L3-01-O control 한 회의 형식이다.

```bash
RUN_ID=auth-e2e-control-1
CHILD_DIR=/root/auth-timeout-cell-runs/$RUN_ID
LIVE_E2E_CONF=/etc/ran-reproducer/live-e2e.conf \
  tools/p5-live-e2e authentication-timeout-exhaustion control "$RUN_ID" L3-01-O "$CHILD_DIR" -- \
  env AUTH_STALL_CELL_CONF=/etc/ran-reproducer/auth-stall-cell.conf \
  reproducers/authentication-timeout-exhaustion/bin/auth-stall-cell-run \
  control -n "$RUN_ID" -e 0
```

attack은 새 `RUN_ID`와 `CHILD_DIR`로 같은 명령의 mode를 `attack`, `-e`를 `1`로 바꾼다.
이 control→attack 쌍을 3회 수행한다. 다른 룰도 표의 runner를 같은 wrapper 형식으로 실행한다.

## E2E 합격 조건

공격별 `control → attack/emulation`을 3세트 실행한다. 각 실행에서 다음을 모두 확인한다.

- 기존 공격·에뮬레이션 판정 통과
- `UE → ZMQ → DU/CU → TeleRAN → production detector → dashboard` 경로 사용
- TeleRAN 100 ms, sequence 연속, gap 0, KPM 존재
- control의 대상 경보 0건, active의 대상 RAISE 1건
- dashboard 수락 1건 이상·거절 0건
- runner·바이너리·설정·증거 SHA-256 봉인

p5 결과를 p4 결과로 복사해 적지 않는다. p4에서 동일한 3세트를 별도로 통과해야 p4 자격으로
기록한다.

## 실패했을 때

다음 자료를 그대로 보존하고 수동 스크립트로 우회하지 않는다.

- `git rev-parse HEAD`, `git status --short`
- 실행 명령과 profile 이름
- runner·OAI UE·DU 설정 SHA-256
- UE·broker·DU·CU·detector 로그와 run 디렉터리
- 인스턴스 유형, 셀 수, UE 프로세스×논리 UE 수

공식 토폴로지와 다른 실행은 공격 실패가 아니라 **시험 무효**로 분류한다.
