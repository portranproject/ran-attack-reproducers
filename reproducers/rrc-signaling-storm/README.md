# RRC 시그널링 스톰 — RRCSetupComplete 미전송형 (L3-01-V)

공격 UE가 랜덤 액세스부터 `RRCSetup`(Msg4) 수신·HARQ ACK까지 정상 수행한 뒤 `RRCSetupComplete`(Msg5)만 생략해, 코어(`InitialUEMessage`)에 닿지 않고 gNB의 미완료 RRC 컨텍스트를 점유하는 프로토콜 재현 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-01-V` |
| `reproducer.json` id | `rrc-context-exhaustion` |
| `ctl.sh` ID / 별칭 | `rrc-storm` (`rrc-signaling-storm`, `rrc-context-exhaustion`, `rrc`) |
| 재현 수준 (`reproduction_level`) | `protocol` |
| active 모드 (`active_mode`) | `attack` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` E2E 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드(ZMQ 또는 RF 차폐 박스) 전용이다. `-e 1` 또는 `--enable` 없이는 공격이 비활성이다. [NOTICE.md](NOTICE.md)를 따른다.

## 동작 요약

```text
공격 UE                        OCUDU DU/CU                   Open5GS
   │ PRACH / RRCSetupRequest (Msg3) │                           │
   │───────────────────────────────>│                           │
   │ RRCSetup (Msg4) + HARQ ACK     │                           │
   │<───────────────────────────────│                           │
   │ (RRCSetupComplete 생략)         │ 가드 타이머 만료까지 점유    │ (InitialUEMessage 없음)
```

- **control** (`-e 0`): 정상 접속(Registration·PDU·ping)을 수행한다.
- **attack** (`-e 1`): 기본 모드(`MSG4_WAIT=1`, `MSG4_ACK=1`)는 Msg5를 생략하는 **RRCSetupComplete 미전송형**이다. 선택 변종으로 `MSG4_WAIT=0`(MAC 확인 Msg3 뒤 즉시 중단)과 `MSG4_ACK=0`(Msg4 HARQ-ACK DTX 억제)이 있다.
- **OAI UE-only 패치**: 기준 커밋 `1c2f4d3c2e68181cdef9f426d161163147ad4b77`(OAI `2026.w38`)에 `bin/rss-build`가 4개 패치(`rss-ue-curated.patch`, `oai-stale-rnti-dci.patch`, `oai-msg4-ack-rnti.patch`, `oai-broker-control-gate.patch`)를 적용한다. OCUDU·Open5GS 소스, timer, capacity는 수정하지 않는다.

- **UE 종료**: 정상 UE 프로세스를 한꺼번에 끄지 않는다. `NORMAL_UE_STOP_GAP_S`(전역 기본 3초) 간격으로 하나씩 INT하고, 10초 뒤 TERM, 다시 10초 뒤 KILL로 올린다. 공격 전 30초·후 90초 유지는 `ctl.sh same-cell campaign` 전용이며 단일 run은 0이다. verdict의 `teardown`에 `ue_stop_signal`·`grace_s`로 남는다.

## 실행 방법

### 통합 컨트롤러 (`ctl.sh`)

```bash
./ctl.sh setup rrc-storm --profile p1
./ctl.sh doctor rrc-storm --profile p1

# 단발/캠페인 실행 (p5 direct ZMQ)
./ctl.sh run rrc-storm control rrc-ctrl-01 --profile p5
./ctl.sh run rrc-storm attack rrc-atk-01 --profile p5 --enable
./ctl.sh campaign rrc-storm rrc-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./ctl.sh same-cell run rrc-storm --profile p1 --mode control --run-id sc-rrc-ctrl-1
./ctl.sh same-cell run rrc-storm --profile p1 --mode attack --run-id sc-rrc-atk-1 --enable
```

`ctl.sh same-cell run`은 내부적으로 `bin/rss-broker-witness`(`BROKER_WITNESS_MULTI_RU=1`, 공격 6프로세스×2 UE + 정상 UE 5대 독립 virtual RU)와 `workloads/normal-ue/tools/same_cell_broker.py`를 `tools/p5-live-e2e`로 감싸 실행한다.

### 직접 실행 (`bin/`)

설정 파일은 `conf/rss.conf.example`을 `conf/rss.conf`로 복사해 사용하며 `RSS_CONF` 환경변수로 재정의한다.

```bash
bin/rss-bootstrap                  # OAI 2026.w38 클론 및 스톡 빌드 (최초 1회)
bin/rss-build                      # 4개 패치 적용 + 3개 타깃 빌드 및 노브 검증
bin/rss-doctor                     # 설정·바이너리·ZMQ·로그 사전 점검
bin/rss-run -e 0 -u 1 -d 30        # 정상 접속 회귀
bin/rss-run -e 1 -u 2 -d 120       # 공격 실행 (-M 0|1, -A 0|1, -i MS, -o N, -H MS, -n RUN_ID)
bin/rss-report --since HH:MM:SS --until HH:MM:SS [--jsonl attempts.jsonl]
```

상세 옵션, ZMQ 무선 파라미터, `NUM_UES 선택`, `기각된 최적화`는 [docs/REFERENCE.md](docs/REFERENCE.md)를 따른다.

## 합격 기준

- **control**: 공격 시도 없음, 정상 UE 등록·PDU·ping 성공, crash/forced kill 0건.
- **attack (단독/same-cell E2E)**: `attempts` > 0 및 Msg5 0건, UE/DU exact F1AP/HARQ-ACK 조인(`du_ack_join=matched`, `canonical_a=true`), TeleRAN 100 ms / gap 0 / KPM 존재, production detector `L3-01-V` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5 성공.
- **campaign**: 고정 순서 `control → attack` 3세트 모두 통과(control 경보 0건, attack 경보 1건).
- **무결성 검증**: `python3 analysis/evidence_manifest.py verify <run-dir> --require-matched` 및 `check_sensitive_artifacts.py` 통과.

## 한계 및 금지 주장

- **서비스 거부 미관측**: p1/p5 E2E 3/3 모두에서 정상 UE 5대 ping이 5/5 유지됐으며 `service_denial`은 `not_observed`이다.
- **기본 cleanup 지속 포화 미입증**: 기본 약 2초 정리시간에서는 admitted Start율이 cleanup과 평형에 머물러 30초 지속 포화나 기지국 전체 마비는 성립하지 않는다.
- **OTA·상용망 미검증**: ZMQ 가상 무선 환경 검증만 완료됐으며 실 SDR 차폐 OTA와 상용 gNB 일반화는 검증하지 않았다.

## NUM_UES 선택

공유 ZMQ 무선 1개를 쓰는 `bin/rss-run`에서는 `-u 2`가 용량(96) 도달 최소 수이자 샘플 손실 공백이 가장 적은 권장값이다. 상세 비교표는 [docs/REFERENCE.md §NUM_UES 선택](docs/REFERENCE.md#num_ues-선택)을 본다.

## 기각된 최적화

`TRANSMIT_TS_ALIGN_TIMEOUT` 상향, `sched_yield` 스핀(`-1`), `RSS_SHARE_WR_MONOTONIC=1`, 코어 핀닝(`UE_TASKSET`), `ACK_GATE=0`은 성능 악화 또는 무효과로 기각했다. 상세 근거는 [docs/REFERENCE.md §기각된 최적화](docs/REFERENCE.md#기각된-최적화)를 본다.

## 관련 문서 및 근거

- 동반 문서: [사용 가이드](docs/USAGE-GUIDE.md), [기술 레퍼런스](docs/REFERENCE.md), [메커니즘](docs/MECHANISM.md), [측정 요약](docs/MEASUREMENTS.md), [라벨 계약](docs/LABEL-CONTRACT.md), [대응 경로 감사](docs/RESPONSE-PATH-AUDIT.md), [알려진 문제](docs/KNOWN-ISSUES.md), [OTA 스모크 게이트](docs/OTA-SMOKE.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 E2E 자격: [p5 L3 5종 E2E](../../artifacts/p5-live-e2e-five-20261117/README.md)
- 모듈 세부 증거: [curated 검증](../../artifacts/curated-verify-20261030/README.md), [label/RLF20](../../artifacts/label-v1-rlf20-20261030/README.md), [기본 cleanup D6](../../artifacts/p5-default-cleanup-rate-v2-20261030/README.md), [broker 안정성](../../artifacts/broker-stability-20261030/README.md)
