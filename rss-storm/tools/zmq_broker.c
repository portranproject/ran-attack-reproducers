/* zmq_broker — N independent OAI UEs on one OAI DU cell over ZMQ.
 *
 * The OAI zmq driver is REQ/REP and assumes one UE endpoint per cell:
 *   DU TX: REP bind tx_port      UE RX: REQ connect tx_port
 *   DU RX: REQ connect rx_port   UE TX: REP bind rx_port
 * The broker terminates both sides and multiplexes N independent UE processes.
 *
 *   DL: one fetch thread drains the DU, per-UE serve threads hand one block per
 *       UE request from a bounded FIFO.
 *   UL: one thread answers each DU request by pulling one block from every UE,
 *       summing them (saturating), and replying once. With no UE yet it replies
 *       silence and paces itself at the radio rate.
 *
 * usage: zmq_broker <n_ue> [dl_du=4556] [ul_du=4557] [ue_ul_base=4600]
 * UE i: tx_channels = ue_ul_base + 2i, rx_channels = ue_ul_base + 1 + 2i
 */
#include <zmq.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define RING 1024
#define MAX_UE 32
#define DEF_SAMPLES 11520
#define SRATE 23.04e6

static int n_ue;
static void *dl_du, *ul_du, *dl_ue[MAX_UE], *ul_ue[MAX_UE];
static volatile int stop;
static long dl_rounds, ul_rounds;
static int ul_await[MAX_UE];

static void *ring[RING]; static size_t rlen[RING];
static int r_head, r_cnt;
static pthread_mutex_t r_mtx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t r_cv = PTHREAD_COND_INITIALIZER;

static int pull_nb(void *s, void **buf, size_t *len) {
  zmq_msg_t m; zmq_msg_init(&m);
  if (zmq_msg_recv(&m, s, ZMQ_DONTWAIT) < 0) { zmq_msg_close(&m); return -1; }
  *len = zmq_msg_size(&m);
  *buf = malloc(*len ? *len : 1);
  if (*len) memcpy(*buf, zmq_msg_data(&m), *len);
  zmq_msg_close(&m); return 0;
}
static int pull(void *s, void **buf, size_t *len) {
  zmq_msg_t m; zmq_msg_init(&m);
  if (zmq_msg_recv(&m, s, 0) < 0) { zmq_msg_close(&m); return -1; }
  *len = zmq_msg_size(&m);
  *buf = malloc(*len ? *len : 1);
  if (*len) memcpy(*buf, zmq_msg_data(&m), *len);
  zmq_msg_close(&m); return 0;
}
static int push(void *s, const void *b, size_t l) {
  zmq_msg_t m;
  if (zmq_msg_init_size(&m, l) < 0) return -1;
  if (l) memcpy(zmq_msg_data(&m), b, l);
  int rc = zmq_msg_send(&m, s, 0); zmq_msg_close(&m); return rc < 0 ? -1 : 0;
}
static int req(void *s) { unsigned char d = 0; return push(s, &d, 1); }
static int rep_recv(void *s) { void *b = NULL; size_t l = 0;
  if (pull(s, &b, &l)) return -1; free(b); return 0; }

static void *dl_fetch(void *arg) {
  (void)arg;
  while (!stop) {
    void *blk = NULL; size_t bl = 0;
    if (req(dl_du) || pull(dl_du, &blk, &bl)) break;   /* DU paces us */
    pthread_mutex_lock(&r_mtx);
    if (r_cnt == RING) { free(ring[r_head]); r_head = (r_head + 1) % RING; r_cnt--; }
    ring[(r_head + r_cnt) % RING] = blk; rlen[(r_head + r_cnt) % RING] = bl;
    r_cnt++;
    pthread_cond_signal(&r_cv);
    pthread_mutex_unlock(&r_mtx);
    if ((++dl_rounds % 20000) == 0)
      fprintf(stderr, "[broker] DL fetched=%ld q=%d\n", dl_rounds, r_cnt);
  }
  return NULL;
}

struct serve_arg { int i; };
static void *dl_serve(void *arg) {
  int i = ((struct serve_arg *)arg)->i;
  while (!stop) {
    if (rep_recv(dl_ue[i])) {                        /* UE asks for a block */
      if (stop) return NULL;
      continue;                                     /* timeout: keep waiting */
    }
    pthread_mutex_lock(&r_mtx);
    while (r_cnt == 0 && !stop) pthread_cond_wait(&r_cv, &r_mtx);
    if (stop) { pthread_mutex_unlock(&r_mtx); return NULL; }
    void *blk = ring[r_head]; size_t bl = rlen[r_head];
    r_head = (r_head + 1) % RING; r_cnt--;
    pthread_cond_broadcast(&r_cv);
    pthread_mutex_unlock(&r_mtx);
    int rc = push(dl_ue[i], blk, bl);
    free(blk);
    if (rc) return NULL;
  }
  return NULL;
}

static unsigned char *pend[MAX_UE];
static size_t pend_len[MAX_UE];

/* Take exactly want bytes from UE i's uplink stream, accumulating whatever
   block sizes the UE happens to send. The DU advances its sample clock by the
   reply size, so a reply of four blocks makes the DU jump four slots; the
   transport has to deliver one slot per request. */
static int take_fixed(int i, unsigned char *out, size_t want) {
  size_t have = 0;
  while (have < want) {
    if (pend_len[i] > 0) {
      size_t n = pend_len[i] < (want - have) ? pend_len[i] : (want - have);
      memcpy(out + have, pend[i], n);
      memmove(pend[i], pend[i] + n, pend_len[i] - n);
      pend_len[i] -= n;
      have += n;
      continue;
    }
    void *b = NULL; size_t l = 0;
    int ok = 0;
    if (ul_await[i]) {
      ok = (pull_nb(ul_ue[i], &b, &l) == 0);
      if (ok) ul_await[i] = 0;
    } else if (req(ul_ue[i]) == 0) {
      ul_await[i] = 1;
      ok = (pull_nb(ul_ue[i], &b, &l) == 0);
      if (ok) ul_await[i] = 0;
    }
    if (!ok) break;
    pend[i] = realloc(pend[i], pend_len[i] + l);
    if (!pend[i]) { free(b); return -1; }
    memcpy(pend[i] + pend_len[i], b, l);
    pend_len[i] += l;
    free(b);
  }
  if (have < want) memset(out + have, 0, want - have);
  return (int)have;
}

static void *ul_thread(void *arg) {
  (void)arg;
  while (!stop) {
    if (rep_recv(ul_du)) break;
    const size_t want_bytes = DEF_SAMPLES * sizeof(int16_t);
    int32_t acc[DEF_SAMPLES];
    memset(acc, 0, sizeof acc);
    int used_ue = 0;
    unsigned char buf[DEF_SAMPLES * sizeof(int16_t)];
    for (int i = 0; i < n_ue; i++) {
      int got_bytes = take_fixed(i, buf, want_bytes);
      if (got_bytes > 0) {
        used_ue = 1;
        const int16_t *sv = (const int16_t *)buf;
        size_t m = (size_t)got_bytes / sizeof(int16_t);
        for (size_t j = 0; j < m; j++) acc[j] += sv[j];
      }
    }
    const size_t n = DEF_SAMPLES, bytes = want_bytes;
    int16_t *out = malloc(bytes ? bytes : 2);
    for (size_t j = 0; j < n; j++) {
      int32_t v = acc[j];
      out[j] = v > 32767 ? 32767 : (v < -32768 ? -32768 : (int16_t)v);
    }
    /* Pace the DU clock by UE consumption: one uplink reply per slot is what
       advances the DU. If the downlink ring is filling up, the UE is behind, so
       hold the reply. Both directions then stop together instead of letting the
       DU TX queue overflow or dropping downlink blocks. */
    pthread_mutex_lock(&r_mtx);
    while (r_cnt > 64 && !stop) pthread_cond_wait(&r_cv, &r_mtx);
    pthread_mutex_unlock(&r_mtx);
    if (stop) break;
    if (push(ul_du, out, bytes)) { free(out); break; }
    if (!used_ue) {  /* silence keeps the DU clock at radio rate */
      static struct timespec next;
      long period_ns = (long)(((double)n / SRATE) * 1e9);
      struct timespec now; clock_gettime(CLOCK_MONOTONIC, &now);
      if (next.tv_sec == 0) next = now;
      next.tv_nsec += period_ns;
      while (next.tv_nsec >= 1000000000L) { next.tv_sec++; next.tv_nsec -= 1000000000L; }
      if (next.tv_sec < now.tv_sec || (next.tv_sec == now.tv_sec && next.tv_nsec < now.tv_nsec))
        next = now;
      else
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
    }
    free(out);
    if ((++ul_rounds % 20000) == 0)
      fprintf(stderr, "[broker] UL=%ld block=%zu used_ue=%d\n", ul_rounds, bytes, used_ue);
  }
  return NULL;
}

static void on_sig(int s) { (void)s; stop = 1; pthread_cond_broadcast(&r_cv); }

int main(int argc, char **argv) {
  n_ue = argc > 1 ? atoi(argv[1]) : 2;
  if (n_ue < 1 || n_ue > MAX_UE) { fprintf(stderr, "n_ue 1..%d\n", MAX_UE); return 1; }
  int dl_du_port = argc > 2 ? atoi(argv[2]) : 4556;
  int ul_du_port = argc > 3 ? atoi(argv[3]) : 4557;
  int base = argc > 4 ? atoi(argv[4]) : 4600;
  signal(SIGINT, on_sig); signal(SIGTERM, on_sig);

  void *ctx = zmq_ctx_new();
  char ep[64];
  dl_du = zmq_socket(ctx, ZMQ_REQ);
  snprintf(ep, sizeof ep, "tcp://127.0.0.1:%d", dl_du_port);
  if (zmq_connect(dl_du, ep)) { perror("connect dl_du"); return 1; }
  ul_du = zmq_socket(ctx, ZMQ_REP);
  snprintf(ep, sizeof ep, "tcp://127.0.0.1:%d", ul_du_port);
  if (zmq_bind(ul_du, ep)) { perror("bind ul_du"); return 1; }
  for (int i = 0; i < n_ue; i++) {
    ul_ue[i] = zmq_socket(ctx, ZMQ_REQ);
    snprintf(ep, sizeof ep, "tcp://127.0.0.1:%d", base + 2 * i);
    if (zmq_connect(ul_ue[i], ep)) { perror("connect ul_ue"); return 1; }
    dl_ue[i] = zmq_socket(ctx, ZMQ_REP);
    snprintf(ep, sizeof ep, "tcp://127.0.0.1:%d", base + 2 * i + 1);
    if (zmq_bind(dl_ue[i], ep)) { perror("bind dl_ue"); return 1; }
    int t = 5000;   /* UE may need seconds before its first uplink block */
    zmq_setsockopt(ul_ue[i], ZMQ_RCVTIMEO, &t, sizeof t);
    t = 200;
    zmq_setsockopt(dl_ue[i], ZMQ_RCVTIMEO, &t, sizeof t);
  }

  pthread_t td, tu, ts[MAX_UE];
  static struct serve_arg sa[MAX_UE];
  pthread_create(&td, NULL, dl_fetch, NULL);
  pthread_create(&tu, NULL, ul_thread, NULL);
  for (int i = 0; i < n_ue; i++) { sa[i].i = i; pthread_create(&ts[i], NULL, dl_serve, &sa[i]); }
  fprintf(stderr, "[broker] n_ue=%d dl_du=%d ul_du=%d ue_base=%d\n",
          n_ue, dl_du_port, ul_du_port, base);
  pthread_join(td, NULL);
  pthread_join(tu, NULL);
  for (int i = 0; i < n_ue; i++) pthread_join(ts[i], NULL);
  fprintf(stderr, "[broker] stopped DL=%ld UL=%ld\n", dl_rounds, ul_rounds);
  return 0;
}
