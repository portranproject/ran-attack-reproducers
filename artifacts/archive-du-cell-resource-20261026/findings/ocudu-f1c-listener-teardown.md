# OCUDU: 한 DU의 비정상 종료가 CU의 F1-C 리스너를 영구히 닫는다

| 항목 | 내용 |
|---|---|
| 발견 | 2026-10-21, AWS 분리형 CU/DU 테스트베드 (p5) |
| 대상 | OCUDU `release_26_10` (`e0db566a`) |
| 분류 | 가용성 — 원격 트리거 가능한 영구 서비스 거부 (프로세스 재시작 전까지 복구 불가) |
| 상태 | 소스 판독으로 경로 확정. 재현 실험은 §6 미실시 항목 참조 |
| 제보 경로 | **GitLab 이슈가 1차** (§8). 미인증 원격 트리거를 입증하지 못했으므로 보안 메일이 아니다 |

## 1. 현상

CU 프로세스(`apps/cu/ocu`)가 **살아 있는 상태로 F1-C 리스닝 소켓(38472)을 잃었다.**

```
06:04:54.718031 [IO-EPOLL] [E] fd=11: Error on file descriptor. Events=0x8
06:04:54.846765 [CU-CP   ] [I] ue=18682: "UE Removal Routine" finished successfully
06:04:54.846807 [CU-CP   ] [I] Logical cell nci=0x66c000 de-realized.
06:04:54.846821 [CU-CP   ] [I] Removed DU 0
```

이후 상태:

- `ss -l --sctp`에 38472 엔드포인트가 **없음** — 구독 해제가 아니라 소켓이 닫힘
  - ⚠️ **진단 주의**: F1-C는 SCTP다. `ss -lnt`(TCP 전용)는 정상일 때도 38472를 보여주지
    않으므로 **상실로 오판하게 된다**(2026-10-21에 실제로 오판했다). 반드시 `ss -l --sctp`.
  - ⚠️ 상실이 의심되면 **복구 재시작 전에** `ss -a --sctp`, `ls /proc/<pid>/fd`,
    `pgrep -a ocu`를 먼저 스냅샷할 것. 재시작하면 판정 근거가 사라진다.
- 모든 DU 재연결이 `Connection refused`
- CU-UP는 1초마다 정상 로그를 계속 출력, 어떤 assert·exception·abort도 없음
- 열린 fd 10개 / 한도 1024 → fd 고갈 아님. RSS 2.43 GB는 `max_nof_ues 8192` 사전 할당
- **CU 재시작만이 복구 수단**

## 2. 트리거

테스트 하네스가 **F1-C가 바쁜 상태에서 DU를 `SIGKILL`**했다(`pkill -9 odu`). 그 시점에
미완료 RRC 컨텍스트 약 96개가 살아 있었고 초당 약 47회로 생성·해제가 반복되고 있었다.
DU는 F1 Removal 절차를 수행할 기회 없이 죽었고 SCTP association이 비정상 종료됐다.

**중요한 대조군**: 같은 `pkill -9`가 같은 날 최소 4회 있었고 매번 다음 DU가 정상 접속했다.
즉 **비정상 종료만으로는 불충분**하다. §4가 그 이유를 설명한다.

## 3. 루트 코즈 (소스 판독, 직접 확인)

`sctp_network_server_impl.cpp`가 **peel-off된 각 association fd**에 등록하는 에러 핸들러가
**리스너용 핸들러와 동일한 동작**을 한다.

```cpp
// subscribe_association_to_broker(), line ~786
assoc_ctxt.io_sub = broker.register_fd(
    ...,
    [this](io_broker::error_code code) {
      logger.info("Connection loss due to IO error code={}.", (int)code);
      defer_socket_shutdown(nullptr);          // ← 서버 전체 종료
    });
```

```cpp
// handle_socket_shutdown(), line ~356
while (not associations.empty()) { ... }
// Stop handling new SCTP events.
io_sub.reset();                                 // ← 리스너의 구독을 해제
```

`io_sub`는 **리스너**의 구독이다 — `subscribe_to_broker()`(line 773)에서만 대입되고
`return io_sub.registered()`(781)로 확인된다. association은 `assoc_ctxt.io_sub`라는
**별도 멤버**(786, 794)를 쓴다.

리스너 fd는 브로커가 **소유**한다. `socket.release()` 직후 `register_fd(unique_fd(...))`로
넘기므로, 구독이 reset되면 브로커의 `fd_handler` 맵 노드가 지워지고 그 안의 `unique_fd`
소멸자가 `::close()`를 호출한다. 그래서 포트가 완전히 사라진다.

**영구성**: `keepalive_token`은 생성 시 `true`로 한 번 설정되고 종료 시 `false`로 한 번
바뀌는 단방향 래치다. 이후 모든 지연 작업이 단락되고, `listen()`과 `subscribe_to_broker()`는
기동 경로에서만 호출되며 재바인드·재리슨 경로가 없다. 소멸자의 `report_error` 가드도 같은
래치에 걸려 있어 프로세스는 조용히 계속 살아 있는다.

## 4. 왜 부하가 있을 때만 터지는가 (두 조건)

**조건 1 — 맨 `EPOLLERR`이어야 한다.** `io_broker_epoll.cpp:130`이 `EPOLLIN`에 절대 우선권을
준다("There is data to receive, even if there are errors signaled. Process data first."), 에러
처리는 `else` 안에 있다. 따라서 `0x9`(IN|ERR)는 깨끗한 per-association 경로로 가고 에러 비트는
버려진다. 로그의 `Events=0x8`은 그 순간 `EPOLLIN`이 **없었다**는 증거다.

**조건 2 — 해제보다 먼저 관측돼야 한다.** 등록과 재무장이 `EPOLLIN | EPOLLONESHOT`을 쓰고
`receive_plain()`은 드레인 루프 없이 `sctp_recvmsg`를 1회만 호출한다. 그래서 COMM_LOST 알림을
읽은 직후 **빈 수신 큐 위에서 fd가 재무장**되고, 커널의 소켓 에러가 래치된 채 다음
`epoll_wait`이 맨 `0x8`을 보고한다. association 해제는 `app_exec` 큐를 거쳐야 하는데,
스톰 중에는 그 큐가 **약 129 ms** 깊었다 — 로그의 `.718031 → .846765` 간격이 그 값이다.
저부하에서는 해제가 레이스를 이기므로 리스너가 살아남는다.

## 5. 공격자 도달 가능성

| 경로 | 판정 |
|---|---|
| UE/무선 측만 통제하는 공격자 | **도달 불가.** F1-C 소켓은 CU의 설정 주소에 바인드되고, UE 기원 내용은 F1AP 페이로드로만 소비된다. RRC 내용으로 F1-C 소켓을 선택·주소지정·종료할 수 없다 |
| DU를 죽이거나 멈추게 할 수 있는 자 | **도달 가능.** 이 결함을 그대로 상속한다. A형 스톰이 DU를 죽일 수 있는지는 미확인 |
| F1 전송망 접근자 | **도달 가능**(SCTP ABORT 주입 등). O-RAN이 F1에 IPsec을 권고하는 이유와 같은 위협 모델 |
| SCTP 재전송 소진 | 이 설치본에서는 **사실상 불가.** `cu.yaml`에 `rto_max`·`assoc_max_rxt`가 미설정이고, 코드가 미설정 시 조용히 건너뛰므로 커널 기본값(재전송 10회, rto_max 60초)이 적용된다. DU가 수 분간 무응답이어야 한다 |

**스톰의 기여**: 스톰 자체가 리스너를 죽이지는 않지만, F1-C 파이프를 채우고 `app_exec` 큐를
깊게 만들어 **어떤 비정상 DU 종료든 치명적으로 만든다**(§4 조건 2). 10분 단독 스톰(47/s)으로는
리스너가 생존했다.

## 6. 미실시 재현 실험 (주장 등급을 올리려면 필요)

1. **E1 — 무부하 `pkill -9` 30회**: 리스너 생존률 기준선. 전부 생존이면 조건 1 설명 강화
2. **E2 — ABORT vs SHUTDOWN**: F1 경로를 `tcpdump`로 잡고, 무부하/만부하에서 각 10회 kill.
   무부하는 SHUTDOWN(chunk 7), 만부하는 ABORT(chunk 6) + 리스너 사망을 예측
3. **E3 — 용량·시도율 도즈 반응**: 실패율이 시도율과 함께 단조 증가하는지
4. **E5 — `SIGTERM` 만부하 20회**: 전부 생존이면 "orderly shutdown은 안전"이 입증되고,
   하네스 완화책(`SIGKILL` → `SIGTERM`)이 검증된다. **이슈를 올리기 전에 E1·E2·E5로
   결정론적 재현 절차를 만든다** — 재현 없는 이슈는 메인테이너가 확인할 수 없다

이 실험들은 gNB 소스·설정을 바꾸지 않는다.

## 7. 수정안

**한 줄 (CU 측)**: association 에러 핸들러를 association 범위로 한정한다. 같은 파일의 정상
경로(`handle_sctp_comm_lost(assoc_id)`, line ~723)가 이미 올바른 동작을 한다.

```cpp
// subscribe_association_to_broker()
-     defer_socket_shutdown(nullptr);
+     handle_sctp_comm_lost(assoc_ctxt.assoc_id);
```

**부가 강화**: `io_broker_epoll.cpp`의 `EPOLLERR` 분기도 다른 제거 경로들처럼 `job_count`와
`pending_fds_to_remove`를 존중하게 한다.

**운영 완화책(gNB 무수정, 즉시 적용 가능)**: F1-C가 바쁜 동안 DU를 `SIGKILL`하지 않는다.
`SIGTERM`을 쓰면 DU가 F1 Removal과 정상 SCTP 종료를 수행한다. 우리 테스트 하네스
(`rss-storm`의 `GNB_RESTART_CMD` → 박스 `ctl.sh`의 `pkill -9 odu`)에 적용 대상이다.

## 8. 제보 경로 판단

OCUDU 정책: *"Most of the time, when you find a bug in OCUDU, it should be reported using GitLab
issues. However, if you are reporting a security vulnerability, please email a report to
security@ocudu.org. This will give us a chance to try to fix the issue **before it is exploited in
the wild**."*

마지막 구절이 기준을 정한다 — **악용 가능성**이다. 우리가 입증한 것과 못한 것:

| | 상태 |
|---|---|
| 코드 경로·영구성·부하 의존성 | **입증** (소스 판독, §3~§4) |
| 트리거 | 우리 **자신의 테스트베드에서 우리가 DU를 `SIGKILL`** — 같은 신뢰 도메인의 운영 행위 |
| 미인증 원격 공격자의 트리거 | **미입증.** UE 측에서는 도달 불가를 확인했고, F1 전송망 공격자는 가설 |
| 영향 | CU의 모든 DU 수용이 재시작까지 영구 중단 — 가용성 영향은 높다 |

따라서 **"신뢰된 피어의 비정상 종료가 서버 전체를 영구히 내리는 견고성 결함"**이 정확한 성격이고,
그 자체로 보안 취약점이라 주장하기엔 **공격자 모델이 비어 있다.**

**결론: GitLab 이슈로 올린다.** 다만 이슈 본문에 보안 관련성을 명시하고, 메인테이너가 F1 전송망을
비신뢰 경계로 본다면(O-RAN 자체 위협 모델은 그렇게 보고 IPsec을 권고한다) 비공개로 전환할지
그쪽이 판단하게 둔다. 보안 메일은 §6의 재현 실험으로 **미인증 트리거가 확인될 때** 보낸다.

출처 적법성도 함께 밝힌다 — 정책이 *"do not accept contributions derived from unauthorized
access"*라고 못박고 있다. 이 발견은 **우리 소유 AWS 테스트베드의 우리 설치본**에서 나왔다.

### 이슈 초안

> Title: CU permanently loses its F1-C listener when one DU association fails abruptly (release_26_10)
>
> Note on scope: this is an availability/robustness defect, not a demonstrated remote exploit. The
> trigger in our run was our own SIGKILL of our own DU on our own testbed. If you consider the F1
> transport an untrusted boundary and would rather handle this privately, say so and we will move it
> to security@ocudu.org.
>
> One abrupt F1-C association failure permanently closes the CU's F1-C listening socket. The CU
> process stays alive and otherwise healthy, but no DU can connect again and the listening port is
> gone from the SCTP endpoint table; only a process restart recovers it.
>
> Cause: `subscribe_association_to_broker()` registers, for every peeled-off association fd, an
> io_broker error handler that calls `defer_socket_shutdown()`. That reaches
> `handle_socket_shutdown()`, which resets `io_sub` — the *listener's* subscription, not the
> association's (`assoc_ctxt.io_sub`). Since the broker owns the listener fd, resetting the
> subscription closes it. `keepalive_token` is a one-way latch and there is no re-listen path, so
> the loss is permanent.
>
> Two conditions make it load-dependent: `io_broker_epoll.cpp` gives EPOLLIN precedence over the
> error bits, so only a bare EPOLLERR reaches the destructive branch; and the EPOLLIN|EPOLLONESHOT
> rearm with a single `sctp_recvmsg` per callback leaves the fd armed on a drained queue with the
> socket error still latched. Under F1 load the association deregistration is queued behind other
> `app_exec` work (~129 ms in our capture) and loses that race.
>
> Observed on release_26_10 (e0db566a), split CU/DU over F1 on two hosts, with the DU SIGKILLed
> while ~96 RRC setup procedures were in flight. Not reachable from the UE/radio side in our
> testing; reachable by anything that can crash or hang a DU, or by an actor on the F1 transport.
>
> Suggested fix (one line): scope the association error handler to
> `handle_sctp_comm_lost(assoc_ctxt.assoc_id)`, which the clean path already uses.
>
> Full write-up, log excerpts and the code path are attached. Happy to submit this as an MR.

## 9. 출처

- OCUDU 소스는 테스트베드 설치본(`/root/OCUDU`, `release_26_10`, `e0db566a`)에서 읽었다.
  사본: `(스크래치패드)/ocudu-src/` — `io_broker_epoll.cpp`, `io_broker_epoll.h`,
  `sctp_network_server_impl.cpp`, `sctp_socket.cpp`, `sctp_network_gateway_common_impl.cpp`
- 사고 당시 CU 로그는 복구를 위한 재시작 때 truncate되어 소실됐다. 본문 발췌는 사고 직후
  세션에서 읽은 내용이다. 재현 시 로그를 먼저 보존할 것
- 관련 측정 기록: `artifacts/verify-20261021/`
