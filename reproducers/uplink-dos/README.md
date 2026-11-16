# Uplink DoS 재현 도구

상향 DoS의 서로 다른 관측면 두 가지를 분리한다. 실제 RF 송신 세기 경쟁은 만들지 않으며
모든 판정에 `rf_overshadowing_observed=false`를 남긴다.

| 시나리오 | 구현 | 용도 |
|---|---|---|
| 단발 NAS 무결성 손상형 | 실제 OAI UE→ZMQ→OCUDU→Open5GS 경로에서 최초 `Service Request` MAC 1비트 변조 | NAS MAC 실패와 서비스 손실·회복 관측 |
| 무효·위조 자격증명 실패 플러드형 | 수정 OAI UE가 실제 ZMQ→DU/CU 경로에서 10개 연결의 `RegistrationRequest→RegistrationReject` 생성 | 탐지 룰 L3-21 branch 1 검증 |

두 시나리오는 같은 공격명이지만 신호가 다르다. 단발 MAC 손상형은 AMF가 조용히 폐기해
L3-21이 세는 Reject 메시지가 0건이다. 실패 플러드형은 10초 안 서로 다른 실패 연결 10개를
만들어 production 기본 임계값을 직접 만족한다.

## 구현 방식

OAI 2026.w38 UE가 등록 후 idle 상태에서 최초 `Service Request`를 만들면, 에뮬레이션
실행에 한해 계산이 끝난 NAS MAC의 한 비트를 정확히 한 번 뒤집는다. 가짜 gNB·코어
로그를 주입하지 않는다. 수정되지 않은 OCUDU와 Open5GS가 실제 메시지를 처리하므로
Open5GS의 `NAS MAC verification failed`, UE의 `Service Reject`, 피해 ping 손실이 원문에
남는다. 다음 paging에서는 변조가 소진돼 같은 UE PID가 정상 `Service Request`로 회복한다.

에뮬레이션은 기본적으로 꺼져 있다. `emulation -e 1`을 함께 지정해야만 켜진다.

## 현재 성능: 단발 NAS 무결성 손상형

2026-11-05 p5 direct 1-cell ZMQ의
`p5-uplink-final-v5-20261105` matched control→emulation 3세트가 모두 통과했다.

| 항목 | control 3회 | emulation 3회 |
|---|---:|---:|
| baseline ping | 모두 5/5 | 모두 5/5 |
| MAC 변조 | 모두 0회 | 모두 정확히 1회 |
| impact ping 성공 | 5/5, 4/5, 3/5 | 모두 0/5 |
| Open5GS MAC 실패 | 0회 | 각 실행에서 확인 |
| 같은 PID 회복 | 모두 5회 연속 성공 | 모두 5회 연속 성공 |
| crash/강제 종료 | 0/0 | 0/0 |

게시용 결과와 원격 원문 해시는
[p5 ZMQ 실측](artifacts/p5-zmq-protocol-impact-20261105/)에 있다.

## 현재 성능: 무효·위조 자격증명 실패 플러드형

2026-11-11 p5에서 무가입 랩 식별자로 실제 F1 `RegistrationReject` 5건을 2.260초 안에
관측했다. 이 PCAP의 SHA-256은
`f3222e81d0cef1904159e724ead95e831a8aefa847761069e8cbdbcc264609e6`이다. 다만 OAI의
반복 RRC 재접속이 PHY에서 불안정해 이 live 경로는 반복 캠페인 기능으로 승인하지 않았다.

과거에는 같은 메시지 순서의 탐지 입력 에뮬레이션만 3/3 검증했다. 현재 runner는 이를
회귀 fixture로 강등하고, 수정 OAI UE가 10개의 새 RAN 컨텍스트를 만드는 실제
`UE→ZMQ→DU/CU→TeleRAN→production detector` 경로를 사용한다. 최신 production 기준은
`n_fail_th=10`, `fail_accept_wait_ms=3000`이다. 2026-11-16 정상 UE 5대 same-cell
control→attack 3세트가 모두 통과했고 attack은 각각 L3-21 경보 1회, 정상 health 5/5였다.
결과는 [L3-21 live same-cell 실측](artifacts/p5-l3-21-live-same-cell-20261116/)에 있다.

## 단발 NAS 무결성 손상형 합격 기준

- control: baseline 5/5, 변조 0회, paging 구간 성공 3/5 이상·연속 손실 2회 이하,
  같은 PID 회복 5회 연속, crash/강제 종료 0
- emulation: baseline 5/5, 변조 정확히 1회, CU의 두 번째 `InitialUEMessage`, AMF의
  `Service request`와 정확한 `NAS MAC verification failed`, UE의 `Service Reject`,
  impact ping 5회 연속 손실, 같은 PID 회복 5회 연속, crash/강제 종료 0
- campaign: 고정 순서 `control → emulation` 3세트의 child 6개가 모두 통과

control에서 허용하는 1~2개 손실은 idle UE paging 연결 시간이며 지속 장애로 보지 않는다.
emulation은 같은 1초 probe에서 5개 전부 실패해야 한다.

## 무효·위조 자격증명 실패 플러드형 합격 기준

- control: 완전한 RRC→등록 거절 연결 1개, 수락 0, L3-21 경보 0
- attack: 완전한 연결 10개, `RegistrationRequest`·`RegistrationReject` 각 10건,
  거절 간격 10초 미만, 수락 0
- 탐지: production 기본 설정에서 L3-21 `branch=1` RAISE 정확히 1회
- campaign: 고정 순서 `control → attack` 3세트의 child 6개가 모두 통과
- 모든 결과: `live_protocol_path_observed=true`, `rf_overshadowing_observed=false`

## 구성

- `patch/uplink-dos-emulator-w38.patch`: UE-only 단발 NAS MAC 변조
- `bin/uplink-build`: 전용 clean OAI 작업 트리 빌드와 마커 검증
- `bin/uplink-run`: 단일 control/emulation 수집·종료·판정
- `bin/uplink-campaign`: matched 3세트 실행
- `bin/uplink-credential-flood-run`: L3-21 실제 UE·TeleRAN·탐지 엔진 실행
- `bin/uplink-credential-flood-fixture-run`: 9/10건 탐지 임계 회귀 fixture
- `bin/uplink-credential-flood-campaign`: L3-21 matched 3세트 실행
- `bin/uplink-profile`: CU의 짧은 idle 전환 프로필 적용·해시 원복
- `analysis/export_labels.py`: child 원문 독립 판정
- `analysis/verify_campaign.py`: 6개 child와 원문 SHA-256 집계
- `analysis/normalize_registration_failures.py`: 실제 F1 PCAP TSV를 같은 탐지 입력으로 변환
- `conf/uplink.conf.example`: p5 ZMQ 예시
- [사용 가이드](USAGE-GUIDE.md): 준비·실행·원복·탐지 입력 절차

## 주장 범위

단발형에는 **p5 ZMQ에서 uplink DoS의 NAS·서비스 영향을 실제 망 경로로 에뮬레이션했다**고
말할 수 있다. 실패 플러드형은 **수정 UE가 실제 망 경로에서 L3-21 입력을 만들고 production
탐지기가 matched 3/3으로 검출했다**고 말할 수 있다. 이는 한 UE가 만든 10개 RAN
컨텍스트이며 10대 UE나 RF 송신 우위를 뜻하지 않는다. 실 SDR OTA와 상용망 일반화는 미검증이다.
