# 설계

## 메시지 경계

정상 NR 절차의 핵심 순서는 다음과 같다.

```text
UE → CU  RRCSetupComplete
CU → UE  SecurityModeCommand
UE → CU  SecurityModeComplete
CU → UE  UECapabilityEnquiry
UE → CU  UECapabilityInformation
```

원 논문의 공격은 MITM 기지국이 보안 전 Enquiry를 보내고 응답 내용을 바꿔 전달한다. 현재
p5 direct ZMQ에는 두 무선 leg와 MITM relay가 없고 정상 OCUDU도 capability를 보안 뒤에
질의한다. 그래서 이 구현은 detector가 볼 수 있는 이상 순서 하나를 가장 작은 변경으로 만든다.

```text
UE → CU  RRCSetupComplete
UE → CU  UECapabilityInformation  # opt-in one-shot, security OFF, 선행 Enquiry 없음
CU → UE  SecurityModeCommand      # 이후 절차는 망 구현 결과로 관측
```

패치는 기존 OAI `nr_rrc_ue_process_ueCapabilityEnquiry()` 인코더를 합성된 NR RAT request로
호출한다. payload는 해당 UE의 원래 capability profile이므로 **내용 변조는 하지 않는다**.
환경변수 `OAI_UE_CAPABILITY_INJECT=1`일 때만 UE instance당 한 번 동작하고 기본값은 OFF다.

## 증거 경계

CU 호스트에서 F1 SCTP 38472를 PCAP으로 수집하고 tshark로 다섯 RRC 메시지와 F1 UE ID를
추출한다. 정규화기는 Capability Information이 있는 단 하나의 context를 선택하고 모든
관측을 같은 CU/DU UE ID로 묶는다. UE marker는 `oracle.json`에 두며 detector 입력인
`observations.jsonl`과 섞지 않는다.

`rrc_security_before`는 같은 context에서 앞서 관측된 `SecurityModeComplete`를 기준으로
OFF/ON을 계산한다. 이는 메시지 순서 특징이며 암호 키나 payload 정답을 입력에 넣지 않는다.

## 완료와 비완료

완료 대상은 보안 전 unsolicited Information의 실제 F1 관측, 정상 대조, 반복성, 증거
봉인이다. MITM RF relay, Enquiry 자체의 가짜 기지국 송신, payload downgrade, 정상 망의
downgrade 수락과 서비스 성능 저하는 이 구현의 비완료 항목이다. 이 항목은 차폐 OTA에서
두 무선 leg와 relay가 준비되거나, 승인된 네트워크 측 시험 훅이 생길 때 별도 모듈/브랜치로
확장한다.
