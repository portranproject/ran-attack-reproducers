# 핸드오프: 테스트베드 공격 도구의 초기 구현 계획(역사 기록)

> 2026-10-19 작성, 2026-10-30 역사 문서로 전환. 아래의 "제안 구현 구조"와 "진행 순서"는 이미 수행된 초기 계획이므로 새 작업 지침으로 사용하지 않는다. RRC storm 서브태스크는 2026-11-02 분석기 평가용으로 동결했다. 현재 상태와 명령은 [AGENTS.md](AGENTS.md), [사용 가이드](reproducers/rrc-signaling-storm/docs/USAGE-GUIDE.ko.md), [reproducers/rrc-signaling-storm/README.md](reproducers/rrc-signaling-storm/README.md)를 우선한다. 표시 규칙(✅/📄/🔍)은 [comparison-5g.md](comparison-5g.md) §0과 같다.

## 2026-10-30 현재 위치

> 정정: 아래 V4 수치는 기본 cleanup 성공 판정이 아니다. 약 2초 정리시간을 32초로
> 늘리고 첫 만료 전에 끝낸 진단이므로 완료 판정을 철회했다. 후속 rate-v2도 기본값에서
> 실제 admission률이 cleanup률과 평형이어서 sustained denial에 실패했다. 이후 D6 RRCSetupRequest 후 중단형은
> 공격 중 service-off와 stop 뒤 별도 UE service-on을 3/3 반복했고 동일 8-endpoint control은
> 정상 서비스에 성공했다. D6F50 RRCSetupComplete 미전송형은 exact DU ACK 149건을 확보했지만 공격 중
> 정상 서비스가 성공했다. 30초 지속 포화·기지국 전체 마비 기준은 여전히 통과하지 못했다. 최신 상태는
> [AGENTS.md](AGENTS.md)와 [기본 cleanup 실패 분석](artifacts/p5-default-cleanup-rate-v2-20261030/README.md)을 따른다.

- 구현은 [`reproducers/rrc-signaling-storm/`](reproducers/rrc-signaling-storm/)에 있고, 기본 패치는 `patch/rss-ue-curated.patch`, 인공 hold32 CU200 진단 명령은 `bin/rss-cu200`이다.
- hold32 V4 UE 바이너리 SHA-256은 `202934f7...`다. 공격 전 4셀 control은 모두
  `RRCSetupComplete`에 도달했고 C3는 Registration·PDU Session·TUN까지 성공했다.
- V4의 세 공격 셀은 RRCSetupComplete 미전송형 exact DU ACK 조인 176건과 Msg5 0건을 만들었다.
  CU 점유는 실제 상한 200에 도달해 15.68초 연속 유지됐다.
- 별도 네 번째 셀의 정상 witness는 16.31초 동안 17회 연속 `RRCReject`를 받았고
  Msg4·`RRCSetupComplete`에는 도달하지 못했다. 이는 인공 hold32 안의 거부 관측이며
  기본 약 2초 cleanup에서 공격자가 통제한 서비스 거부를 뜻하지 않는다.
- V4 증거는 [`artifacts/p5-cu200-3cell-20261030/`](artifacts/p5-cu200-3cell-20261030/)에
  보존했다. 기본 cleanup의 최신 D6 3회 반복과 matched control은
  [`artifacts/p5-default-cleanup-rate-v2-20261030/`](artifacts/p5-default-cleanup-rate-v2-20261030/)에 보존했다.

## 사용자와 작업 방식
- 사용자는 팀 프로젝트 "O-RAN 기반 5G 기지국 위협 탐지 솔루션"에서 RRC 폭주 공격 도구를 맡고 있다. 배경지식이 적으므로 결론만 주지 말고 쉽게 설명한다.
- 근거를 중시한다. 리포 문서도 AI가 쓴 것이므로, 주장은 원본(코드·박스 출력·논문)과 대조한다.
- 로컬 세션은 셸로 EC2 박스를 직접 조작한다. 아래 안전 규칙을 지킨다.
- `comparison-5g.md` §8의 `TODO(human)`은 사용자가 직접 쓴다. 대신 쓰지 않는다.

## 목표
팀 AWS 테스트베드에서 **실제로 도는 공격 UE**를 만든다. 동작은 다음과 같다. 단말이 `RRCSetup`(Msg4)을 받고 HARQ ACK까지 보낸 뒤 `RRCSetupComplete`(Msg5)를 보내지 않는다. 그리고 새 식별자로 `RRCSetupRequest`를 반복한다. 문서에서는 중단 지점을 그대로 드러내는 설명형 이름인 **RRCSetupComplete 미전송형**을 사용한다. 이는 3GPP 공식 공격 분류명이 아니다.

첫 마일스톤은 [design.md](design.md) §9의 **M1a**다. 기본 설정에서 공격이 성립하는지만 본다. 즉 CU에 미완료 절차가 생겼다가 2초 뒤 해제되는 것이 반복되는지 확인한다. 포화(정상 UE 접속 실패)는 M1a의 합격 조건이 아니다.

## 확정된 사실 (세부는 [testbed-checklist.md](testbed-checklist.md))
| 항목 | 값 |
|---|---|
| 환경 | AWS EC2, 세트 p5. CU 박스 `172.31.5.10`, DU 박스 `172.31.5.11`, F1 분리 |
| 셀 | n78 TDD, `dl_arfcn` 632628, 30 kHz, 20 MHz(51 PRB), ZMQ |
| gNB | OCUDU `release_26_10` (`e0db566a`), 소스 `/root/OCUDU`. 수정 금지 |
| 코어 / RIC | Open5GS(Docker `open5gs_5gc`) / FlexRIC |
| UE | OAI `2026.w38` (`1c2f4d3c`), 소스 `/root/OAI`, 설정 `/root/oai_nrue.conf`. 실행 인자는 checklist §4.1 |
| 미완료 접속 유지 시간 | `t300` 1000 + `rrc_procedure_guard_time_ms` 1000 = **2000 ms** ✅ (checklist §5) |
| 정상 접속 기준선 | `RRCSetupRequest → RRCSetupComplete` 약 103 ms ✅ (checklist §7) |
| 이식할 곳 | UE 쪽 4곳: U1 `rrc_UE.c:2465` rrcSetup 분기, U3 `rrc_defs.h:144` 타이머 필드, U4 `rrc_timers_and_constants.c:174` tick, U5 `:446` 간격 설정 ✅ (checklist §6). 행 번호는 박스 트리(w38) 기준이다. design.md §7의 행 번호는 w40 기준이라 다르다 |
| 제외할 곳 | 5gattacks 패치의 gNB 변경(UL failure 타이머 단축 등)과 로그 7곳 |

## 환경 제약 (설계에 직접 걸림)
1. **UE만 재시작할 수 없다.** UE만 다시 띄우면 odu와 ZMQ 샘플 흐름이 어긋나 멈춘다. 그래서 박스 `ctl.sh ue`는 항상 odu와 UE를 함께 재기동한다 ✅. 공격 반복은 **한 UE 프로세스 안에서** 일어나야 한다. 프로세스 재시작 방식은 쓸 수 없다.
2. **ZMQ는 1:1 연결이다.** DU에 붙는 UE는 하나뿐이다. 공격 UE를 띄우면 정상 UE를 동시에 붙일 수 없다. 그래서 M1a는 "CU에 미완료 컨텍스트가 쌓이는지"만 본다. 정상 UE 영향(포화)을 보려면 ZMQ 브로커로 다중 UE를 붙여야 한다(design.md §10, M1b). 공식 srsRAN 3 UE 브로커가 참고 자료다 📄.
3. **정상 상태에서도 Msg5가 가끔 유실된다**(팀 시험 24회 중 2회) ✅. 공격 결과를 셀 때 이 기준선을 빼야 한다. 분석기 오탐 기준에도 반영한다.
4. **박스 안 변경은 `destroy`하면 사라진다.** 골든 이미지로 초기화되기 때문이다. 패치와 스크립트의 원본은 항상 리포에 두고, 박스에는 복사해서 쓴다.

## 제안 구현 구조 (리포에 새로 만들 것)
```
tool/
  oai-patch/rss-ue.patch     # /root/OAI(2026.w38)에 적용할 UE 전용 패치. gNB 파일은 건드리지 않음
  box/deploy.sh              # 패치 복사 → 박스에 별도 git 브랜치로 적용 → nr-uesoftmodem 빌드
  box/run_attack.sh          # odu+공격 UE 기동, max_duration 킬 스위치, 로그 수집
  box/collect.sh             # CU /tmp/ocu.log에서 started/timed out/rrcSetupComplete 집계
  README.md                  # 사용법, 노브, 결과 판독법
```
- 1차 노브: 공격 on/off, 재시도 간격(ms, 실행 인자), `max_duration_s`, `honor_reject`(기본 true). 5gattacks는 간격이 100 ms 빌드 상수였다(U5). 우리 패치는 이를 실행 인자로 뺀다. OAI 설정·인자 체계(`paramdef`)로 등록하는 방법은 박스 소스에서 확인할 것 🔍.
- 기록: 시도마다 시각, 식별자(randomValue), Msg4 수신, Msg5 생략 여부를 JSONL로 남긴다(design.md §8 스키마). 분석기 평가용 정답지가 된다.
- 판정: CU 로그에서 `"RRC Setup Procedure" timed out after 2000ms`가 시도 수만큼 쌓이고 `rrcSetupComplete`는 없어야 한다(checklist §7 명령).
- 원본 바이너리를 보존한다. 박스 `/root/OAI`에 git 브랜치를 따로 만들어 빌드하고, 정상 UE로 되돌리는 명령을 README에 적는다.

## 안전 규칙 (역사 기록)

아래 승인 대기 규칙은 2026-10-19 당시 것이다. 사용자는 현재 p5 사용·실험을 명시적으로
승인했고 LLM 노출 및 private GitHub의 랩 credential은 작업 차단 사유가 아니라고 정했다.
대상 제한·kill switch·비용 절감·gNB 소스 무수정 원칙은 계속 적용한다.
1. **비용**: 켜 둔 시간만큼 팀 예산이 과금된다. 작업이 끝나면 로컬 p5 폴더에서 `./ctl.sh stop`을 실행한다. `destroy`는 사용자 확인 없이 하지 않는다.
2. **비밀**: `credentials`, `portran-key.pem`, `/root/oai_nrue.conf`의 가입자 값(IMSI·키·OPc)은 출력·커밋하지 않는다.
3. **gNB(OCUDU) 소스 수정 금지.** gNB 설정을 바꾸는 실험(로그 레벨, `t300`, guard 값 등)은 사용자 승인 후에 한다.
4. **공격 대상 제한**: 승인된 p5 세트 박스 외의 다른 팀원 세트나 외부 대상은 금지다. 항상 `max_duration` 킬 스위치를 켠다.
5. 박스에 시스템 패키지를 설치하는 것처럼 되돌리기 어려운 작업은 먼저 묻는다.

## 로컬 제어판 (p5 폴더 경로는 사용자에게 물을 것)
```bash
./ctl.sh status | start | up | ssh cu | ssh du | stop
```
기동 순서는 CU(코어→RIC→ocu)가 먼저이고 그다음 DU+UE다. `up`이 이 순서를 지킨다. F1 문제는 DU `/tmp/odu.boot.log`로 진단한다.

## 진행 순서
1. 박스 `/root/OAI`에서 U1·U3·U4·U5 위치를 다시 열어 확인하고, 실행 인자 등록 방식을 조사한다(코드 읽기).
2. 리포에 `tool/oai-patch/rss-ue.patch` 초안을 작성한다. 사용자에게 diff를 보여 준다.
3. 승인을 받으면 박스에 적용하고 빌드한다. 공격을 끈 상태(off)로 정상 접속이 그대로 되는지 먼저 확인한다(회귀 시험).
4. 승인을 받으면 짧게(예: 30초) 공격을 켜서 M1a를 판정한다. 결과를 checklist에 새 절로 기록한다.
5. 다음 단계는 재시도 간격 스윕(M2)과 다중 UE 브로커(M1b)다.

## 남은 확인
- OCUDU 26.10에서 미완료 컨텍스트가 실제로 쌓이는지, 먼저 걸리는 용량 한도가 무엇인지 🔍
- StormShield(45.7 Msg3/s)·Nguyen(132.07 Msg3/s) 수치는 arXiv에서 원문 재확인이 필요하다 📄
- 5gattacks 저자의 재사용 허가(라이선스 없음). 우리 패치는 동작을 참고해 새로 쓴 것임을 명시한다
- AGENTS.md는 아직 "3-노트북 RF 차폐" 전제로 쓰여 있다. 고칠지는 사용자가 정한다
