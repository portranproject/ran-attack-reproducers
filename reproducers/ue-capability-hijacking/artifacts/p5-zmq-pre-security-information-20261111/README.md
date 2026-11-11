# p5 보안 전 Capability Information 실측

2026-11-11 p5 CU 1대·DU 1대의 direct 1-cell ZMQ에서
`p5-ue-capability-final-20261111` matched control→emulation 3세트를 실행했다.

## 결과

- 캠페인 판정: 3/3 통과
- control 3회: 각 실행에서
  `RRCSetupComplete → SecurityModeCommand → SecurityModeComplete → UECapabilityEnquiry → UECapabilityInformation`
  순서가 같은 F1 UE ID pair로 관측됐다.
- emulation 3회: 각 실행에서
  `RRCSetupComplete → UECapabilityInformation → SecurityModeCommand → SecurityModeComplete → UECapabilityEnquiry → UECapabilityInformation`
  순서가 관측됐다. 첫 Information은 security OFF·선행 Enquiry 없음이고 두 번째는 정상
  security ON 응답이다.
- 모든 control/emulation에서 Registration·PDU Session·ping이 성공했고 crash·forced kill은
  0이었다.
- UE one-shot marker는 control 0회, emulation 정확히 1회였다.

matched 항목은 OAI commit, UE patch·binary, UE/gNB/core config SHA-256이다.

```text
source_commit       6d6782b48484efd935c14e834832032743f9b138
ue_patch_sha256     ef50149a8313acb5ae2b32febac7f19e4506552cca5be2eccd5d2e3ed68f7707
ue_binary_sha256    755c76b43637383e1aa9b2a080213799dc256d6dad57f63ac6a68df58228f079
gnb_config_sha256   35ea900e8253013aeec398952d4a6c3c1f407880018d940270b53497700e0b17
core_config_sha256  3fc960e9fc6d6551948699610c7ea625cdc0dfe48d08c0adb2a46d65180cc158
ue_config_sha256    1476a2ddae912dadec8cc04a786cb31163e01403a1153719a1344127486aa8fb
```

원시 PCAP·UE/CU 로그·child manifest는 p5 DU의
`/root/ue-capability-tool/runs/p5-ue-capability-final-20261111-*`에 로컬 보존한다. 이
디렉터리에는 검토한 campaign 결과와 원격 원문의 SHA-256만 게시한다.

## 허용 주장

**p5 F1에서 UE Capability Hijacking 계열 탐지 입력인 보안 전·선행 질의 없는 상향
`UECapabilityInformation`을 통제 가능한 one-shot으로 재현했다.**

실제 MITM relay, capability payload 변조, gNB의 downgrade 수락, 서비스 저하, 실 SDR
OTA는 관측하지 않았다. 캠페인도 해당 필드를 모두 false로 고정·검증한다. 팀 탐지 엔진의
정탐·오탐률은 이 실행에서 평가하지 않았다.
