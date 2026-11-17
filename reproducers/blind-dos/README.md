# Blind DoS 재현 도구

상태: **현재 유효 5G-GUTI 재사용형의 p5 ZMQ G5 검증 완료.** 2026-11-02에
사전 고정한 control→attack 3세트를 모두 첫 시도에 통과했다. 세 attack 모두 피해 UE의
기존 AMF binding 변화, 5회 연속 ping 손실, 동일 UE 프로세스의 재등록·PDU session 재생성,
회복 뒤 ping 20/20 성공을 exact join으로 확인했다. 세 control은 공격 이벤트 0건과
ping 손실 0건이었다.

실행 절차는 [사용 가이드](USAGE-GUIDE.md), 구현과 판정 경계는
[구현·검증 계획](IMPLEMENTATION-PLAN.md), 보존 결과는
[G5 실측 자료](artifacts/p5-zmq-nas-guti-g5-20261102/)를 따른다.

same-cell 경로는 승인 범위가 아니다. 다중 `InitialUEMessage`에서 피해자 IMSI와 현재
S-TMSI가 일치하고 해제되지 않은 mapping 하나를 고르는 oracle은 구현·회귀 검증했지만,
p5에서는 별도 victim·attacker ZMQ 프로세스의 상향 시간축이 어긋나 피해 UE가 RA를
완료하지 못했다. 실측은 [same-cell 한계 기록](artifacts/p5-same-cell-limit-20261116/)을
따른다.

## 무엇을 재현하는가

이 모듈의 Blind DoS는 공격자가 피해자의 SUPI·인증 키를 모르는 상태에서 현재 유효한
임시 식별자를 재사용해 AMF가 가진 피해 UE의 연결 상태를 바꾸고 서비스를 끊는 **단발
표적형 서비스 거부**다. 다수 컨텍스트로 용량을 고갈시키는 RRC signaling storm과 다르다.

현재 구현의 설명형 이름은 **현재 유효 5G-GUTI 재사용형**이다.

1. 피해 UE가 정상 등록·PDU session·ping 서비스를 만든다.
2. runner가 해당 등록 수명의 48-bit 5G-S-TMSI와 AMF Region ID를 랩 oracle로 읽는다.
3. 별도 가입자인 공격 UE가 RRC Msg3/Msg5에 그 5G-S-TMSI를 넣는다.
4. 공격 UE의 plain NAS Registration Request에는 PLMN·AMF Region·AMF Set·AMF Pointer·
   5G-TMSI를 합친 **피해자의 전체 5G-GUTI**를 넣는다.
5. AMF가 피해자의 기존 NG context를 새 접근과 연결하는 상태 변화를 만든 뒤, 공격 UE는
   Authentication Request에 응답하지 않고 종료 상태로 들어간다.

핵심은 5G-S-TMSI만 RRC에 복사하는 것이 아니라 NAS Registration Request에도 전체
5G-GUTI를 넣는 것이다. 이전 RRC-only 구현은 AMF 도달과 상태 변화가 불완전해 G5를
만족하지 못했다. Open5GS의 관련 상태 전이는
[Open5GS issue #4577](https://github.com/open5gs/open5gs/issues/4577)을 1차 근거로 삼았다.

5G-S-TMSI는 gNB가 발급하는 C-RNTI가 아니다. AMF가 할당한 5G-GUTI의
`AMF Set ID(10) + AMF Pointer(6) + 5G-TMSI(32)`인 48-bit 단축 식별자다.
`RRCSetupRequest`는 오른쪽 39-bit Part1, `RRCSetupComplete`는 왼쪽 9-bit Part2를
운반한다. NAS 5G-GUTI에는 이 48 bit에 PLMN과 AMF Region ID가 추가된다.

## 성공 조건

이 도구의 완료 기준은 G5다.

```text
attack 통과 = 인프라 정상
            ∧ 표적 식별자 유지
            ∧ 공격 송신과 기존 피해 context 변화의 exact join
            ∧ 같은 피해 UE의 연속 서비스 손실
            ∧ one-shot 종료 뒤 같은 UE 프로세스의 서비스 회복

campaign 통과 = matched control 정상 ∧ attack 통과를 N/N 세트에서 만족
```

기본 N은 3이며 실행 전에 3~100에서 고정한다. `Known UE`, `Holding NG Context`,
InitialUEMessage 도달, 공격자 자신의 context 정리만으로는 성공이 아니다.

| 게이트 | 필요한 증거 | 현재 상태 |
|---|---|---|
| G3 식별자 도달 | 공격자 commit과 AMF identity reach의 동일 GUTI·NGAP ID 조인 | 통과 |
| G4 표적 상태 변화 | snapshot의 기존 피해 binding 변화가 공격과 exact join | 통과 |
| G5 단발 서비스 중단 | matched control 정상, attack 손실, 같은 PID 회복을 N/N 반복 | **3/3 통과** |
| G6 현실적 입력 획득 | UE·gNB·코어 oracle 없이 현재 식별자를 Uu에서 획득 | 미구현 |
| G7 지속 서비스 거부 | 재접속마다 다시 표적화해 관측창 전체를 차단 | 미구현 |

따라서 현재 허용 주장은 **p5 ZMQ 환경의 oracle 보조 단발 Blind DoS 재현기 성공**이다.
비특권 식별자 획득, 지속 차단, 실 SDR OTA, 상용망 일반화는 주장하지 않는다.

2026-11-17에는 같은 direct 2-cell runner를 실제 F1/N2→TeleRAN→production
detector→dashboard와 함께 실행했다. 대조군 L3-20 경보 0건, attack RAISE 1건을 matched
3/3 반복했으며 공통 판정과 봉인 해시는
[E2E 자격 요약](../../artifacts/p5-live-e2e-five-20261117/)에 있다.

## p5 실측 결과

스택은 OCUDU 26.10 CU/DU, Open5GS, OAI 2026.w38 UE, direct 2-cell ZMQ다.
피해 UE와 공격 UE는 서로 다른 가입자 프로필과 서로 다른 DU cell/endpoint를 쓴다.

| 항목 | control 3회 | attack 3회 |
|---|---:|---:|
| 첫 시도 통과 | 3/3 | 3/3 |
| 공격 이벤트 | 0 | 각 5개 terminal chain |
| 공격 중 연속 ping 손실 | 0 | 각 5회 이상 |
| 기존 피해 context 효과 | 없음 | 3/3 |
| 동일 victim PID 유지 | 3/3 | 3/3 |
| Registration/PDU count | 1→1 | 1→2 |
| 회복 뒤 ping | 각 20/20 | 각 20/20 |
| crash / forced kill | 0 / 0 | 0 / 0 |

회복은 자연 회복 시간을 측정한 값이 아니라 테스트 오케스트레이터가 one-shot 종료 뒤 같은
victim PID에 재등록을 요청한 결과다. OAI의 `blind.recovery_mode=1`은 Registration Reject
뒤 테스트 프로세스를 유지하고, runner는 `SIGUSR1`을 **메인 PID에만** 보낸다. 프로세스
그룹 전체에 보내면 OAI의 TUN 보조 프로세스까지 종료되므로 금지한다.

2-cell ZMQ에서는 한 endpoint를 먼저 종료하면 공통 radio clock이 멈출 수 있다. 따라서
공격 UE는 `authentication_request_withheld` 뒤 추가 공격 이벤트를 내지 않는 idle 상태로
회복 검증이 끝날 때까지 살아 있고, runner가 두 UE를 함께 정리한다.

## 구성

```text
reproducers/blind-dos/
├── patch/blind-ue-w38.patch       # OAI 2026.w38 UE-only 패치
├── bin/blind-build                # clean worktree 확인·패치·빌드
├── bin/blind-run                  # 단일 control/attack 실행·봉인
├── bin/blind-campaign             # matched N세트 실행
├── bin/blind-p5-phase             # direct 2-cell p5 수집기
├── bin/blind-p5-hook              # CU/DU/core 관측 hook
├── analysis/export_labels.py      # 독립 판정기
├── analysis/evidence_manifest.py  # run 무결성 봉인·검증
├── tools/p5_evidence.py           # snapshot·망 이벤트 정규화
├── conf/p5-zmq.conf.example
├── conf/p5-du-2cell-zmq.yaml.example
└── artifacts/                     # 게시 가능한 결과·원문 SHA-256
```

공격은 기본 off다. 공격 실행에는 `blind-run attack -e 1` 또는
`blind-campaign -e 1`이 필요하다. 표적 파일은 runner가 피해 snapshot 뒤 원자적으로
생성하며, 공격 UE는 한 번만 Msg3/NAS chain을 제출한다.

## 안전·증거 경계

- 팀 소유 장비, ZMQ 또는 RF 차폐 환경에서만 사용한다.
- 피해자와 공격자는 서로 다른 팀 가입자다. 동일 SIM 복제는 무효다.
- gNB·코어 소스와 기본 timer/capacity는 수정하지 않는다. 패치는 UE에만 적용한다.
- 전체 식별자 공간 스캔, 추측, 자동 표적 수집은 구현하지 않는다.
- 탐지기 입력에는 oracle·공격자 정답을 넣지 않는다. detector 출력 봉인 뒤 조인한다.
- raw log/pcap은 Git에 넣지 않고 run별 manifest와 원격 SHA-256으로 식별한다.
- OAI 기준 commit은 `6d6782b48484efd935c14e834832032743f9b138`, 최종 패치
  SHA-256은 `5ee58d5b0009431dbddbba0c08f0dbe25f46c7b4d48f06a9accdb88c06b3697a`다.
- same-cell에서 피해 UE TUN은 정상 풀과 충돌하지 않도록 `oaitun_ue1`을 사용한다. 이
  격리는 TUN 충돌을 해결하지만 ZMQ 상향 시간축 문제를 해결하지는 않는다.

다른 변형인 RRC 재수립 식별자 위조형, RRC 재개 식별자 위조형, 무작위·만료 식별자
대조는 이 구현과 합산하지 않는다. 필요하면 별도 시나리오와 라벨 계약으로 추가한다.
