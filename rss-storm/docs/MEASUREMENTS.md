# Measurements

Reference testbed: OCUDU 26.10 (srsRAN-derived) with CU and DU on separate
hosts, F1 over IP, attacker UE on the DU host over a ZMQ virtual radio
(`tcp://127.0.0.1`). Cell: n78, 30 kHz SCS, 51 PRB. OAI UE at
`1c2f4d3c2e68181cdef9f426d161163147ad4b77` (`2026.w38`).

Every number here came from the gNB's own log or from the UE's own
instrumentation. Nothing is extrapolated.

---

## 1. The single change that mattered most

Upstream's ZMQ TX poll thread can only be woken by a socket event. When a
sample request has arrived but the local TX queue is still empty, the peer is
blocked waiting for the reply and sends nothing more, so `zmq_poll` can only
return on its own 10 ms timeout.

Instrumented, single UE, 60 s:

```
TX antenna 0: 4250 REQs starved / 36203 served,
              42555 ms waiting for the local TX queue
```

42555 / 4250 = **10.01 ms per starved request** — the poll timeout exactly.
42.5 s is 85% of the process lifetime.

| | `RSS_ZMQ_TX_WAIT_US=0` (upstream) | `=-2` (default) |
|---|---:|---:|
| radio time per wall second | 0.46 – 0.54 | 2.39 – 2.46 |
| cost per starved request | 10.01 ms | 0.185 ms |
| requests served | 36,203 | 219,597 |
| attempts/s (wall) | 6.7 | 19.5 – 33.8 |
| peak occupancy | 20 / 96 | 90 – 96 / 96 |

UE and DU are on one host over loopback, where a round trip is tens of
microseconds. 10 ms could only ever have been a timeout constant, not latency.

---

## 2. Attempt cost

From `analysis/attempt_phases.py`, which reads both clocks out of
`attempts.jsonl`. Single UE, default gNB config:

| phase | wall | radio | share of wall |
|---|---:|---:|---:|
| Msg3 to Msg4 | 22.8 ms | 30 ms | **79%** |
| Msg4 to retrigger | 3.6 ms | 10 ms | 13% |
| retrigger to next Msg3 | 1.2 ms | 0 ms | 4% |
| **cycle** | **28.9 ms** | **40 ms** | 100% |

The 30 ms radio time for Msg3 to Msg4 was identical in two sessions whose wall
times differed by 6x (100–113 ms at radio/wall 0.29, 22.8 ms at 1.41). A
quantity that is constant in radio time and not in wall time is set by the
air-interface schedule, not by host speed. **That is why reducing gNB log
level was never tried: it cannot move this term.**

---

## 3. UE count

60 s runs, default gNB config (capacity 96, hold 2000 ms):

| UE | attempts/s | peak occupancy | `RRCReject` | sample loss | gaps >= 200 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 33.8 | 90 / 96 | 0 | 0 | 0 |
| 2 | 38.6 | 96 / 96 | 33 | 5,136 | 3 (5%) |
| 3 | 36.2 | 96 / 96 | 198 | 14,718 | 22 (39%) |
| 4 | 37.4 | 96 / 96 | 312 | 39,765 | 25 (45%) |

A 120 s run at 2 UE: 3904 attempts (32.5/s), peak 96, hold median 1896 ms,
only 4 gaps >= 200 ms (1% of the run), occupancy >= 48 for **99% of the run with
a 55.41 s continuous plateau**.

The attempt rate stops growing after 2 UE. All instances share one radio and
one DU MAC. What grows instead is sample loss, and loss appears as
second-long stalls that drain occupancy.

---

## 4. Held saturation

Occupancy is approximately attempt rate times hold time. At default config the
cell holds 96 contexts for about 2 s, so **holding** capacity needs about 48
attempts/s. The shared radio caps at 33–38/s, so default config reaches
capacity in bursts (peak 96, rejects present) but the longest continuous
plateau at 96 measured 0.93 s.

Reducing the cell's capacity by **configuration only** (no gNB source change,
see `bin/rss-gnb-profile`) moves the requirement into reach: capacity 12 with a
measured hold of about 1.5 s needs about 8 attempts/s.

Two UE, capacity 12. The `HONOR_REJECT=0` column is a 200 s window out of a
420 s run (`ZWfinal-064626Z`); the `=1` column is a 102 s window
(`ZWsat-063645Z`):

| | `HONOR_REJECT=1` | `HONOR_REJECT=0` |
|---|---:|---:|
| attempts/s | 5.6 | 6.5 |
| peak occupancy | 12 / 12 | 12 / 12 |
| hold median | 1457 ms | 1610 ms |
| `RRCReject` | 388 | **7,551 (61.3/s)** |
| `DU is not able to serve` | 130 | **2,517 (20.4/s)** |
| occupancy >= 6 | — | **100%, 199.8 s continuous** |
| occupancy >= 9 | — | 94%, 15.2 s continuous |
| occupancy >= 12 | — | 33%, 0.87 s continuous |
| `rrcSetupComplete` | 0 | **0** |
| NGAP `InitialUEMessage` | 0 | **0** |

`HONOR_REJECT=1` backs off on every rejection, so the attacker spends 95% of
the run idle. **`HONOR_REJECT=0` is what holds saturation.**

Once at capacity the gNB refuses the next UE immediately, so occupancy
oscillates just below the cap while service is denied continuously. The metric
that answers "is denial held" is therefore the rejection stream, which
`analysis/cu_count.py` reports:

```
denial continuity (rrcReject, window 123.2 s)
  ramp-up to first rejection   0.02 s
  denial held for              123.17 s
  gap between rejections       p50 0 ms  p99 177 ms  max 454 ms
  longest lapse once held      0.45 s
```

No half-second of the run passed without the gNB refusing a UE. The required
arrival rate for this configuration is 12 / 1.61 s = 7.5/s and the tool
sustained 6.5/s, which is why the cell sits just under the cap and refuses
continuously instead of oscillating between empty and full.

---

## 5. Rejected ideas

| Idea | Measured result |
|---|---|
| raise `TRANSMIT_TS_ALIGN_TIMEOUT` from 0 ms | no effect by construction: `align()` returns "timestamp passed" from its first branch, before the timeout is read |
| `sched_yield` spin (`=-1`) | starved wait 28.5 s to 0.117 s, but radio time 2.15 to 1.26 and attempts fell. It starves the producer it waits on |
| condition variable vs usleep | 237 us vs 240 us per starved request. The residual is the producer's real latency, not the wait mechanism |
| `MSG4_WAIT=0` | UE logged 10,878 attempts; the gNB created **1** context. Without waiting for Msg4 the random access never completes, so Msg3 never arrives |
| `RSS_SHARE_WR_MONOTONIC=1` | sample loss 21,178 to 0 but attempts 2,387 to **32**. The clamp advances once per flush and there are more flushes than slots, so it ran into the future |
| `RSS_SHARE_LOCKSTEP=1` | partial: out-of-order batches 9.19% to 7.70%, loss 33,144 to 27,139, radio time 1.12 to 1.26. Kept on |
| core pinning | worse: 33.8 to 24.2 attempts/s, peak 90 to 51 |
| `ACK_GATE=0` | no change (34.1 vs 33.8 attempts/s) |

---

## 6. Variance

Three 4-UE runs in different sessions: attempts 2202–2387, sample loss
21k–40k, radio time 0.87–1.63. Attempt counts are stable; loss and radio time
are not. **Compare loss and timing only within one session.**

---

## 7. Tool bugs found while measuring

Recorded so they are not reintroduced.

- Building only the `nr-uesoftmodem` target left the old `liboai_zmqdevif.so`
  in place, so edits under `radio/zmq/` reached the source tree but never the
  run. `bin/rss-build` now builds all three targets and greps each artifact
  for the knobs it must carry.
- A window filter of `$0 >= "HH:MM:SS"` compares the whole log line. Every line
  starts with `2026-...`, which sorts above any clock time, so the filter passed
  the entire log and whole-log totals were read as one run's totals.
- Counting only `timed out` as a procedure end missed `cancelled`, which is
  how most procedures actually end when the DU releases first. Occupancy came
  out as 591 against a capacity of 96 — an impossible number that exposed it.
- Counting the interval before the first rejection as a lapse in denial made a
  healthy run look discontinuous.
- Occupancy was tracked twice: once as a set of live UE ids (for the peak) and
  once as a +1/-1 event timeline (for the plateaus). They disagreed, because an
  end whose start fell before the window still pushed a -1 into the timeline,
  and because a plain tuple sort applies an end before a start at the same
  timestamp. The report said "peak 12" next to "0.0 s above 9". Occupancy now
  comes from one source: `len(live)` is sampled after every change.
- A run id whose second character is `O` kills the UE at startup: OAI's `-O`
  scan tests `argv[i][1] == 'O'` without checking for a leading `-`.
  `bin/rss-run` rejects such ids.
