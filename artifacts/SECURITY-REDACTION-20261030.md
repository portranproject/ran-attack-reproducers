# 과거 UE 로그 credential redaction — 2026-10-30

과거 실험 산출물을 점검하면서 raw 가입자·인증 값을 가진 plain UE 로그 7개·민감 행
18개와, 같은 값을 중복 포함한 압축 blob 4개 안의 member 7개를 확인했다. 현재 작업
트리에서는 민감 행 전체를 `[REDACTED subscriber/auth material]`로 치환하고 압축
묶음도 정제된 파일로 다시 만들었다. 추가로 정제한 `tool/runs/*/ue.log` 5개는 필드명이
있었지만 값은 원래부터 angle-bracket placeholder였으며 실제 credential 노출 집계에는
포함하지 않는다. 나머지 로그 행과 실험 결과는 유지했다.

재발 원인은 OAI w38의 `openair3/UICC/usim_interface.c`가 초기화 때 가입자·장기 키를
INFO로 출력하고, 정상 인증 때 OPc·AMF·Ki·SQN·RAND·IK·CK·RES·AUTN을 level gate 없는
`log_dump()`로 출력하며, runner가 stdout 전체를 보존한 것이었다. 현재 curated patch는
초기화 로그를 값 없는 문장으로 바꾸고 direct dump 9개를 모두 제거한다. runner도 run
디렉터리/파일을 0700/0600으로 만들고 UE 종료 직후 원자 정제한 뒤, run 전체 scanner가
성공해야만 evidence manifest를 만든다. 예상 밖 정제가 한 줄이라도 발생하면 인증값은
제거하되 해당 run은 무효다.

이 정제는 **현재 파일만** 바꾼다. 기존 Git commit, tag, remote ref에는 정제 전 blob이
남아 있을 수 있으므로 저장소 전체를 외부에 게시하거나 mirror하지 않는다. 노출된 랩
가입자 credential은 회전하고, 팀과 ref·tag 영향 범위를 합의한 뒤 별도 fresh mirror에서
이력을 정리해야 한다. 현재 dirty worktree에서 history rewrite나 force-push는 하지 않는다.

재유입 검사는 다음 명령으로 수행한다. 값은 출력하지 않고 파일·archive member와
필드 이름만 보고한다.

```bash
python3 rss-storm/analysis/check_sensitive_artifacts.py
python3 rss-storm/analysis/check_sensitive_history.py
```

첫 명령은 현재 tracked·untracked 파일을, 둘째 명령은 모든 로컬 ref에서 도달 가능한
과거 Git blob과 그 안의 압축 member를 검사한다. 이력 정리 뒤에는 둘 다 성공해야 한다.

## 현재 local ref 범위

2026-10-30 전수검사 결과는 다음과 같다. 값은 출력하거나 문서화하지 않았다.

- reachable blob 472개 중 finding 14개, 고유 민감 blob 11개
- plain 로그 경로 7개, 압축 경로 4개(압축 member finding 7개)
- 모두 commit `fbdedd95c62378c1d768827c0b3a5988bdff0b94`에서 유입
- 그 commit을 포함하는 ref는 현재 snapshot에서
  `refs/heads/claude/msg4-ack-variant`와
  `refs/remotes/origin/claude/msg4-ack-variant`뿐이며 tag는 없음

reachable blob 총수는 Codex turn-diff 같은 비민감 local ref가 생성되면 달라질 수 있다.
따라서 정리 판정은 총수 자체가 아니라 finding 0, 영향 commit을 포함하는 ref, 그리고
정리 전 민감 blob OID의 제거 여부로 한다.

remote 서버의 숨은 ref나 이후 갱신은 local remote-tracking ref만으로 증명할 수 없다.
정리 직전 새 mirror에서 모든 branch·tag를 fetch한 뒤 scanner를 다시 실행한다.
현재 영향 구간은 유입 commit부터 remote tip까지 merge 없는 직선 3개 commit이며,
뒤 두 commit은 아래 11개 경로를 다시 수정하지 않았다. 그래도 실제 정리는 특정 ref만
부분 rewrite하지 않고 fresh mirror의 전체 ref를 대상으로 한다.

영향 경로는 다음 11개다.

```text
artifacts/spike-cu90-20261026/du/run-first/ue.log
artifacts/spike-cu90-20261026/du/run-probe/ue.log
artifacts/spike-cu90-20261026/du/spike-cu90-du.tar.gz
artifacts/spike-cu90-20261026/round4-probe/du/du.tar.gz
artifacts/spike-cu90-20261026/round4-probe/du/ue2-alone.log
artifacts/spike-cu90-20261026/round4-probe/du/ue2-attack.log
artifacts/spike-cu90-20261026/second-du/du/du.tar.gz
artifacts/spike-cu90-20261026/second-du/du/ue2-alone.log
artifacts/spike-cu90-20261026/second-du/du/ue2-attack.log
artifacts/verify-20261021/ue.log
artifacts/verify-20261021/ue.log.gz
```

## 정리 순서와 합격 게이트

1. 먼저 랩 가입자 credential을 회전하고 이전 profile을 폐기한다.
2. 팀과 affected branch의 쓰기 동결·PR/ref 처리·force-push 시간을 합의한다.
3. 현재 dirty worktree와 다른 managed worktree의 tracked·untracked 변경 전체를 접근
   제한 백업으로 보존하고 실제 복원 가능성을 확인한다. 아래 17개 묶음은 artifact
   복원용일 뿐 현재 작업 전체의 백업이 아니다.
4. 현재 dirty multi-worktree가 아닌 새 `git clone --mirror`에서 모든 branch·tag를 다시
   fetch하고 history scanner로 영향 범위를 재확인한다.
5. 위 11개 경로의 **현재 정제본**과 아래 의존 파일 6개를 mirror 밖의 접근 제한
   staging에 함께 보존하고 17개 파일의 SHA-256을 기록한다.

   ```text
   artifacts/spike-cu90-20261026/MANIFEST.sha256
   artifacts/spike-cu90-20261026/README.md
   artifacts/spike-cu90-20261026/round4-probe/README.md
   artifacts/spike-cu90-20261026/second-du/README.md
   artifacts/verify-20261021/SHA256SUMS
   artifacts/verify-20261021/README.md
   ```

6. fresh mirror 전체 ref에서 `git-filter-repo`로 위 11개 민감 경로를 제거한다. 공식
   문서상 [`--refs`는 `--partial`을 암시](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt)해
   old/new history와 미수출 ref를 함께 남길 수 있으므로 사용하지 않는다. `--dry-run`도
   원본·필터링 fast-export 사본을 저장하므로 접근 제한 mirror 밖에서는 실행하지 않는다.
   이 호스트에는 현재 `git-filter-repo`가 없으므로 설치와 실행은 팀 승인 뒤에 한다.
7. 새 checkout에 staging의 17개 파일을 다시 추가하고 manifest를 검증한 뒤 별도
   정제 commit으로 남긴다.
8. `check_sensitive_artifacts.py`와 `check_sensitive_history.py`가 모두 exit 0이고,
   `git fsck --full`이 성공하며, 정리 전 민감 blob 11개가 filter-repo cleanup 뒤 object
   database에서 사라졌고, artifact manifest 두 개도 검증될 때만 coordinated
   force-push를 한다.
9. 팀원이 기존 clone을 폐기하거나 새 이력으로 재동기화한 뒤 branch protection·PR·CI를
   재확인한다.

정리 명령은 새 mirror에서 확정된 ref와 설치된 `git-filter-repo` 버전을 다시 확인한 뒤
작성한다. 현재 worktree에서 ref 삭제, history rewrite, garbage collection, force-push를
하지 않는다.

정제 때문에 과거 원문 SHA-256은 더 이상 현재 파일을 가리키지 않는다. 해당 artifact
manifest는 정제 파일 기준으로 다시 계산했고, 문서의 실험 수치가 “미가공 원문”이라는
표현은 철회했다.
