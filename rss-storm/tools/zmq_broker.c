/* zmq_broker — N independent OAI UEs on one OAI DU cell over ZMQ.
 *
 * OAI's zmq driver is REQ/REP and assumes one UE endpoint per cell:
 *   DU  TX: REP bind tx_port (4556)   UE RX: REQ connect 4556
 *   DU  RX: REQ connect rx_port (4557) UE TX: REP bind 4557
 * The broker terminates both sides and multiplexes N UEs:
 *   DL thread: pull one block from the DU, fan it out to N UE REP peers.
 *   UL thread: on each DU request, pull one block from every UE, sum them and
 *              reply once. Every UE supplies a block per DU request (zeros when
 *              it has nothing to send), so the round stays in lockstep and the
 *              DU sees a single continuous uplink stream.
 *
 * usage: zmq_broker <n_ue> [dl_du=4556] [ul_du=4557] [ue_ul_base=4600]
 *        UE i: tx_channels=ue_ul_base+2i   rx_channels=ue_ul_base+1+2i
 */
#include <zmq.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

static int n_ue;
static void *dl_du, *ul_du;
static void *dl_ue[64], *ul_ue[64];
static long dl_rounds, ul_rounds;
static volatile int stop;
static size_t default_bytes = 11520 * sizeof(int16_t);

static int pull(void *s, void **buf, size_t *len) {
  zmq_msg_t m; zmq_msg_init(&m);
  if (zmq_msg_recv(&m, s, 0) < 0) { zmq_msg_close(&m); return -1; }
  *len = zmq_msg_size(&m);
  *buf = malloc(*len ? *len : 1);
  if (*len) memcpy(*buf, zmq_msg_data(&m), *len);
  zmq_msg_close(&m); return 0;
}
static int push(void *s, const void *buf, size_t len) {
  zmq_msg_t m;
  if (zmq_msg_init_size(&m, len) < 0) return -1;
  if (len) memcpy(zmq_msg_data(&m), buf, len);
  int rc = zmq_msg_send(&m, s, 0);
  zmq_msg_close(&m); return rc < 0 ? -1 : 0;
}
static int req(void *s) { unsigned char d = 0; return push(s, &d, 1); }
static int rep_recv(void *s) { void *b = NULL; size_t l = 0;
  if (pull(s, &b, &l)) return -1; free(b); return 0; }

static void *dl_thread(void *arg) {
  (void)arg;
  /* FIFO of DL blocks: the DU produces one block per slot, the UE consumes one
     per request. Serving the newest block dropped slots whenever the UE was a
     little late, and the UE lost sync every few hundred frames. */
  void *ring[256]; size_t rlen[256];
  int head = 0, cnt = 0;
  void *last = NULL; size_t last_len = 0;
  while (!stop) {
    void *blk = NULL; size_t bl = 0;
    if (req(dl_du) || pull(dl_du, &blk, &bl)) break;
    if (cnt == 256) { free(ring[head]); head = (head + 1) % 256; cnt--; }
    ring[(head + cnt) % 256] = blk;
    rlen[(head + cnt) % 256] = bl;
    cnt++;
    for (int i = 0; i < n_ue; i++) {
      zmq_pollitem_t it = {dl_ue[i], 0, ZMQ_POLLIN, 0};
      if (zmq_poll(&it, 1, 0) <= 0 || !(it.revents & ZMQ_POLLIN)) continue;
      void *send_b = cnt > 0 ? ring[head] : last;
      size_t send_l = cnt > 0 ? rlen[head] : last_len;
      if (rep_recv(dl_ue[i])) { free(last); return NULL; }
      if (push(dl_ue[i], send_b, send_l)) { free(last); return NULL; }
      if (cnt > 0) {
        free(last);
        last = ring[head]; last_len = rlen[head];
        head = (head + 1) % 256; cnt--;
      }
    }
    if ((++dl_rounds % 5000) == 0)
      fprintf(stderr, "[broker] DL rounds=%ld q=%d\n", dl_rounds, cnt);
  }
  free(last);
  return NULL;
}

static void *ul_thread(void *arg) {
  (void)arg;
  while (!stop) {
    if (rep_recv(ul_du)) break;            /* DU asks for one uplink block */
    size_t n = 0, bytes = 0;
    int32_t *acc = NULL;
    int used_ue = 0;
    for (int i = 0; i < n_ue; i++) {
      void *b = NULL; size_t l = 0;
      int ok = (req(ul_ue[i]) == 0) && (pull(ul_ue[i], &b, &l) == 0);
      size_t got = ok ? l / sizeof(int16_t) : 0;
      if (!acc) {
        n = ok ? got : default_bytes / sizeof(int16_t);
        bytes = n * sizeof(int16_t);
        acc = calloc(n ? n : 1, sizeof(int32_t));
      }
      if (ok) {
        used_ue = 1;
        const int16_t *s = (const int16_t *)b;
        size_t m = got < n ? got : n;
        for (size_t j = 0; j < m; j++) acc[j] += s[j];
        free(b);
      }
    }
    int16_t *out = malloc(bytes ? bytes : 2);
    for (size_t j = 0; j < n; j++) {
      int32_t v = acc[j];
      out[j] = v > 32767 ? 32767 : (v < -32768 ? -32768 : (int16_t)v);
    }
    free(acc);
    if (push(ul_du, out, bytes)) { free(out); return NULL; }
    /* Pace the DU sample clock at the radio rate. Without a UE the fallback
       blocks are produced instantly, which drives the DU clock far ahead of
       real time (RF overflow). With a UE the pull already waits for it, so this
       sleep is a no-op there. */
    {
      static struct timespec next;
      long period_ns = (long)(((double)(bytes / sizeof(int16_t)) / 23.04e6) * 1e9);
      struct timespec now;
      clock_gettime(CLOCK_MONOTONIC, &now);
      if (next.tv_sec == 0) next = now;
      next.tv_nsec += period_ns;
      while (next.tv_nsec >= 1000000000L) { next.tv_sec++; next.tv_nsec -= 1000000000L; }
      if (next.tv_sec < now.tv_sec || (next.tv_sec == now.tv_sec && next.tv_nsec < now.tv_nsec))
        next = now;
      else
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
    }
    free(out);
    if ((++ul_rounds % 2000) == 0)
      fprintf(stderr, "[broker] UL rounds=%ld block=%zu\n", ul_rounds, bytes);
  }
  return NULL;
}

static void on_sig(int s) { (void)s; stop = 1; }

int main(int argc, char **argv) {
  n_ue = argc > 1 ? atoi(argv[1]) : 2;
  if (n_ue < 1 || n_ue > 64) { fprintf(stderr, "n_ue 1..64\n"); return 1; }
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
  }
  for (int i = 0; i < n_ue; i++) {
    int t = 200;
    zmq_setsockopt(ul_ue[i], ZMQ_RCVTIMEO, &t, sizeof t);
    zmq_setsockopt(dl_ue[i], ZMQ_RCVTIMEO, &t, sizeof t);
  }

  pthread_t td, tu;
  pthread_create(&td, NULL, dl_thread, NULL);
  pthread_create(&tu, NULL, ul_thread, NULL);
  fprintf(stderr, "[broker] n_ue=%d dl_du=%d ul_du=%d ue_base=%d\n",
          n_ue, dl_du_port, ul_du_port, base);
  pthread_join(td, NULL);
  pthread_join(tu, NULL);
  fprintf(stderr, "[broker] stopped after DL=%ld UL=%ld rounds\n", dl_rounds, ul_rounds);
  return 0;
}
