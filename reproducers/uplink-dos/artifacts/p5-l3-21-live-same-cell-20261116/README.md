# p5 L3-21 실제 프로토콜 same-cell 자격

2026-11-16 정상 UE 5대와 공격 UE 1대를 같은 DU·셀에 두고, 수정 OAI UE가 만든
`RegistrationRequest → RegistrationReject`를 TeleRAN 100 ms 계측과 production detector
고정 commit `766f5569d0ddb425c14bf210a31c38ac60eceef9`으로 검증했다.

| 세트 | control | attack | 정상 UE |
|---|---|---|---|
| 1 | 1 Reject, 경보 0 | 10 Reject / 9,333 ms, 경보 1 | 모든 표본 5/5 |
| 2 | 1 Reject, 경보 0 | 10 Reject / 8,627 ms, 경보 1 | 모든 표본 5/5 |
| 3 | 1 Reject, 경보 0 | 10 Reject / 9,202 ms, 경보 1 | 모든 표본 5/5 |

세 control과 세 attack 모두 `mechanism`, `detection_input`, `detector_result`가 `pass`였다.
서비스 거부는 관측되지 않았고 `rf_cause_observed=false`다. 공격 runner는 목표를 만든 뒤
RF clock을 유지했고, controller가 공격 UE 종료 전에 정상 UE 5/5를 확인했다.

원문은 p5 DU의 `/root/uplink-credential-flood-live-v2/`와
`/root/uplink-credential-flood-live-v2-raw/`에 보관한다. Git에는 식별자 원문을 넣지 않고
아래 판정·manifest SHA-256만 둔다.

| run | verdict SHA-256 | manifest SHA-256 |
|---|---|---|
| `l321-same-control-r10-20261116` | `85672efb9b00185467accfa7281d8319c97252bc1005fb7404a65b408905dcb7` | `600a085e4598c1fb2ed294a05de71b07e09cb38431214ee3e5ff244260c60676` |
| `l321-same-attack-r7-20261116` | `383f2a2301106a8a8bca77312d28f40a1410c093d1211855e784450ea73812ff` | `91bb674fa6e73dc0da84d1727c65472e7678230d84bcb3d8ca892953e6019e1c` |
| `l321-same-control-r11-20261116` | `cb0326446a448c74e64ede6c7d53ce893c0b085d20b1c2bef8eb7920131700ba` | `accb83ec4bc6cf57d70a236748114e1b51e75fa774bb3a1f183408290e834b0f` |
| `l321-same-attack-r8-20261116` | `51d0d918a2f15be6a904fe66d8541c1db3618977e8ed27c2fe1b7163d958ea14` | `6589d7b89b3dacca7cdc238f4e982ce3f52a39b20d430db832febf2d30a9e060` |
| `l321-same-control-r12-20261116` | `567d1673366695ff21e7ad1b8849ea5b7cdd26f7016ff39fb2daa006efc87ff9` | `686a06ee5ba01bc5dbbdc15c4ebcd3f91603a664c8523ccd9441570a6e483e1b` |
| `l321-same-attack-r9-20261116` | `d87fcf6d3e2bb9834554f592f00f02c9abf053ea88dc1ed92e01af29f64b2558` | `0d34666ab5dd9240fe6610f5b379d7911029626b61db6743045c28ea0392bebb` |

최종 broker 원복 회귀 `l321-clock-regression-attack-r11-20261116`도 10 Reject / 7,998 ms,
경보 1, 정상 표본 5/5로 통과했다. verdict SHA-256은
`f7d9e26a57d60dfed1a1a1bfad37c1352cdf593aea25eb96f72274cfdf2b1395`다.

커밋 직전 최종 코드 회귀 `l321-final-code-r12-20261116`은 10 Reject / 8,539 ms,
경보 1, 대시보드 수락/거절 97/0, 종료 전 정상 health 5/5로 통과했다. verdict와 manifest
SHA-256은 각각 `823d6ec70fda9d6b947b8a2d9531cf4d98bcf0aeab5d24fdeb4e01eb02c5fe00`,
`c72ce636b6634c3bfd296e1cff80f3b5b4ec831fbc43c64058ff3829877c71be`다.
