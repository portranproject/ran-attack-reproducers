# p5 종합 플랫폼 엔드투엔드 검증 (2026-11-13)

## 범위

- p5 기본 CU 1대와 DU 1대만 사용했다. 과거 `rss-smooth-lane` 인스턴스 7대는 시작하지 않았다.
- 재현기·탐지기·텔레메트리·대시보드 4개 저장소를 `/home/ubuntu/portran-e2e-20261113/`에 고정 리비전으로 배치했다.
- credential, 가입자 키, 원시 NAS 식별자와 공인 endpoint는 이 기록과 Git에 포함하지 않는다.
- 실제 프로토콜 경로는 정상 UE 대조군으로 검증했다. 기존 6개 공격의 live 캠페인을 다시 실행한 결과가 아니다.

## 고정 리비전

| 구성 | 리비전 |
|---|---|
| ran-attack-reproducers | `2be52203955a95f9b849c6514d645b01eb686a71` |
| detection | `a34b358e585e24aa91b1586da022ad14ef98d3e0` |
| telemetry | `7550153a58a993942303bd3d4a6cd635b664468b` |
| dashboard | `01a1a44a12ed7b3b6a1fe7465849d1f3daa41e20` |

## 빌드·회귀

- 탐지기 Release 빌드와 `ctest`: `755/755` 통과.
- 대시보드 AWS compose의 InfluxDB·collector·nginx ingest·Grafana 기동 후 pytest: `253/253` 통과.
- 재현 플랫폼 manifest 13개 검증과 공통 테스트: CU `14/14`, DU `14/14` 통과.
- 텔레메트리: pinned ASN.1 생성, read-only BPF 검사와 `build/portran` 링크 통과. 별도 단위 테스트 target은 없다.
- p5 profile doctor는 detector·config·telemetry 실행 파일과 100 ms 계약을 모두 통과했다.

빌드 산출물 SHA-256:

- detector: `f50ce9bd8149663c7a3f3fddc88d46fbd8edf204649f7d8c72c7414bbb97e067`
- telemetry: `048f7aa182c4cacb83459b260019bd8128cb6a26ea069a3eef69cfb8b3a4916c`

## 실제 정상 UE 종단 경로

`OAI UE → OCUDU DU/CU → F1/N2 eBPF telemetry → production detector`

- CU↔AMF, DU↔CU F1, DU↔RIC E2 연결 성공.
- UE 등록·PDU session과 `oaitun_ue1` 할당 성공.
- UE→코어 gateway ping `5/5`, 손실 `0%`.
- 100 ms 원문은 `hello 1`, `f1_evt 1`, `kpm2 902`, `ue_evt 19`, 총 `923`줄이다.
- `seq=1..923` 연속, session 1개, `gap=0`이며 KPM에는 non-zero 값이 있었다.
- RRCSetupRequest/Setup/SetupComplete, NAS 인증·보안·등록, UE context setup 메시지를 실제 경로에서 관측했다.
- 정상 대조군의 production detector 공격 경보는 `0`건이었다.
- 원문 SHA-256: `ecd44d4c0b883b6b7764d4360052449bd846d9a2f85ccf7f1ca11d6090c321de`.

## 재현기→production detector 회귀

- 새 탐지 입력 에뮬레이션 7종(L3-06, AN-01, AN-06a, AN-02, AN-04, AN-07, AN-08)의 matched control→emulation을 각각 3회 실행했다.
- 총 7개 캠페인·42개 child run이 모두 통과했다. control은 예상 룰 경보 0건, emulation은 예상 룰 RAISE를 확인했다.
- L3-21 무효·위조 자격증명 실패 플러드도 별도 matched 3/3을 통과했다. 각 emulation은 2초 내 실패 5건과 branch 1 RAISE 1건을 만들었다.
- `verify`, `replay`, `report` 공통 명령을 AN-01 봉인 run에 다시 적용해 모두 통과했다.

이 결과는 detector-input emulation의 종단 회귀다. `live_protocol_path_observed`, `rf_cause_observed`, `service_denial_observed`를 참으로 바꾸는 근거가 아니다.

## 탐지기→대시보드 종단 경로

`production detector → dashboard_sender → 자체 서명 TLS nginx → collector → InfluxDB → Grafana`

- AN-01 출력 `alert 1 + evidence 16`을 HTTPS로 전송했고 `accepted=17`, `rejected=0`이었다.
- 실제 p5 정상 원문을 detector input recorder로 다시 봉인한 뒤 전송기가 3초 KPM으로 집계했다. `accepted=33`, `rejected=0`이었다.
- 최종 raw recording은 `alert 1`, `evidence 16`, `hello 1`, `f1_evt 1`, `kpm2 31`, 총 `50`줄이다.
- InfluxDB에서 다섯 measurement를 확인했고 Grafana provisioning 쿼리 두 세트도 통과했다.
- raw recording SHA-256: `2ec3510d8f021be499e64978923532e4e96544f15592f85c80462be2215529df`.

대시보드의 현재 AWS source 계약이 `p4`로 고정돼 있어 p5 실험도 화면 표시를 위해 `env=p4`로 보냈다. 실행의 p5 정답과 run metadata는 공통 report에서 구분한다.

## 판정과 남은 범위

4개 저장소의 빌드·기본 회귀와 실제 정상 프로토콜의 텔레메트리→탐지, 고정 공격 입력의 탐지→대시보드 경로는 통과했다. p5에서 플랫폼 통합을 계속 개발할 수 있는 기준선으로 사용 가능하다.

이번 실행은 기존 6개 프로토콜 공격을 새 바이너리로 다시 빌드하거나 live attack 3/3을 재수행하지 않았다. 해당 성능 주장은 각 모듈의 기존 봉인 artifact를 유지한다. 또한 OTA·RF 원인과 서비스 거부는 검증하지 않았다.
