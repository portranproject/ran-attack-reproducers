# 원본 5g-rrc-storm 도구 빌드 (수정 없이)

- 원본: https://github.com/5gattacks/5g-rrc-storm, 커밋 `0e71f7aee24999b66d44e10db4612f96b5219d98`
- 원본이 지정한 OAI: `92980ceb725a94dbfe97c509d16f1313eee083e0`
- 라이선스: 저장소에 라이선스 파일이 없다. 재배포하지 않고 빌드 산출물만 랩 안에서 쓴다.
- 원본 패치: `storm-attack.patch` (UE 공격 분기). gNB 변경분은 빌드 대상이 아니다.

`bin/build-reference`는 원본 저장소와 OAI를 고정 커밋으로 clone하고 원본 패치를
**그대로** 적용해 `nr-uesoftmodem`만 빌드한다. 공격 로직은 한 줄도 바꾸지 않는다.

## 2026-11-20 p1 결과

- 원본 패치 UE `5814a864…`, 무패치 control `9a268619…` 빌드 성공.
- 브리지가 DU ZMQ DL을 rfsim으로 변환해 UE로 전달하는 단계까지 확인했으나, UE 초기
  sync가 45초 안에 성립하지 않았다(`synch Failed`). numpy 변환·0.5 ms 상향 블록으로
  고친 뒤에도 같았다.
- 그래서 control/attack의 production detector 판정은 실행하지 못했다.
- 실행은 `./ctl.sh reference run ref-rrc-storm --profile p1 --mode control|attack`로 한다.
