# 보안 전 UE Capability Information 주입

이 모듈은 **UE Capability Hijacking 계열의 탐지 관측치**를 p5 direct 1-cell ZMQ의 실제
UE→PDCP/RLC/MAC→DU→F1→CU 경로로 만든다. OAI UE가 `RRCSetupComplete`를 보낸 직후,
아직 `SecurityModeCommand`를 받기 전에 표준 `UECapabilityInformation`을 한 번 주입한다.
OCUDU·Open5GS 소스와 timer/capacity는 수정하지 않는다.

중요한 범위 구분은 다음과 같다.

- 원 논문의 Capability Hijacking은 가짜 기지국/MITM이 **AS 보안 설정 전**
  `UECapabilityEnquiry`를 중계하고, UE 응답의 category·band·feature를 변조해 정상 망에
  전달하는 공격이다.
- 이 모듈은 MITM과 무선 중계를 만들지 않는다. 현재 p5의 1:1 ZMQ와 정상 OCUDU는 그
  공격 조건을 제공하지 않으므로, 탐지 규칙이 소비하는 **보안 전·선행 질의 없는 상향
  Capability Information**만 재현한다.
- 따라서 합격해도 `mitm_relay_observed=false`, `capability_content_modified=false`,
  `capability_downgrade_accepted=false`다. 이름에 Hijacking 계열을 쓰되 완전한 공격
  성공으로 부르지 않는다.

## 근거와 공개 코드 사용 범위

- [Shaik 등의 Capability Hijacking 연구 원문](https://zenodo.org/records/4671828/files/New%20vulnerabilities%20in%204G%20and%205G%20cellular%20access%20networkprotocols%20%20exposing%20device%20capabilities.pdf)은 LTE 실험에서 보안 전 capability 질의·응답의 평문성과 MITM 변조 영향을 보였다.
- [3GPP TS 38.331 공식 보관소](https://www.3gpp.org/ftp/Specs/archive/38_series/38.331/)는 5G NR의 `UECapabilityEnquiry`와 `UECapabilityInformation` 메시지를 정의한다.
- [OAI 2026.w38의 UE RRC 구현](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/1c2f4d3c2e68181cdef9f426d161163147ad4b77/openair2/RRC/NR_UE/rrc_UE.c)은 표준 Capability Information 인코더와 SRB1 전송 경로를 제공한다. 이 모듈은 그 공개 경로를 재사용한다.
- [팀 탐지 규칙 L3-14](https://github.com/portranproject/detection/blob/766f5569d0ddb425c14bf210a31c38ac60eceef9/src/core/rules/cap_hijack.cpp)는 보안 전 하향 Enquiry와 선행 질의 없는 보안 전 상향 Information을 별도 분기로 본다.

공개된 공격 도구를 복사한 것은 아니다. 조사 범위에서는 원 논문의 MITM 구현 소스가
공개된 것을 확인하지 못했다. 이 저장소가 추가한 부분은 OAI w38용 opt-in one-shot 주입,
기본 OFF 안전장치, F1 PCAP 정규화, CU/DU UE ID exact join, 정상 대조군·3회 캠페인,
oracle 분리와 fail-closed 판정이다.

## 성공 조건

단일 emulation이 통과하려면 모두 만족해야 한다.

1. 같은 `(GNB_DU_UE_F1AP_ID, GNB_CU_UE_F1AP_ID)`에서 `RRCSetupComplete` 뒤
   `UECapabilityInformation`이 상향으로 관측된다.
2. 그 Information보다 앞선 `UECapabilityEnquiry`와 `SecurityModeCommand`가 없다.
3. UE one-shot marker가 정확히 1회이며 F1 PCAP 해시와 원문이 일치한다.
4. UE crash와 강제 종료가 없다.

control은 주입 marker와 보안 전 Capability Information이 없어야 하고 Registration,
PDU Session, ping이 모두 성공해야 한다. 최종 캠페인은 `control → emulation` 3세트가
동일 UE 바이너리·설정·gNB·core 해시로 모두 통과해야 한다. 서비스 저하와 capability
강등 수락은 성공 조건이 아니다.

## 구성

- `patch/ue-capability-injection-w38.patch`: OAI UE opt-in one-shot 패치
- `bin/ue-capability-build`: 고정 commit 확인·패치·ZMQ UE 빌드
- `bin/ue-capability-run`: F1 capture, control/emulation 실행, 증거 봉인
- `bin/ue-capability-campaign`: matched 3세트 실행
- `analysis/normalize_f1.py`: F1 메시지를 탐지 입력 JSONL로 변환
- `analysis/verify_run.py`, `verify_campaign.py`: 주장 경계와 합격 조건 검증
- `DETECTION-CONTRACT.md`: 탐지 입력·oracle·라벨 계약
- `USAGE-GUIDE.md`: 준비·실행·결과 해석

2026-11-11 `p5-ue-capability-final-20261111` matched control→emulation 3세트가 모두
통과했다. control은 정상 capability 교환과 Registration·PDU·ping 3/3, emulation은
보안 전 unsolicited Information 각 1건과 이후 정상 Information 각 1건, 서비스 정상
3/3, crash/forced kill 0이었다. 원문 해시는
[p5 실측 기록](artifacts/p5-zmq-pre-security-information-20261111/)을 따른다.

2026-11-17에는 같은 runner를 실제 F1→TeleRAN→production detector→dashboard와 함께
실행했다. 대조군 L3-14 경보 0건, emulation RAISE 1건을 matched 3/3 반복했으며 공통
판정과 봉인 해시는 [E2E 자격 요약](../../artifacts/p5-live-e2e-five-20261117/)에 있다.
