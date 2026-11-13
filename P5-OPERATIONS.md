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

2026-11-12 inventory 감사에서 기본 CU·DU와 과거 lane 7대는 모두 stopped였고, 기본 두
대만 짧게 기동해 현재 detection/telemetry 미배포를 확인한 뒤 다시 중지했다. 따라서 새
7개 룰의 p5 live 자격과 기존 6개 룰의 새 통합 detector 종단 자격은 pending이다.
