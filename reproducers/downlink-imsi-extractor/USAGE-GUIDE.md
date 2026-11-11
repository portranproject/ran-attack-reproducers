# 하향 IMSI 추출 계열 재현기 사용 가이드

## 전제

- 팀 소유 p5 ZMQ 또는 RF 차폐 테스트베드에서만 실행한다.
- OAI UE만 패치하며 OCUDU·Open5GS 소스와 timer/capacity는 바꾸지 않는다.
- 기본 입력은 `control`이고 emulation은 `-e 1`을 명시해야 한다.
- p5 CU에는 N2 capture 정규화를 위한 `tcpdump`와 `tshark`가 필요하다.
- 원시 pcap에는 SUCI가 있으므로 detector 입력 전달과 보관 권한을 제한한다. 일반 분석에는
  `observations.jsonl`을 사용한다.

## 빌드

깨끗한 OAI w38 작업 트리에서 실행한다.

```bash
OAI=/root/OAI-downlink-imsi-w38 bin/downlink-imsi-build
```

빌드 스크립트는 기준 커밋, 패치 clean apply, 바이너리의 control/emulation 마커를
fail-closed로 확인한다. 패치 기본값은 off다.

## 설정

```bash
cp conf/p5-zmq.conf.example conf/downlink-imsi.conf
chmod 600 conf/downlink-imsi.conf
```

실제 키 파일은 저장소 밖에 둔다. CU/core를 먼저 준비하고, DU에는 기존 UE·DU 프로세스가
없어야 한다. 실행기는 매 run마다 DU를 재시작해 ZMQ socket 상태를 초기화한다.

## 단일 실행

```bash
DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf \
  bin/downlink-imsi-run control -n sample-control -e 0

DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf \
  bin/downlink-imsi-run emulation -n sample-emulation -e 1
```

control은 등록·PDU·ping을 필수로 본다. emulation은 등록 실패를 필수 성공 조건으로 쓰지
않으며, 같은 N2 context의 `Authentication Request → Identity Response`, Identity Request
부재, UE one-shot 마커, pcap·fingerprint 조인을 필수로 본다.

## 3세트 캠페인

```bash
DOWNLINK_IMSI_CONF=conf/downlink-imsi.conf \
  bin/downlink-imsi-campaign -n campaign-id -e 1
```

순서는 `control → emulation`을 세 번 반복한다. 각 child는 독립 `verdict.json`과
`evidence_manifest.json`으로 봉인되고, 마지막에 matched 설정 해시와 3/3을 검증한다.

## 탐지 사용

탐지 입력은 우선 `observations.jsonl`과 해당 run의 N2 시계 정보를 사용한다. CU/F1/eBPF
관측이 있으면 같은 RAN/AMF UE ID와 시간창으로 추가 조인한다.
`ue.log`, `oracle.json`, AMF 로그는 detector 출력이 봉인된 뒤에만 정답으로 연다.

주요 규칙은 동일 RAN/AMF UE ID에서 다음 전이를 찾는 것이다.

```text
Registration Request → Authentication Request → Identity Response
                                      Identity Request는 없음
```

정상 identification의 `Identity Request → Identity Response`는 경보에서 제외한다.

## 원복

실행기는 UE와 DU를 종료하고 capture를 닫는다. 작업 종료 뒤 CU/DU EC2 인스턴스도 중지한다.
OAI 소스 원복은 새 worktree를 제거하거나 패치 전 깨끗한 기준 worktree를 다시 사용한다.
