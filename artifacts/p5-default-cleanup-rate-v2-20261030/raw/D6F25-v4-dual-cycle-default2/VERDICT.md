# D6F25 판정

기본 약 2초 cleanup을 유지한 한 실행 안에서 다음 서비스 수준 on/off 순환은 성립했다.

- 공격 중 primary witness `0x484f`는 `RRCSetupComplete`와 인증까지 갔지만,
  DU가 후속 무선 자원을 배정하지 못해 `UEContextSetupFailure`를 반환했다.
  CU 원인은 `no-radio-resources-available`이며 Registration·PDU·ping은 0이다.
- 공격 프로세스 네 개가 각각 kill switch를 한 번 기록한 뒤 새 attempt/retrigger는
  없었다. 진행 중이던 마지막 Msg3도 45.6ms 안에 끝났다.
- 같은 broker와 gNB에 처음부터 대기한 별도 recovery witness `0x4c67`은 마지막
  kill 뒤 9.33초에 Msg3, 9.47초에 RRC 연결, 10.86초 안에 Registration·PDU와
  첫 ping에 도달했다. ping은 295/295였다.

이 결과는 **공격 중 정상 서비스 실패 → 공격 종료 후 정상 서비스 회복** 한 사이클의
증거다. 다음 주장은 성립하지 않는다.

- 96개 미완료 컨텍스트의 지속 포화: peak 83/96, 96 유지 0초
- 30초 연속 RRCReject: primary는 공격 중 `RRCSetupComplete`까지 도달했다.
- 같은 UE 프로세스의 회복: recovery는 같은 가입자 profile을 쓰는 별도 선기동
  프로세스다.
- 반복 재현성: 이 dual-witness 사이클은 1회만 실행했다.

`result.json`의 primary `attached/ping_ok=true`는 당시 runner가 TUN/ping을 전역으로
집계해 recovery 결과를 primary에도 표시한 것이다. `service_ok=false`와
Registration/PDU=0은 올바르다. 이 결함은 후속 runner SHA-256
`84da7a685f6bf140db816058c411348777a8af04c4f4ecb6434c63b48f9e77c0`에서
역할별 귀속으로 수정했다. 최종 판정은 `verdict.json`을 사용한다.
