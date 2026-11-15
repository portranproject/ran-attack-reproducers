# p5 동일 셀 정상 UE 풀 자격 검증 (2026-11-13)

## 판정

동일 DU·셀에서 공격용 quiet endpoint 1개와 정상 UE용 독립 virtual RU/ZMQ endpoint 5개를
broker로 합치는 구조를 기본 5대 정상 배경 트래픽 용도로 승인한다. cold-start 3회 모두
정상 UE 5/5가 Registration accept, PDU session accept, TUN, 개별 gateway ping까지 통과했다.
세 실행 모두 ZMQ channel timeout과 crash marker는 0이었다.

## 반복 결과

| run | 5/5 최초 ping | Registration/PDU | UE별 ping | timeout/crash | 판정 |
|---|---:|---:|---:|---:|---|
| `nue-multiru-q1-g1` | 60.1초 | 5/5 | 5/5 | 0/0 | 통과 |
| `nue-multiru-q2-g1` | 62.3초 | 5/5 | 5/5 | 0/0 | 통과 |
| `nue-multiru-q3-g1` | 12.7초 | 5/5 | 5/5 | 0/0 | 통과 |

세 번째 실행은 안정 유지 뒤 각 TUN에서 추가 5회 ping을 보내 25/25를 확인했다. 세 실행의
지속 ping 원문에는 각각 602, 109, 355개 reply가 남았다. `status`는 모든 TUN의 주소와
각 interface의 단일 ping이 성공할 때만 `healthy`를 반환한다.

## 통과한 운영 검증

- 서로 다른 가입자 5개와 설정 권한을 `doctor`가 검사한다. 가입자 설정에 고정 `RUs`나
  `cells`가 있으면 거부하고, 실행 시 요청 대수에 맞춘 권한 `0600` 설정을 생성한다.
- runner가 반복 실패해도 supervisor가 수동 `stop` 전까지 새 generation을 시작한다.
  강제 실패 fixture에서 4초 동안 5 generation을 확인했다.
- `stop`은 supervisor, UE, broker, 소유 DU를 종료한다. 종료 재시험 뒤 잔존 프로세스는
  UE 0, broker 0, DU 0이었다.
- 정상 UE 5대는 하나의 OAI 프로세스지만 UE마다 독립 RU와 ZMQ endpoint를 사용한다.
  broker가 이를 하나의 DU endpoint로 합치므로 대시보드에서는 같은 셀 트래픽이다.
- 기존 공격용 한-RU 다중 UE 경로는 유지한다. `normal-multi-ru.patch`는 RU 수와 UE 수가
  같을 때만 custom RU-sharing을 끈다.

## 증거 식별자

- 정상 UE OAI binary SHA-256:
  `a41035bef6a1a51b7837456aa84ca235b3dfdf2250040be026d987710c937359`
- 배포 runner / controller / broker SHA-256:
  `acf58f95e410d35fa20bf31588afa0a997daf98c839d4f456cbc51c736979fc4` /
  `4e5396b1fc518b0ea23a18f9881cc54e02e10f738771a1b2adef07e8c914ef3a` /
  `d696e8b6e35df74dad3e7cec681651b0be2762c05c5880a654b7684d0b71a12d`
- 가입자 설정 SHA-256(원문은 Git 제외):
  `78d972d242433c8314bbc1a398c3983f76949b36d8b813741e2a4960885d4654`
- q1 `ue2.log` / `witness_ping.txt`:
  `c54bd9898f16882f1612192f7d1c41286b75e1e66d1fc63e811e0ef14de42c5b` /
  `eb9d0ae52915905857e1963ff05452ae324ebc5167572f03a85901545b01e5c8`
- q2 `ue2.log` / `witness_ping.txt`:
  `2e71f06f23db116df05bcf2417116a51017f659b94435e1876aaeb0d5c3fa6ac` /
  `8841c4b82266e1bb418fd67657d72e7aa40d322cf8be1dd19a9e6023150e3125`
- q3 `ue2.log` / `witness_ping.txt`:
  `8f379d85154798c9ac3683bddebac00c16772a285bb32cd644ca3fa3b33142ca` /
  `857e9c14db5567ff921274298bde8331752491200301fbb79050995822143105`
- 원격 원문 위치: p5 DU `/root/normal-ue-qualification/runtime/runs/`

## 남은 제한

자격 범위는 p5 ZMQ의 정상 UE 5대 배경 트래픽이다. 실 SDR OTA, 장시간 soak, 대수를 바꾼
반복 자격, 정상 풀을 유지한 공격 hot-swap은 아직 검증하지 않았다. 과거 한-RU 공유 구조의
실패 원인과 이번 우회 설계는 [RU-sharing 원인 분석](RU-SHARING-ROOT-CAUSE-20261113.md)을
따른다.
