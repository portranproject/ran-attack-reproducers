# 봉인 증거의 과거 명칭표

현재 문서는 3GPP 메시지명에 기반한 설명형 이름을 사용한다. 아래 과거 이름은 3GPP
공식 공격 분류가 아니며, 체크섬으로 봉인된 실험 기록·run ID·JSON 필드의 재현성을
지키기 위해서만 남아 있다.

| 봉인 증거의 과거 이름 | 현재 설명형 이름 |
|---|---|
| `A`, `A형`, `정규 A`, `A-type` | RRCSetupComplete 미전송형 |
| `canonical A`, `canonical_a*` | DU ACK 확인 RRCSetupComplete 미전송형 |
| `A_early`, `A-early`, `canonical_msg3*` | RRCSetupRequest 후 중단형 |
| `A_no_ack`, `A-no-ack` | RRCSetup HARQ-ACK 억제형 |
| `A-NAS` | NAS Authentication Response 미전송형 |
| `B형` | UE 재시작 반복형 |
| `B-churn` | 비활성 타이머 기반 재연결 반복형 |
| `C형` | RRCResume 반복형 |
| `D형` | PRACH 반복형 또는 해당 기록에 명시된 RRCSetupRequest 이전 중단형 |
| `Mode A`, `모드 A` | 기본 cleanup 프로필 |
| `Mode B`, `모드 B` | 용량 12·보유 7초 진단 프로필 |

`ACK A/B`처럼 A/B가 두 공격 유형이 아니라 실험군 비교를 뜻하는 기록도 있다. 현재
문서에서는 이를 `ACK-on/off 비교` 또는 `attack-on/off 비교`로 풀어 쓴다.

다음 항목은 이름을 바꾸지 않는다.

- `scenario="A"`, `scenario="A_early"`, `scenario="A_no_ack"`를 포함한 과거 `run.json`
- `canonical_a*`, `canonical_msg3*` label v1 필드
- run ID, 디렉터리명, 파일명과 그 값을 참조하는 manifest
- SHA-256 대상 JSON·JSONL·로그·판정문
- 검증 바이너리의 계보를 고정한 patch와 branch 이름

새 실행 순서와 용어는 [사용 가이드](../reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.md)를 따른다.
