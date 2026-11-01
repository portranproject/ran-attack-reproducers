# p5 실제 Msg3-only 및 paired witness 검증 (2026-10-30)

> **2026-10-30 정정:** G4/G13/G14의 DU 설정 SHA `7679413a...`에는
> `cell_cfg.pucch.nof_cell_sr_res: 1`이 들어 있어 부팅 capacity가 12였다.
> 따라서 아래 Msg3-only 절차·probe 거부 증거는 유효하지만, “변경하지 않은
> capacity-96에서 숨은 12 병목을 발견했다”는 해석은 틀렸다. 실제 capacity-96
> 재검증과 정상 probe 지속 거부 결과는
> [후속 artifact](../p5-msg3-cap96-20261030/README.md)를 따른다.

## 결론

- `A_early`는 UE 로그상의 의도가 아니라 실제 MAC `msg3_tx` 뒤 RA를
  `GO_TO_IDLE_KEEP_CAMPED`로 초기화하는 구현이다. p5 G2에서 10회 모두
  UE TC-RNTI와 OCUDU CU의 `Rx RRCSetupRequest`가 exact join됐다.
- capacity-12 프로필에서 G4는 Msg3 661건, CU 요청 661건, 절차 시작 55건,
  `DU is not able to serve` 606건이었고 재구성 피크는 12였다.
- 동일 최종 빌드의 paired run에서 저부하 G14는 정상 probe가 첫 시도에
  Registration, PDU session, TUN까지 성공했다. 고속 G13은 probe가 1초 간격으로
  10회 실제 Msg3를 보냈지만 10회 모두 CU에서 exact RRC request 후
  `DU is not able to serve`로 거부됐고 Msg4·Registration·PDU는 0이었다.
- G13 뒤 DU를 clean restart한 G14가 다시 완전 접속했으므로 영구 장비·구성 고장은
  배제했다. 재시작 없는 자연 회복 시간은 측정하지 않았다.

이는 **같은 OAI 프로세스와 shared ZMQ 안의 통제된 witness 결과**다. 독립 SDR/실물
UE의 서비스 거부까지 입증한 것은 아니며, 그 주장은 차폐 OTA 또는 안정적인 별도
프로세스 broker control/attack pair가 필요하다.

## G13/G14 최종 버전과 설정

- OAI base: `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (`2026.w38`)
- RSS patch SHA-256:
  `7b289c0fdbeb3e4c0d852b832c9805cc3f30af7c16998d5975bea775f74bcd1c`
- UE binary SHA-256:
  `cc5b7569e68ce3d829dd2e8fb91a6c863bc9ea76a7cf66eac5e8b9a40bcebac2`
- runner SHA-256:
  `45b7c4944544ebb7089581404aedde54b940cede94307902872850f01c509949`
- label exporter SHA-256:
  `d596a74be8f56f5ef3ecf46567975d6b7dcf9079ab89edd2555e4fd55f2d5adf`
- CU config SHA-256:
  `2ab32fc1f27e709b1dd80a4aaf72d61363c96638d064e413cdd539fe3abb15b0`,
  실제 `max_nof_ues: 200` 유지
- DU config SHA-256:
  `7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3`;
  `nof_cell_sr_res: 1` override로 실제 부팅 capacity 12

CU cap과 gNB 소스는 바꾸지 않았지만, DU는 capacity-12 프로필이었다.
G2/G4는 같은 OAI base의 앞선 계보다. 두 run의 UE binary는
`dcd19e9b0d7b604a3379117d35e772808ce5db9ac6c3f22fbae6d4c71ee6cfca`,
patch는 `a1590b3726cca77a838964672399ca025f76ae19c43450109ee17c19329a74d4`,
runner는 각각 `2c1484871f08a88ab3bd48c641b4ef880bfd8452bec582a447c59e0231ddf32f`와
`0b1f2f514897a42598564f9cd24bb181877a123f693f19c8ccf4ac5a55ed5197`이다.

## 핵심 run

### G2 — actual Msg3-only 도달 확인

- 원격: `/root/rss-runs-msg3-v2-20261030/G2-msg3-0140`
- 조건: UE 1, `-M0 -i2000 -d20`
- 10 attempts, 10 `msg3_tx`, attacker Msg4 0
- CU TC-RNTI exact join 10/10, `canonical_msg3_only=true` 10/10
- CU join 라벨은 원 run manifest 뒤에 만든 별도 derived artifact이며, 원 manifest가
  이 결론까지 봉인한 것은 아니다.
- CU slice SHA-256:
  `d799a7d481c2b9128cea14d7e4c029093e1b117ca0b33b7d7e40ee74f7e75257`
- attempts SHA-256:
  `3bbb6282afea1de85cba1f755c55c2b36a3495593b609e4f3d41d82b4837f35f`

### G4 — capacity-12 프로필의 자원 병목

- 원격: `/root/rss-runs-msg3-v2-20261030/G4-u1-i0-clean`
- 조건: UE 1, `-M0 -i0 -d10`
- valid, 662 attempts, 661 `msg3_tx`, attacker Msg4 0
- CU 요청 661, RRC 절차 시작 55, DU 거절 606
- 재구성 동시 절차 피크 12, hold median 1.791 s, p90 1.999 s
- CU slice SHA-256:
  `40c444b874635cfd19b30966ba2b501c41ec3aa50d775e4acdf73f409ce04ee7`
- attempts SHA-256:
  `afd7218df54e5c9cda818281ae24317e370bcbbe0da0ba58fa5a9f2c7cad5c63`

12는 별도 숨은 pool이 아니라 `nof_cell_sr_res: 1`에서 계산된 같은 PUCCH 자원
상한이다. 이 run으로 capacity-96의 병목을 주장하지 않는다.

### G13 — 고속 paired attack

- 원격: `/root/rss-runs-msg3-v2-20261030/G13-pair-attack-valid`
- 조건: UE 2 중 UE0 normal probe, UE1 attacker; `-t5000 -M0 -i0 -d20`
- valid, `stop_reason=duration_limit_sigkill`
- 1,030 attempts, 1,029 `msg3_tx`, attacker Msg4 0, probe Msg4 0
- CU 요청 921, 절차 시작 84, DU 거절 837, `InitialUEMessage=0`, PDU 성공 0
- probe TC-RNTI 10/10이 CU RRC request 1회 + DU 자원 거절 1회와 exact 일치
- attacker derived label: exact canonical 911, unknown 108; 마지막 경계 attempt 1건은
  MAC-confirmed Msg3가 없어 false
- CU slice SHA-256:
  `bc5b2fea0a9e54853fea876b5cec99a5d1f58f1f517aefffb882d6eb63d3ff90`
- attempts SHA-256:
  `1027b7ff643bdfb0419993cba7e84fdebd20a9d4502323dbd1667743924f231e`
- derived CU labels SHA-256:
  `3e8a0b0c1061dbc7b6ace7e6e2d67bf0fe88eee4733473715e5a573caeb56f85`
- 원 run evidence manifest verify 통과. 위 CU-derived labels는 별도 산출물이다.

### G14 — clean DU restart 뒤 동일 빌드 저부하 control

- 원격: `/root/rss-runs-msg3-v2-20261030/G14-pair-recovery-control`
- 조건은 G13과 같고 attacker interval만 `i=10000`
- valid, probe는 첫 시도에서 Msg4/Msg5 후 Registration Accept, PDU Session Accept,
  `oaitun_ue1=10.45.1.2`까지 성공
- CU에서 RRC Setup, Initial Context Setup, PDU Session Resource Setup 성공 확인
- CU slice SHA-256:
  `1fcdbb40e678d9390c8bddf47ba945128ca222518ecfc7af6e67d870a972184a`
- attempts SHA-256:
  `31546d2a533f35e18b9d6b94acd9000a700f0a076b3a89c204a903406fec69c8`
- evidence manifest verify 통과

## 막힌 이유와 해결

1. 기존 `probe_delay`는 첫 공격 Msg3 기준이 아니었고 SIB1의 자동 RA도 막지 않았다.
   `t=8000`인 G8에서도 probe와 attacker가 같은 `air_ms=1280` 슬롯에서 Msg3를 보냈다.
2. SIB1의 probe `can_start_ra`를 막고, 최초 non-probe MAC-confirmed Msg3 시각을
   atomic으로 기록해 그 시점부터 delay를 계산했다. G9/G13/G14에서 probe는 공격
   Msg3 뒤 실제 5초 후 시작했다.
3. OAI w38의 multi-UE teardown은 INT와 TERM 모두 SIGSEGV를 냈다. duration watchdog은
   먼저 marker를 남기고 즉시 SIGKILL한다. 오직 duration marker + kill marker + rc137이
   모두 맞을 때만 `duration_limit_sigkill`로 유효 처리하며, 외부 kill/OOM은 invalid다.
4. same-process shared TX는 여전히 out-of-order와 channel timeout이 있다. 다만 G13은
   timeout 2,466건인데 서비스가 거부됐고, G14 control은 timeout 30,001건이어도 완전
   접속했다. 더 직접적으로 G13 probe 10회 모두 CU까지 도달해 DU 자원 부족으로
   거부됐으므로 단순 RF 유실만으로 결과를 설명할 수는 없다. 그래도 독립 UE 증거는
   아니므로 주장 범위를 유지한다.

## 각 조치가 필요한 이유

- 정상 control: 셀·코어·가입자·PDU 경로의 원래 고장을 공격 효과로 오판하지 않는다.
- 공격 Msg3 기준 probe 지연: 두 UE의 첫 RA 충돌과 동일 TC-RNTI 우연을 제거한다.
- current-run CU slice: 이전 run의 RNTI 재사용을 섞지 않고 실제 기지국 도달·거절을
  확인한다.
- TC-RNTI exact join: UE의 의도 로그가 아니라 해당 attempt가 CU에 실제 도달했음을
  입증한다.
- unchanged config: 임의로 낮춘/높인 용량이 아니라 현재 배치의 첫 병목을 측정한다.
- clean-restart 후행 control: 영구 장비·구성 고장을 배제하고 서비스 가용성을 다시
  확인한다. 재시작 없는 자연 회복을 증명하지는 않는다.
- marker-gated SIGKILL: OAI teardown crash를 피하면서 의도된 duration stop과 외부 kill을
  구분한다.

## 로컬 보존물

- `G13-pair-attack-valid/`, `G14-pair-recovery-control/`: run/stop, attempts,
  ground truth, manifest, redaction report
- `G13-pair-attack-valid-cu.log`: G13 current-run CU slice
- `p5-msg3-selected-json.tgz` SHA-256:
  `51835cb5f950134cc9e2cf00fd0d28beae68e50f34405d5c2026b678d42aa3e1`

G14 CU 원시는 세션 보안 키를 포함하므로 로컬에는 복사하지 않았고 p5의
`/tmp/G14-pair-recovery-control-cu.log`와 위 SHA만 기록했다. G2/G4 원시는 p5 DU/CU
디스크의 위 경로에 보존돼 있다.
