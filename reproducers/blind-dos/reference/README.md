# 원본 5GSEC/OAI-5G Blind DoS UE 빌드

- 원본: https://github.com/5GSEC/OAI-5G, 커밋 `b631b577cc00929e50947a453dc5d4c2dcdfa887`
- 공격 플래그: `--blind-dos-attack`, `--RRC-TMSI`
- 라이선스: OAI-5G 저장소의 라이선스 파일을 따른다.
- 원본 코드는 수정하지 않는다. 실행에 필요한 RF 설정만 런타임 인자로 준다.

`bin/build-reference`는 원본 저장소를 고정 커밋으로 clone하고 UE를 빌드한다.

## 2026-11-20 확인

원본 NR RRC의 `blind_dos_attack` 분기는 `!IS_SOFTMODEM_RFSIM` 조건이라 rfsim에서
공격 분기가 실행되지 않는다(고정 커밋 소스 확인). OAI ZMQ 장치로 바꾸면 우리 broker의
srsRAN ZMQ 형식과 달라 브리지로 붙일 수 없다. 빌드도 완료하지 못했고 탐지 비교는
실행하지 않았다.
