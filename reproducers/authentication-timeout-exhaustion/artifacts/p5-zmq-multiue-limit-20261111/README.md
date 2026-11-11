# p5 direct 4-cell 다중 UE 한계 실측 (2026-11-11)

## 결론

OAI w38 공유 무선 패치로 공격자 3프로세스×2 UICC와 독립 witness를 direct 4-cell ZMQ에
배치했다. 최종 control은 통과했고 attack은 인증 응답 미전송 기전과 동시 pre-auth
컨텍스트 6개를 재현했지만 witness 서비스 거부는 만들지 못했다.

| 항목 | control | attack |
|---|---:|---:|
| 공격 가입자 | 6 | 6 |
| exact join 컨텍스트 | 30 | 30 |
| Authentication Response 억제 | 0 | 30 |
| 피크 동시 pre-auth | 6 | 6 |
| impact 등록 실패 | 0/5 | 0/5 |
| recovery 성공 | 5/5 | 5/5 |
| crash/forced kill | 0 | 0 |
| 단일 판정 | 통과 | 실패(DoS 미성립) |

프로세스당 10 UICC 진단은 120초 안에 11/20명만 인증했고 약 85만 건의 ZMQ channel
timeout이 발생했다. 프로세스당 4 UICC도 반복 phase timeout으로 무효였다. 이 두 진단은
봉인된 성능 근거가 아니며, 최종 허용 주장은 6개 동시 컨텍스트까지다.

gNB·코어 소스, timer, capacity는 변경하지 않았다. 가입자 설정과 원문은 p5의 암호화된
EBS에만 두고 Git에는 판정과 SHA-256만 보존한다.

## 원격 run과 해시

### control: `auth-timeout-final-control-20261111`

- `run.json`: `08bce8bd13f8cdbc53651f8e305e500f1c981f7c2eb9ee97511ac491a9ee5281`
- `verdict.json`: `a35b6d3622e6278a38f98bb935c612fb3d10ad0888380e3cce09ca5790428a31`
- `evidence_manifest.json`: `7d0be351fff4b23d80ff11ec4d632b34d48b0e3ce9cb793859317e67028ade42`
- manifest 검증 파일: 15개

### attack: `auth-timeout-final-attack-20261111`

- `run.json`: `465aaa240037c8f62a9493cee08a99f87a0b8c05a94f42313cd1f21d7b927b6f`
- `verdict.json`: `7b5384197c88c6d564992f264b9f7335aed53e3be0e671ad399ea4d2c1fddceb`
- `evidence_manifest.json`: `65168d6ef5afb5b538c01b55f1e35e701cc46031e887375fc1c6a5c7cddb2ba0`
- manifest 검증 파일: 15개

두 run의 공통 provenance는 다음과 같다.

- OAI 기준 commit: `6d6782b48484efd935c14e834832032743f9b138`
- 인증 미응답 패치: `bc8f29473155494ada7c07c16e095f99b96e2d82989c9bc6aa9a3d7f57817e07`
- 공유 무선 패치: `c2e91eb6b73fc602e90ee13baf62ce594c263aa9968d5756c85abac6f00fdacb`
- UE binary: `8c443c2ad74084729868fc75e3f22ca7894457612cc5bee2af33504bf9b5a0cb`
- ZMQ library: `d9adbadd994cdcab8373c560781e49364ace3a8fe9fc822886021d9751a65951`

로컬 판정 사본은 [control](control-verdict.json)과 [attack](attack-verdict.json)이다.
