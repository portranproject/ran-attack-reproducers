# Blind DoS same-cell 결합 한계

2026-11-16 기존 direct 2-cell 구현을 정상 UE 배경과 같은 한 셀에 결합했다. oracle은
`InitialUEMessage`가 하나뿐이라는 가정을 제거하고 다음 순서로 피해자를 선택한다.

1. 현재 실행 AMF slice에서 피해자 IMSI가 붙은 mapping만 남긴다.
2. 현재 victim log의 5G-S-TMSI와 일치하는 mapping을 우선한다.
3. 이후 Release가 확인된 과거 mapping을 제외한다.
4. live 후보가 정확히 하나가 아니면 추측하지 않고 실패한다.

단위 테스트는 정상 배경 mapping 무시, 해제 뒤 재시도 선택, target 불일치와 모호성의
fail-closed를 포함한다. p5에서는 oracle 단계 전에 피해 UE가 등록하지 못했다.

| run | 정상 배경 | 정상 health | 피해 UE 결과 |
|---|---:|---|---|
| `blind-same2-attack-r4-20261116` | 2 | 141개 표본 2/2 | sync 3회, RAR 실패 7회, Registration 0 |
| `blind-same1-attack-r5-20261116` | 1 | 155개 표본 1/1 | sync 3회, RAR 실패 7회, Registration 0 |

두 실행 모두 `SERVICE_READY_TIMEOUT_S=180`에서 `victim baseline service timed out`으로
`infrastructure-invalid`였다. 배경 UE 수나 CPU 부족이 아니라 독립 victim·attacker ZMQ
프로세스의 상향 sample 시간축을 raw sample 합산 broker가 정렬하지 못하는 한계다. 공격 UE에
대기 중 실제 하향 clock을 주는 우회는 Blind 정상 배경을 살렸지만 기존 L3-21 경로의 Reject를
0건으로 만들어 폐기했다.

원문은 p5 DU의 `/root/blind-dos-runs-g5/`와
`/root/normal-ue-qualification/persistent/same-cell/`에 보관한다.

| run | run_stop SHA-256 | diagnostics SHA-256 | manifest SHA-256 |
|---|---|---|---|
| `blind-same2-attack-r4-20261116` | `0e712d0a36e2c37ecc1b420257ee60707f5d22491d3b486a40fc2be0dec40b02` | `aa8805c887a65d613bd71a14a032babab4b8d51bd357fe2dd369b4d37f24cbca` | `ea7bafe2871a09210fa4fd9070200dcdccbdede1a8d0b268bb29e14c2037cc58` |
| `blind-same1-attack-r5-20261116` | `cc748140e16052c7707fd208275bc36d4042833e92ae73df840f13894111c434` | `108f8415b87a3fbd00346f94f10d8d826c81fd571edff594ade6817172c0e793` | `9219f9d637536b842c058e7cdc095848f2d037aa04060162163af0754e1a17a1` |

따라서 L3-20의 승인 경로는 계속 direct 2-cell G5 3/3이다. same-cell을 승인하려면
timestamp-aware sample 정렬 broker 또는 victim·attacker를 같은 OAI 다중-UE clock에 넣는
별도 포팅이 필요하다.
