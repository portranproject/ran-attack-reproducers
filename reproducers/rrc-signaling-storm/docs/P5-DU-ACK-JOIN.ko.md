# p5 DU ACK exact join 실기 게이트

> **버전별 판정:** J1a는 patch
> `f0072a558d926baaf39ef5ab2f0d8e7e5d23223ec24309fef4835e778e5bbd38`, binary
> `015d4f2b77de128302e60b0525732035ef773a40627bfe597893487ae80802fc`에서
> 10/10 exact ACK join과 `canonical_a=true`를 이미 통과했다.
> 최종 binary `202934f7d34db2f81763b28d43f2d09f5cdac9175d4146a412d778174f3c4c2b`는
> V4의 세 공격 sector에서 DU ACK 확인 RRCSetupComplete 미전송형 합계 176건을 통과했다.
> 해당 버전의 4셀 정상 대조군도 성공했다. 근거와 해시는
> [V4 hold32 진단](../../../artifacts/p5-cu200-3cell-20261030/README.md)에 있다.

아래 절차는 새 바이너리마다 run-scoped 조인이 실제 OCUDU FAPI 로그에서
`canonical_a=true`를 만드는지 짧게 확인하는 독립 게이트다. 공격 범위를 넓히거나 서비스
거부를 측정하는 실험이 아니다. 팀 소유 p5 ZMQ 세트의 비용·공격 실행은 승인된 상태이며,
실행 직전에 인스턴스 상태만 확인한다.

## 0. 사전 조건

- 로컬 제어판: `/Volumes/owc/Users/ideal/tmp/p5-panel/p5/ctl.sh`
- DU 로그: `/tmp/odu.log`
- DU 설정: `/root/OCUDU/configs/du.yaml`
- 기존 보존본과 겹치지 않는 새 `LOGDIR`
- 최신 `rss-storm`을 DU에 복사하고 다음 파일의 로컬/원격 SHA-256 일치 확인:
  `bin/rss-run`, `analysis/export_labels.py`, `analysis/capture_du_log.py`,
  `analysis/evidence_manifest.py`, `analysis/sanitize_ue_log.py`,
  `analysis/check_sensitive_artifacts.py`, `patch/rss-ue-curated.patch`
- 현재 curated patch로 OAI UE를 clean rebuild하고 `rss-doctor`의
  `subscriber-secret UICC log removed`와 `direct Milenage authentication dumps removed`를
  모두 통과한다. 과거 binary는 새 credential과 인증 벡터를 다시 출력하므로 사용하지 않는다.
- 과거 credential 기록은 private p5 재실행을 막지 않는다. 저장소를 외부에 공개하기
  전에는 credential 회전과 Git 이력 정리 여부를 다시 확인한다.

`./ctl.sh up`은 기본 DU와 UE까지 함께 띄우므로 쓰지 않는다. 로컬 `start`로 인스턴스만
켜고 CU stack을 먼저 올린 뒤, DU는 `rss-run`의 stop/restart hook으로 기동해야 ZMQ
샘플 흐름이 정렬된다.

## 1. 인스턴스와 CU만 기동

```bash
cd /Volumes/owc/Users/ideal/tmp/p5-panel/p5
./ctl.sh start
./ctl.sh ssh cu
sudo /root/workspace/ctl.sh start
```

DU 셸을 별도로 연다.

```bash
./ctl.sh ssh du
# 접속된 DU 셸에서
sudo -i
```

## 2. DU 설정과 sector 고정

`du.yaml`의 SHA-256과 접근 제한 백업을 먼저 남긴다. 단일 sector인지, 실제
`sector_id`가 무엇인지 읽고 그 값을 이후 `ODU_SECTOR_ID`로 사용한다. OCUDU 기본
FAPI log level은 warning이므로 `log.fapi_level: debug`를 설정한다. gNB 소스는 수정하지
않는다.

```bash
DU_CFG=/root/OCUDU/configs/du.yaml
DU_CFG_BACKUP="${DU_CFG}.pre-dujoin-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a -- "$DU_CFG" "$DU_CFG_BACKUP"
DU_CFG_SHA_BEFORE=$(sha256sum "$DU_CFG" | awk '{print $1}')
printf 'backup=%s\nsha256_before=%s\n' "$DU_CFG_BACKUP" "$DU_CFG_SHA_BEFORE"
```

설정 변경 전·후 hash, sector ID, 변경자와 시각을 실험 기록에 남긴다. sector를
추측하거나 여러 sector가 섞인 로그를 사용하지 않는다.

## 3. DU 환경

기존 `rss.conf`의 빈 값이 환경변수를 덮지 않도록 이 실험은 `/dev/null` conf를 쓴다.
프롬프트에는 2단계에서 확인한 실제 sector ID를 입력한다.

```bash
cd /root/rss-storm
export RSS_CONF=/dev/null
export LOGDIR=/root/rss-runs-dujoin-20261030
export ODU_LOG=/tmp/odu.log
read -r -p '확인한 sector ID (0..65535): ' ODU_SECTOR_ID
export ODU_SECTOR_ID
export GNB_STOP_CMD='/root/workspace/ctl.sh stop'
export GNB_RESTART_CMD='/root/workspace/ctl.sh start'
export GNB_READY_CMD='pgrep -x odu >/dev/null && grep -q "F1-C: Connection to CU-CP .* completed" /tmp/odu.boot.log && ss -ltn | grep -q ":4556 "'
```

## 4. 정상 대조군

```bash
CONTROL_ID=J1b-$(date -u +%H%M%S)
./bin/rss-doctor
./bin/rss-run -e 0 -u 1 -d 40 -n "$CONTROL_ID"
./bin/rss-doctor
python3 analysis/evidence_manifest.py verify "$LOGDIR/$CONTROL_ID"
```

정상 attach·Registration·PDU가 성립하고, doctor가 지정 sector의 최근 FAPI PUCCH
0/1 HARQ 행을 확인해야 한다. control이 불안정하거나 FAPI 행이 없으면 공격을 실행하지
않고 설정·로그 경로부터 고친다.

## 5. 짧은 ACK-on RRCSetupComplete 미전송형

20초 kill switch와 2초 간격으로 부하를 제한한다.

```bash
ATTACK_ID=J1a-$(date -u +%H%M%S)
./bin/rss-run -e 1 -u 1 -A 1 -i 2000 -d 20 -n "$ATTACK_ID"
python3 analysis/evidence_manifest.py verify \
  "$LOGDIR/$ATTACK_ID" --require-matched
```

다음 조건이 모두 맞아야 통과다.

- `run_stop.json`: `valid=true`, `label_export=ok`, `du_ack_join=matched`
- `run_stop.json.sensitive_artifact_scan=ok`, `ue_redaction.json.status=clean`
- `ground_truth.jsonl`: `canonical_a=true` 최소 1건과 각 행의 `du_ack_evidence`
- UE/DU 양쪽 `(RNTI, frame, slot)`이 run 전체에서 유일
- label sector ID = `run.json.orchestration.du_sector_id`
- `odu.log` SHA-256 = `du_log_slice.json.sha256` = `run_stop.du_log_sha256`
- `evidence_manifest.py verify --require-matched` 성공

`no_match`, capture 실패, 다른/missing sector, 중복 tuple은 음성 결과가 아니라
**inconclusive**다.

## 6. 원복과 종료

DU 설정을 백업본으로 복원하고 변경 전 SHA-256과 일치하는지 확인한다. DU와 CU stack을
종료한 뒤 로컬 제어판에서 인스턴스를 중지한다. `destroy`는 하지 않는다.

```bash
# DU root 셸
/root/workspace/ctl.sh stop
cp -a -- "$DU_CFG_BACKUP" "$DU_CFG"
test "$(sha256sum "$DU_CFG" | awk '{print $1}')" = "$DU_CFG_SHA_BEFORE"

# CU 셸
sudo /root/workspace/ctl.sh stop

# 로컬
cd /Volumes/owc/Users/ideal/tmp/p5-panel/p5
./ctl.sh stop
./ctl.sh status
```

로컬 `stop`은 중지 요청만 반환하므로 직후 `stopping`은 정상이다. 5~10초 간격으로
`./ctl.sh status`를 다시 실행해 **CU와 DU가 모두 `stopped`**가 될 때까지 확인한다.
원복 hash 불일치나 최종 상태가 `stopped`가 아닌 경우는 실험 완료가 아니다.
