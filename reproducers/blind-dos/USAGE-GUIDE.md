# Blind DoS 사용 가이드

이 가이드는 팀 소유 p5형 ZMQ 테스트베드에서 **현재 유효 5G-GUTI 재사용형**을 실행하고
G5 판정을 읽는 절차다. 외부 망이나 비차폐 RF에서는 실행하지 않는다.

## 1. 실행 결과가 의미하는 것

정상 attack 결과는 다음 순서를 한 번 재현한다.

1. 피해 UE가 Registration·PDU session·ping 서비스 중이다.
2. 공격 UE가 피해자의 현재 5G-GUTI를 RRC와 NAS Registration Request에 사용한다.
3. 공격 commit과 피해자의 기존 AMF context 변화가 exact join된다.
4. 피해 UE ping이 사전 고정한 횟수만큼 연속 실패한다.
5. one-shot 공격이 끝난 뒤 같은 victim PID가 새 Registration·PDU를 만들고 ping을 회복한다.

단일 attack 통과만으로 캠페인 성공은 아니다. 같은 설정의 control→attack을 사전 고정한
N세트 모두 통과해야 G5다. 기본 N은 3이다.

현재 검증 범위는 p5 direct 2-cell ZMQ(G5 3/3, E2E 6/6)와 `p1` clean-origin 정상 UE 5대 same-cell E2E(`p1q9-20261119` 6/6)이다. 비특권 식별자 획득(G6), 지속 차단(G7), OTA 성능은 검증하지 않는다.

> `same-cell` E2E 실행은 `./ctl.sh same-cell run blind-dos --profile <p1|p5> --mode <control|attack> --run-id <id> [--enable]`을 사용한다. 아래 절차는 직접 `bin/blind-run` / `bin/blind-campaign`(p5 direct 2-cell) 기준이다.

## 2. 준비물

- OCUDU 26.10 CU/DU와 Open5GS가 동작하는 격리 테스트베드
- clean OAI worktree, commit
  `6d6782b48484efd935c14e834832032743f9b138`
- 피해자·공격자용 서로 다른 팀 가입자 프로필
- DU host에서 CU host로 비대화형 SSH가 가능한 전용 key와 known_hosts
- 측정된 host clock offset·uncertainty와 그 증거 SHA-256
- 검토한 G0 inventory hash

가입자 프로필과 SSH key는 Git 밖 권한 0600 경로에 둔다. 같은 가입자 fingerprint를 넣으면
runner가 실행 전 실패한다.

## 3. OAI UE 빌드

전용 clean worktree에서 실행한다.

```bash
cd /path/to/ran-attack-reproducers
OAI=/root/OAI-blind-dos-w38 \
  reproducers/blind-dos/bin/blind-build
```

`bin/blind-build`는 `patch/blind-ue-w38.patch`와 `../authentication-timeout-exhaustion/patch/same-cell-ra-gate-w38.patch`를 순서대로 적용하고 다음을 검사한다.

- OAI HEAD가 고정 commit인지
- worktree가 clean인지
- 패치가 `git apply --check`를 통과하는지
- `nr-uesoftmodem`과 ZMQ device library가 생성됐는지
- one-shot 옵션·이벤트 문자열이 binary에 있는지
- 가입자·인증 재료를 출력하던 OAI 문자열이 제거됐는지

공격 기본값은 off다. 출력된 source commit, patch hash, binary hash를 실험 기록에 보존한다.

## 4. direct 2-cell 구성

DU 설정 예제를 테스트베드 전용 경로로 복사해 주소·주파수·cell 값을 검토한다.

```bash
cp reproducers/blind-dos/conf/p5-du-2cell-zmq.yaml.example \
  /안전한/경로/du-2cell-zmq.yaml
```

기본 endpoint 배치는 다음과 같다.

| 역할 | DU TX / UE RX | DU RX / UE TX |
|---|---|---|
| 피해 UE, cell 0 | `4556` | `4557` |
| 공격 UE, cell 1 | `4558` | `4559` |

GNU Radio broker/relay는 사용하지 않는다. 피해 UE와 공격 UE는 별도 프로세스·별도 cell을
쓴다. 한 endpoint만 먼저 종료하면 2-cell ZMQ clock이 멈출 수 있으므로 수동으로 프로세스를
중간 종료하지 않는다.

## 5. 실행 설정

예제를 Git 밖으로 복사한다.

```bash
cp reproducers/blind-dos/conf/p5-zmq.conf.example \
  /안전한/경로/blind.conf
chmod 600 /안전한/경로/blind.conf
```

최소한 다음 값을 실제 환경에 맞춘다.

- `OAI_BLIND_BIN`, `VICTIM_UE_CFG`, `ATTACKER_UE_CFG`, `UECAP`
- `P5_CU_HOST`, `P5_SSH_KEY`, `P5_KNOWN_HOSTS`
- `P5_DU_BIN`, `P5_DU_CFG`, `P5_CU_LOG`, core container 이름
- 피해 TUN과 ping target
- `AMF_REGION_ID`
- `CLOCK_*`, `LAB_INVENTORY_SHA256`
- 서로 다른 `VICTIM_PROFILE_FINGERPRINT`, `ATTACKER_PROFILE_FINGERPRINT`

실행 전에 고정할 threshold는 다음이다.

```bash
OBSERVATION_S=12
RECOVERY_TIMEOUT_S=30
BASELINE_PING_COUNT=20
LOSS_CONSECUTIVE_PINGS=5
RECOVERY_PING_COUNT=20
MATCHED_REPETITIONS=3
INFRA_RETRY_LIMIT=1
```

값은 캠페인 도중 바꾸면 안 된다. runner가 설정·정책·실행기 hash 변화를 감지하면
`infrastructure-invalid`로 중단한다.

## 6. control 먼저 실행

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-run control -n control-001
```

control에서도 공격 UE endpoint는 같은 binary와 cell에서 표적 게이트를 기다린다. 게이트를
열지 않으므로 공격 이벤트는 0이어야 한다. 피해 UE는 baseline·관측·after service를 모두
통과해야 한다.

`run_stop.json`의 필수 결과:

```json
{
  "classification": "passed",
  "mode": "control",
  "verdict": {
    "victim_service_before": true,
    "victim_service_loss": false,
    "victim_service_after": true,
    "target_owner_state_effect": false,
    "crash_count": 0,
    "forced_kill_count": 0
  }
}
```

control이 실패하면 attack을 실행하지 않고 ZMQ endpoint, 가입자 상태, TUN, clock과 hook을
먼저 고친다.

## 7. 단일 attack 실행

공격은 명시적 `-e 1` 없이는 시작되지 않는다.

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-run attack -e 1 -n attack-001
```

runner는 피해 snapshot 뒤에만 표적 파일을 생성한다. 공격 UE는 아래 terminal chain을
정확히 한 번 기록해야 한다.

```text
target_gate_opened
target_msg3_committed
nas_guti_selected
rrc_setup_complete_submitted
authentication_request_withheld
```

attack 통과의 핵심 verdict:

```json
{
  "classification": "passed",
  "mode": "attack",
  "verdict": {
    "exact_join": true,
    "target_owner_state_effect": true,
    "victim_service_loss": true,
    "same_victim_recovery": true,
    "victim_service_after": true,
    "crash_count": 0,
    "forced_kill_count": 0
  }
}
```

`same_victim_recovery`는 before/after `victim_pid`가 같고 Registration·PDU count가 모두
증가해야 참이다. 새 프로세스를 시작해 회복한 것은 통과로 세지 않는다.

## 8. G5 matched campaign

기본 3세트:

```bash
BLIND_CONF=/안전한/경로/blind.conf \
  reproducers/blind-dos/bin/blind-campaign \
  -e 1 -n blind-g5-$(date +%Y%m%d) -R 3
```

10세트를 사전 고정하려면 `-R 10`을 쓴다. 허용 범위는 3~100이다. 각 세트는 반드시
control→attack 순서다.

성공한 `campaign_result.json` 예:

```json
{
  "status": "passed",
  "passed": true,
  "required_sets": 3,
  "completed_sets": 3,
  "reason": "all_matched_sets_passed"
}
```

`campaign_events.jsonl`에서 모든 control/attack이 `try01`에 통과했는지, 인프라 무효
재시도가 있었는지도 확인한다. 유효한 공격 실패는 재시도하거나 다른 결과로 대체하지 않는다.

## 9. 증거 검증

각 child run은 개별 manifest를 가진다.

```bash
python3 reproducers/blind-dos/analysis/evidence_manifest.py verify \
  /run/root/campaign/children/set001-attack-try01
```

필수 확인 항목:

- `evidence_manifest.py verify` 성공
- `sensitive_artifact_check.txt`가 `ok`
- `raw_evidence_unchanged_by_verifier=true`
- `configuration_unchanged=true`, `software_unchanged=true`
- attack은 exact join·state effect·loss·same PID recovery가 모두 참
- control은 공격 이벤트·state effect·loss가 모두 거짓
- crash/forced kill 0

raw log와 pcap은 Git에 올리지 않는다. Git에는 campaign/result, child verdict·run_stop·
manifest, 전체 원문 SHA-256 목록만 둔다.

## 10. 결과 해석

| 결과 | 의미 | 조치 |
|---|---|---|
| `passed` control | 대조 서비스 정상 | 같은 설정의 attack 진행 가능 |
| `passed` attack | 단일 G5 phase 통과 | 사전 고정 N/N 여부 확인 |
| `valid-failure` | 인프라는 정상이나 공격 효과 부족 | 실패로 보존, 자동 재시도 금지 |
| `infrastructure-invalid` | 증거·프로세스·clock·설정 문제 | 원인 수정 후 새 run ID로 제한 재시도 |

G5를 통과해도 “식별자를 무선에서 훔쳤다”, “지속적으로 차단한다”, “OTA에서도 같다”,
“기지국 전체가 마비됐다”라고 쓰지 않는다. 정확한 표현은 **oracle 보조 단발 Blind DoS가
p5 direct 2-cell ZMQ에서 3/3 재현됐다**이다.

## 11. 자주 보는 실패

- `target_gate` timeout: CU snapshot 또는 target file 경로 확인
- baseline timeout: 피해 Registration/PDU/TUN/ping과 cell 0 endpoint 확인
- attack terminal event 없음: NAS 5G-GUTI 구성, AMF Region ID, attacker cell 확인
- victim이 회복 중 종료: `blind.recovery_mode=1`과 최종 OAI patch 확인
- victim status 141/0: `SIGUSR1`을 process group에 보내는 구버전 runner인지 확인
- cell clock 정지: attack terminal 직후 공격 endpoint를 수동 종료하지 않았는지 확인
- exact join 거짓: current-run CU/AMF log slice와 before NGAP IDs 확인
- same-cell baseline timeout: 배경 UE 수를 늘리거나 timeout만 연장하지 않는다. 피해 UE가
  반복 동기화 뒤 RAR 실패라면 독립 ZMQ 송신기 시간축 한계이며 direct 2-cell을 사용한다.
- manifest verify 실패: 봉인 뒤 파일이 추가·삭제·변경됐는지 확인

## 12. 종료와 원복

runner의 정상 종료가 UE 두 개, DU, capture와 log slice를 정리한다. 중단 시에는 동일
hook으로 잔여 PID를 확인하고, 테스트용 core/subscriber 변경을 원본 compose·DB 상태로
돌린 뒤 인스턴스를 중지한다. 넓은 `pkill`이나 패널 전체 stop 대신 run이 사용한 정확한
프로세스와 인스턴스만 대상으로 한다.
