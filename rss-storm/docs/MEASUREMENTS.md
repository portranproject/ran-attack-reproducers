# Internal measurement summary

Reference testbed: OCUDU 26.10 (srsRAN-derived) with CU and DU on separate
hosts, F1 over IP, attacker UE on the DU host over a ZMQ virtual radio
(`tcp://127.0.0.1`). Cell: n78, 30 kHz SCS, 51 PRB. OAI UE at
`1c2f4d3c2e68181cdef9f426d161163147ad4b77` (`2026.w38`).

Unless a section names a retained artifact, these are historical internal notes
attributed to gNB logs and UE instrumentation. **The raw logs, run manifests,
exact window boundaries and analysis versions are not included for the
historical sections.** Preserve this distinction when citing them; this file is
a summary, not a regression fixture for the current parsers. Section 5 records
the newer p5 evidence retained under `artifacts/p5-msg3-only-20261030/`.

Counts of matching log lines are **not unique messages or UEs**. Duplicate
logging and incomplete coverage may affect them. Zero matches do not prove
that an event never occurred. The historical sections did not measure
normal-user attachment failure; section 5 adds only a same-process ZMQ probe,
not an independent UE.
The current offline parsers use explicit start-inclusive, end-exclusive windows
and cautious observational labels; historical outputs below predate those checks.

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
The original notes also claimed 85% of process lifetime, but the denominator
is not documented and conflicts with the stated 60 s run. No lifetime
percentage is retained as a result.

| | `RSS_ZMQ_TX_WAIT_US=0` (upstream) | `=-2` (default) |
|---|---:|---:|
| radio time per wall second | 0.46 – 0.54 | 2.39 – 2.46 |
| cost per starved request | 10.01 ms | 0.185 ms |
| requests served | 36,203 | 219,597 |
| attempts/s (wall) | 6.7 | 19.5 – 33.8 |
| peak occupancy | 20 / 96 | 90 – 96 / 96 |

UE and DU are on one host over loopback, where a round trip is tens of
microseconds according to the notes. The attribution of this wait to the
timeout is an interpretation; raw timing evidence is absent.

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
quantity was interpreted as schedule-related in those sessions. These records
do not rule out host bottlenecks or establish a universal rate ceiling. A gNB
log-level comparison was not performed.

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

## 4. Occupancy and recurring rejection logs

Internal notes report capacity 96, a hold near 2 s, and attempt rates of
33–38/s under the default configuration. The recorded peak was 96, but the
longest full-capacity plateau was only 0.93 s. A separate reduced-capacity
configuration used capacity 12 and a measured hold near 1.6 s. These figures
do not by themselves establish sustained capacity or user-service denial.

Two UE, capacity 12. The `HONOR_REJECT=0` column is a 200 s window out of a
420 s run (`ZWfinal-064626Z`); the `=1` column is a 102 s window
(`ZWsat-063645Z`). The rejection-count rows instead use a reported 123.2 s
window for `=0`; the exact boundaries and relationship between windows are
unverifiable from this package:

| | `HONOR_REJECT=1` | `HONOR_REJECT=0` |
|---|---:|---:|
| internally recorded attempts/s (definition/window unverified) | 5.6 | 6.5 |
| peak occupancy | 12 / 12 | 12 / 12 |
| hold median | 1457 ms | 1610 ms |
| log lines containing `RRCReject` | 388 | **7,551 (reported 123.2 s window)** |
| log lines containing `DU is not able to serve` | 130 | **2,517 (reported 123.2 s window)** |
| occupancy >= 6 | — | **rounded to 100%, 199.8 s continuous** |
| occupancy >= 9 | — | 94%, 15.2 s continuous |
| occupancy >= 12 | — | 33%, 0.87 s continuous |
| log lines containing `rrcSetupComplete` | 0 | **0** |
| log lines containing NGAP `InitialUEMessage` | 0 | **0** |

The notes describe `HONOR_REJECT=1` as idle for 95% of its window. This is an
unverified summary, not a controlled proof that one setting sustains denial.

The historical counter output recorded a 123.2 s window, a 0.02 s delay to
the first rejection log, and a 123.17 s span after that first occurrence.
Reported gaps were p50 0 ms, p99 177 ms and maximum 454 ms (rounded to 0.45 s
in the table). These describe **log cadence**, not service availability.
They also cannot be combined with occupancy figures from the 200 s window.

---

## 5. MAC-confirmed post-RRCSetupRequest abort on p5 (2026-10-30)

The initial `MSG4_WAIT=0` experiment reset random access before the queued Msg3
reached PHY, so the UE counter ran while the gNB created only one context. The
current post-RRCSetupRequest abort implementation moves the decision after the MAC scheduler's
actual Msg3 handoff, bridges that confirmation to RRC, then performs the
camped-idle reset. It is a separate variant, not RRCSetupComplete-omission.

| run | observed result |
|---|---|
| `G2-msg3-0140` | 10 UE `msg3_tx`, zero attacker Msg4, and 10/10 unique TC-RNTIs joined to current-run CU `Rx ... rrcSetupRequest` |
| `G4-u1-i0-clean` | capacity-12 profile (`nof_cell_sr_res: 1`): 661 MAC-confirmed Msg3 and 661 CU requests; 55 RRC procedure starts, 606 `DU is not able to serve` rejections, reconstructed peak 12 |
| `G13-pair-attack-valid` | same capacity-12 profile: marker-authenticated duration SIGKILL; 1,029 total Msg3, zero attacker/probe Msg4; CU 921 requests, 84 starts, 837 resource rejections, zero `InitialUEMessage` and PDU success |
| `G14-pair-recovery-control` | capacity-12 post-restart control; probe attached on its first attempt and completed Registration/PDU/TUN |
| `G34-control-cap96-hold32-valid` | corrected capacity-96 profile; attack-off Registration/PDU/TUN succeeded |
| `G35-msg3-cap96-hold32-probe` | corrected capacity-96 profile; 11/11 probe TC-RNTIs reached the CU and were resource-rejected; Msg4/Msg5/connection zero for 10.13 s |

All ten G13 probe TC-RNTIs matched exactly one CU request and one
`DU is not able to serve` rejection. Thus the probe reached the gNB rather than
disappearing in the UE's shared-radio path. The G4 peak of 12 came from the
explicit SR-resource override and is not evidence of a second hidden pool.

The corrected capacity-96 campaign first falsified sustained denial: G21 and
G32 both allowed the normal probe to connect. G26 then isolated the cause as
100 consecutive undecoded CSI reports followed by `t310=1000ms`. Extending the
experiment cleanup window without changing capacity produced G35: 11 normal
probe Msg3 transmissions, 11 exact CU requests, 11 DU-resource rejections, and
zero Msg4/Msg5/connection over 10.13 seconds. The final profile and hashes are
retained in the
[capacity-96 artifact](../../artifacts/p5-msg3-cap96-20261030/README.md).

G13/G14 use an ordinary probe in the **same OAI process and shared ZMQ radio**.
They are controlled diagnostic evidence of admission denial and post-restart
service availability, not spontaneous recovery or an independent physical
normal-UE DoS result. Independent service-impact claims
still require a stable separate-process broker or shielded OTA witness. Selected
JSON evidence, the G13 CU slice and hashes are retained in the
[p5 post-RRCSetupRequest-abort artifact](../../artifacts/p5-msg3-only-20261030/README.md).

---

## 6. Rejected ideas

| Idea | Measured result |
|---|---|
| raise `TRANSMIT_TS_ALIGN_TIMEOUT` from 0 ms | no effect by construction: `align()` returns "timestamp passed" from its first branch, before the timeout is read |
| `sched_yield` spin (`=-1`) | starved wait 28.5 s to 0.117 s, but radio time 2.15 to 1.26 and attempts fell. It starves the producer it waits on |
| condition variable vs usleep | 237 us vs 240 us per starved request. The residual is the producer's real latency, not the wait mechanism |
| old pre-PHY `MSG4_WAIT=0` hook | UE logged 10,878 attempts while the gNB created **1** context because the reset erased queued Msg3 before PHY transmission. Superseded by the MAC-confirmed post-RRCSetupRequest-abort path in section 5 |
| `RSS_SHARE_WR_MONOTONIC=1` | sample loss 21,178 to 0 but attempts 2,387 to **32**. The clamp advances once per flush and there are more flushes than slots, so it ran into the future |
| `RSS_SHARE_LOCKSTEP=1` | partial: out-of-order batches 9.19% to 7.70%, loss 33,144 to 27,139, radio time 1.12 to 1.26. Kept on |
| core pinning | worse: 33.8 to 24.2 attempts/s, peak 90 to 51 |
| `ACK_GATE=0` | no change (34.1 vs 33.8 attempts/s) |

---

## 7. Variance

Three 4-UE runs in different sessions: attempts 2202–2387, sample loss
21k–40k, radio time 0.87–1.63. Attempt counts are stable; loss and radio time
are not. **Compare loss and timing only within one session.**

---

## 8. Tool bugs found while measuring

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
- Earlier reports treated the interval before the first rejection as a lapse
  in denial. Both that interpretation and claims of continuous denial were
  unsupported; the current report describes only observed rejection cadence.
- Occupancy was tracked twice: once as a set of live UE ids (for the peak) and
  once as a +1/-1 event timeline (for the plateaus). They disagreed, because an
  end whose start fell before the window still pushed a -1 into the timeline,
  and because a plain tuple sort applies an end before a start at the same
  timestamp. The report said "peak 12" next to "0.0 s above 9". Occupancy now
  comes from one source: `len(live)` is sampled after every change.
- A run id whose second character is `O` kills the UE at startup: OAI's `-O`
  scan tests `argv[i][1] == 'O'` without checking for a leading `-`.
  `bin/rss-run` rejects such ids.

---

## 9. Historical longer run of the packaged tool

Run `ZWperm`, 2026-10-20. The **packaged** `rss-storm` deployed to the DU host
and driven entirely through `bin/rss-run` — not the development scripts — then
read back through the packaged `analysis/` on the CU host. reduced-capacity diagnostic profile
applied (`nof_cell_sr_res 1`, `t300 2000`, capacity 12). Command:

```
bin/rss-run -e 1 -u 2 -r 0 -H 1500 -d 0 -n ZWperm
```

The notes report a run of about **2191 s (36.5 min)**. Exact analysis windows
cannot be reconciled without the original logs: occupancy was labeled 2191 s,
while rejection counts/rates and the separate 25.2 s ramp-up imply different
denominators. Do not treat these as one verified common window.

Historical `analysis/cu_occupancy.py` summary (capacity 12, reported window 2191 s):

| level | share of window | longest continuous plateau |
|---|---:|---:|
| occupancy >= 3 | **100%** | **428.4 s** |
| occupancy >= 6 | 98% | **426.1 s** |
| occupancy >= 9 | 89% | 50.1 s |
| occupancy >= 12 (full cap) | 36% | 1.8 s |

peak occupancy 12/12; end reasons `cancelled` 12,339, `timed out` 1; hold
median 1846 ms.

Historical `analysis/cu_count.py` summary (exact window unverified):

| matching log pattern | occurrences |
|---|---:|
| `rrcReject` | 85,797 |
| `DU is not able to serve` | 28,599 |
| `rrcSetupComplete` | **0** |
| NGAP `InitialUEMessage` | **0** |

Previously reported rates used an inconsistent denominator and are omitted.
Do not reinterpret occurrence counts as unique over-the-air messages.

Historical cadence notes: first rejection after 25.2 s, gaps p50 0 ms / p99
256 ms, **maximum gap 2.53 s** (reported once). The separate claim of a full
2191 s after ramp-up conflicts with the stated overall window and is withdrawn.

UE side (`attempts.jsonl`): 40,253 attempts, 13,420 `msg4_rx`, 27,597
`rrc_reject`, sample loss 1.40 M.

Interpretation limits:

- The recorded share at or above half capacity is **98%, not the entire run**;
  the longest continuous interval is 426.1 s. The displayed 100% at quarter
  capacity is rounded and does not prove uninterrupted occupancy.
- Full capacity was recorded for 36%, with a longest interval of 1.8 s.
  Recurring rejection logs do not establish continuous denial, especially with
  the recorded 2.53 s gap and unresolved analysis-window boundaries.
- Zero matching completion/core-message lines is consistent with RRCSetupComplete-omission under
  adequate logging, but coverage cannot be rechecked here.
- Normal-user service impact and stability beyond this run were not tested.
- The notes report no issue with `--rss.gate_timeout_ms` (default 500) during
  this run; this is not a general reliability guarantee.
