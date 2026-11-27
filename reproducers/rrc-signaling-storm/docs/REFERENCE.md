# RRC 시그널링 스톰 기술 레퍼런스 (L3-01-V)

> 이 문서는 [../README.md](../README.md)에서 분리한 `rrc-signaling-storm` 상세 기술 레퍼런스다. 기본 실행은 [사용 가이드](USAGE-GUIDE.md)와 [상위 E2E 가이드](../../../docs/E2E-EXECUTION-GUIDE.md)를 따른다.

## 테스트베드 스펙 및 전제

### 토폴로지

```text
   CU 호스트 (c6i.xlarge)                 DU 호스트 (c6i.2xlarge)
 +----------------------+   F1 / IP    +--------------------------+
 |  OCUDU CU            |<------------>|  OCUDU DU                |
 |  Open5GS 코어        |              |  공격 UE (이 패키지)      |
 |  TeleRAN / detector  |              |   ZMQ 가상 무선          |
 |  CU 로그 /tmp/ocu.log|              |   tcp://127.0.0.1:4556-7 |
 |  bin/rss-report      |              |                          |
 +----------------------+              +--------------------------+
        판정                                    공격 실행
```

- 공격 UE는 DU와 같은 호스트에서 동작한다. 현재 `rss-build`·`rss-doctor`·`rss-run`은 `oai_zmqdevif`만 허용한다.
- `RRCSetupComplete` 미전송형은 코어(AMF)까지 도달하지 않지만, CU에 AMF와 CU-UP가 연결돼 있지 않으면 OCUDU CU-CP가 모든 `RRCSetupRequest`를 거절한다.

### 소프트웨어 및 셀 파라미터

| 구성요소 | 버전 / 커밋 | 비고 |
|---|---|---|
| gNB | OCUDU `release_26_10` (`e0db566a`) | 소스 무수정 |
| 공격 UE | OAI `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (`2026.w38`) | `bin/rss-build` 기준 커밋 |
| 무선 드라이버 | OAI `oai_zmqdevif` | `radio/zmq/` 패치 포함 |
| 분석 | `python3` 표준 라이브러리 | 외부 패키지 불필요 |
| 셀 파라미터 | `BAND=78`, `DL_FREQ=3489420000`, `NUMEROLOGY=1`, `PRB=51` | `ZMQ_TX=tcp://127.0.0.1:4557`, `ZMQ_RX=tcp://127.0.0.1:4556` |

## 빌드·실행 상세 (1~10단계)

### 1단계 — OAI 트리 준비

```bash
bin/rss-bootstrap            # 2026.w38 클론 + 스톡 빌드 (최초 1회)
# 라이브러리 부족 시: bin/rss-bootstrap --deps
```

`OAI`(기본 `/root/OAI`)에 트리가 없으면 `2026.w38` 태그를 shallow clone해 `1c2f4d3c...`를 체크아웃하고 `build_oai --nrUE -w ZMQ`로 스톡 빌드한다. 로컬 변경이나 다른 커밋 빌드가 있으면 거부한다.

### 2단계 — 설정

```bash
cp conf/rss.conf.example conf/rss.conf
$EDITOR conf/rss.conf
```

필수 검토 항목은 `OAI`, `UE_CFG`, `BAND`, `DL_FREQ`, `NUMEROLOGY`, `PRB`, `ZMQ_TX`, `ZMQ_RX`, `GNB_RESTART_CMD`, `LOGDIR`, `ODU_LOG`, `ODU_SECTOR_ID`, `GNB_LOG`, `CAPACITY`이다. `ENABLE=0`을 기본값으로 유지한다. `GNB_RESTART_CMD`에는 파이프라인을 쓰지 않고 DU만 재기동하는 단일 명령을 넣는다.

### 3단계 — 빌드

```bash
bin/rss-build
```

`rss-build`는 깨끗한 `1c2f4d3c...` 트리에서 `rss-ue-a-type` 브랜치를 만들고 실제 다음 4개 패치를 순서대로 적용한다.

1. `patch/rss-ue-curated.patch`
2. `patch/oai-stale-rnti-dci.patch`
3. `patch/oai-msg4-ack-rnti.patch`
4. `patch/oai-broker-control-gate.patch`

그 뒤 `nr-uesoftmodem`, `oai_zmqdevif`, `zmq_radio_static` 3개 타깃을 빌드하고, 노브 문자열과 민감 로그(`UICC simulation: IMSI=`, `milenage output ik:`) 제거 여부를 검사한다. 기존 바이너리는 `.orig`로 백업한다. (`patch/oai-pucch-null-fix.patch`는 `rss-build`가 아니라 상위 `tools/ctl.sh`가 `6d6782b4...` 기준 커밋을 재생성할 때 사용한다.)

### 4단계 — 진단 및 실행

```bash
bin/rss-doctor
bin/rss-run -e 0 -u 1 -d 30            # 정상 접속 회귀 (-u 1 필수)
bin/rss-run -e 1 -u 2 -d 120           # 공격 실행 (-d 0이면 수동 SIGINT 종료)
```

`run_id`는 ASCII 영문자·숫자로 시작하고 두 번째 문자가 `O`일 수 없다(OAI `-O` 파싱 버그 회피). 동일 `RUN_ID` 경로가 이미 있으면 실행을 거부한다.

### 산출물과 자체 점검

`$LOGDIR/<run_id>/`에 `run.json`, `attempts.jsonl`(`-e 1` 전용, 탐지 입력 금지), `ground_truth.jsonl`, `odu.log`, `du_log_slice.json`, `ue.log`(정제됨, `0600`), `ue_redaction.json`, `sensitive_artifact_check.txt`, `gnb_boot.txt`, `run_stop.json`, `evidence_manifest.json`이 생성된다.

```bash
python3 analysis/evidence_manifest.py verify <run-dir>
python3 analysis/evidence_manifest.py verify <run-dir> --require-matched
```

### 판정 (CU 호스트) 및 원복

```bash
bin/rss-report --since 2026-10-20T06:31:00 --until 2026-10-20T06:33:10 \
               --jsonl /root/rss-runs/<run_id>/attempts.jsonl
```

진단 프로필을 적용한 경우 `bin/rss-gnb-profile --role du restore` 및 `--role cu restore` 후 gNB를 재기동해 원복한다.

## 파라미터 및 무선 효율

우선순위는 **명령행 > `conf/rss.conf` > 환경변수 > 내장 기본값**이다.

| 옵션 | 환경변수 / conf | 기본값 | 의미 |
|---|---|---:|---|
| `-e 0\|1` | `ENABLE` | `0` | 공격 off / on |
| `-u N` | `NUM_UES` | `1` | 공유 무선을 쓰는 공격 UE 인스턴스 수 |
| `-i MS` | `INTERVAL_MS` | `0` | 시도 사이 추가 지연 (0 = 최대 속도) |
| — | `PHASE_MS` | `0` | non-probe UE 매 재시도에 `UE ID × PHASE_MS` stride 추가(0..5000ms) |
| `-d SEC` | `MAX_DURATION_S` | `60` | 킬 스위치 (0 = 중지할 때까지 계속) |
| `-o N` | `TARGET_OCCUPANCY` | `0` | UE 측 추정 점유 목표 (실제 gNB 피드백 없음) |
| `-H MS` | `HOLD_MS` | `2000` | 추정 보유시간 가정 |
| `-c PCT` | `COMPLETION_PCT` | `0` | 0보다 크면 1회 완료 후 종료(1회성 점검용) |
| `-r 0\|1` | `HONOR_REJECT` | `1` | `RRCReject` waitTime 준수 / 즉시 재시도 |
| `-g 0\|1` | `ACK_GATE` | `1` | Msg4 ACK 대기 중 RA 재시작 차단 |
| `-G 0\|1` | `RA_GATE` | `1` | RA 진행 중 재시작 차단 |
| `-M 0\|1` | `MSG4_WAIT` | `1` | 1 = Msg5 생략(`RRCSetupComplete` 미전송형), 0 = Msg3 뒤 중단형 |
| `-A 0\|1` | `MSG4_ACK` | `1` | 0 = Msg4 HARQ-ACK(최초+재전송) DTX 억제 |
| `-p N` | `PROBE_UES` | `0` | 인스턴스 0..N-1을 동일 프로세스 내 probe로 동작 |
| `-t MS` | `PROBE_DELAY_MS` | `0` | probe 첫 접속 지연 |
| — | `PROBE_RA_ONLY` / `PROBE_INTERVAL_MS` | `0` / `1000` | RA-only probe 및 재시도 최소 간격 |
| — | `GATE_TIMEOUT_MS` | `500` | 게이트 강제 해제 시간 (0 = 없음) |
| — | `RSS_ZMQ_TX_WAIT_US` | `-2` | ZMQ TX 대기 방식 (`-2` 조건 변수) |
| — | `RSS_SHARE_LOCKSTEP` | `1` | UE별 하향 커서 lockstep |
| — | `RSS_SHARE_NUE` | `NUM_UES` | 부분 배치 거부 (반드시 `NUM_UES`와 일치) |
| — | `RSS_SHARE_WR_MONOTONIC` | `0` | `0` 유지 |

## NUM_UES 선택

레퍼런스 테스트베드(OCUDU 26.10, 기본 용량 96, 유지 2000 ms, 60초, 공유 ZMQ 무선 1개) 실측이다.

| UE | 시도/초 | 피크 점유 | `RRCReject` | `channel timeout` | 200 ms 이상 공백 |
|---:|---:|---:|---:|---:|---:|
| 1 | 33.8 | 90 / 96 | 0 | 0 | 0 |
| 2 | 38.6 | **96 / 96** | 33 | 5,136 | 3 (5%) |
| 3 | 36.2 | 96 / 96 | 198 | 14,718 | 22 (39%) |
| 4 | 37.4 | 96 / 96 | 312 | 39,765 | 25 (45%) |

모든 인스턴스가 무선 1개와 DU MAC 1개를 공유하므로 **2 UE**가 용량 도달 최소 수이자 샘플 손실·정지 공백이 가장 적은 권장값이다. 탐지기 학습용 무손실 스트림이 필요하면 1 UE를 사용한다.

## 도구에 들어간 최적화

1. **ZMQ TX 웨이크업 (`RSS_ZMQ_TX_WAIT_US=-2`)**: 업스트림 10 ms `zmq_poll` 대기를 조건 변수 웨이크업으로 바꿔 시도율을 약 3배(6.7 → 19.5~33.8/s)로 높였다.
2. **동일 프로세스 무선 공유 및 UE별 읽기 커서**: `unitTransfer == res` 어서션 깨짐을 막기 위해 UE별 읽기 커서를 분리하고 `RSS_SHARE_LOCKSTEP=1`로 묶었다.
3. **same-cell broker 통합 (`tools/ctl.sh same-cell` / `bin/rss-broker-witness`)**: `BROKER_WITNESS_MULTI_RU=1`과 `workloads/normal-ue/tools/same_cell_broker.py`를 통해 공격 UE 6프로세스×2 UE와 독립 virtual RU 5개 정상 UE 풀을 한 DU·셀에 cold-start 통합한다.

## 기각된 최적화

| 아이디어 | 결과 |
|---|---|
| `TRANSMIT_TS_ALIGN_TIMEOUT` 상향 | 구조상 무효과 (`align()`이 타임아웃 전 즉시 반환) |
| `sched_yield` 스핀 (`=-1`) | 생산자 스레드를 굶겨 무선 시간·시도 감소 |
| usleep vs 조건 변수 (`=-2` vs `>0`) | 비용 동일 (237 us vs 240 us); CPU 절약을 위해 `-2` 유지 |
| `RSS_SHARE_WR_MONOTONIC=1` | 샘플 손실 0이나 클램프 폭주로 시도 2,387 → 32 |
| 코어 핀닝 (`UE_TASKSET`) | 33.8 → 24.2 시도/초로 성능 하락 |
| `ACK_GATE=0` | 변화 없음 (34.1 vs 33.8 시도/초) |

*(참고: `MSG4_WAIT=0` RRCSetupRequest 후 중단형은 2026-10-30 `nr_rss_note_msg3_tx()` 수정으로 기각 철회 후 별도 변종으로 유지된다.)*

## 문제 해결 요약

| 증상 | 원인과 조치 |
|---|---|
| `bin/rss-doctor` `[FAIL]` | 출력된 해결 명령부터 수행 |
| `[RSS]` 배너 없음 / `unknown option: --rss.*` | 패치 누락 또는 구형 빌드. `bin/rss-build` 재실행 |
| UE가 `Intializing UE Threads`에서 멈춤 | ZMQ 스트림 불일치. `GNB_RESTART_CMD`로 DU 동반 재기동 |
| `run_id ...: second character must not be 'O'` | OAI `-O` 파서 버그 회피를 위해 런 ID 변경 |
| `Error, channel timeout` 과다 | 샘플 손실. `-u`를 2 이하로 축소 |
| 모든 접속 거절 | CU에 AMF/CU-UP 미연결 |
| `another broker witness run is active` | 구버전 lock FD 9 상속 문제; 최신 `rss-broker-witness` 사용 |

## 모듈 구성 파일

- `bin/`: `rss-bootstrap`, `rss-build`, `rss-doctor`, `rss-run`, `rss-report`, `rss-gnb-profile`, `rss-cu200`, `rss-broker-witness`, `rss-broker-witness-retry`, `rss-probe`, `rss-lab-suite`
- `conf/`: `rss.conf.example`, `ota-inventory.example.json`
- `patch/`: `rss-ue-curated.patch`, `oai-stale-rnti-dci.patch`, `oai-msg4-ack-rnti.patch`, `oai-broker-control-gate.patch`, `oai-pucch-null-fix.patch` (상위 `tools/ctl.sh`용) 및 과거 보관본(`rss-ue.patch`, `rss-ue-anas.patch`, `rss-ue-full-20261023.patch`, `anas-identity.c`)
- `analysis/`: `export_labels.py`, `evidence_manifest.py`, `capture_du_log.py`, `sanitize_ue_log.py`, `check_sensitive_artifacts.py`, `check_sensitive_history.py`, `validate_ota_inventory.py`, `cu_occupancy.py`, `cu_count.py`, `run_summary.py`, `compare.py`, `attempt_phases.py`, `log_window.py`, `probe_data.py`, `probe_summary.py`
- `tools/`: `multi_ue_{2,5,6,7,8,10}ue.py`, `zmq_broker.c`
- `tests/`: `python3 -m unittest discover -s tests` (189개 오프라인 단위 테스트)
