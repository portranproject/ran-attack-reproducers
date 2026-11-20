
## 원본 도구 교차 검증 (2026-11-20, p1)

원본 공개 구현을 고정 커밋에서 **수정 없이** 빌드하고, 같은 셀에서 우리 detector 입력과
비교하기 위한 교차 검증이다. 원본 로직은 바꾸지 않았고, RF 인터페이스만 외부에서 변환했다.

| 도구 | 원본 커밋 | 빌드 | 셀 접속 | 판정 |
|---|---|---|---|---|
| 5g-rrc-storm | `0e71f7aee24999b66d44e10db4612f96b5219d98` + OAI `92980ceb725a94dbfe97c509d16f1313eee083e0` | 성공(`reproducers/rrc-signaling-storm/reference/bin/build-reference`) | rfsim↔ZMQ 브리지가 DL 8191샘플 수신, 45초 내 UE sync 실패 | 탐지 비교 미완료 |
| 5GSEC/OAI-5G blind DoS | `b631b577cc00929e50947a453dc5d4c2dcdfa887` | 미완료 | — | 미실시 |

- 원본 소스 변경: **없음**. 원본 OAI UE는 rfsim(TCP, c16)만 말하므로
  `reproducers/rrc-signaling-storm/reference/bin/oai-rfsim-zmq-bridge`가
  broker ZMQ(cf_t)와 변환한다. 이 브리지는 원본 트리 밖의 실행 래퍼다.
- 원본 OAI 설정은 `dnn`/`nssai_sst` 구식 형식과 `LD_LIBRARY_PATH`가 필요했다.
  이는 실행 환경 설정이며 공격 로직 변경이 아니다.
- 5g-rrc-storm 저장소에는 라이선스 파일이 없어 재배포하지 않는다. 5GSEC/OAI-5G는
  저장소 라이선스를 따른다.
- 이 교차 검증 결과를 기존 11-19 p1hold의 7도구 RAISE 1/CLEAR 1 비교로 대체하지 않는다.
  접속·sync가 성립하지 않았으므로 control 1 + attack 1 비교는 수행하지 않았다.
