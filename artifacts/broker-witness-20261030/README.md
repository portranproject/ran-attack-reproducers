# 독립 정상 UE 증인 A/B 검증 (2026-10-30 KST)

## 판정

5개 **별도 OAI UE 프로세스**를 srsRAN GNU Radio 5-UE 브로커에 연결했다. 제어군은
4개 delayed ordinary load UE와 1개 일반 증인 UE, 공격군은 4개 A형 Msg5-skip UE와
1개 일반 증인 UE다. 모든 실행은 팀 소유 AWS ZMQ 격리 환경에서만 수행했다.

| run | mode | 유효성 | 5 UE sync | A형 시도 | 증인 결과 |
|---|---|---:|---:|---:|---|
| `bw-control-r21-1030` | control | valid | 5/5 | 0 | attach 6 s, Registration/PDU 성공, ping 40/264 (loss 84.8485%) |
| `bw-attack-r2-1030` | attack | valid | 5/5 | 8, Msg5 0 | RRCSetupComplete 2회 뒤 Registration/PDU/tunnel/ping 실패 |
| `bw-attack-r3-1030` | attack | valid | 5/5 | 294, Msg5 0 | attach 50 s, Registration/PDU 성공, ping 51/52 (loss 1.92308%) |

`bw-control-r8-1030`은 이전 판정기에서 control load UE의 정상 Msg5를 공격 Msg5로
오인해 `valid=false`가 됐지만, 원자료는 5/5 sync, crash 0, 증인 attach 39 s,
Registration/PDU 성공, ping 102/102였다. 따라서 진단용으로만 보존한다.

결론은 **A형 스톰이 일반 UE 서비스를 비결정적으로 방해할 수 있지만, 현재 프로파일에서
지속적·단조로운 서비스 거부를 보장하지 않는다**는 것이다. 8회 공격 런에서는 서비스가
실패했지만 294회 공격 런에서는 50초 뒤 서비스가 성립했다. 공격 시도 수만으로 서비스
거부를 예측하거나 “항상 불가”라고 주장하면 안 된다.

## 이번에 제거한 실행기 결함

- RSS 옵션을 첫 RRC 호출 때 lazy 등록하던 결함을 수정했다. 이제
  `get_common_options()` 직후 `nr_rss_config_init()`가 `--rss.*`를 소비하므로 브로커
  지연 중 OAI의 unknown-option 종료가 발생하지 않는다.
- 실행기 lock FD 9를 gNB·broker·UE·ping 자식에 상속하지 않게 했다. control 직후
  attack 연속 실행이 실제 Linux 환경에서 lock을 다시 획득했다.
- OAI endpoint 5개를 먼저 기동하고 broker를 뒤에 기동한다.
- 전역 `pkill nr-uesoftmodem`을 제거하고 실행기가 만든 PID/프로세스 그룹만 정리한다.
- control의 load UE 초기 정상 RRC를 공격 시도로 세지 않도록 `load_ue_*`와
  `attacker_*` 결과 필드를 분리했다.

## 재현 조건과 한계

- OAI base: `1c2f4d3c2e68181cdef9f426d161163147ad4b77`
- OCUDU base: `e0db566aac6e6376ddd60e83c84f58698fcc4d70`
- DU 실험 프로파일: `nof_cell_sr_res: 1`(부팅 로그상 12 UE 상한), PRACH 64,
  broker ports 2000/2001. CU `max_nof_ues: 200`.
- 이는 기본 설정이 아니라 **통제된 saturation profile**이다.
- 5-UE broker는 `sync=0` 시작 경합이 자주 발생한다. 유효 실행만 효과 판정에 사용했다.
- 관측 종료 시 Qt/GNU Radio 자식이 간헐적으로 segfault 메시지를 냈다. 관측 창 중
  broker 생존과 UE crash 0은 확인했지만 teardown 결함은 남아 있다.
- control 자체도 ping 품질이 0%~84.8% 손실로 변동했다. ZMQ broker 결과를 OTA RF
  성능으로 일반화할 수 없다.
- 차폐 OTA, 팀 분리형 CU/DU의 실 SDR interop, F1 수준 라벨, 대응 폐루프는 아직
  검증하지 않았다.

## 보존 정책

원문은 DU의 `/root/rss-broker-runs-curated/<run_id>`에만 보존했다. UE 로그와 JSONL에는
가입자·NAS·IP 식별자가 포함될 수 있으므로 저장소에는 복사하지 않았다. 이 디렉토리의
`SHA256SUMS.remote`로 원문의 동일성만 확인한다.

### 빌드/도구 SHA-256

```text
c511b43a73d051ad5e87992bf80017405829e43bd04c345d7c607bee4e21233f  nr-uesoftmodem
2a843d45ea62b458679f02522a2a57387c9e0b74308db719de9d4171c7e31baa  rss-ue-curated.patch
db77463343bc0d863a6d3ab3b02adaf43d81b7dbd4e85bc8bd2057d2c1bdacc1  rss-broker-witness
fdfa1fc443ab402555af87a172484b70aabcae4214a7d58c459d1300489e38cf  multi_ue_5ue.py
24395619907e87f37607f9d5cd71669b8f9537e70d29874e74ab36ab5b36e250  du.yaml (실험 중)
7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3  du.yaml (원복 백업)
```
