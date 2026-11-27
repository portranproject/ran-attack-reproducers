# 정상 UE 워크로드

공격 슬롯과 같은 DU·셀 ID에서 동작하는 정상 UE 5대 풀과 `same-cell` 통합 실행 하니스다. p5 단독 자격에 이어 2026-11-19 p1 clean-origin에서 L3 7종 통합 `control → active` 3세트 **42/42**를 통과했다([p1 자격 기록](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)). 실 SDR OTA 공존은 미검증이다.

## 아키텍처

- **독립 virtual RU 5개**: 하나의 `nr-uesoftmodem` 프로세스 안에서 `RUs`·`cells`·`zmq` 설정 배열로 UE별 독립 virtual RU/ZMQ endpoint 5개를 만든다. `normal-multi-ru.patch`가 `UE 수 > RU 수`일 때만 custom RU-sharing을 켜므로 5 UE/5 RU 경로에는 상향 batch 공유가 개입하지 않는다.
- **ZMQ broker (`tools/same_cell_broker.py`)**: 정상 UE 5개와 공격 슬롯 endpoint(`1`, `2`, 또는 `10`개, 합계 최대 `15`개)의 하향 신호를 복제하고 상향 신호를 합산해 하나의 DU 셀에 전달한다.
- **상시 clocked 공격 슬롯**: 공격 UE는 DU보다 먼저 시작해 sample clock을 맞춘다. `persistent_attack` 모드에서 `dl_gate`는 항상 `1.0`으로 고정하고, `ul_gate`만 정상 UE 5/5 준비 전까지 `0.0`으로 두었다가 활성화 시 `1.0`으로 전환한다. 공격 완료 후 `retire` 단계에서 `ul_selector`를 `null_source`로 넘긴 뒤 정상 UE 5/5 회복을 확인하고 공격 UE를 종료한다.

## 실행 명령

### 1. 통합 `same-cell` 실행 (L3 7종 자격 경로)

```bash
./tools/ctl.sh same-cell doctor --profile p1
./tools/ctl.sh same-cell run downlink-imsi --profile p1 --mode control --run-id id-control-1
./tools/ctl.sh same-cell run downlink-imsi --profile p1 --mode emulation --run-id id-emulation-1 --enable
./tools/ctl.sh same-cell campaign l3-live --profile p1 --sets 3 --count 5 --enable
```

- `tools/ctl.sh same-cell`은 공개 L3 7종(`rrc-storm`, `auth-timeout`, `blind-dos`, `uplink-credential-flood`, `downlink-imsi`, `ue-capability`, `nas-counter-desynchronization`)과 `--count 5`만 허용한다. `bin/same-cell-run`은 legacy `uplink` 별칭과 `--count 1..7`도 받지만 공식 자격에는 `./tools/ctl.sh same-cell`만 사용한다. AN fixture 6종과 legacy `uplink-dos` MAC 변조형은 제외한다.
- phase마다 CU 인스턴스와 DU 설정·셀 ID(`cu_restarts=0`, `cell_restarts=1`)는 유지하고 DU·broker·UE 프로세스만 cold-start한다. 종료 시 PID와 시작시각이 일치하는 소유 프로세스만 정리하고 CU·코어·dashboard는 유지한다.

### 2. 정상 UE 풀 단독 실행 (`normal-ue`)

```bash
./tools/ctl.sh normal-ue setup --profile p5
./tools/ctl.sh normal-ue build --profile p5    # 고정 OAI 기준선에서 최초 1회
./tools/ctl.sh normal-ue doctor --profile p5   # 기본 5대
./tools/ctl.sh normal-ue start --profile p5 --count 5
./tools/ctl.sh normal-ue status --profile p5
./tools/ctl.sh normal-ue stop --profile p5
```

- `start`는 수동 `stop` 전까지 supervisor가 5초 재시도 주기로 세션을 유지한다.
- `normal-ue status`는 `oaitun_ue$i`와 고정 기본 TUN 게이트웨이 주소로 `healthy`/`degraded`를 판정하고, `same-cell-run`은 `oaitun_ue${i}p${NORMAL_UE_PDU_SESSION_ID}`와 `$NORMAL_UE_GATEWAY`로 공격 전·후 5/5를 판정한다.

## 빌드와 패치

`bin/normal-ue-build`는 고정 OAI 기준선(`1c2f4d3c2e68181cdef9f426d161163147ad4b77`)에 아래 9개 패치를 적용해 단일 `OAI-normal-ue-w38` 바이너리를 빌드한다.

- RRC/broker 기반 패치(4종): `reproducers/rrc-signaling-storm/patch/{rss-ue-curated,oai-stale-rnti-dci,oai-msg4-ack-rnti,oai-broker-control-gate}.patch`
- 정상 UE 전용 패치(5종): `workloads/normal-ue/patch/{normal-multi-ru,normal-probe-phase,normal-tun-suffix,normal-reconnect-w38,normal-safe-initial-ra}.patch`

`workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`는 정상 UE용이 아니라 5개 공격 모듈(`blind-dos`, `uplink-dos`, `downlink-imsi-extractor`, `ue-capability-hijacking`, `nas-counter-desynchronization`) 빌드에 사용된다.

## 정상 UE 유지(pre/post hold)

- `same-cell campaign`은 공격 전 30초(`SAME_CELL_NORMAL_PRE_HOLD_S`)와 공격 종료·정상 UE 회복(5/5) 뒤 90초(`SAME_CELL_NORMAL_POST_HOLD_S`)를 정상 UE 5대로 유지한다. 탐지기가 경보 `clear`를 보낼 시간을 벌기 위해서다. 단일 `same-cell run`의 기본값은 0(이전 동작)이고, 환경변수로 넘긴 값은 campaign에서도 그대로 우선한다.
- 유지 중 매초 건강 수를 실행 디렉터리의 `normal-hold.tsv`에 남긴다. 두 값을 0으로 두면 이전 동작과 같다.
- 유지 시간만큼 자식 runner의 release 대기(`SAME_CELL_READY_TIMEOUT_S`)를 `120 + 30 + 전 + 후`초로 늘린다. rrc 경로는 `BROKER_NORMAL_PRE/POST_HOLD_S`를 쓰고 브로커 기한은 `240 + 전 + 후`초로 계산한다(캠페인 기본 360초, 유지 0이면 240초). blind 공격자 target 게이트도 `240 + 전 + 후`초로 늘린다.
- 6개 룰의 clear는 RAISE+60초 고정이라 후 유지는 60초 + 여유보다 짧게 두지 않는다(p1 실측 2026-11-19).
- 각 단일 실행(`same-cell run`과 campaign의 각 phase) 직전에 탐지 엔진 입력 기록 회전을 피한다. `SAME_CELL_HOUR_GUARD`(기본 1)가 켜져 있으면 남은 시간이 예상 실행 시간(`전 + 후 + SAME_CELL_HOUR_GUARD_MARGIN_S`, 기본 360초 → 480초) 이하일 때 다음 정각+10초까지 기다린다. 대기 시작·끝은 로그와 `run.json`의 `hour_guard`에 남는다. `SAME_CELL_HOUR_GUARD=0`이면 끈다.
- `normal-hold.tsv`는 `p5-live-e2e`가 실행 디렉터리로 복사하고, self-live same-cell 경로는 공격 runner 증거에 복사해 `evidence_manifest.json`에 넣는다.
- rrc 경로는 UE 프로세스를 `NORMAL_UE_STOP_GAP_S`(전역 기본 3초, `0`이면 동시) 간격으로 하나씩 INT하고, 10초 뒤 TERM, 다시 10초 뒤 KILL로 올린다. `same-cell-run`은 정상 UE 프로세스를 같은 INT→10초→TERM→10초→KILL 사다리로 끝낸다(5 logical UE가 한 프로세스라 프로세스 간격은 없다).
- 유지(pre/post hold)와 순차 종료는 적용 범위가 다르다. 유지 30초·90초는 `same-cell campaign` 전용이고 단일 `same-cell run`은 0이다. 반면 UE를 한꺼번에 끄지 않고 간격을 두고 하나씩 내리는 순차 종료는 전역 기본값이다(`NORMAL_UE_STOP_GAP_S=3`).
- 캠페인 기본값이면 회당 120초가 늘어나므로 42회 캠페인은 유지 구간만 약 84분 길어진다. 정각 회전 회피 대기는 위 자동 대기가 처리한다.

## 운영 계약과 제한

- **가입자 설정**: `0600` 권한, 서로 다른 가입자 `count`명 이상, 설정 파일 내 `RUs`·`cells`·`zmq` 섹션 금지(실행 시 `multi_ru_config.py`가 동적 생성), Git 외부 보관.
- **수렴 및 회복 대기**: p5 cold-start 5/5 수렴에 12.7~62.3초가 걸렸으므로 시작 직후 `degraded`는 최종 실패가 아니다. `auth-timeout`(L3-01-O)은 공격 UE 10대가 0.8초 간격(7.2초 내)으로 진입하고 총 15 UE 회복을 위해 회복 관측 `240초`, runner 종료 대기 `300초`를 사용한다(망 timer 무수정).
- **hot-swap 미승인**: 과거 selector 기반 무재시작 hot-swap은 p5 검증에 실패해 비활성화했다.

## 기술·이력 문서 (2026-11-13 기록)

- [p5 단독 자격 검증](docs/P5-QUALIFICATION-20261113.md)
- [RU-sharing 원인 분석](docs/RU-SHARING-ROOT-CAUSE-20261113.md)
- [RRC storm 공존 실측](docs/RRC-COEXISTENCE-20261113.md)
- [hot-swap 검증 기록](docs/SAME-CELL-HOT-SWAP-20261113.md)
