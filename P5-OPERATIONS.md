# p5 운영

## 원칙

- 기본 자원 상한은 `role=cu` 1대와 `role=du` 1대다.
- 과거 `rss-smooth-lane` 인스턴스는 서비스 거부 재현을 위해 다시 켜지 않는다.
- p5 제공 제어판의 `start`는 stopped 상태의 같은 set 인스턴스를 모두 켤 수 있으므로,
  lane이 남은 현재 inventory에서는 기본 검증에 직접 사용하지 않는다.
- 실행 전후 EC2 tag·state와 CU/DU 정확한 instance ID를 읽기 전용 조회하고, 종료 시 같은 두
  ID만 중지됐는지 확인한다.

## 준비

1. Git 밖의 credential과 SSH key 권한을 각각 0600 이하로 둔다.
2. `profiles/p5.example.json`을 `profiles/p5.json`으로 복사해 현재 CU/DU public/private
   endpoint와 detector·telemetry 경로를 채운다.
3. `./ctl.sh doctor --profile p5`가 manifest 13개, production detector/config,
   telemetry `period_ms=100`을 모두 통과해야 한다.
4. OCUDU/FlexRIC만 있고 현재 integration lock의 detector·telemetry가 없으면 자격 검증을
   시작하지 않는다.

## 실행 순서

정상 CU→DU 기동과 정상 UE attach·PDU·ping을 확인한 뒤 control을 먼저 수행한다. active
실행은 `--enable`을 요구한다. 중단·timeout 후 UE·telemetry·detector 잔존 프로세스와 설정
원복을 확인한다. large raw evidence는 원격 보관하고 Git에는 정제 입력·판정·SHA-256만 둔다.

2026-11-17 기준 production detector `766f5569...`, TeleRAN `7550153a...`를 사용했다.
7개 L3 공격은 모두 p5 실제 경로 matched 3/3을 통과했고 6개 AN 입력 fixture는 공격 자격
범위 밖의 replay 회귀로만 유지한다. L3-01-V·L3-01-O·L3-20·L3-24·L3-14 결과는
[공통 E2E 기록](artifacts/p5-live-e2e-five-20261117/), L3-21과 L3-06은 각 모듈 artifact를
따른다. 종료 뒤 CU·DU와 과거 lane 7대가 모두 stopped임을 확인했다.

p5가 아닌 같은 스택의 ZMQ 호스트는 [포팅 가이드](PORTING-GUIDE.md)에 따라 별도 profile과
module conf를 만든다. p5 자격 결과를 새 환경의 자격으로 그대로 옮겨 적지 않는다.
