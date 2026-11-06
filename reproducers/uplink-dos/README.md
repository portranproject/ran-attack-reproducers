# Uplink DoS 프로토콜 영향 재현 에뮬레이터

5G uplink overshadowing 이후 피해 UE의 NAS `Service Request` 인증이 깨졌을 때 보이는
망·서비스 영향을 실제 OAI UE→ZMQ→OCUDU DU/CU→Open5GS 경로에서 재현한다. 실제 RF
송신 세기 경쟁은 만들지 않으며 모든 판정에 `rf_overshadowing_observed=false`를 남긴다.

## 구현 방식

OAI 2026.w38 UE가 등록 후 idle 상태에서 최초 `Service Request`를 만들면, 에뮬레이션
실행에 한해 계산이 끝난 NAS MAC의 한 비트를 정확히 한 번 뒤집는다. 가짜 gNB·코어
로그를 주입하지 않는다. 수정되지 않은 OCUDU와 Open5GS가 실제 메시지를 처리하므로
Open5GS의 `NAS MAC verification failed`, UE의 `Service Reject`, 피해 ping 손실이 원문에
남는다. 다음 paging에서는 변조가 소진돼 같은 UE PID가 정상 `Service Request`로 회복한다.

에뮬레이션은 기본적으로 꺼져 있다. `emulation -e 1`을 함께 지정해야만 켜진다.

## 현재 성능

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

## 합격 기준

- control: baseline 5/5, 변조 0회, paging 구간 성공 3/5 이상·연속 손실 2회 이하,
  같은 PID 회복 5회 연속, crash/강제 종료 0
- emulation: baseline 5/5, 변조 정확히 1회, CU의 두 번째 `InitialUEMessage`, AMF의
  `Service request`와 정확한 `NAS MAC verification failed`, UE의 `Service Reject`,
  impact ping 5회 연속 손실, 같은 PID 회복 5회 연속, crash/강제 종료 0
- campaign: 고정 순서 `control → emulation` 3세트의 child 6개가 모두 통과

control에서 허용하는 1~2개 손실은 idle UE paging 연결 시간이며 지속 장애로 보지 않는다.
emulation은 같은 1초 probe에서 5개 전부 실패해야 한다.

## 구성

- `patch/uplink-dos-emulator-w38.patch`: UE-only 단발 NAS MAC 변조
- `bin/uplink-build`: 전용 clean OAI 작업 트리 빌드와 마커 검증
- `bin/uplink-run`: 단일 control/emulation 수집·종료·판정
- `bin/uplink-campaign`: matched 3세트 실행
- `bin/uplink-profile`: CU의 짧은 idle 전환 프로필 적용·해시 원복
- `analysis/export_labels.py`: child 원문 독립 판정
- `analysis/verify_campaign.py`: 6개 child와 원문 SHA-256 집계
- `conf/uplink.conf.example`: p5 ZMQ 예시
- [사용 가이드](USAGE-GUIDE.md): 준비·실행·원복·탐지 입력 절차

## 주장 범위

허용 주장은 **p5 ZMQ에서 uplink DoS의 NAS·서비스 영향을 실제 망 경로로 에뮬레이션했다**는
것이다. 공격자의 RF 송신 우위, 피해 신호 overshadowing, 실 SDR OTA, 상용망 일반화,
비특권 식별자 획득은 입증하지 않았다. 이 도구만으로 RF 원인을 탐지했다고 주장해서는
안 된다.
