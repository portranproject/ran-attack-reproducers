# p5 exact DU ACK join 검증 (2026-10-30)

## 결과

- 정상 대조군 `J1b-011009`: RRC Setup Complete, Registration Accept, PDU
  Session Accept, Sector#0 FAPI HARQ를 모두 확인했다. `valid=true`,
  민감정보 검사와 UE 로그 정제가 모두 clean이었고 evidence manifest
  verify가 통과했다. 공격 이벤트가 없으므로 `du_ack_join=no_match`는
  정상이다.
- ACK-on A형 `J1a-011228`: UE 1대, 2초 간격, 20초 시도 제한으로
  10회 시도했다. UE 측 A 후보 10개가 모두 Sector#0 DU HARQ ACK와
  exact `(RNTI, frame, slot)` join되어 `A final=10`, `A unknown=0`이었다.
  `evidence_manifest.py verify --require-matched`가 raw UE/DU 증거로 라벨을
  재생성해 통과했다.

## 고정된 버전과 해시

- OAI base: `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (`2026.w38`)
- RSS patch SHA-256:
  `f0072a558d926baaf39ef5ab2f0d8e7e5d23223ec24309fef4835e778e5bbd38`
- UE binary SHA-256:
  `015d4f2b77de128302e60b0525732035ef773a40627bfe597893487ae80802fc`
- DU capture helper SHA-256:
  `e4e061a88b64d3db4d3220ce16c7821506ad91ad093f1d50823ef5886ce49d7b`
- control DU slice SHA-256:
  `a9f274dbb5d88fdc8a5fcbd4a42dfcdd521d8d35af44249ed18e7b8db2fb8401`
- attack DU slice SHA-256:
  `f8bca2a37ad9a66f6d7d3ddebb66c81d402004b6f1e973ad155821a15a660e04`

원시 산출물은 중지된 p5 DU 디스크의
`/root/rss-runs-dujoin-20261030T0101Z/` 아래에 보존했다.

## 막힌 원인과 조치

1. OCUDU 파일 로거는 실행 중 4 KiB 버퍼 단위로 내리므로,
   파일 끝이 줄바꿈이 아닌 시점이 정상적으로 생긴다. 기존 capture
   helper는 이를 손상으로 보고 시작을 거부했다.
2. capture helper를 수정해 시작 시점에 이미 진행 중인 한 행의
   나머지만 버리고, 그 다음 완전한 행부터 봉인하게 했다. inode,
   capture offset, 기존 prefix hash, 종료 부분 행 제거 검증은 그대로
   유지했다.
3. 수정 후 DU capture 회귀 5개와 전체 테스트 126개가 통과했다.

## 각 실행 게이트가 필요한 이유

- clean rebuild: 구형 바이너리와 현재 패치의 영향을 분리한다.
- `fapi_level: debug`: UE의 ACK 예정이 아니라 DU가 실제 받은 HARQ ACK를
  tuple로 확인한다.
- 정상 대조군: CU/DU·코어·ZMQ 장애를 공격 효과로 오판하지 않게
  한다.
- run-scoped DU slice: 이전 run의 같은 SFN/RNTI tuple이 섞이는 것을
  막는다.
- 20초·2초 제한: 필요한 증거를 얻되 부하를 작게 고정한다.
- `--require-matched`: 저장된 결론을 믿지 않고 raw 이벤트로 동일 라벨을
  재생성한다.
- 설정 해시 원복·stack 종료·EC2 stop: 후속 실험 오염과 불필요한
  과금을 막는다.

## 종료 상태와 남은 제약

- DU 설정은 실험 전 SHA-256
  `7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3`로
  원복했다.
- DU/CU stack을 종료했고 p5 DU `c6i.2xlarge`, CU `c6i.xlarge` 둘 다
  `stopped`를 확인했다.
- 두 run 모두 시도 제한 후 OAI UE 프로세스가 자체 종료하지 않아
  runner의 `duration + 20s` 외부 timeout이 종료했다. run은 `valid=true`였고
  공격 시도는 20초에 멈춰지만, wall-clock 종료를 20초로 맞추는 별도
  종료 경로 수정은 아직 하지 않았다.
