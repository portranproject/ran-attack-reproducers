# 비정상 Identity Response·식별자 노출 (L3-24)

OAI UE가 망의 선행 `Identity Request` 없이 첫 `Authentication Request` 응답으로 평문 `Identity Response(SUCI)`를 한 번 제출해, Downlink IMSI Extractor 계열이 만드는 프로토콜 결과 신호를 재현하는 에뮬레이션 모듈이다.

| 항목 | 값 |
|---|---|
| 룰 ID | `L3-24` |
| `reproducer.json` id | `downlink-identifier-exposure` |
| `tools/ctl.sh` ID / 별칭 | `downlink-imsi` (`downlink-imsi-extractor`, `downlink-identifier-exposure`, `downlink`) |
| 재현 수준 (`reproduction_level`) | `protocol-result-emulation` |
| active 모드 (`active_mode`) | `emulation` |
| 자격 현황 | `p1` same-cell 6/6 통과 (`p1q9-20261119`), `p5` E2E 6/6 통과, `OTA` pending |

> 격리된 팀 소유 테스트베드 전용이다. `-e 1` 또는 `--enable` 없이는 정상 `Authentication Response`를 제출한다.

## 동작 요약

```text
OAI UE                       OCUDU DU/CU                 Open5GS
   │ RRCSetupComplete + Registration Request │              │
   │────────────────────────────────────────>│ InitialUEMessage
   │                                         │─────────────>│
   │                    Authentication Request              │
   │<────────────────────────────────────────│<─────────────│
   │ (control)   Authentication Response     │              │
   │ (emulation) Identity Response(SUCI) 1회 │ (선행 Identity Request 없음)
```

- **control** (`-e 0`): 정상 `Authentication Response`와 Registration·PDU·ping을 수행하며 `Identity Response`는 0건이다.
- **emulation** (`-e 1`): 첫 `Authentication Request`에서 `generateIdentityResponse(..., FGS_MOBILE_IDENTITY_SUCI)`를 1회 호출한다. protection scheme 0(null-scheme)일 때만 oracle 가입자 fingerprint 일치 여부를 별도 판정한다.
- **OAI UE-only 패치**: 기준 커밋 `6d6782b48484efd935c14e834832032743f9b138`에 `bin/downlink-imsi-build`가 2개 패치(`patch/downlink-imsi-ue-w38.patch`, `../../workloads/normal-ue/patch/same-cell-ra-gate-w38.patch`)를 적용한다. OCUDU·Open5GS 소스와 timer/capacity는 수정하지 않는다.

## 실행 방법

### 통합 컨트롤러 (`tools/ctl.sh`)

```bash
./tools/ctl.sh setup downlink-imsi --profile p1
./tools/ctl.sh doctor downlink-imsi --profile p1

# 단발 및 matched 3세트 캠페인 (p5 direct)
./tools/ctl.sh run downlink-imsi control dl-ctrl-01 --profile p5
./tools/ctl.sh run downlink-imsi emulation dl-emu-01 --profile p5 --enable
./tools/ctl.sh campaign downlink-imsi dl-camp-01 --profile p5 --enable

# 정상 UE 5대 same-cell E2E 실행 (p1/p5)
./tools/ctl.sh same-cell run downlink-imsi --profile p1 --mode control --run-id sc-dl-ctrl-1
./tools/ctl.sh same-cell run downlink-imsi --profile p1 --mode emulation --run-id sc-dl-emu-1 --enable
```

### 직접 실행 (`bin/`)

`tools/ctl.sh`는 `conf/p5-zmq.conf.example`을 복사한 `conf/downlink-imsi.conf`(`DOWNLINK_IMSI_CONF`)를 사용한다(`conf/downlink-imsi.conf.example`도 존재한다). **주의:** `conf/p5-zmq.conf.example`의 `UECAP` 경로가 `/root/OAI-uplink-dos-w38/...`로 적혀 있으므로 로컬 `conf/downlink-imsi.conf` 복사 후 `/root/OAI-downlink-imsi-w38/...`로 맞춰야 한다.

```bash
OAI=/root/OAI-downlink-imsi-w38 bin/downlink-imsi-build
DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf bin/downlink-imsi-run control -n dl-ctrl -e 0
DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf bin/downlink-imsi-run emulation -n dl-emu -e 1
DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf bin/downlink-imsi-campaign -n dl-camp -e 1
```

## 합격 기준

- **control**: 정상 인증·등록·PDU·ping 성공, 예상하지 않은 `Identity Response` 0건, `L3-24` 경보 0건.
- **emulation**: 동일 RAN/AMF UE NGAP ID에서 선행 `Identity Request` 없이 `Authentication Request → Identity Response(SUCI)` 1건 exact join, `verdict.json`에서 `passed=true`, `unexpected_identity_response_observed=true`, `suci_observed=true`, `dl_overshadowing_observed=false`, TeleRAN 100 ms / gap 0 / KPM 존재, production `L3-24` RAISE 1건, dashboard 수락 ≥ 1건·거절 0건, same-cell 정상 UE 5대 전후 ping 5/5.
- **campaign**: 고정 순서 `control → emulation` 3세트 모두 통과.

## 한계 및 금지 주장

- **RF overshadowing 미관측**: 실제 하향 RF 신호 경쟁을 만들지 않았으며 `dl_overshadowing_observed`는 항상 `false`다.
- **SUCI 보호 우회 아님**: null-scheme(scheme 0) 랩 프로필에서만 MSIN 기반 fingerprint를 대조하며 Profile A/B 복호화는 주장하지 않는다.
- **서비스 거부 미관측·OTA 미검증**: `service_denial`은 `not_observed`이며 실 SDR OTA(하향 waveform injector 필요)와 상용망 일반화는 검증하지 않았다.

## 관련 문서 및 근거

- 동반 문서: [설계](DESIGN.md), [사용 가이드](USAGE-GUIDE.md), [탐지 계약](DETECTION-CONTRACT.md), [계보](PROVENANCE.md)
- p1 same-cell 42/42 자격: [p1 clean-origin L3 7종 E2E](../../artifacts/p1-clean-origin-live-e2e-20261119/README.md)
- p5 E2E 자격: [p5 L3 5종 E2E](../../artifacts/p5-live-e2e-five-20261117/README.md)
- 모듈 세부 증거: [p5 1-cell 3/3 실측](artifacts/p5-zmq-identity-response-20261111/README.md)
