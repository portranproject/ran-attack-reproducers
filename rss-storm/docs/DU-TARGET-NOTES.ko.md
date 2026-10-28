# DU 포화 목표 — 진행 기록 (2026-10-29)

목표: DU UE context cap 96(기본설정 가정), CU 96 이상에서 DU RRC storm 폭주 재현,
정상 UE 연결 불가.

## 확인된 사실

1. **DU의 96 상수는 코드에 없다.** OCUDU DU의 하드 한도는
   `MAX_NOF_DU_UES_PER_CELL = 2048`(include/ocudu/ran/du_types.h)이고, 실제 셀 한도는
   `min(PUCCH/SRS 자원 수, 2048)`로 계산된다(du_ran_resource_manager_impl.cpp:188).
   "기본 96"이 무엇을 가리키는지는 소스에서 확인하지 못했다. 실측이 필요하다.
2. **한 프로세스 다중 UE 한도 ≈ 10.**
   - N=8: 정상(동기 74, 시도 188)
   - N=10: 정상(동기 47, 시도 234)
   - N=12: 12 UE가 shared RX에 조인한 뒤 `Error, channel timeout`
   - N=20/60/101: RSS 배너 없이 초기화 단계에서 정지
   - 원인 후보: 공유 TX lockstep이 모든 UE의 write를 기다리는 구조에서 UE가 늘면
     정지. `RSS_SHARE_NUE=5`로 바꿔도 N=20은 실패.
3. CU는 `max_nof_ues: 200`으로 설정(≥96), DU ZMQ 직접 포트(4556/4557) 복원.
4. 브로커 경로(프로세스당 1 UE)는 정상. 5 UE까지 검증됨.

## 다음 단계 후보

- A: 10 엔드포인트 브로커 × 프로세스당 10 UE = 100 UE로 DU 포화 시도.
  플로우그래프 확장은 `add_vcc(1)`에 연결 추가로 가능(5 UE까지 검증).
- B: 공유 TX lockstep을 N>10에서도 동작하도록 수정(코드 변경, 리스크 큼).
- C: DU 실제 컨텍스트 한도를 먼저 실측(브로커 5×10=50 UE로 어디서 막히는지 확인).

## 2026-10-29: 브로커 5×10 = 50 UE 실측

- 5 엔드포인트 브로커에 프로세스당 `--num-ues 10`(총 50 UE)을 연결.
- 각 프로세스에서 동기 다수, RRCSetupComplete 0~3건.
- CU admission limit 로그 0 (CU 200 미포화). DU 로그에 용량 거부 없음(정상 UE Context Release만).
- 결론: 50 UE로는 CU/DU 어느 쪽도 한도에 닿지 않는다. 96 실측에는 100 UE가 필요하다.
- 10 엔드포인트 플로우그래프(`tools/multi_ue_10ue.py`)를 준비했다.

## 2026-10-29: 10 엔드포인트 검증

- 10 엔드포인트 플로우그래프(포트 2100~3001, `slow_down_ratio=2`)로:
  - **10 UE(엔드포인트당 1 UE): 정상** (동기 18회).
  - 50 UE(엔드포인트당 5 UE): **전부 channel timeout**. 라우팅 문제가 아니라
    DU 호스트(c6i.2xlarge, 8 vCPU)의 CPU/스레드 포화로 보인다.
- 결론: 96 UE를 채우려면 UE 프로세스를 두 호스트로 분산하거나 인스턴스를 키워야 한다.
  다음 단계: 플로우그래프의 ZMQ 주소를 DU 사설 IP로 바꿔 CU 호스트에서 UE 절반을 실행.

## 2026-10-29: ratio 4·10엔드포인트×5UE — 실패

- `slow_down_ratio=4`로 낮춰도 10 엔드포인트 × 5 UE(50 UE)는 전부 timeout.
- 정상 조합: **5 엔드포인트 × 10 UE(50 UE)**, **10 엔드포인트 × 1 UE(10 UE)**.
- 즉 실패는 UE 수가 아니라 **10 스트림 + 부하**의 조합에서 나온다(5스트림은 50 UE도 정상).
- 다음 경로: 프로세스당 UE 상한(현재 10, N=12에서 shared RX 조인 후 timeout)을 올려
  5 엔드포인트 × 20 UE = 100 UE를 만드는 것이 더 짧다. shared RX 코드 조사 필요.

## 2026-10-29: SHARE_NUE 조정 실패, 프로세스당 한도는 CPU

- `RSS_SHARE_NUE=6`으로 lockstep 배치를 줄여 N=12/20을 시도했으나, N=12는
  `shared RX: 12 UE joined` 후 timeout, N=20은 배너도 못 찍고 초기화 실패.
- 원인은 lockstep 대기만이 아니라 **프로세스당 UE의 CPU 부담**(UE당 PHY/L2 스레드)이다.
  DU 호스트 8 vCPU에서 한 프로세스 10 UE가 실질 상한이다.
- 96 UE 경로: UE 프로세스를 CU 호스트로 분산(빌드 복사)하거나 인스턴스를 키운다.
  다음 단계: DU의 OAI 빌드 디렉터리를 CU 호스트로 복사해 5×10 + 5×10 구성 시도.

## 2026-10-29: 인스턴스 상향 불가 (IAM 정책)

- DU 호스트를 c6i.4xlarge로 올리려 했으나 `ec2:ModifyInstanceAttribute` 권한이 없다
  (UnauthorizedOperation, user p5).
- `./ctl.sh create`로 더 큰 타입을 새로 만드는 방법은 골든 AMI에서 새 인스턴스를
  만들므로 **현재 EBS의 OAI RSS 빌드가 사라진다**. 재구축 비용이 크다.
- 따라서 이 인스턴스 쌍(DU 8 vCPU + CU 4 vCPU)에서는 물리적으로 96 UE를 띄울 수 없다.
  - 확인된 상한: 5 엔드포인트 × 10 UE = 50 UE(정상). 10 엔드포인트 × 5 UE는 실패.
- 96 UE 실측을 위해서는 사용자 결정이 필요하다:
  (a) IAM 정책에 ModifyInstanceAttribute 허용 추가(가장 안전, 비용은 시간당 증가),
  (b) create로 새 세트(큰 타입) 생성 후 OAI RSS 패치 재적용(빌드 재구성 필요),
  (c) 목표를 "DU에 50 UE까지 채우고 거동 관찰"로 축소.

## 2026-10-29: 96 피크 재현과 수락률 상한 실측 (기존 설정 그대로)

이전 세션 기록(`artifacts/archive-du-cell-resource-20261026/ARCHIVE.md`)의 재현:
- 2 UE, 120초, 3,863 셋업(32.2/s), **max_occ 96**, t≥96 0.11초.
- 4 UE: 38.6/s, 96 피크. `-r 0`(거부 백오프 해제): 43.0/s.
- 5 UE `-r 0`: 42.6/s. 6 UE `-r 0`: 38.7/s.
- UE 수를 늘려도 수락률이 43/s에서 포화 → RA/무선 경로 한계이지 UE 수 한계가 아니다.

점유 유지 조건(이전 세션 실측 T_slot 2.14 s): **96/2.14 = 44.9/s** 필요.
현재 최고 43.0/s로 **4% 부족** → 평균 점유 약 92, 96은 순간 접촉(0.11초).
따라서 용량 경로로 "96 유지 + 정상 UE 거부"는 기존 안정 도구로 불가능하다.
남은 레버는 archive의 실험 패치(RA pipelining/evict/harvest)이며, evict는 C-RNTI
수확 커버리지 1/3이라는 한계가 이미 기록돼 있다.
