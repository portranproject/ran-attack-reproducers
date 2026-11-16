# Uplink DoS 재현 도구 사용 가이드

## 0. 시나리오 선택

- NAS MAC 실패·서비스 손실을 보려면 기존 `uplink-run`을 사용한다.
- 탐지 룰 L3-21을 검증하려면 `uplink-credential-flood-run`을 사용한다.

두 실행은 합격 기준과 허용 주장이 다르므로 결과를 한 campaign으로 섞지 않는다.

## 1. 전제

- 팀 소유 p5 ZMQ 또는 RF 차폐 환경에서만 사용한다.
- OCUDU DU/CU와 Open5GS 소스는 수정하지 않는다.
- OAI 기준 커밋은 `6d6782b48484efd935c14e834832032743f9b138`이다.
- 한 실행에는 UE 한 대만 사용한다.
- `runs/` 원문은 Git에 올리지 않는다.

## 2. 빌드

기존 OAI 작업 트리를 수정하지 말고 기준 커밋에서 전용 worktree를 만든다.

```bash
git -C /root/OAI worktree add --detach /root/OAI-uplink-dos-w38 \
  6d6782b48484efd935c14e834832032743f9b138
OAI=/root/OAI-uplink-dos-w38 ./bin/uplink-build
```

빌드 결과에는 에뮬레이션 마커가 있어야 하며 기본값은 off다.

## 3. CU idle 프로필

`Service Request`를 만들려면 등록된 UE가 RRC idle로 전환돼야 한다. p5의 7200초
운영값은 실험에 너무 길므로 CU 호스트에서 2초 프로필을 적용한다. 이는 공격 지속시간을
늘리는 변경이 아니라 paging 절차를 짧게 유도하는 준비 설정이다.

```bash
sudo ./bin/uplink-profile apply /root/OCUDU/configs/cu.yaml
```

실행기는 PDU setup 완료 뒤 4초 keepalive를 유지하고, UE의 `RRCRelease`뿐 아니라 CU의
context `Removed`까지 확인한 다음 impact probe를 보낸다. 이 두 게이트는 PDU setup과
release가 서로 경합해 paging이 사라지는 p5 변동을 막는다.

## 4. 설정

```bash
cp conf/uplink.conf.example conf/uplink.conf
chmod 600 conf/uplink.conf
```

`OAI_BIN`, UE 설정, CU 접속 주소·키, TUN과 피해 IP를 실제 랩 값으로 검토한다. 개인키와
가입자 설정은 저장소 밖에 둔다.

L3-21 live 실행에는 무가입 랩 프로필과 CU의 TeleRAN·production detector 경로를 추가한다.

```bash
CREDENTIAL_FLOOD_UE_CFG=/root/oai-invalid-subscriber.conf
CU_PLATFORM_ROOT=/home/ubuntu/portran-e2e-20261113
```

## 5. 실행

먼저 정상 대조를 실행한다.

```bash
UPLINK_CONF=conf/uplink.conf ./bin/uplink-run control -n smoke-control -e 0
```

그다음 명시적으로 에뮬레이션을 켠다.

```bash
UPLINK_CONF=conf/uplink.conf ./bin/uplink-run emulation -n smoke-emulation -e 1
```

최종 반복성 평가는 matched 3세트로 실행한다.

```bash
UPLINK_CONF=conf/uplink.conf ./bin/uplink-campaign \
  -n uplink-protocol-impact-YYYYMMDD -e 1
```

동일 run ID는 덮어쓰지 않는다. 설정 누락, 기존 UE, PDU setup 미완료, release 미완료,
child 실패가 있으면 fail-closed로 중단한다.

### L3-21 실패 플러드 실제 UE 경로

```bash
UPLINK_CONF=conf/uplink.conf ./bin/uplink-credential-flood-run \
  control -n l321-control -e 0
UPLINK_CONF=conf/uplink.conf ./bin/uplink-credential-flood-run \
  attack -n l321-attack -e 1
UPLINK_CONF=conf/uplink.conf ./bin/uplink-credential-flood-campaign \
  -n l321-campaign-YYYYMMDD -e 1
```

통합 컨트롤러에서는 공격 ID `uplink-credential-flood`를 사용한다.

```bash
./ctl.sh run uplink-credential-flood attack l321-smoke --enable
./ctl.sh campaign uplink-credential-flood l321-campaign --enable
./ctl.sh same-cell run uplink-credential-flood -n l321-same --count 5 -- \
  ./reproducers/uplink-dos/bin/uplink-credential-flood-run attack -n l321-same -e 1
```

이 경로는 OAI UE를 실행해 실제 ZMQ→DU/CU→TeleRAN 입력을 production detector에 전달한다.
합성 9/10건 임계 회귀는 별도 `uplink-credential-flood-fixture-run`만 사용한다.

## 6. 결과 읽기

각 run에는 다음 원문과 판정이 생긴다.

- `ue.log`: 변조 마커, Service Reject/Accept, RRC release
- `cu.log`, `amf.log`, `du.log`: 실제 망 처리 원문
- `service.jsonl`: baseline·impact·recovery ping과 피해 PID
- `process.json`: crash·강제 종료 수
- `verdict.json`: 단일 실행 판정
- `<campaign>-campaign.json`: 6개 child 판정과 모든 원문 SHA-256

L3-21 live run에는 다음 파일이 생긴다.

- `observations.jsonl`: 연결별 RRC·NAS 메시지 순서
- `live/telemetry.jsonl`: `hello`·`ue_evt`·`kpm2` 원문
- `live/detector-input.jsonl`: 탐지기가 실제 받은 입력
- `detector.jsonl`: production 탐지 결과
- `verdict.json`: 신호 모양·탐지 결과·주장 경계 판정
- `evidence_manifest.json`: 위 파일의 크기와 SHA-256

탐지기에는 UE 변조 마커나 `verdict.json`을 입력으로 주지 않는다. 먼저 CU·AMF·DU
텔레메트리만으로 탐지 결과를 봉인한 뒤 ground truth와 비교한다. 재현 성공과 탐지 성공은
별도다. 탐지 평가는 탐지율, 오탐률, 탐지 지연으로 채점한다.

## 7. 종료와 원복

캠페인 뒤 DU/CU 프로세스를 중지하고 CU 호스트에서 설정을 원복한다.

```bash
sudo ./bin/uplink-profile restore /root/OCUDU/configs/cu.yaml
```

스크립트는 적용 전 백업 SHA-256과 원복 후 파일을 비교한다. 원복 검증 전에는 다른
공격 실험을 시작하지 않는다.

## 8. 금지 주장

결과의 `rf_overshadowing_observed`는 항상 `false`다. 따라서 다음을 주장하지 않는다.

- 실제 공격자가 더 강한 RF 신호로 피해 UE를 덮었다.
- 실 SDR OTA나 상용망에서 같은 성공률이 보장된다.
- 탐지기가 RF 원인까지 식별했다.
- 한 UE의 10개 RAN 컨텍스트를 물리 UE 10대로 일반화한다.

허용되는 표현은 “uplink DoS 이후의 NAS 인증 실패와 서비스 영향을 실제 프로토콜
경로에서 에뮬레이션했다”와 “수정 UE가 실제 망 경로에서 만든 실패 플러드를 p5
production L3-21이 matched 3/3으로 검출했다”이다.
