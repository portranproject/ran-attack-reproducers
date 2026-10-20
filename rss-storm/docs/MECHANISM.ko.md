# A형 RSS는 왜 통하는가 — 소스·설정·실측으로 본 성립 조건

이 문서는 "`RRCSetupComplete`를 안 보내면 기지국이 왜 무너지는가"에 대한 답이다.
주장마다 근거의 **종류**를 밝힌다.

| 표기 | 뜻 |
|---|---|
| (소스) | 기지국 소스 코드를 읽어 확인. 실행으로 확인한 것이 아니다 |
| (규격) | 3GPP 규격 문서 |
| (논문) | 공개 논문의 실험 결과. 해당 논문의 환경에서 나온 수치다 |
| (실측) | **이 테스트베드에서 실행해 측정.** 출처는 [MEASUREMENTS.md](MEASUREMENTS.md) |
| (추론) | 위 근거들로부터의 추론. 직접 확인한 사실이 아니다 |

인용한 OCUDU 소스의 줄 번호는 커밋 `440cdbb` 기준이다. 시험 대상은 OCUDU
26.10이었으므로 **줄 번호는 설치본과 다를 수 있다.** 기본값과 동작은 실측과
대조했고, 어긋난 지점은 §3.4와 §9에 적었다.

---

## 1. 한 문장과 식

> A형 RSS는 **인증 이전에**, 완료하지 않을 RRC 연결 설정 절차를 빠르게 반복해,
> 기지국이 미완료 시도를 정리하지 않는 **보유 시간** 동안 UE 컨텍스트와 전용
> 무선 자원을 붙잡아 고갈시키는 공격이다.

성립 여부는 세 숫자로 결정된다.

```
점유량      N      ≈  R × T_hold            (리틀의 법칙 꼴)
포화 조건   R × T_hold  ≥  N_cap
채움 시간   T_fill =  N_cap / R
```

- `R` — 공격자가 만드는 초당 시도 수. **공격자가 올릴 수 있는 유일한 항** (§6)
- `T_hold` — 기지국이 미완료 컨텍스트를 붙잡는 시간. **기지국 설정이 정한다** (§3)
- `N_cap` — 먼저 바닥나는 자원의 한도. **기지국 설정이 정한다** (§5)

공격이 통하는 이유는 이 식이 성립할 수 있기 때문이고, 그 이유는 다시 세 가지다.
**자원이 인증보다 먼저 잡히고**(§2), **망 쪽에 그것을 즉시 회수할 타이머가 표준에
없고**(§3), **코어가 아예 관여하지 않아 코어 쪽 방어가 닿지 않는다**(§4).

---

## 2. 자원은 인증보다 먼저 잡힌다

### 2.1 Msg3 한 통에 할당되는 것

OCUDU DU는 단말 객체 생성을 **Msg3 수신 시점까지 미룬다**. MAC 문서가 "the
creation of a new UE in the DU is deferred until Msg3 is received"라고 명시한다
(소스) [S1]. 즉 프리앰블만으로는 아무것도 잡히지 않는다. 그러나 `RRCSetupRequest`
한 통이 도착하면 그 자리에서 다음이 생긴다 (소스) [S2][S3][S4].

| 위치 | Msg3 수신 시 할당되는 것 |
|---|---|
| DU | 단말 컨텍스트, C-RNTI, **전용 상향 제어 자원(SR·CSI·SRS)**, SRB0/SRB1, F1AP·RLC·MAC 단말 객체 |
| CU-CP | gNB-CU UE F1AP ID, UE 컨텍스트, RRC 단말 객체, **RRC 설정 트랜잭션과 그 제한 시간 타이머** |

여기서 **전용 상향 제어 자원이 핵심이다.** 이것이 §5의 용량 한도를 직접 결정한다.
그리고 이 모든 할당은 가입자 인증보다 한참 앞이다. `RRCSetupRequest`에는 IMSI를
실을 칸 자체가 없고, 가입자 식별은 Msg5에 실리는 NAS 메시지 이후의 일이다
(규격) [T1, §6.2.2]. 따라서 **기지국은 "누구인지 모르는 상대"에게 자원을 먼저 주고
나중에 확인한다.** 이 비대칭이 공격의 토대다.

A형이 TCP SYN 플러딩과 같은 계열인 이유가 이것이다. 핸드셰이크 중간 상태를
서버가 먼저 기억하고, 그 상태를 공격자가 공짜로 만들 수 있다.

### 2.2 그런데 Msg4까지는 받아야 한다

Msg3만 보내고 사라지면 될 것 같지만 안 된다. **경합 해소가 끝나지 않으면 절차가
성립하지 않는다.** Msg4의 HARQ ACK은 "경합 해소 성공" 신호이며, 단말이 자기
식별자가 맞다고 확인했을 때만 생성된다 (규격) [T2, §5.1.5, §5.3.2.2].

이것은 추론이 아니라 측정으로 확인됐다. Msg3 직후 포기하는 변종(`MSG4_WAIT=0`)은
UE 쪽 로그상 5배 빨라 보였지만, **시도 10,878건에 대해 기지국이 만든 컨텍스트는
1개였다** (실측) [M, §5]. 그래서 이 도구는 Msg4를 기다리고 HARQ ACK까지 보낸 뒤
멈춘다. 재현기의 `MSG4_WAIT=1`을 바꾸지 말라고 적어 둔 이유다.

**공격자가 멈추는 지점은 정확히 한 곳이다**: Msg4 HARQ ACK 직후, `RRCSetupComplete`를
보내야 할 자리.

UE 패치가 실제로 하는 일도 그 한 지점이다. `openair2/RRC/NR_UE/rrc_UE.c`의
DL-CCCH 처리에서 `rrcSetup` 분기만 갈아낀다 — 정상 처리 함수
`nr_rrc_process_rrcsetup()` 호출을 건너뛰고, 단말의 T300을 멈추고, 바로 다음 시도를
예약한다. 패치 주석 그대로다.

> "A-type: Msg4 is accepted and MAC still sends the HARQ ACK, but
> `nr_rrc_process_rrcsetup()` is skipped, so no cell group is applied, no
> `RRCSetupComplete` is generated and RRC stays in IDLE."
> — [patch/rss-ue.patch](../patch/rss-ue.patch)

MAC 계층은 손대지 않으므로 HARQ ACK은 정상적으로 나간다. 기지국이 보기에 이
단말은 **경합 해소까지 성공한 정상 단말**이고, 그다음부터 응답이 없을 뿐이다.

---

## 3. 왜 자원이 즉시 풀리지 않는가 — 보유 시간의 출처

### 3.1 망 쪽에는 "Msg5 대기 타이머"가 표준에 없다

A형이 가능한 가장 구조적인 이유다. `RRCSetup`을 보낸 뒤 `RRCSetupComplete`를
얼마나 기다릴지는 **3GPP가 정하지 않는다.** T300은 단말이 돌리는 타이머이고
(규격) [T1, §7.1.1], 미완료 절차를 언제 정리할지는 구현에 맡겨져 있다.

여기서 두 가지가 따라온다.

1. **공격자는 자기 T300을 자유롭게 다룰 수 있다.** 단말 타이머이므로 패치가
   멈춰도 기지국은 모른다. 실제로 이 도구는 Msg4를 받은 뒤 T300을 정지시킨다.
2. **보유 시간은 기지국 구현·설정의 값이다.** 공격자가 바꿀 수 없지만,
   운영자는 바꿀 수 있다 — 즉 **방어 가능한 파라미터**다.

### 3.2 OCUDU에서의 보유 시간

OCUDU CU-CP의 RRC 설정 절차는 제한 시간을 이렇게 계산한다 (소스) [S5, L41].

```cpp
procedure_timeout = context.cell.timers.t300 + context.cfg.rrc_procedure_guard_time_ms;
```

| 항 | 기본값 | 설정 키 | 출처 |
|---|---:|---|---|
| `t300` | 1000 ms | `cell_cfg.sib.t300` (DU, SIB1로 방송) | (소스) [S12] |
| RRC 절차 가드 | 1000 ms | `cu_cp.rrc.rrc_procedure_guard_time_ms` (CU) | (소스) [S11] |
| **합** | **약 2000 ms** | | |

**보유 시간이 t300에 묶여 있다는 점이 중요하다.** t300은 단말에게 "이만큼 기다려라"
라고 방송하는 값인데, OCUDU는 같은 값을 자기 정리 시점의 기준으로도 쓴다. 공격
단말은 t300을 지키지 않으므로, 이 값을 늘리면 **정상 단말의 인내심과 공격자의
점유 시간이 함께 늘어난다.** 3GPP가 정한 t300의 최대값은 2000 ms다 (규격) [T1].

### 3.3 타임아웃 뒤에 일어나는 일

응답이 오지 않으면 CU-CP는 실패 원인을 `no_reply`로 기록하고 해제를 진행한다
(소스) [S5, L62–L66]. 경로는 다음과 같다.

```
타임아웃 → no_reply 기록
        → NG 컨텍스트가 없으므로 NGAP 해제 요청을 건너뛴다
        → F1 UE Context Release Command (SRB1에 RRCRelease 실어서)
        → DU는 RRC 컨테이너 전달 ACK를 최대 120 ms 기다린 뒤 단말 삭제
```

(소스) [S5][S6][S7]. 공격 단말은 이미 다음 시도로 넘어갔으므로 `RRCRelease`를
받지 않는다. 즉 **해제조차 기지국 혼자 처리한다.**

### 3.4 실측: 예측과 맞은 곳, 어긋난 곳

| | 소스 예측 | 실측 | 판정 |
|---|---:|---:|---|
| 기본 설정 보유 시간 | 1000 + 1000 = **2000 ms** | 중앙값 **1896 ms** | 일치 (실측) [M, §3] |
| 모드 B 보유 시간 | 2000 + 5000 = **7000 ms** | 중앙값 **1457–1846 ms** | **어긋남** (실측) [M, §4, §8] |

어긋남의 원인은 종료 사유 분포가 알려 준다. 36.5분 런에서 절차 종료 사유는
`cancelled` 12,339건 대 `timed out` **1건**이었다 (실측) [M, §8]. 즉 모드 B에서는
**CU의 가드 타임아웃이 걸리기 전에 DU 쪽에서 먼저 해제가 일어난다.**

여기서 실무적으로 중요한 결론이 나온다. **"설정값을 더하면 보유 시간"이라는 계산은
기본 설정에서만 맞았다.** 그래서 이 도구는 보유 시간을 `-H`로 받고, 설정에서
유도하지 말고 로그에서 재라고 요구한다. 점유 제어기(`-o`)의 정확도가 이 값에
직접 달려 있다.

---

## 4. 왜 코어 쪽 방어가 닿지 않는가

`RRCSetupComplete`가 없으면 CU는 AMF로 NGAP `InitialUEMessage`를 보내지 않는다
(소스) [S5, L126], (규격) [T3, §8.1]. 36.5분 런에서 `InitialUEMessage` **0건**으로
확인됐다 (실측) [M, §8].

결과는 양날이다.

- **방어 쪽에 불리한 면**: 코어는 공격을 아예 보지 못한다. 가입자 기반 차단,
  NAS 레벨 레이트 제한, AMF 과부하 제어가 전부 무의미하다. 압박은 기지국 내부에만
  존재한다.
- **탐지 쪽에 유리한 면**: 신호가 깨끗하다. `rrcSetupComplete` 0과
  `InitialUEMessage` 0은 "이 부하가 전부 미완료 시도"라는 증명이 된다. 이 도구가
  두 값을 판정 기준으로 출력하는 이유다.

관측 경계도 여기서 정해진다 (추론).

| 관측 지점 | A형이 보이는가 |
|---|---|
| Msg1·Msg2, Msg4 HARQ ACK | 안 보임. DU의 MAC·PHY 안에서 끝난다 |
| F1-C (Initial UL RRC → DL RRC → 무응답 → 해제) | **보임.** 시도 단위 관측이 가능한 유일한 경계 |
| E2SM-KPM | **간접적으로만.** `RRC.ConnEstabAtt − ConnEstabSucc` 차이로만 드러난다. 실제 실패 원인 `no_reply`는 KPM에 노출되지 않고, 보고 주기도 최소 1초다 (소스) [S16] |
| 코어(AMF) | 안 보임 |

용량이 차서 DU가 단말 생성 자체를 거부하는 단계(§5.3)는 F1AP 객체 생성 **전에**
끝나므로 F1과 CU에도 보이지 않고 DU 로그와 스케줄러 지표에만 남는다 (추론)
[S8, L233–L241].

---

## 5. 무엇이 먼저 바닥나는가 — 용량의 출처

### 5.1 OCUDU의 한도 계산식

OCUDU DU는 셀마다 단말 객체를 최대 2048개 둘 수 있다 (소스) [S10]. 그중
**64개는 `RRCReject`를 보낼 단말용으로 예약**된다 (소스) [S9].

```
수립 가능 수 = min( 가용 SR 설정 수,
                    (주기적 CSI를 쓰면) CSI 설정 수,
                    (주기적 SRS를 쓰면) SRS 자원 수,
                    2048 − 64 )
셀 최대 단말 객체 = 수립 가능 수 + 64
```

(소스) [S8, L197–L212][S9]. DU 기동 로그가 이 구조를 스스로 설명한다.

> "This is determined by the lowest of the following limits: SR ({}), CSI ({}),
> SRS ({}) and UE contexts per cell ({}). Up to {} UE contexts can be created in
> the cell, the extra ones being used to RRC Reject UEs." [S8, L136–L138]

**즉 용량을 정하는 것은 메모리나 CPU가 아니라 상향 제어 자원의 수다.** 2048은
사실상 걸리지 않는 상한이고, 실제 한도는 SR·CSI·SRS 쪽에서 먼저 걸린다. 같은 로그가
이 값조차 상한일 뿐 "the actual number might be lower than that"이라고 밝히므로,
**실제 값은 기동 로그에서 읽어야 한다** (소스) [S8, L135–L136].

### 5.2 우리 셀의 값

| | 값 | 출처 |
|---|---:|---|
| 기본 설정 용량 | **96** | DU 기동 로그에서 확인 (실측) |
| 모드 B 용량 | **12** | `nof_cell_sr_res` 8 → 1 적용 후 (실측) |

`nof_cell_sr_res`(셀 SR 자원 수)를 내리면 위 `min()`의 첫 항이 내려가므로 용량이
같이 내려간다. `bin/rss-gnb-profile`이 하는 일이 정확히 이것이고, **기지국 소스는
건드리지 않는다.**

CU-CP 쪽 단말 상한(`max_nof_ues`, 기본 8192)은 훨씬 뒤에 걸린다 (소스) [S11].
그래서 A형에서 먼저 아프는 곳은 언제나 **DU의 셀 단위 자원**이다.

### 5.3 한도에 닿은 뒤 — 두 단계로 나빠진다

1. **수립 가능 수가 차면 `RRCReject`.** 거절용 64개 자리를 써서 거절 메시지를
   보낸다 (소스) [S8][S9].
2. **거절용까지 차면 단말 생성 자체를 거부.** 이때는 Msg4가 아예 나가지 않고
   (소스) [S2, L44–L50][S8, L233–L241], 정상 단말은 경합 해소 타이머가 만료된 뒤
   Msg1부터 다시 시도한다 (추론).

실측에서 두 단계가 모두 관측됐다. 모드 B 200초 구간에서 `RRCReject` 7,551건
(61.3/s)과 `DU is not able to serve the UE` 2,517건(20.4/s)이 동시에 나왔다
(실측) [M, §4]. **서비스 거부가 이 공격의 실제 결과물이다.**

정상 사용자 쪽 증상은 논문이 보고한다. KAUST 실험에서 상용 폰은 여러 번
시도해도 접속하지 못했고 (논문) [P1], Nguyen 실험에서 기지국 가용률은 4.02%,
곧 약 95% 불가용이었다 (논문) [P2].

---

## 6. 성립 조건의 산수 — 왜 "그냥 돌리면" 안 되는가

### 6.1 기본 설정에서는 유지되지 않는다

§1의 조건 `R × T_hold ≥ N_cap`에 §3·§5의 값을 넣으면 필요한 시도율이 나온다.

| | `N_cap` | `T_hold` (실측) | 필요한 `R` | 이 도구의 `R` (실측) | 결과 |
|---|---:|---:|---:|---:|---|
| 기본 설정 (모드 A) | 96 | 약 1.9 s | **약 48/s** | 33–38/s | 용량에 **버스트로만** 도달. 96에서 최장 평탄 구간 0.93초 |
| 포화 프로필 (모드 B) | 12 | 약 1.6 s | **약 7.5/s** | 5.6–6.5/s | **포화 유지.** 거부가 36.5분 연속 |

(실측) [M, §3, §4, §8]. 참고로 KAUST가 OAI에서 측정한 공격자 시도율은 약 25회/초로
(논문) [P1], 우리 33–38/s와 같은 자릿수다. **즉 "시도율이 부족한 것"은 이 도구의
결함이 아니라 공격 자체의 물리적 한계에 가깝다** (추론).

### 6.2 조건을 맞추는 방향은 셋뿐이다

식을 보면 선택지가 자동으로 정해진다.

| 항 | 누가 바꾸는가 | 이 프로젝트에서 |
|---|---|---|
| `N_cap` ↓ | 운영자(설정) | 모드 B: `nof_cell_sr_res` 8 → 1 (96 → 12) |
| `T_hold` ↑ | 운영자(설정) | 모드 B: `t300` 1000 → 2000, 가드 1000 → 5000 |
| `R` ↑ | **공격자** | §6.3 |

앞의 둘은 공격자가 못 바꾼다. 그래서 모드 B는 "공격을 세게 만든 것"이 아니라
**방어 측 설정을 불리한 쪽으로 돌려 둔 조건에서 탐지를 검증하는 것**이다. 이 구분을
흐리면 "포화시켰다"는 주장이 과장된다.

### 6.3 공격자가 R을 올린 유일한 실질 수단은 무선 경로였다

`R`을 올리려는 시도 중 실제로 효과가 있었던 것은 **ZMQ 송신 스레드의 깨우기
방식 하나**였다 (실측) [M, §1].

| | 수정 전 | 수정 후 |
|---|---:|---:|
| 시도/초 | 6.7 | **19.5–33.8** |
| 피크 점유 | 20 / 96 | **90–96 / 96** |

원인은 상수 하나였다. 업스트림의 송신 폴 스레드는 소켓 이벤트로만 깨어나는데,
샘플 요청은 왔지만 로컬 큐가 비어 있으면 상대는 응답을 기다리며 아무것도 보내지
않는다. 그래서 `zmq_poll`이 **자기 타임아웃 10 ms**로만 복귀한다. 굶은 요청
4,250건 × 10.01 ms = 80초 런에서 42.5초 손실 — 프로세스 수명의 85%다.

**이것은 호스트 성능 문제가 아니었다.** UE와 DU는 `127.0.0.1`로 통신하고 왕복은
수십 마이크로초이므로, 10 ms는 지연이 아니라 타임아웃 상수일 수밖에 없다.
1 ms 미만의 늦음이 무선 프레임 하나를 통째로 잡아먹고 있었다.

반면 효과가 없었던 것들(코어 핀닝, 스핀 대기, 로그 레벨 조정)은 모두
**시도 주기의 비용 구조**로 설명된다. 한 주기는 무선 시간 40 ms를 쓰고 그중
30 ms가 랜덤 액세스 절차 자체다. 이 30 ms는 벽시계 시간이 6배 차이 나는 두 세션에서
동일했다 — 호스트 속도가 아니라 **공중 인터페이스 스케줄**이 정하는 양이라는 뜻이다
(실측) [M, §2]. 그래서 UE 쪽 최적화로는 줄일 수 없다.

### 6.4 왜 UE 인스턴스 2개가 상한인가

MAC 하나는 랜덤 액세스를 한 번에 하나씩만 진행한다 (규격) [T2, §5.1.1]. 그래서
`R`을 더 올리려면 단말 인스턴스를 늘려야 한다. 그런데 측정 결과 **2개를 넘으면
시도율이 늘지 않는다** (실측) [M, §3].

| UE | 시도/초 | 샘플 손실 | 200 ms 이상 공백 |
|---:|---:|---:|---:|
| 1 | 33.8 | 0 | 0 |
| 2 | **38.6** | 5,136 | 5% of run |
| 4 | 37.4 | 39,765 | 45% of run |

모든 인스턴스가 무선 하나와 DU MAC 하나를 공유하므로 공유 계층이 36–38/s에서
포화되고, 그 뒤로는 **샘플 손실만 늘어난다.** 손실은 1초 단위 정지로 나타나고
정지 중에는 점유가 빠지므로, 인스턴스를 늘리면 오히려 포화 유지에 불리하다.

---

## 7. 공격자가 조작하는 값과, 기지국이 무시하는 값

### 7.1 기지국이 실제로 보는 것

| 공격자가 바꾸는 값 | OCUDU의 수락·거절 판단에 주는 영향 | 근거 |
|---|---|---|
| `RRCSetupComplete` 생략 | **결정적.** 보유 시간 전체를 점유한다 | §2–§3 |
| 시도 간격 (`-i`), 인스턴스 수 (`-u`) | `R`을 정한다 → 포화 여부 | §6 |
| 초기 UE identity (무작위/5G-S-TMSI-Part1) | **없음.** 저장만 하고 중복을 검사하지 않는다 | (소스) [S4, L90–L98] |
| `establishmentCause` | **없음.** 지표 기록에만 쓰이고 우선 수용 로직이 없다 | (소스) [S4, L68, L105] |

뒤의 두 줄이 탐지 설계에 직접 영향을 준다. **identity와 접속 원인은 기지국의
동작을 바꾸지 못하지만, 탐지기가 보는 특징은 바꾼다.** 즉 "매 시도 새 무작위
identity"는 공격을 강하게 만들지 않고 탐지 난이도만 조절한다. 재현기가 이 값을
노브로 노출하는 이유이자, 탐지기가 이 특징에만 의존하면 안 되는 이유다 (추론).

### 7.2 `RRCReject` — OCUDU 기본값이 공격자에게 유리하다

`RRCReject`에는 단말을 쉬게 하는 `waitTime`을 실을 수 있고, 이것을 받은 단말은
T302 동안 재시도를 멈춘다 (규격) [T1, §5.3.15.2]. 그러나 **OCUDU는 기본적으로
`waitTime`을 보내지 않는다.** 설정 주석이 명시한다: "If not provided, no waitTime
field will be sent with RRC Reject" (소스) [S11].

따라서 기본 설정에서는 **지킬 T302 자체가 존재하지 않는다.** 이 도구의 `-r`
노브가 이 공백을 다룬다.

| 설정 | 동작 | 모드 B 200초 구간 실측 |
|---|---|---|
| `-r 1` (기본) | T302가 있으면 지키고, 없으면 재현기 자체의 기본 백오프 1000 ms를 적용 | 시도 5.6/s, 런의 95%를 쉼. `RRCReject` 388건 |
| `-r 0` | 거절을 무시하고 10 ms 후 재시도 | 시도 6.5/s, `RRCReject` **7,551건(61.3/s)**, 점유 ≥ 6/12를 구간의 100% 유지 |

(실측) [M, §4]. **포화를 유지시키는 것은 `-r 0`이다.** 다만 기본값을 `-r 1`로 둔
것은 의도적이다. 거절을 지키는 공격 단말은 표준을 따르는 단말도 낼 수 있는 부하를
재현하므로, 탐지기가 "예의 바른 공격"도 잡는지 확인할 수 있다.

여기서 방어 측 함의가 하나 나온다. **`rrc_reject_wait_time_s`를 설정하는 것은
공짜 완화책이 아니다.** 공격자는 무시하고(`-r 0`), 정상 단말만 기다린다. 완화
효과는 "표준을 지키는 단말이 만드는 부하"에만 작동한다 (추론).

---

## 8. 이 공격이 통하지 않는 조건

반증 가능성을 적어 두는 것이 이 문서의 목적 중 하나다. 아래가 참이면 A형은
실패하거나 의미를 잃는다.

| 조건 | 왜 실패하는가 | 근거 |
|---|---|---|
| `R × T_hold < N_cap` | 첫 컨텍스트가 정리되기 전에 한도를 못 채운다. 기본 설정 + 단일 무선이 실제로 이 경우다 | §6.1 (실측) |
| Msg4를 기다리지 않음 | 경합 해소가 끝나지 않아 Msg3이 기지국에 도달하지 않는다. 시도 10,878건 → 컨텍스트 1개 | §2.2 (실측) |
| AMF나 CU-UP가 연결돼 있지 않음 | OCUDU는 **모든** `RRCSetupRequest`를 거절한다. 공격이 통하는 게 아니라 **실험 자체가 성립하지 않는다.** 실험 전 코어 연결 확인이 필수인 이유다 | (소스) [S15] |
| 셀 파라미터 불일치 | 셀 탐색에서 멈춘다. 시도 0 | §6, 실패 모드 |
| 탐지 후 선별 해제가 동작함 | KAUST는 TA 버킷별 반열림 카운터로 공격 버킷을 선별 해제하고, 그 버킷의 새 시도에는 정상 단말이 완료할 수 있는 짧은 시간만 주는 완화책을 제시했다 | (논문) [P1] |

반대로, **공격을 막지 못하는 것**도 분명히 해 둘 가치가 있다. 경합 해소 타이머
만료는 스케줄러에서 단말을 비활성화할 뿐이고(기본 64 ms) (소스) [S13][S14], DU
컨텍스트와 전용 자원은 CU 타임아웃 뒤 F1 해제에서 풀린다 (소스) [S5][S6]. 즉
**짧은 MAC 타이머는 A형의 자원 점유를 끊지 못한다.**

---

## 9. 아직 확인되지 않은 것

1. **설치본의 로드된 설정값.** `t300`과 가드의 실제 로드값을 덤프해 확인하지
   않았다. 기본 설정 보유 시간 실측 1896 ms가 기본값 합 2000 ms와 일치하는 것이
   간접 증거다.
2. **모드 B의 조기 해제 경로.** `cancelled`가 지배적인 이유(DU 쪽 어느 경로가 먼저
   해제하는지)를 소스에서 특정하지 않았다.
3. **용량 96의 유도 과정.** 기동 로그에서 읽은 값이며, SR·CSI·SRS 중 어느 항이
   96을 결정했는지 분해하지 않았다.
4. **정상 단말의 서비스 거부 실측.** ZMQ 포트 쌍 하나로는 공격자와 정상 단말을
   동시에 붙일 수 없어 이 경로에서는 측정할 수 없다. 거부의 근거는 기지국이 내는
   `RRCReject`·`DU is not able to serve the UE` 스트림이다.
5. **실 SDR OTA.** 모든 측정은 ZMQ 가상 무선에서 나왔다. OTA에서는 Msg4 ACK의
   타이밍 요구가 달라질 수 있다 (논문) [P1].
6. **소스 줄 번호와 설치본의 일치.** 인용은 `440cdbb` 기준이고 시험 대상은 26.10이다.

---

## 참고

### OCUDU 소스 (커밋 `440cdbb`)

| 키 | 파일 | 이 문서에서 쓰인 사실 |
|---|---|---|
| S1 | [`lib/mac/procedures.md#L55`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/mac/procedures.md#L55) | DU 단말 생성을 Msg3까지 미룬다 |
| S2 | [`lib/du/du_high/du_manager/procedures/ue_creation_procedure.cpp#L44`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/du/du_high/du_manager/procedures/ue_creation_procedure.cpp#L44) | Msg3 시점의 DU 자원 할당, 생성 거부 경로 |
| S3 | [`lib/cu_cp/du_processor/du_processor_impl.cpp#L590`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/cu_cp/du_processor/du_processor_impl.cpp#L590) | CU UE 컨텍스트·RRC 단말 생성 |
| S4 | [`lib/rrc/ue/rrc_ue_message_handlers.cpp#L65`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/rrc/ue/rrc_ue_message_handlers.cpp#L65) | `RRCSetupRequest` 처리, identity 미검사, `establishmentCause` 미사용 |
| S5 | [`lib/rrc/ue/procedures/rrc_setup_procedure.cpp#L41`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/rrc/ue/procedures/rrc_setup_procedure.cpp#L41) | **보유 시간 식**, `no_reply`, NGAP 미송신 |
| S6 | [`lib/f1ap/du/procedures/f1ap_du_ue_context_release_procedure.cpp#L39`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/f1ap/du/procedures/f1ap_du_ue_context_release_procedure.cpp#L39) | F1 해제 절차 |
| S7 | [`.../f1ap_du_ue_context_release_procedure.h#L33`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/f1ap/du/procedures/f1ap_du_ue_context_release_procedure.h#L33) | RRC 컨테이너 ACK 최대 120 ms 대기 |
| S8 | [`lib/du/.../du_ran_resource_manager_impl.cpp#L197`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/du/du_high/du_manager/ran_resource_management/du_ran_resource_manager_impl.cpp#L197) | 용량 식, 기동 로그 문구, 생성 거부 |
| S9 | [`lib/du/.../du_ran_resource_manager_impl.h#L69`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/du/du_high/du_manager/ran_resource_management/du_ran_resource_manager_impl.h#L69) | 거절용 컨텍스트 64개 예약 |
| S10 | [`include/ocudu/ran/du_types.h#L18`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/include/ocudu/ran/du_types.h#L18) | 셀당 단말 객체 2048 |
| S11 | [`apps/units/o_cu_cp/cu_cp/cu_cp_unit_config.h#L241`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/apps/units/o_cu_cp/cu_cp/cu_cp_unit_config.h#L241) | 가드 기본 1000 ms, `waitTime` 미송신, `max_nof_ues` 8192 |
| S12 | [`apps/units/flexible_o_du/o_du_high/du_high/du_high_config.h#L1073`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/apps/units/flexible_o_du/o_du_high/du_high/du_high_config.h#L1073) | `t300` 기본 1000 ms |
| S13 | [`include/ocudu/ran/prach/rach_config_common.h#L116`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/include/ocudu/ran/prach/rach_config_common.h#L116) | 경합 해소 타이머 기본 64 ms |
| S14 | [`lib/scheduler/ue_context/ue_repository.cpp#L434`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/scheduler/ue_context/ue_repository.cpp#L434) | 경합 해소 만료 시 비활성화만 수행 |
| S15 | [`lib/cu_cp/cu_cp_controller/cu_cp_controller.cpp#L83`](https://gitlab.com/ocudu/ocudu/-/blob/440cdbbee077e97e824db285bf227c15c84bd0bb/lib/cu_cp/cu_cp_controller/cu_cp_controller.cpp#L83) | AMF·CU-UP 부재 시 전부 거절 |
| S16 | [Supported E2 Metrics](https://docs.ocudu.org/knowledge_base/e2sm_kpm_metrics/) | KPM 노출 범위 |

### 규격·논문·측정

| 키 | 출처 |
|---|---|
| T1 | 3GPP TS 38.331 (RRC) — T300, `ue-Identity`, `waitTime`/T302 |
| T2 | 3GPP TS 38.321 (MAC) — 랜덤 액세스 1회 제한, 경합 해소와 HARQ ACK |
| T3 | 3GPP TS 38.401 (NG-RAN 아키텍처) — F1 시퀀스, NGAP 송신 시점 |
| P1 | A. Abou Hasna, A. El Falou, "Experimental Validation and Mitigation of RRC Storm Attacks in 5G Cellular Networks," [arXiv:2608.16441](https://arxiv.org/abs/2608.16441) |
| P2 | D. K. Nguyen, R. El Malki, F. Rebecchi, "RRC Signaling Storm Detection in O-RAN," [arXiv:2504.15738](https://arxiv.org/abs/2504.15738) |
| M | 이 저장소의 실측 기록 — [MEASUREMENTS.md](MEASUREMENTS.md) |
