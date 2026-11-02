# 현재 빌드 DU HARQ-ACK 조인 (J2, 2026-10-30)

이 artifact는 당시 현재 바이너리의 exact ACK 증거 공백을 해소했다.

- control `J2b-current-20261030T033158Z`: 정상 Registration, PDU session, TUN 설정
- attack `J2a-current-20261030T033158Z`: 후보 9/9가 `canonical_a=true`, `du_ack_state=ack`
- attack은 Msg5를 보내지 않음
- 두 evidence manifest 모두 검증 통과

버전 식별 정보:

- OAI commit: `1c2f4d3c2e68181cdef9f426d161163147ad4b77`
- UE binary: `cc5b7569e68ce3d829dd2e8fb91a6c863bc9ea76a7cf66eac5e8b9a40bcebac2`
- curated patch: `7b289c0fdbeb3e4c0d852b832c9805cc3f30af7c16998d5975bea775f74bcd1c`
- attack manifest: `977525d825d4aff11612837676c5acfca9c0c36d7d22a78099361534168edce9`
- control manifest: `9371563688a82d0352af3d0924b30fa786826cf1ce383e4dbad99a0c4e384622`

이 결과는 의도적으로 해당 버전에만 유효하다. 이후 all-probe delay 수정으로 바이너리와
patch hash가 바뀌었다. 최종 바이너리의 exact ACK는
`../p5-cu200-3cell-20261030/final-v4/`에서 입증됐다(exact canonical 시도 176건). 해당
hold32 진단은 기본 cleanup에서의 서비스 거부를 입증하지 않는다.
