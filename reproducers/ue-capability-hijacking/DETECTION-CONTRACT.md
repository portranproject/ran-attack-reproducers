# 탐지 계약

## 입력

탐지 입력은 `observations.jsonl`의 `ue-capability.observation.v1`이다.

```json
{
  "schema": "ue-capability.observation.v1",
  "order": 1,
  "source": "f1ap",
  "direction": "uplink",
  "message": "UECapabilityInformation",
  "gnb_cu_ue_f1ap_id": 7,
  "gnb_du_ue_f1ap_id": 9,
  "realtime_ns": 1790000000000000000,
  "rrc_security_before": "OFF"
}
```

허용 메시지는 `RRCSetupComplete`, `SecurityModeCommand`, `SecurityModeComplete`,
`UECapabilityEnquiry`, `UECapabilityInformation`이다. 모든 행은 같은 F1 UE context에 exact
join되어야 한다.

## 탐지 조건

이 모듈이 만드는 positive는 다음 조건이다.

```text
direction == uplink
message == UECapabilityInformation
rrc_security_before == OFF
같은 context에서 앞선 UECapabilityEnquiry 없음
```

원 논문에 더 가까운 별도 positive는 `rrc_security_before == OFF`인 하향
`UECapabilityEnquiry`다. 현재 모듈은 그 branch를 만들지 않는다. 두 branch를 같은
“완전한 hijack 성공” 라벨로 합치면 안 된다.

## oracle과 라벨

UE 로그 marker를 센 `oracle.json`은 정답 생성에만 사용하며 detector 입력에서 제외한다.

- control: `label=0`, 주입 marker 0, 보안 전 Information 0, 정상 서비스
- emulation: `label=1`, 주입 marker 1, 보안 전 unsolicited Information 관측

`service_effect_observed`는 부가 결과다. `mitm_relay_observed`,
`capability_content_modified`, `capability_downgrade_accepted`는 항상 false로 검증한다.
탐지기의 정탐은 emulation 관측창에서 경보 1개 이상, 오탐은 control 관측창에서 0개로
채점한다. UE oracle은 detector 실행과 threshold 결정이 끝난 뒤에만 결합한다.
