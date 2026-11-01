# Current-build DU HARQ-ACK join (J2, 2026-10-30)

This artifact closed the exact-ACK gap for the then-current binary:

- control `J2b-current-20261030T033158Z`: normal Registration, PDU session, and TUN setup;
- attack `J2a-current-20261030T033158Z`: 9/9 candidates have `canonical_a=true` and `du_ack_state=ack`;
- attack sends no Msg5;
- both evidence manifests verify.

Version identity:

- OAI commit: `1c2f4d3c2e68181cdef9f426d161163147ad4b77`
- UE binary: `cc5b7569e68ce3d829dd2e8fb91a6c863bc9ea76a7cf66eac5e8b9a40bcebac2`
- curated patch: `7b289c0fdbeb3e4c0d852b832c9805cc3f30af7c16998d5975bea775f74bcd1c`
- attack manifest: `977525d825d4aff11612837676c5acfca9c0c36d7d22a78099361534168edce9`
- control manifest: `9371563688a82d0352af3d0924b30fa786826cf1ce383e4dbad99a0c4e384622`

This result is intentionally version-bound. The later all-probe delay fix changed the binary and patch hashes. Final-binary exact ACK is proven by `../p5-cu200-3cell-20261030/final-v4/` (176 exact canonical attempts); that hold32 diagnostic does not prove service denial under default cleanup.
