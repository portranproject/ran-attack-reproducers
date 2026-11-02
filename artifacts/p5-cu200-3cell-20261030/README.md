# P5 CU 200 canonical-A hold32 진단 (2026-10-30)

## 판정 — 진단 전용, 기본 cleanup 성공 기준 아님

이 run은 **공격자가 통제하는 지속 서비스 거부**로 인정하지 않는다. 미완료 컨텍스트
수명을 기본 약 2 s에서 약 32 s로 변경했고 첫 만료 물결 전에 종료했다. canonical-A 경로,
exact ACK 조인, CU 200 도달 가능성, 인공 hold 중 witness 거부는 입증하지만, 공격 유입률이
기본 해제율을 이긴다는 것은 입증하지 않는다.

해당 진단 hold 관측창 안에서 `final-v4`는 다음을 기록했다.

- 수정하지 않은 OCUDU CU는 설정된 `max_nof_ues: 200`을 사용했다.
- 공격 셀 세 개가 canonical A 시도(Msg4 복호, DU HARQ ACK 조인, Msg5 없음)를 생성했다.
- 복원한 CU RRC setup 점유가 정확히 200에 도달했다.
- 별도 네 번째 셀의 정상 UE가 16.31 s 동안 연속 17회 무선 접속을 시도했다.
- 17회 모두 `RRCReject`를 받았고 Msg4, `RRCSetupComplete`, Registration, PDU session,
  channel timeout은 모두 없었다.

이는 **인공 hold 상태의 거부 관측**이며, 기본 약 2 s cleanup에서 공격자가 통제하는
서비스 거부의 증거가 아니다. 공격 시간은 측정된 미완료 컨텍스트 수명 32 s 이하로
제한해 첫 만료 물결 전에 witness 관측창이 끝나게 했다. 더 길었던 V2/V3 진단은 이 경계를
넘었다. witness는 처음에는 거부됐지만 결국 만료되는 슬롯 하나를 확보했다.

## 프로파일에 셀이 네 개인 이유

1. CU 한도는 전역이다. 기본값에서 유도한 DU capacity 96인 셀 두 개는 최대 192개
   컨텍스트만 제공하므로, CU 200에는 공격 셀 세 개가 최소다.
2. 네 번째 셀에는 정상 witness만 둔다. 이로써 CU admission 실패와 동일 무선의 자원
   고갈을 분리한다.
3. 공격자 세 개는 `target_occupancy=0`, `honor_reject=0`으로 실행한다. 실제 상한은 변경하지
   않은 CU의 200 그대로이며, 이 노브들은 새로 열린 모든 슬롯을 계속 경합하게 할 뿐이다.
4. witness 프로세스는 무선과 함께 시작하지만 RRC를 15 s 지연한다. OCUDU ZMQ endpoint의
   재연결 불가 동작을 피하면서 첫 정상 요청이 포화 뒤에 도착하도록 한다.
5. CU guard와 DU cleanup 설정에서 미완료 컨텍스트 수명이 32 s로 측정됐다. capacity 값은
   바꾸지 않았으며, 늘어난 수명은 유한한 처리율의 세 셀 구성에서 결정적인 witness 관측창을
   만든다.

## 최종 run

실행 ID:

- 공격자: `C200V4-A0/A1/A2-20261030T041400Z`
- witness: `C200V4-W3-20261030T041400Z`
- 정상 대조군: `H4V2-C0/C1/C2/C3-20261030T040300Z`

| 작업자 | 시도 | Msg4 | exact canonical A (`du_ack_state=ack`) | RRCReject | Msg5 |
|---|---:|---:|---:|---:|---:|
| A0 | 211 | 70 | 55 | 140 | 0 |
| A1 | 192 | 65 | 60 | 126 | 0 |
| A2 | 186 | 65 | 61 | 120 | 0 |
| W3 정상 witness | 17 | 0 | 0 | 17 | 0 |

worker 네 개 모두 `Error, channel timeout`이 없었다. 모든 run manifest는 로컬 검증을
통과한다. exact canonical 합계는 176이며, 나머지 복호 또는 거부 시도는 `unknown`으로
보존하고 ACK 증거로 승격하지 않는다.

`[04:14:14, 04:14:47)` 구간의 CU 복원 결과:

```text
started 200
peak occupancy 200 at 04:14:25.735702
occupancy >= 200: 15.68 s continuous
admission-limit messages: 405
successful RRC Setup procedures: 0
```

witness의 첫 시도는 run 시작 15.083 s 뒤였고, 17번째이자 마지막 거부는 31.393 s였다.
관측된 전 시도 실패 구간은 16.310 s였다.

## 대조군

공격 부하 전에 최종 바이너리 대조군 worker 네 개가 모두 `RRCSetupComplete` 한 건을
생성했고 channel timeout은 없었다. C3는 추가로 Registration, PDU Session Establishment, TUN 설정까지
완료했다. 이 결과는 hold32 관측창의 거부를 CU admission 탓으로 보기 전에 witness의
PCI/port/core 경로가 정상임을 입증한다.

## 버전과 설정 식별 정보

| 항목 | SHA-256 |
|---|---|
| 최종 OAI UE 바이너리 | `202934f7d34db2f81763b28d43f2d09f5cdac9175d4146a412d778174f3c4c2b` |
| curated UE 패치 | `4b822132a73af5777ffe7116be06460f69dfe74aa1619b1f8c5d1bf97c92b751` |
| `rss-run` | `4bb6f256d0ec41198aa32f558d9048ac568f7c1d9bee5cd17f385cab7c28ae9c` |
| P5 smoke 검증 `rss-cu200` | `1dade7289f864af624d966aa656b4233aeec2d790e579948c0c13fc4ee5928d9` |
| 네 셀 DU 설정 | `5e55ca58e10c4f5ce91a358ba5db8badb3e0798eaf6bceecbaa13ef2997c4e77` |
| CU cap200/guard30s 설정 | `cdf0acec7e0bdcf29e183d7b55f403c62630cbe0ef2bf31493a60bc3049d53fe` |
| CU 로그 slice | `382e99f5c926f153497150047968771eb2d6aa37f92e648e2feaee4e0f25b70d` |

`final-v4/cu-base-before-hold.yaml` (`2ab32f...`)은 복구용 복사본이다. 캡처 뒤 p5 호스트를
해당 CU 설정과 배포된 DU 설정으로 원복했다.

현재 checkout의 wrapper hash는
`fcb258524944f8f0524ec1bca16ce6e19363a922bcd52d71d68bf14671d9997d`다. P5에서 smoke
검증한 복사본과의 차이는 ODU·worker 자식 프로세스 경계에서 run-lock file descriptor를
닫는 것뿐이며, 로컬 계약 테스트 네 개를 통과한다. 무선 인자와 실험 계약은 바뀌지 않았다.

## 재현

`du-4cell-hold32.yaml`로 새 네 셀 ODU를 시작한 뒤 같은 wrapper로 대조군과 공격을 실행한다.

```bash
bin/rss-cu200 control -n CU200-control -d 25
bin/rss-cu200 attack  -n CU200-attack  -d 32
```

배포 환경에 맞춰 `OAI`, `UE_BIN`, `PATCH`, `UE_CFG`, `UECAP`, `LOGDIR`, `ODU_LOG`를
설정한다. wrapper가 worker 네 개를 시작하기 전에 ODU를 한 번 재시작하게 하려면
`CU200_GNB_STOP_CMD`와 `CU200_GNB_RESTART_CMD`를 함께 설정한다.
`CU200_GNB_READY_CMD`는 F1과 네 셀 ODU가 준비됐음을 입증해야 한다.

wrapper는 `HOLD_MS`보다 긴 공격 시간을 거부한다. 이는 정확히 실측한 의미, 즉 컨텍스트
만료 때문에 결과가 확률적으로 바뀌기 전에 witness 관측창이 끝난다는 조건을 보존한다.

## 디렉터리 구성

- `final-v4/runs/` — 공격 worker 세 개와 정상 witness, 각각 봉인된 증거 포함
- `final-v4/control/` — 네 셀 정상 대조군
- `final-v4/cu/` — 변경 불가능한 CU 로그 slice와 캡처 경계
- `final-v4/wrapper-smoke/` — P5에서 실제 실행한 `rss-cu200 control`; 네 셀 모두 RRC 완료
- `cap-only-run/` — 유효한 witness가 없었던 이전 cap-200 입증 자료
- `default-run/` — 기본 타이머 진단 run; 성공 증거 아님
- `runs/C3S*/` — 세 셀 정상 smoke
