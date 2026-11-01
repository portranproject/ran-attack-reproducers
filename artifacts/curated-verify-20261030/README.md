# Curated 실기 검증 증거 목록 — 2026-10-30

이 디렉터리는 p5 ZMQ 실험의 **안전한 요약과 원격 원문 해시**만 보존한다. UE·DU
원문 로그에는 식별자와 가입 절차 자료가 포함될 수 있어 저장소로 복사하지 않았다.
원문은 중지된 p5 DU의 보존 디스크 `/root/rss-runs-curated/`에 남아 있으며,
`SHA256SUMS.remote`로 같은 파일인지 확인할 수 있다.

## 빌드 계보

| 항목 | 값 |
|---|---|
| OAI 기준 | `2026.w38`, `1c2f4d3c2e68181cdef9f426d161163147ad4b77` |
| 적용 순서 | 공식 PUCCH 수정 → `rss-ue-curated.patch` |
| curated 패치 SHA-256 | `6a28a9e8d936fc1cf8a3daee58097ccf26f7860bdb33adca2842d52d0714f57c` |
| 빌드된 `nr-uesoftmodem` SHA-256 | `733e88f66a7e378dae2eaac4c31fef0ae745d09ddfd632606e672adb7b2b44a7` |
| 소스 일치 | clean apply 결과의 11개 변경 파일과 빌드 worktree가 모두 byte-identical |

## Msg4 ACK 3회 교차 반복

모든 실행은 단일 공격 UE, 2초 시도 간격, 20초 공격 창이었다.

| 반복 | ACK 노브 | 시도 | ACK | DTX | max-retx | Msg5 | crash |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 10 | 64 | 19 | 0 | 0 | 0 |
| 1 | 0 | 10 | 0 | 477 | 40 | 0 | 0 |
| 2 | 1 | 10 | 64 | 20 | 0 | 0 | 0 |
| 2 | 0 | 10 | 0 | 475 | 40 | 0 | 0 |
| 3 | 1 | 10 | 65 | 18 | 0 | 0 | 0 |
| 3 | 0 | 10 | 0 | 456 | 38 | 0 | 0 |

판정과 한계는
[`rss-storm/docs/CURATED-VALIDATION-20261030.ko.md`](../../rss-storm/docs/CURATED-VALIDATION-20261030.ko.md)를
따른다. 특히 OCUDU의 `ConRes CE ACKed` 문자열은 실제 ACK 증거가 아니다.
