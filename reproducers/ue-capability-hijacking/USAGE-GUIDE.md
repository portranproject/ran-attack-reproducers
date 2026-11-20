# 사용 가이드

## 준비와 빌드

격리된 p5/p1 ZMQ 테스트베드에서만 실행한다. CU·core가 먼저 정상이어야 한다. 직접 `bin/ue-capability-build`를 실행하려면 `/root/OAI-ue-capability-w38`에 OAI 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`의 깨끗한 worktree가 미리 있어야 한다(없으면 `./ctl.sh setup ue-capability --profile <p1|p5>` 사용). `bin/ue-capability-build`는 `patch/ue-capability-injection-w38.patch`와 `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`를 적용한다.

```bash
cd reproducers/ue-capability-hijacking
# (worktree가 이미 있을 때)
OAI=/root/OAI-ue-capability-w38 bin/ue-capability-build
cp conf/p5-zmq.conf.example conf/ue-capability.conf
chmod 600 conf/ue-capability.conf
```

설정의 OAI/UE/DU/CU 경로, SSH key, CU·DU IP를 실제 랩 값과 대조한다. 패치는 기본 OFF이며
runner가 emulation에서만 `OAI_UE_CAPABILITY_INJECT=1`을 넣는다.

## 단일 실행

```bash
UE_CAPABILITY_CONF=conf/ue-capability.conf \
  bin/ue-capability-run control -n cap-control -e 0

UE_CAPABILITY_CONF=conf/ue-capability.conf \
  bin/ue-capability-run emulation -n cap-emulation -e 1
```

runner는 기존 결과를 덮어쓰지 않는다. `runs/<RUN_ID>/verdict.json`의 `passed`와
`pre_security_injection_observed`를 확인한다. 원시 F1 PCAP과 UE/CU 로그는 `runs/`에만
보존하고 Git에는 올리지 않는다.

## 3세트 캠페인

```bash
UE_CAPABILITY_CONF=conf/ue-capability.conf \
  bin/ue-capability-campaign -n cap-matched-3 -e 1
```

각 세트는 control 뒤 emulation 순서다. `cap-matched-3-campaign.json`이 동일 바이너리와
설정 해시, child 봉인, 3/3 합격을 확인한다. 정상 UE 5대 `same-cell` E2E는 `./ctl.sh same-cell run ue-capability --profile <p1|p5> --mode <control|emulation> --run-id <id> [--enable]`을 사용하며, `p1q9-20261119`에서 6/6 통과했다.

## 결과 해석

합격 주장은 “p5 F1에서 보안 전·선행 질의 없는 `UECapabilityInformation` 관측치를
통제 가능하게 재현했다”까지다. 다음 표현은 금지한다.

- 실제 MITM 또는 가짜 기지국 relay에 성공했다.
- UE capability 내용을 변조했다.
- gNB가 downgrade를 수락했다.
- 서비스 저하나 기지국 마비를 만들었다.

이 효과들은 `verdict.json`에서 별도 false 필드로 남는다.
