# p5 direct 3-cell ZMQ 기전 smoke (2026-11-11)

OAI w38 공격자 2명과 정상 witness 1명을 서로 다른 direct ZMQ 셀에서 실행했다. 각
impact/recovery 시도는 ZMQ 연결 상태를 격리하기 위해 UE 세트와 DU를 재기동했다. OCUDU와
Open5GS의 소스·timer·capacity는 변경하지 않았다.

## 결과

| 실행 | 결과 |
|---|---|
| `auth-timeout-smoke-control-v24-20261111` | 통과. impact 정상 서비스 5/5, recovery 5/5, crash/forced kill 0 |
| `auth-timeout-smoke-attack-v3-20261111` | 기전·자원 누적 통과, 공격 성공 불합격. Response 억제 10건, pre-auth 피크 2, witness 실패 0/5, recovery 5/5 |

따라서 현재 허용 주장은 **Authentication Response 미전송 기전과 공격자 2명의 동시
pre-auth 컨텍스트를 p5 ZMQ에서 재현했다**까지다. 정상 UE 서비스 거부와 matched 3세트
공격 성공은 입증하지 않았다.

## 원격 증거 해시

원문은 p5 DU의 `/root/auth-timeout-runs/`에 보존했다. 가입자 설정과 원문 로그는 Git에
복사하지 않았다.

| 실행 | 파일 | SHA-256 |
|---|---|---|
| control v24 | `run.json` | `cb4d976d01da64bb7b911941db0aa72f10ec1b1a72007c8c09817b8621dd9360` |
| control v24 | `verdict.json` | `cd9ff45352da3f38144cc2413a6848c42c271e4f4fe37654cef9e9bb5d8c12c4` |
| control v24 | `evidence_manifest.json` | `d60a3700d04212530ba8028a050841412215498186933289bb1362aebbc6a342` |
| attack v3 | `run.json` | `3a0844c4ad54eb0773d4b3c9074acc90354d9accb3c28cfb883832d58667a354` |
| attack v3 | `verdict.json` | `efa0fd9f5df114ec45153cf51b34c9b2ff73b8ab7b199677fa52c38a1cf88f67` |
| attack v3 | `evidence_manifest.json` | `684ca559e0d7aacdc6c5ceebeac0a847cf8602571636da8a48b84e24ecb56426` |
