# D6F50 — 기본 cleanup canonical A 기전 성립, 서비스 거부 실패

판정: **canonical A의 exact DU ACK 조인은 성립했지만, 정상 UE 서비스 거부에는 실패했다.**

## 고정 조건

- OCUDU gNB 소스는 수정하지 않았다.
- DU 설정 SHA-256은 `173aea40348339a2d3a8583fb881bb0c4c7fb9a0c701b25e518bc996c97cad44`다. hold32·cleanup·RLF override가 없는 기본 프로필이다.
- CU 설정 SHA-256은 `294923bad6395fad9a3823978058f458d763b68cfb057386d8446ac56b94fff9`이고 `max_nof_ues: 200`이다.
- v6 UE 바이너리 SHA-256은 `6b4f254f4bad2104aed32f26cced31446ef9355abb276e155cfb8affcf06f911`이다.
- 실제 실행 runner는 `runner-executed.sh`, SHA-256 `245fe0222abd92c370d80b04caac62be2ee6b4d1c5e2c45b0743db3f6541c2c8`이다. 실행 뒤 로컬에서 바뀐 runner 사본은 증거에서 제거했다.
- 공격은 6개 OAI 프로세스 × 2 logical UE, `msg4_wait=1`, 60초, Msg5 0건이다.

## canonical A exact join

공격자 6개 JSONL의 로컬 UE 번호가 서로 겹치므로, 원문은 그대로 둔 채 파생 파일 `attacker-events-combined.jsonl`에서 process별 UE 번호를 전역 0–11로 매핑했다. 그 한 파일을 label-v1 exporter에 한 번 입력해 ACK tuple 중복 검사를 전체 공격자 범위에서 수행했다.

| label-v1 결과 | 건수 |
|---|---:|
| 전체 attempt | 2,129 |
| Msg4 수신 뒤 Msg5 생략 후보 | 205 |
| current-run DU ACK exact join, `canonical_a=true` | **149** |
| 후보지만 DU ACK 미확인, `canonical_a=null` | 56 |
| Msg4 미도달 | 1,803 |
| RRCReject | 116 |
| 기타 unknown | 5 |

UE 원문에는 `msg4_ack_scheduled` 1,998건이 있고 모두 유효한 nonzero RNTI다. 그러나 canonical A 성공으로 세는 단위는 Msg4 수신·Msg5 생략 후보 중 `(RNTI, frame, slot)`이 UE 전체에서 유일하고 current-run OCUDU FAPI `HARQ: harq_ack=ack` 한 줄과 정확히 일치한 149건뿐이다. `ConRes CE ACKed` 문자열이나 ACK 미확인 56건은 성공으로 승격하지 않았다.

`ground_truth.jsonl`이 이 보수적 판정의 전 행이다. 조인에 사용한 압축 전 DU 로그 SHA-256은 `b41d12ddb7ae9103ccc03e16518f640212ec6af19ab6ef68b7a8c35df707a93f`다.

## 공격률과 기본 cleanup

공격자 Msg3는 2,112건, 60.647초에 `34.824/s`였다. 실제 DU Create/F1은 1,945건, stage-span 기준 `32.071/s`였다. CU에서는 정확히 다음처럼 분기했다.

```text
1,945 F1 arrivals = 1,720 admitted Setup + 225 immediate RRCReject
1,720 admitted Setup = 1,720 default-timeout cleanup
```

관측한 Setup 수명은 median `1,999.424ms`, p90 `1,999.792ms`다. stage-span 기준 비율은 다음과 같다.

- offered Msg3 / cleanup: `1.228×`
- DU provisional Create / cleanup: `1.131×`
- admitted Setup / cleanup: `1.000066×`

즉 제공률과 DU provisional 유입은 cleanup보다 높았지만 초과분은 admission 전에 거절됐다. 실제 수용된 Setup은 cleanup과 평형이었고, 공격자 미완료 Setup 점유 peak는 `84/96`, 96 점유는 0초였다. 공격자 `RRCSetupComplete`와 `InitialUEMessage`는 모두 0건이다.

## 정상 UE 영향

Primary 정상 UE는 공격창 안에 RRC Setup Complete, Registration Accept, PDU Session Accept를 각각 1회 얻었고 ping 194/195에 성공했다. 따라서 이 런은 다음 주장에 **불합격**이다.

- 공격 중 정상 UE 연결 불가
- 30초 지속 포화 또는 반복 거부
- 공격자의 stop으로 서비스가 off→on 전환
- 기지국 마비

공격 종료 뒤 recovery endpoint도 Registration/PDU에는 도달했지만 primary가 이미 서비스를 점유하고 계속 활동했으므로 ping 귀속이 분리되지 않았다. recovery의 `service_ok=false`는 공격 후 서비스 실패 증거가 아니라 **동일 subscriber/TUN 귀속 조건 미충족**이다.

## 증거 범위

- `ue1.jsonl`–`ue6.jsonl`: 변경하지 않은 공격자 UE 원문
- `attacker-events-combined.jsonl`: 전역 tuple 중복 검사를 위한 파생본
- `ground_truth.jsonl`: label-v1 exact ACK 판정
- `odu.log.gz`: current-run DU 원문
- `cu-rrc-events.log.gz`: UTC `18:09:20`–`18:13:20.999999` CU 읽기 전용 slice
- `stats.json`: rate·cleanup·점유·서비스 판정
- `run.json`, `result.json`: orchestration과 runner 판정

결론적으로 D6F50은 **기본 cleanup에서 canonical A 기전이 실제로 149건 성립했다**는 증거다. 같은 조건에서 정상 UE가 서비스에 성공했으므로 denial 성공 자료로는 쓰지 않는다.
