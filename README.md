# ran-rrc-storm

팀 O-RAN 침입탐지·대응 테스트베드 중 **외부자 UE 측 — RRC signaling storm 재현 도구** 서브태스크 기록.

처음 읽을 문서는 [AGENTS.md](AGENTS.md)(프로젝트 컨텍스트·내 역할·결정·다음 액션).

| 문서 | 내용 |
|---|---|
| [AGENTS.md](AGENTS.md) | 팀 프로젝트 그림 + 내 서브태스크 + 확정/열린결정/리스크/다음액션 |
| [tool-survey.md](tool-survey.md) | 공개 도구 조사 — 계열 A(5gattacks/OAI, 턴키·신뢰가능) vs 계열 B(UCD/srsRAN, 코드미공개·데이터셋만), srsRAN+ZMQ 뼈대, 신뢰성 평가 |
| [methodology.md](methodology.md) | 공격 메커니즘(Msg5 생략+루프), 변조 지점(5gattacks 패치 실측), 재현 파라미터(노브), 탐지 특징, OCUDU 성립 전제 |
| [sources/](sources/) | 1차 자료: 논문 PDF 2건 + 5gattacks 공격 패치 |

상태(2026-10-08): 조사·설계 단계. 구현 전. **다음 = interop 스모크 테스트**(정상 UE↔OCUDU 연결 확인).
