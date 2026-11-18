# L3 공격 7종 E2E 실행 가이드

이 문서는 다른 팀원이나 AI가 **검증된 실행 경로만** 사용하도록 고정한 운영 기준이다.
공격 이론과 개별 판정 기준은 각 모듈 README를 따르며, 여기서는 배포·토폴로지·실행 진입점만
정한다.

## 반드시 지킬 것

1. ZIP·파일 복사본이 아니라 Git clone을 사용한다.
2. 개별 모듈은 `./ctl.sh doctor --profile <환경>`, 정상 UE 5대 통합 실행은
   `./ctl.sh same-cell doctor --profile <환경>`을 통과한다.
3. 공식 runner가 없거나 doctor가 실패하면 중단한다. OAI 바이너리를 직접 실행하거나
   `/tmp` 수동 스크립트로 대체하지 않는다.
4. control을 먼저 통과한 뒤 active 모드를 실행한다. active에는 `--enable`을 붙인다.
5. CU·DU EC2 인스턴스는 그대로 재사용한다. runner가 공격별 DU **프로세스와 설정**을
   시작·정리할 수 있지만 인스턴스를 생성·삭제하지 않는다.

`doctor`는 Git checkout, 최소 자격 커밋, 추적 파일 변경 여부, 핵심 runner 해시,
detector·telemetry 고정 버전을 검사한다. p5에서는 권한 0600의 `credentials_file`에 적힌
`SSH_KEY`·`KNOWN_HOSTS`를 사용해 CU의 production 바이너리와 배포 revision을 원격 확인한다.
DU에는 패킷 증거 수집용 `tshark`도 필요하다. 하나라도 다르면 그 환경은 자격 검증 대상이 아니다.

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

## L3 7종 same-cell 통합 경로

공개 진입점은 아래 세 하위 명령(`doctor`, `run`, `campaign`)뿐이다.

```bash
./ctl.sh same-cell doctor --profile p5
./ctl.sh same-cell run blind-dos --profile p5 --mode control --run-id blind-control-1
./ctl.sh same-cell run blind-dos --profile p5 --mode attack --run-id blind-attack-1 --enable
./ctl.sh same-cell campaign l3-live --profile p5 --sets 3 --count 5 --enable
```

`l3-live`는 L3-01-V·L3-01-O·L3-20·L3-21·L3-24·L3-14·L3-06만 실행한다. AN fixture는
공격 자격 범위가 아니므로 포함하지 않는다. active mode는 프로토콜 재현이면 `attack`,
결과·관측 에뮬레이션이면 `emulation`이며, `ctl.sh`가 공격별 허용 mode를 검사한다.

통합 경로는 같은 CU·DU EC2 인스턴스와 같은 셀 식별자를 계속 사용한다. 다만 공격 사이에
상태가 섞이지 않도록 각 control·active phase마다 DU·broker·UE **프로세스**를 종료하고
cold-start한다. CU·코어·production dashboard는 유지한다. 이는 한 RF 스트림에 실행 중 새
UE를 삽입하는 hot-swap이 아니며, dashboard에는 같은 셀의 시간축에 phase 사이의 재시작
구간이 생긴다.

각 phase는 정상 UE 5대와 해당 공격 슬롯을 DU 시작 전에 broker에 모두 연결한다. 공격 전과
종료 단계의 정상 UE 5대 Registration·PDU·gateway ping 상태를 별도로 기록한다. 공격 중
일시 저하는 공격 효과로 분리하며, 종료 단계에서 5/5 회복을 확인하지 못하면 정상 UE 동반
자격은 실패다. 인증 미응답형은 10개 미인증 컨텍스트를 만든 공격 UE가 계속 재시도하므로
공격 UE를 먼저 종료하고 회복을 측정하며 `attack_teardown_before_recovery=true`를 남긴다.

탐지 입력을 직접 만들거나 KPM·detector socket으로 주입하지 않는다. 자격 경로는 항상
`UE → ZMQ broker → DU/CU → TeleRAN → production detector → dashboard`를 사용한다.
L3-24·L3-14·L3-06은 기존과 같이 UE 쪽에서 논문 공격의 결과 또는 관측 신호를 만드는
에뮬레이션이며, RF overshadowing·MITM·NAS counter wrap의 실제 원인을 재현했다고 주장하지
않는다.

## 기존 개별 자격 토폴로지

모든 자격 실행은 **CU 인스턴스 1대와 DU 인스턴스 1대**를 순차 재사용한다. Blind DoS의
2-cell은 DU 두 대가 아니라 동일 DU 프로세스의 논리 셀 두 개다.

| 룰 | 공격 runner 진입점 | 기존 자격 토폴로지 | 당시 금지·미승인 경로 |
|---|---|---|---|
| L3-01-V | `ctl.sh campaign rrc-storm` | 1 DU·1 cell | 임의 timer/capacity 완화 |
| L3-06 | `ctl.sh campaign l3-06` | direct 1-cell | 정상 UE same-cell |
| L3-24 | `ctl.sh campaign downlink-imsi` | direct 1-cell | RF 원인 재현 주장 |
| L3-14 | `ctl.sh campaign ue-capability` | direct 1-cell | MITM·내용 변조 주장 |
| L3-21 | `ctl.sh campaign uplink-credential-flood` | 한 UE가 10개 실패 연결 생성 | 단발 MAC 변조를 L3-21로 주장 |
| L3-01-O | `ctl.sh campaign auth-timeout` | 한 셀, 2 OAI 프로세스×5 UE, shared endpoint 2개 | 한 프로세스 `--num-ues 10` |
| L3-20 | `bin/blind-run`·`bin/blind-p5-phase` | direct 2-cell, victim·attacker 동시 실행 | 순차 재사용·same-cell |

이 표는 이미 봉인된 개별 모듈 결과의 출처를 설명한다. 새 정상 UE 5대 통합 자격을 만들 때는
runner나 `tools/p5-live-e2e`를 직접 호출하지 않고 앞 절의 `ctl.sh same-cell`만 사용한다.
기존 개별 자격을 same-cell 자격으로 복사해 적지 않는다.

## E2E 합격 조건

공격별 `control → attack/emulation`을 3세트 실행한다. 각 실행에서 다음을 모두 확인한다.

- 기존 공격·에뮬레이션 판정 통과
- `UE → ZMQ → DU/CU → TeleRAN → production detector → dashboard` 경로 사용
- TeleRAN 100 ms, sequence 연속, gap 0, KPM 존재
- control의 대상 경보 0건, active의 대상 RAISE 1건
- dashboard 수락 1건 이상·거절 0건
- runner·바이너리·설정·증거 SHA-256 봉인
- 정상 UE 5대의 공격 전·종료 직전 Registration·PDU·ping 상태 봉인

p5 결과를 p4 결과로 복사해 적지 않는다. p4에서 동일한 3세트를 별도로 통과해야 p4 자격으로
기록한다.

현재 새 통합 경로는 구현 단계다. 기존 증거로 정상 UE 5대 same-cell matched 3/3이 확인된
것은 L3-21이며, UE Capability는 control·emulation 각 1회, RRC는 별도 공존 실측만 있다.
Blind DoS·L3-01-O·L3-06을 포함한 7종 전체는 새 CLI로 p5 control→active 3/3과 dashboard
전송을 다시 봉인하기 전까지 **구현됐으나 미자격**이다. 기존 direct 1-cell·2-cell 자격은
유효하지만 새 통합 자격을 대신하지 않는다.

## 실패했을 때

다음 자료를 그대로 보존하고 수동 스크립트로 우회하지 않는다.

- `git rev-parse HEAD`, `git status --short`
- 실행 명령과 profile 이름
- runner·OAI UE·DU 설정 SHA-256
- UE·broker·DU·CU·detector 로그와 run 디렉터리
- 인스턴스 유형, 셀 수, UE 프로세스×논리 UE 수

공식 토폴로지와 다른 실행은 공격 실패가 아니라 **시험 무효**로 분류한다.
