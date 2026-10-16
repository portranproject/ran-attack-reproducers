# ran-rrc-storm

팀 O-RAN 침입탐지·대응 테스트베드 중 **외부자 UE 측 — RRC signaling storm 재현 도구** 서브태스크 기록.

처음 읽을 문서는 [AGENTS.md](AGENTS.md)(프로젝트 컨텍스트·내 역할·결정·다음 액션).

| 문서 | 내용 |
|---|---|
| [AGENTS.md](AGENTS.md) | 팀 프로젝트 그림 + 내 서브태스크 + 확정/열린결정/리스크/다음액션 |
| [tool-survey.md](tool-survey.md) | OCUDU 공식 UE 연결 예제, 5gattacks 패치, UCD 데모, 다중 UE ZMQ 공개물의 실제 범위 |
| [methodology.md](methodology.md) | RSS 실험 시나리오, A형 절차, F1 관측 경계, 재현기 기록과 단계별 검증 기준 |
| [rss-theory.md](rss-theory.md) | RSS 원리: 단계별 자원 할당, 조작 파라미터, 고갈 동역학, OCUDU 대입 |
| [rss-landscape.md](rss-landscape.md) | RSS 변종 분류, 논문·공개 도구 비교, 재현기 요구사항 |
| [comparison-5g.md](comparison-5g.md) | 5G 기준 기존 연구·공격 도구 비교 요약판. 주장별 원본 대조 여부 표시, 독립 재검색 결과 |
| [testbed-checklist.md](testbed-checklist.md) | 팀 테스트베드 설정 체크리스트(값 미기입), OCUDU 설정에서 TDD/FDD 읽는 법, 베이스 UE 결정 규칙 |
| [design.md](design.md) | A형 재현기 설계: 아키텍처, 상태 기계, 노브, 라벨 스키마, 단계별 계획 |
| [sources/](sources/) | 1차 자료: 논문 PDF 2건 + 5gattacks 공격 패치 |

상태(2026-10-09): 조사·설계 단계. 구현 전. **다음 = 팀 RF 설정에서 정상 UE↔OCUDU 연결 확인.** 공식 OAI UE ZMQ 정상 접속 사례는 있지만 팀의 차폐 OTA·CU/DU 분리 경로는 미검증이다. A형은 탐지 검증을 먼저 수행하고, 폐루프는 실제 대응 수단과 정상 UE 영향 확인 후 평가한다.
