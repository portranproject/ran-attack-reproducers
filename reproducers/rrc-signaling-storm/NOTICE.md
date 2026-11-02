# NOTICE

## 이 도구는 무엇인가

침입 탐지와 완화 기능을 시험하기 위해 **사용자가 소유한** 5G NR 기지국을 대상으로
RRC signaling storm(불완전한 초기 접속)을 재현하는 연구 도구다.

## 사용 목적과 제한

- 격리된 테스트베드에서만 사용한다. 사용자가 소유했거나 시험 권한을 명시적으로 받은
  장비를 RF 차폐함 안에서 사용하거나 ZMQ 같은 가상 무선을 사용한다.
- 공용망, 공유 셀 또는 사용자가 소유하지 않은 기지국을 대상으로 절대 사용하지 않는다.
  이러한 사용은 대부분의 관할권에서 불법이다.
- 공격은 기본적으로 꺼져 있다. `-e 1`을 명시적으로 전달해야만 실행된다.
- `MAX_DURATION_S > 0`이면 프로세스 내부 타이머와 외부 `timeout`이라는 서로 독립적인
  두 개의 kill switch가 항상 활성화된다.

## 출처와 저작자 표시

이 도구는 OpenAirInterface NR UE에 적용하는 패치다. 기지국 소스는 수정하지 않는다.

- **OpenAirInterface (OAI)** — 이 패치가 적용되는 UE다.
  패치 기준선은 commit `1c2f4d3c2e68181cdef9f426d161163147ad4b77`(tag
  `2026.w38`)이다. 해당 릴리스는 소스 라이선스를 Common Source Software License 1.0
  (`LicenseRef-CSSL-1.0`)으로 명시한다. 적용되는 조건은 OAI의 `LICENSE` 파일을 확인한다.
  https://gitlab.eurecom.fr/oai/openairinterface5g
- **OAI의 radio/zmq**에는 `SPDX-License-Identifier: BSD-3-Clause-Open-MPI`가
  표시되어 있으며, 그 자체가 OCUDU/srsRAN ZMQ radio에서 파생됐다. 이 패치의
  `radio/zmq/` 수정 사항은 해당 코드에 대한 변경이다.
- **OCUDU**(srsRAN에서 파생)는 시험 대상 기지국이었다. 이 저장소에서는 이를 수정하거나
  재배포하지 않는다.
- RRCSetupComplete 미전송 시나리오(Msg4를 수신한 뒤 `RRCSetupComplete`를 생략)는
  KAUST RRC storm 검증 논문(arXiv:2608.16441)에 설명된 실험 구성을 따른다. 결과를
  출판할 경우 해당 논문을 인용한다.
- `5gattacks/5g-rrc-storm`은 가장 가까운 기존 공개 구현이다. 이 구현은 더 오래된 OAI
  commit을 대상으로 하며, 이 도구와 달리 gNB 타이머도 변경한다. **라이선스 파일이
  없으므로** 해당 구현의 코드는 이 저장소에 복사하지 않았다.

이 패치는 OAI 소스에 적용되므로 *패치가 적용된 결과물*을 재배포할 때는 OAI의 CSSL 1.0
조건을 준수해야 한다. 이 디렉터리의 패치·스크립트·문서는 이 프로젝트의 독자적인
저작물이며, 이 저장소는 제3자 OAI 코드에 별도의 라이선스 허가를 부여하지 않는다.
