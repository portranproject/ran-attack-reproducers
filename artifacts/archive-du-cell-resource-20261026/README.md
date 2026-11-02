# 보존 기록 — rss-storm v1 (DU 셀 자원 고갈)

`ARCHIVE.md`는 `MANIFEST.sha256`에 포함된 봉인 원문이므로 수정하지 않는다. 이
`README.md`는 해당 원문 전체를 한국어로 옮긴 안내본이며, 내용이 다르게 해석될 경우
봉인된 `ARCHIVE.md`를 기준으로 한다.

**상태: 보존 처리됨, 개발 중단. 2026-10-26.**
이 문서는 2026-10-21/23 시점의 A형 RRC signaling storm 재현기를 설명한다.
이 재현기는 **DU 셀 자원 고갈** 계열로 보존됐다.
**CU-CP 용량/CPU 고갈 도구가 아니다.**

## 무엇인가

- OAI `2026.w38` UE 패치와 셸 실행기다. gNB(OCUDU 26.10)는 수정하지 않았다.
- A형: Msg4 수신 + HARQ ACK 송신 후 `RRCSetupComplete`(Msg5)를 생략하고,
  프로세스 내부에서 새 RA를 반복한다.
- 안정 노브: 시도율, 완료율, 게이트, 목표 점유, 다중 UE.
- 실험 브랜치(probe/A-NAS/evict/harvest/RO)는
  `patches/rss-ue-full-20261023.patch`에 있으며, 안정 A형 도구의 일부가 **아니다**.

## 증거와 함께 검증된 내용

- 120초, UE 2대 실행: 시도 4,438건(37/s), 피크 **96/96**,
  `rrcSetupComplete` / `InitialUEMessage` **0**, hold **1,999 ms**,
  `rrcReject` 15건. CU 원시 로그: `../verify-20261021/`.
- 590초, UE 4대 실행: 시도 25,095건(42.5/s), 점유 >= 72인 시간이 100%
  (최장 176.7초), >= 96인 시간은 1.3초, `rrcReject` 16,227건(27.5/s),
  completion/NGAP 0. 보고서: `../modeA-sustained-20261021/`.
- Mode B(capacity 12): 거부가 지속됐고, 점유 >= 6/12인 시간이 98%, 최장 426초.
  로그: `../midterm-modeb/`.
- 정상 UE probe: 첫 시도에 연결됐으며, 연결 지연은 약 75 ms에서 약 180 ms로 증가했다
  (2.4~2.8배). 서비스 거부는 아니다.
- 점유·거부 기전과 상한 96:
  `findings/gap-metric-mechanism.md`.

## 범위 정정(중요)

- 희소 자원은 CU-CP가 아니라 **DU 셀의 UE context + dedicated SR/CSI**(96)다.
- CU-CP는 시도마다 RRC transaction과 1,000 ms guard를 유지하고, CU F1-C에는 A형
  특징이 나타난다. 그러나 CU-CP context 상한은 8,192로 DU의 96보다 85배 크므로
  **CU-CP는 병목이 아니다**.
- 따라서 올바른 표기는 **DU-bound, CU-visible**이다.
  이 도구를 근거로 "CU-CP 자원 고갈"을 주장하면 안 된다.

## 알려진 한계

- ZMQ 공유 무선: 높은 부하의 실행에서 sample 손실, SSS 손실, UE core dump가 발생한다.
- 정상 UE probe는 별도 표준 UE가 아니라 프로세스 내부 인스턴스다.
- 2026-10-22/23 조사 결과와 전체 실험 패치는 Git에 커밋되지 않았다
  (`findings/`는 gitignore 대상). 이 보존 기록에는 복사본이 포함돼 있다.
- 전체 패치에는 안정 A형 도구에 속하지 않는 실험 기능
  (probe/A-NAS/evict/harvest/RO arbitration)이 포함돼 있다.

## 내용물

- `findings/` — 연구 기록 8개(A-NAS, eviction, 정상 UE 거부, coverage, gap metric,
  RA pipelining, F1C teardown, 보안 보고서 초안).
- `midterm-rss-draft.md` — 중간 보고서 초안(2026-10-20).
- `patches/` — `rss-ue-full-20261023.patch`, `rss-ue-anas.patch`,
  `anas-identity.c`.
- `MANIFEST.sha256` — 위 파일들의 해시.

## Git 상태

- 태그: `du-cell-resource-v1`(보존된 커밋에서 생성).
- 추적된 도구: 해당 태그의 `rss-storm/`.
- 로컬 원시 artifact(Git에 없음, `artifacts/` 기준 상대 경로):
  `verify-20261021/`, `modeA-sustained-20261021/`,
  `modeA-peak-6ue-20261021/`, `ro-arbitration-20261022/`,
  `midterm-modeb/`.

## 후속 설계로 대체됨

향후 CU 대상 설계로 대체된다. 설계 논의를 참고한다. 새 도구를 만들기 전에 CU 대상을
운영상 명확히 정의해야 한다(CU-CP 처리, CU-CP 컨텍스트 테이블, CU-CP 코드 경로 취약점
또는 CU F1-C 관측).
