# p1 clean-origin L3 7종 same-cell E2E 자격

## 결론

AWS origin snapshot에서 복원한 p1 CU 1대·DU 1대에 저장소와 고정 production 구성요소를
새로 설치한 뒤, 정상 UE 5대와 같은 셀에서 L3 공격 7종의 matched
`control → attack/emulation` 3세트를 실행했다. 총 42회가 모두 통과했다.

- 캠페인: `p1q9-20261119`
- 실행 구간: 2026-11-18 21:29:05~22:33:26 UTC
- 명령: `./ctl.sh same-cell campaign l3-live --profile p1 --campaign-id p1q9-20261119 --sets 3 --count 5 --enable`
- 로컬 검증 소스: `f07fa81`까지의 `codex/same-cell-l3-suite`
- p1 적용 결과 commit: `91c86d6b2dbc1abc5197493d77ed4dd83e4672c2`
- detector: `766f5569d0ddb425c14bf210a31c38ac60eceef9`, binary SHA-256 `14732a800fc348cadf4383a72cbd87baf7d6229fe1df090dbc7ebc25c1d35fe0`
- TeleRAN: `7550153a58a993942303bd3d4a6cd635b664468b`, binary SHA-256 `2f913878d9a3060a951b0adb2b8ef357b4d0daec4a0a601f26a426bf8853e22e`
- dashboard: `01a1a44a12ed7b3b6a1fe7465849d1f3daa41e20`

## 결과

| 룰 | 시나리오 | control | active | 합계 |
|---|---|---:|---:|---:|
| L3-01-V | RRCSetupComplete 미전송형 | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-01-O | 인증 응답 미전송형 | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-20 | 현재 유효 5G-GUTI 재사용형 | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-21 | 무효 자격증명 실패 플러드 | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-24 | 예상 밖 Identity Response | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-14 | 보안 전 UE Capability Information | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |
| L3-06 | 요청되지 않은 SecurityModeReject | 3/3, 경보 0 | 3/3, 경보 1 | 6/6 |

42회 전수 감사에서 다음 조건을 모두 확인했다.

- profile `p1`, TeleRAN `period_ms=100`, 입력 sequence 연속, gap 0, KPM 존재
- 고정 production detector·TeleRAN revision과 binary SHA-256 일치
- production dashboard sender 종료 0, 수락 1건 이상, 거절 0건
- 공격 전과 종료 직전 정상 UE 5대의 TUN·gateway ping 5/5
- `direct_detector_input=false`, `ue_to_ran_path_required=true`, 공격 중 DU 재시작 없음
- 공개 evidence manifest 42개와 L3-21·L3-06 원시 manifest 12개의 파일 크기·SHA-256 일치
- 종료 뒤 공격 UE·broker·DU·campaign 잔존 프로세스 각각 0

각 manifest 자체의 SHA-256은 [MANIFEST.sha256](MANIFEST.sha256)에 고정했다.
가입자 식별자와 원시 로그는 p1의 권한 제한 디렉터리에만 보존하고 Git에는 넣지 않았다.

## 주장 범위

모든 공격 입력은 `UE → ZMQ broker → DU/CU → TeleRAN → production detector → dashboard`
경로를 통과했다. KPM이나 detector 입력을 직접 주입하지 않았다. gNB·CU·코어 소스와 망
timer/capacity도 수정하지 않았다.

L3-01-V·L3-01-O·L3-20·L3-21은 프로토콜 기전을 재현했다. L3-24·L3-14·L3-06은 UE에서
공격 이후의 프로토콜 결과 또는 관측 신호를 만드는 에뮬레이션이다. 따라서 RF
overshadowing, MITM, 실제 NAS counter wrap은 이 결과로 주장하지 않는다. 서비스 거부도
7종 모두 `not_observed`이며 재현 도구 자격 조건으로 강제하지 않았다.

## 이전 p4 보고서와의 관계

2026-11-18 p4 보고서는 구버전 runner에서 일부 공격을 수동 토폴로지와 재시도로 실행한
비교 자료다. 현재 자격의 근거로 사용하지 않았다. 현재 버전은 독립 virtual RU 5개,
사전 clock 공급 공격 슬롯, 공격별 gate/adapter, 피해 UE 식별 oracle, 원자적 정상 UE
건강 상태 봉인과 공개 증거 재봉인을 포함한다. clean-origin 이식성과 전체 7종 통합 자격은
이 p1 캠페인으로 별도 확인했다.

실 SDR 차폐 OTA와 상용망 일반화는 이 자격 범위가 아니다.
