# 제보문 초안 — OCUDU 재수립 경로의 인증 없는 제3자 컨텍스트 해제

> **상태: 초안. 발송 전 사용자 검수 필수.**
> 보내기 전에 확인할 것: ① 상류 srsRAN 동일 분기 존재 여부(미확인) ② 연락 경로
> ③ 공개 일정. 로그 발췌에 자격증명·가입자 식별자는 포함하지 않았다.

---

## 요약

OCUDU CU-CP 의 RRC 재수립 처리 경로에서, **인증되지 않은 요청 하나로 제3자 UE 의
컨텍스트를 해제**할 수 있다. 공격자는 AS 보안 컨텍스트가 필요 없고, 셀을 포화시킬
필요도 없으며, 기지국에 대한 어떠한 접근 권한도 필요 없다. 표준 Uu 인터페이스에서
UE 측 동작만으로 성립한다.

## 영향 범위 (정확히 한정)

**영향 있음**: 접속 수립 중인 UE. 실측상 접속 후 **약 7.16초 이내**의 컨텍스트가
대상이며, 그 안에 있으면 **이미 PDU 세션을 받아 서비스 중인 UE 도 포함**된다.

**영향 없음(실측)**: 접속 후 7.16초를 넘긴 컨텍스트. 축출 성공 120건 중 7.16초를
초과한 사례는 **0건**이다.

→ 따라서 이 결함으로 **셀 전체 마비나 지속적 서비스 거부는 성립하지 않는다.**
   영향은 "수립 중 UE 의 서비스 거부" 로 한정된다. 본 제보는 그 이상을 주장하지 않는다.

## 대상 버전

- OCUDU `release_26_10`, 커밋 `e0db566a` (CU/DU 분리 배치)
- 상류 srsRAN 에 동일 분기가 있는지는 **미확인**

## 기전

`lib/rrc/ue/rrc_ue_message_handlers.cpp` 의 `handle_rrc_reest_request` 는
`du_to_cu_container` 가 비어 있을 때 **(PCI, C-RNTI) 만으로** 기존 UE 를 찾아
`on_rrc_reestablishment_failure` 로 컨텍스트 해제를 요청한다.
이 분기에서는 `shortMAC-I` 가 검증되지 않는다 — 검증은
`rrc_reestablishment_procedure.cpp` 의 정상 경로에만 있다.

따라서 공격자는 `shortMAC-I = 0` 과 임의의 (PCI, C-RNTI) 를 담은
`RRCReestablishmentRequest` 를 CCCH 로 보내는 것만으로 그 (PCI, C-RNTI) 의
UE 를 끊을 수 있다.

### 표준과의 차이

TS 38.473 §8.4.1.2 는 이 상황에서 **새로 들어온 UE 를 거절**할 것을 요구한다.
OCUDU 가 추가한 "기존 UE 해제" 동작 자체가 표준 요구사항을 넘어서는 것이며,
그 추가 동작에 인증이 빠져 있다.

### 해제 메시지 두 형태 (둘 다 `shortMAC-I = 0` 으로 도달)

```
old_ue=N was not fully attached yet. Requesting UE context release
Requesting UE context release for old_ue=N
```

## 실증

차폐된 자체 테스트베드(격리 환경, 팀 자체 장비)에서 UE 측만 변조해 재현했다.
기지국 소스와 설정은 수정하지 않았다.

### 인과 사슬 (서비스 중 UE 가 끊긴 사례)

```
15:41:15.230641  ue=1623: "RRC Setup Procedure" finished successfully
15:41:15.457243  ue=1623: "Initial Context Setup Procedure" finished successfully
15:41:15.708461  ue=1623: "PDU Session Resource Setup Procedure" finished successfully
15:41:17.301741  ue=1639 c-rnti=0x4621: old_ue=1623 was not fully attached yet.
                 Requesting UE context release          ← 위조 요청, shortMAC-I = 0
15:41:17.303327  ue=1623: Tx SRB1 DCCH DL rrcRelease    ← 1.6 ms 뒤
```

같은 관측 창에서 `not able to serve` = 0, `rrcReject` = 0 —
**셀 용량 압력이 전혀 없는 상태에서 성립했다.**

주목할 점: `ue=1623` 은 PDU 세션까지 수립을 마친 UE 인데 로그는
`was not fully attached yet` 이라고 적는다. OCUDU 의 "fully attached" 판정이
실제 서비스 상태와 일치하지 않는다.

### 집계

| 항목 | 값 |
|---|---|
| 축출 성공(접속 시각 매칭) | **120건** |
| 축출 시점 컨텍스트 나이 | min 657 ms / p50 2,473 ms / max **7,157 ms** |
| 7.16초 초과 | **0건** |
| 분포 | 2~3초 구간에 61.7% |

## 권고 수정

해당 분기에서 기존 UE 를 해제하기 전에 **`shortMAC-I` 를 검증**할 것.
검증할 수 없는 경우에는 TS 38.473 §8.4.1.2 대로 **새 UE 만 거절**하고 기존 UE 는
건드리지 않는 것이 표준에 부합한다.

부수적으로, "fully attached" 판정이 NGAP/E1 수립 완료 상태를 반영하는지 점검을
권한다 (PDU 세션 보유 UE 가 `not fully attached` 로 분류됐다).

## 재현 도구

UE 측 패치와 실행 하네스를 보유하고 있다. 요청 시 책임 있는 공개 절차에 따라
제공할 수 있다. 공격 코드는 격리된 테스트베드 전용이며 공개 저장소는 비공개 상태다.

## 제보자

(사용자 기입)
