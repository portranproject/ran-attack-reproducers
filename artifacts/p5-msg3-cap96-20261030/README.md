# p5 DU capacity-96 Msg3-only 검증 (2026-10-30)

## 결론

DU capacity를 96으로 유지하되 RLF/CU 정리를 관측창 뒤로 미룬 hold32 진단에서,
`A_early` 재현기가 정상 probe 11/11을 10.13초 동안 거부했다. 기본 RLF 정책의 G21은
probe가 첫 시도에 연결됐으므로 기본 cleanup의 지속 거부 성공 증거는 아니다.

- 최종 공격 run: `G35-msg3-cap96-hold32-probe`
- 공격자: 같은 OAI 프로세스의 UE 1~3, 실제 MAC-confirmed Msg3 뒤 중단
- 정상 probe: UE 0, 공격 첫 Msg3 뒤 8초에 시작
- probe 관측창: 10.13초
- probe: 11 attempts, 11 Msg3, Msg4 0, Msg5 0, 연결 0
- probe TC-RNTI 11/11이 CU의 `RRCSetupRequest`와 일치했고, 모두
  `DU is not able to serve the UE`로 거부됐다.
- probe 시작 시 CU 재구성 미완료 절차 carry-in은 96이었다.
- 전체 run에서 `RRCSetupComplete=0`, `InitialUEMessage=0`이었다.
- run manifest와 민감정보 검사가 통과했다.

이는 shared ZMQ의 패킷 유실만으로 설명되는 실패가 아니다. 정상 probe의 요청이
CU까지 도달한 뒤 DU 자원 부족으로 거부된 것을 TC-RNTI로 확인했다. 다만 같은 OAI
프로세스의 통제된 probe이므로 독립 SDR/상용 UE의 OTA DoS 증거는 아니다.

## 중요한 정정: G4/G13은 capacity 96이 아니었다

앞선 `artifacts/p5-msg3-only-20261030`의 G4/G13/G14 설정 SHA
`7679413a...`에는 다음 override가 들어 있었다.

```yaml
cell_cfg:
  pucch:
    nof_cell_sr_res: 1
```

이 값 때문에 부팅 상한이 12였다. 따라서 G4/G13의 Msg3-only 절차와 probe 거부
결과는 유효하지만 **cap12 프로필** 결과다. 별도의 숨은 12-context pool을 발견한
것이 아니다. 실제 capacity-96 기준선은 이 override가 없는 SHA
`35ea900e8253013aeec398952d4a6c3c1f407880018d940270b53497700e0b17`이다.

## 왜 기본 capacity-96에서 처음에는 막히지 않았나

`G18`은 실제 Msg3-only로 96까지 채웠지만, 기본 `pucch.max_consecutive_kos=100`이
약 1.8초 뒤 CSI-DTX RLF를 만들고 기본 `t310=1000ms` 뒤 컨텍스트를 해제했다.
G26 첫 UE의 실제 흐름은 다음과 같다.

1. `02:57:17.801260` — DU context 생성
2. `02:57:19.605859` — `100 consecutive undecoded CSIs` RLF
3. `02:57:20.642678` — RLF timer 만료, F1 release 전송
4. `02:57:20.658743` — CU가 RRC Setup을 취소

G26 전체 RLF expiry 622건 중 613건(98.6%)이 CSI-DTX 원인이었다. 그래서 CU guard나
`t300`만 늘려도 DU가 먼저 F1 release를 보내 효과가 없었다.

중간 실험도 성공으로 과장하지 않는다.

| run | 결과 | 판정 |
|---|---|---|
| G21, 기본 RLF 정책 | 정상 probe가 첫 시도에 RRC 연결 | 지속 거부 반증 |
| G29, max KOs 200 | hold 중앙값 4.41초, 96 최장 1.59초 | 부족 |
| G30/G31, max KOs 400 | hold 7초, 96 최장 1.74/2.62초 | 부족 |
| G32, max KOs 400 | probe 3회 거부 뒤 4번째에 Registration/PDU 성공 | 지속 거부 반증 |
| G33 | 이전 DU의 F1-U 2152 점유로 새 DU 부팅 실패 | 무효, 사용 금지 |

## 최종 실험 프로필

gNB 소스와 capacity 값은 바꾸지 않았다. 부팅 로그는 계속 다음을 선언했다.

```text
upper-bound ... 96 ... SR (96), CSI (96), UE contexts per cell (1984)
```

실험 관측창 안에서 조기 해제 창만 없애기 위해 다음 두 프로필을 사용했다.

- DU: `du-cap96-t3002000-maxkos2000.yaml`
  - `pucch.max_consecutive_kos: 2000`
  - `sib.t300: 2000`
- CU: `cu-cap200-guard30000.yaml`
  - `max_nof_ues: 200` 유지
  - `rrc_procedure_guard_time_ms: 30000`

이 값들은 capacity를 늘리는 설정이 아니다. Msg3-only UE가 CSI를 내지 않을 때 DU가
RLF로 판정하는 시점과 CU가 미완료 RRC 절차를 정리하는 시점만 관측창 뒤로 미룬다.
정상 불량 링크 정리도 늦추므로 **실험 전용 프로필**이며 상시 운영값으로 쓰지 않는다.

프로필 SHA-256:

- DU: `4e093d750004f6215bb62c6bdb4e849ee23a7cbffc0e6af24cab60c7bf74d0dc`
- CU: `cdf0acec7e0bdcf29e183d7b55f403c62630cbe0ef2bf31493a60bc3049d53fe`

## paired 결과

### G34 — attack-off 정상 대조군

- `valid=true`, readiness check 통과
- capacity 96 부팅 확인
- `RRCSetupComplete`, Registration Accept, PDU Session Accept, TUN 구성 성공
- evidence manifest verify 통과

### G35 — attack-on + 정상 probe

- `valid=true`, `duration_limit_sigkill`, artifact scan 통과
- 2,206 attempts, 2,203 MAC-confirmed Msg3
- attacker Msg4 0, 전체 Msg4 0
- CU-derived labels: attacker 2,195행 중 exact Msg3-only 1,923,
  unknown 269, false 3; probe 11행은 모두 `rrc_reject`
- probe TC-RNTI 11개 모두 CU 요청·DU 자원 거절과 1:1 일치
- probe 관측창 동안 Msg4/Msg5/Registration/PDU/TUN 0
- 관측창 종료 시 공격 컨텍스트 96개가 살아 있었다.

G35의 같은 프로세스 무선에는 channel timeout 2,661건과 shared TX out-of-order
3.92%가 있었다. 그래서 무선 상태만으로 성공을 판정하지 않고, probe의 모든
TC-RNTI가 CU 자원 거절에 도달한 사실을 판정 근거로 사용했다.

## 재현 명령

기존 `rss-run`만 사용한다. 별도 wrapper는 필요 없다. p5에서 CU→DU 순으로 프로필을
적용하고, 먼저 attack-off control을 통과시킨 뒤 다음과 같이 실행했다.

```bash
env RSS_CONF=/dev/null \
  OAI=/root/OAI-rss-dujoin-20261030 \
  UE_BIN=/root/OAI-rss-dujoin-20261030/cmake_targets/ran_build/build/nr-uesoftmodem \
  PATCH=/root/rss-storm-dujoin-20261030/patch/rss-ue-curated.patch \
  LOGDIR=/root/rss-runs-msg3-cap96-20261030 \
  GNB_RESTART_CMD='/root/workspace/ctl.sh start' \
  GNB_STOP_CMD='/root/workspace/ctl.sh stop' \
  GNB_SETTLE_S=4 \
  GNB_READY_CMD='pgrep -x odu >/dev/null && grep -q "E2 Setup procedure successful" /tmp/odu.log' \
  GNB_READY_TIMEOUT_S=30 \
  /root/rss-storm-dujoin-20261030/bin/rss-run \
    -e 1 -u 4 -p 1 -t 8000 -M 0 -i 0 -d 30 \
    -n G35-msg3-cap96-hold32-probe
```

각 조치가 필요한 이유:

- attack-off control: 셀·코어·가입자 고장을 공격 효과로 오판하지 않는다.
- gNB readiness check: wrapper가 내부 DU 부팅 실패를 0으로 반환한 경우를 차단한다.
- 8초 probe 지연: capacity가 차기 전에 정상 UE가 먼저 접속하는 순서 오류를 제거한다.
- current-run CU slice: 이전 run의 재사용 RNTI를 섞지 않고 요청·거절을 조인한다.
- 30초 kill switch: 실험 범위를 제한하고 자동 종료한다.
- 종료 후 원복: 긴 RLF/guard가 정상 불량 UE 정리를 늦추는 운영 위험을 제거한다.

## 증거 해시

- OAI commit: `1c2f4d3c2e68181cdef9f426d161163147ad4b77`
- UE binary: `cc5b7569e68ce3d829dd2e8fb91a6c863bc9ea76a7cf66eac5e8b9a40bcebac2`
- RSS patch: `7b289c0fdbeb3e4c0d852b832c9805cc3f30af7c16998d5975bea775f74bcd1c`
- runner: `0fed456867024ad4116f4a20792412eff47e0e4cc2748b9a76f65e7b9d0f322a`
- G34 manifest: `174267251915ef60d458ec634fde851ed3ed1e3d06672ddaed1ed73cb82813e9`
- G35 manifest: `93c10890a0bc45d0d14889b2e51bfd789a86c18ff48a1c4601ebd46fb60aeac2`
- G35 CU slice: `e427c684aff7dc24e2e8d3a27183189b4409422b8f9a1e7ccd47ddff3ddd16d7`
- G35 CU-derived labels: `c1ef6c8ba0b814f7472c117e0a32621709d51140d6b20ae34068f91186a1b53f`

원격 G26 전체 DU 로그는 재기동 전에
`/root/G26-msg3-cap96-hold7-odu.log`로 보존했고 SHA-256은
`b1df5bc96e55de0f8fc0dd4467e8bb0dc2be9c178ef8a682bc6697487aed43e8`이다.
이 파일은 252MB이며 현재 저장소 manifest에는 포함하지 않았다.

## 원복 기준

- DU capacity-96 기준선:
  `35ea900e8253013aeec398952d4a6c3c1f407880018d940270b53497700e0b17`
- CU cap-200 기준선:
  `2ab32fc1f27e709b1dd80a4aaf72d61363c96638d064e413cdd539fe3abb15b0`

실험 종료 후 이 두 SHA로 복원하고 CU/DU stack과 EC2를 정지한다.

이번 실험 종료 때 실제로 DU `35ea900e...`, CU `2ab32fc1...`를 다시 확인했고,
두 stack을 내린 뒤 로컬 `ctl.sh status`에서 CU·DU EC2 모두 `stopped`임을 확인했다.
