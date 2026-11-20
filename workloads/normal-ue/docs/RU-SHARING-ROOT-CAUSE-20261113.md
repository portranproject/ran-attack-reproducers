# OAI `--num-ues` RU-sharing 불안정성 원인 분석 (2026-11-13)

> 이 문서는 2026-11-13 원인 분석 기록이다. 현재 운영 구성과 패치 스택은 [정상 UE README](../README.md)를 따른다.

## 결론

현재 5 UE 정상 풀의 주된 불안정 원인은 코어·가입자·ZMQ broker가 아니라 OAI UE에
추가한 RU-sharing의 **단일 상향 batch 집계 방식**이다.

`rss_shared_write()`는 `(timestamp, nsamps, nant)`가 같은 쓰기를 하나의 열린 batch에
더하고 호출 횟수가 UE 수에 도달하면 전송한다. 그러나 다섯 UE thread 중 다음 timestamp를
가진 호출이 먼저 도착하면, 아직 다섯 UE가 모이지 않은 기존 batch를 즉시 partial flush한다.
뒤늦게 도착한 UE가 이전 timestamp를 다시 열어 전송하면서 ZMQ 장치가 이미 지난 timestamp로
판단해 해당 상향 sample을 버린다. 로그에는 `Error, channel timeout`으로 나타난다.

하향 read cursor의 lockstep은 PHY thread의 상향 write 완료 순서까지 보장하지 않는다.
실측에서 lockstep timeout인 `bail`은 0이었지만 partial flush와 timestamp 역행이 발생했다.
따라서 phase·재시도 간격이나 lockstep 대기시간을 늘리는 것은 근본 해결이 아니다.

## 코드 경로

1. `--num-ues > 1`이면 `nrue_ru_sharing_enabled()`가 켜진다.
2. 하향은 공용 ring을 UE별 cursor로 읽고 read cursor만 lockstep으로 맞춘다.
3. 상향은 하나의 `wr_ts/wr_joined/wr_acc` batch만 유지한다.
4. 새 key가 오면 `wr_joined < n_ue`여도 `rss_flush_locked()`를 호출한다.
5. 늦은 UE의 과거 timestamp batch는 ZMQ `align()`에서 폐기된다.

관계 코드는
`reproducers/authentication-timeout-exhaustion/patch/ru-sharing-w38.patch`의
`rss_shared_read()`, `rss_flush_locked()`, `rss_shared_write()`에 있다.

## 비교 실험

동일한 CU·DU·broker·가입자·PDU 설정을 사용하고 정상 풀의 `--num-ues`만 바꿨다.

| run | `--num-ues` | RU-sharing | channel timeout | RRC complete | Registration/PDU | 결과 |
|---|---:|---|---:|---:|---:|---|
| `rootcause-n1b-20261113` | 1 | 꺼짐 | 0 | 1 | 1/1 | ping 288/288, 통과 |
| `rootcause-n2-20261113` | 2 | 켜짐 | 6 | 8 | 0/0 | 실패 |
| `rootcause-n5diag-20261113` | 5 | 켜짐 | 15 | 6 | 0/0 | 실패 |

5 UE 진단 binary는 첫 2,000 flush까지 다음을 추가 계측했다.

- partial flush: 4
- 중복 UE contributor: 0
- timestamp 역행: 1회, 11,520 samples
- lockstep wait: 9,209
- lockstep bail: 0

즉 관측된 원인은 같은 UE의 중복 합산이 아니라, 서로 다른 UE thread의 write 순서가
엇갈릴 때 하나뿐인 열린 batch를 미완성 상태로 닫는 것이다.

기존 5 UE 7개 표본도 같은 현상을 보였다. 마지막 누적 시점 기준 상향 batch의
19.93~28.91%가 역행했고 실행별 channel timeout은 28,914~194,548회였다. 일부 실행에서
2/5 PDU가 성공한 것은 문제가 없는 것이 아니라, 폐기되지 않은 상향 절차만 우연히 끝까지
진행한 결과다.

`rootcause-n1-20261113`의 단일 UE 첫 실행은 UE가 RRCSetupComplete를 생성했지만 CU가
먼저 context release를 시작한 별도 timing race가 있어 비교 근거에서 제외했다. 초기 지연과
재시도 간격을 줄인 `rootcause-n1b-20261113`은 2초 안에 등록·PDU·ping을 통과했다.
두 설정 변경 중 어느 것이 timing race를 제거했는지는 이 분석에서 분리하지 않았다.

## 증거

원문은 p5 DU `/root/normal-ue-qualification/rootcause/`에 보존했다.

- `rootcause-n1b-20261113/result.json`:
  `8eaa1f9e2293f6d112eafa26e3e5458b25e1f0cb6e158a430531087fae91b8b5`
- `rootcause-n1b-20261113/ue2.log`:
  `1fa6a0ab55a65f12336d29e440e47db764d9358843c9aa0be0e38b2eeea51e5b`
- `rootcause-n2-20261113/result.json`:
  `8b3b5b91bb416683f810cf9ed0d34426f5544475695adaceedfb199acc0611ca`
- `rootcause-n2-20261113/ue2.log`:
  `7d9d694b3d8101bed29cd405e601ba5efb39749c7c5f2ebf2c9243e01f727b42`
- `rootcause-n5diag-20261113/result.json`:
  `c6cc4820bea01eaea69b02dc847f1bde2d92f1f5cfbfbc44ce8d889f0f7f44e4`
- `rootcause-n5diag-20261113/ue2.log`:
  `0021f1f851af01abe6cb20b87d97caa127f105038bfe98131e76c4d28598cc4d`

진단 binary SHA-256은
`92fc68a645bb0b4d80353acfa9691bfa8881f618a7fd731854da598a6aacdc80`이다. 진단 뒤
소스와 운영 binary를 먼저 원복했으며, 그 시점의 binary SHA-256은
`6f9a43087966df2810c8749bd60f32efd952b248c6a2e15927aca8dd865a77e2`였다. 아래 해결 패치를
적용한 최종 binary hash는 [p5 자격 검증](P5-QUALIFICATION-20261113.md)에 따로 기록했다.

## 적용한 해결

상향 집계기를 더 복잡하게 고치는 대신 정상 풀에서는 공유 자체를 없앴다.

1. 하나의 OAI 프로세스에 UE 수와 같은 수의 virtual RU를 생성한다.
2. UE마다 독립 ZMQ endpoint를 배정한다.
3. GNU Radio broker가 5개 상향을 합치고 하나의 DU endpoint로 전달한다.
4. `nrue_ru_sharing_enabled()`는 `UE 수 > RU 수`일 때만 참으로 바꾼다.

따라서 정상 5 UE/5 RU에는 문제가 난 custom batch 집계가 개입하지 않고, 기존 공격 도구의
다중 UE/1 RU 경로는 그대로 유지된다. gNB 입장에서는 broker가 합친 하나의 RF·동일 셀이므로
대시보드 셀 분리 문제도 생기지 않는다.

`normal-multi-ru.patch`를 적용한 p5 cold-start 3회는 모두 Registration/PDU/ping 5/5,
channel timeout 0, crash 0으로 통과했다. 최초 ping 수렴은 12.7~62.3초였다. 종료 후 UE,
broker, TUN 잔존도 0이었다. 상세 해시는 [p5 자격 검증](P5-QUALIFICATION-20261113.md)에
기록했다.

timestamp별 ordered queue와 bounded flush도 진단 중 시험했지만 반복 5/5를 만들지 못했고
공유 경로 복잡도만 키우므로 운영 패치에 포함하지 않았다. `RSS_SHARE_WR_MONOTONIC=1`처럼
늦은 timestamp를 미래로 강제 이동하는 방식도 접속 시도를 급감시켜 제외했다.
