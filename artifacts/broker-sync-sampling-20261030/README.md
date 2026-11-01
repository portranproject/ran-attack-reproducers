# 5 UE broker sync·대조군 고정 표본 (2026-10-30 KST)

## 결론

사전에 실행 수를 **15회로 고정**한 control 캠페인에서 5/5 sync는 5회 모두
3~4초 안에 끝났고, 나머지 10회는 60초까지 **0/5**였다. 31~60초의 늦은 sync는
없었다. 현재 표본은 느린 꼬리보다 `fast-success`/`stuck-0/5`의 이봉형 시작 경합을
지지한다. 따라서 실행기의 30초 기본 제한은 운영상 유지할 수 있지만, 이 표본으로
30초 분위수나 성공 보장을 주장하지 않는다.

5개 fast-sync 런 가운데 유효한 대조군은 3개뿐이었다. 두 런은 quiet load UE가
예정된 최초 4회보다 더 접속을 시도해 `control_load_ue_activity_unexpected`로
분리했다. 유효한 세 런의 witness ping 손실은 **0.833333%~93.5484%**, attach는
**1~36초**였다. 이 분산 때문에 현 broker 경로는 정상 서비스 안정성이나 공격에
의한 DoS를 판정하는 기준선으로 쓰지 않는다.

팀 소유 AWS ZMQ 격리 환경에서만 실행했고 gNB 소스는 수정하지 않았다. 15회 모두
UE 5개와 broker가 exit 0, forced kill 0, SIGSEGV 0으로 정리됐다. 캠페인 이후 DU
설정은 원본 해시와 4556/4557 포트로 복원했고 CU·DU 인스턴스를 중지했다.

## 사전 고정 조건

- 모드: `control`
- 실행 수: 15, 결과에 따른 연장 없음
- 실행기: `rss-broker-witness` 직접 1회 실행; retry wrapper 미사용
- 5/5 sync 제한: 60초
- 관측 창: 60초
- witness 시작 지연: 5초
- 동일 profile: 12 UE 동시 cap, PRACH preamble 64, CU `max_nof_ues: 200`
- 원문 정책: UE/NAS 로그는 DU에만 두고 식별자 없는 판정과 SHA-256만 저장소에 보존

실행 전에 고정한 run id와 분류 규칙은 [`campaign.json`](campaign.json)에 있다.

## 결과

| 범주 | 횟수 | 해석 |
|---|---:|---|
| 5/5 sync, 30초 이내 | 5 | 모두 3~4초 |
| 5/5 sync, 31~60초 | 0 | 현재 표본에 늦은 꼬리 없음 |
| 60초 clean timeout | 10 | 모두 0/5, 서비스 분모에서 제외 |
| 유효 control | 3 | c04, c07, c13 |
| 의미론상 무효 control | 2 | c08, c10; quiet load UE 재시도 |

| run | sync | 판정 | attach | ping tx/rx | loss | 평균 RTT |
|---|---:|---|---:|---:|---:|---:|
| c01 | 60초, 0/5 | clean timeout | - | - | - | - |
| c02 | 60초, 0/5 | clean timeout | - | - | - | - |
| c03 | 60초, 0/5 | clean timeout | - | - | - | - |
| c04 | 3초, 5/5 | **valid** | 1초 | 285/19 | 93.3333% | 58.829 ms |
| c05 | 60초, 0/5 | clean timeout | - | - | - | - |
| c06 | 60초, 0/5 | clean timeout | - | - | - | - |
| c07 | 4초, 5/5 | **valid** | 3초 | 279/18 | 93.5484% | 62.185 ms |
| c08 | 3초, 5/5 | invalid: load attempts 5 | 3초 | 274/15 | 94.5256% | - |
| c09 | 60초, 0/5 | clean timeout | - | - | - | - |
| c10 | 4초, 5/5 | invalid: load attempts 6 | 37초 | 119/114 | 4.20168% | - |
| c11 | 60초, 0/5 | clean timeout | - | - | - | - |
| c12 | 60초, 0/5 | clean timeout | - | - | - | - |
| c13 | 3초, 5/5 | **valid** | 36초 | 120/119 | 0.833333% | 65.288 ms |
| c14 | 60초, 0/5 | clean timeout | - | - | - | - |
| c15 | 60초, 0/5 | clean timeout | - | - | - | - |

ping은 run별로만 보고하며 합산하지 않는다. c08/c10은 service 결과가 있더라도
대조군 의미론을 위반했으므로 유효 분모에 넣지 않았다.

## 종료와 crash 확인

- 15/15: `ue_exit_statuses=[0,0,0,0,0]`
- 15/15: `broker_exit_status=0`
- 15/15: `forced_kill_count=0`, UE/broker SIGSEGV 0
- 캠페인 시작 이후 kernel journal에서 `segfault`, `nr-uesoftmodem`, `UL__actor`
  일치 항목 없음

이는 2단계 UE 종료(INT 두 번)가 이번 캠페인에서도 안정적으로 작동했다는 증거다.
시작 성공률이나 서비스 품질이 안정됐다는 뜻은 아니다.

## 계보와 보존

```text
38fc2d453979ede543f3814d6a04ed7b80ce183069e683c025e9570bb15ca7aa  campaign.json
90bd249596325fe047e6803e8a0cb1a92eac7f2a91d0622977465abeec8416b8  rss-broker-witness
cb9e876c6f37483695085a5311e6c904b942f2b881f0863c80585965cfca11b0  rss-broker-witness-retry (배포만 함; 실행에는 미사용)
fdfa1fc443ab402555af87a172484b70aabcae4214a7d58c459d1300489e38cf  multi_ue_5ue.py
c511b43a73d051ad5e87992bf80017405829e43bd04c345d7c607bee4e21233f  nr-uesoftmodem
2a843d45ea62b458679f02522a2a57387c9e0b74308db719de9d4171c7e31baa  rss-ue-curated.patch
24395619907e87f37607f9d5cd71669b8f9537e70d29874e74ab36ab5b36e250  du.yaml (실험 중, 2000/2001)
7679413a01591b7eb8514fd8102d8223c15b44026ae89824a61d26863d6527c3  du.yaml (실험 전·원복 후, 4556/4557)
```

원문은 중지된 DU의 `/root/rss-broker-sync-sampling-20261030/`에 남겼다. 각
`run.json`, `result.json`과 fast-sync 런의 `witness_ping.txt` 원격 SHA-256은
[`SHA256SUMS.remote`](SHA256SUMS.remote)에 있다. UE/NAS 원문은 가입자·IP 식별자를
포함할 수 있어 로컬 저장소로 복사하지 않았다. kernel journal의 음성 검색은 실행 중
확인했지만 별도 파일로 복사하지 않았으므로, 제3자 재검증에는 중지된 DU를 다시 열어야
한다.

## 판정 경계

- 15회 중 sync 성공은 5회(33.3%), 유효 control은 3회(20.0%)다.
- 성공 5회가 모두 3~4초였으므로 30초 제한을 늘릴 직접 근거는 없지만, 성공 표본
  5개로 분위수를 보장할 수도 없다.
- 유효 control의 ping 손실과 attach 시간이 크게 흔들리므로 broker A/B로 안정적인
  정상 서비스 거부나 보존을 주장하지 않는다.
- 이 캠페인은 sync timeout과 control 품질만 평가했다. attack 캠페인, 차폐 OTA,
  탐지→대응 폐루프 검증이 아니다.
