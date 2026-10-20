# rss-storm — RRC signaling storm reproducer (A-type incomplete access)

A controlled reproducer for an **RRC signaling storm** against a 5G NR base
station **you own**. It drives repeated initial-access attempts that are
deliberately never completed, so the gNB accumulates incomplete UE contexts
until it runs out of capacity and starts rejecting new UEs.

It is built as a **patch to the OpenAirInterface NR UE**. The base station is
never modified and never patched.

> **Isolated testbeds only.** RF-shielded enclosure or a virtual radio (ZMQ), on
> equipment you own. The attack is off unless you pass `-e 1`. See
> [NOTICE.md](NOTICE.md).

---

## What "A-type" means

| Step | Normal UE | This tool |
|---|---|---|
| PRACH / Msg1-2 | yes | yes |
| `RRCSetupRequest` (Msg3) | yes | yes |
| `RRCSetup` (Msg4) received + HARQ ACK | yes | yes |
| `RRCSetupComplete` (Msg5) | **sent** | **skipped** |
| Result at the gNB | UE attaches | context held until the gNB's guard timer expires, then released |

Because Msg5 never arrives, the gNB never sends `InitialUEMessage` to the core.
The core is never touched; the pressure is entirely on the base station's
connection state. That is what makes it a clean detection target.

---

## Requirements

- An OAI source tree, already built once, at commit
  `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (tag `2026.w38`).
  `bin/rss-build` warns if your HEAD differs.
- A 5G gNB under test and a radio path between them: ZMQ virtual radio
  (what this was developed on) or a real SDR in a shielded enclosure.
- `cmake`, a C/C++ toolchain, `python3` for the analysis scripts.
- Root on the UE host if your OAI tree lives under `/root`.

---

## Quick start

```bash
cp conf/rss.conf.example conf/rss.conf
$EDITOR conf/rss.conf          # paths, cell, gNB restart hook

bin/rss-build                 # patch + build the attacker UE

# 1. regression first: prove a normal attach still works on this build
bin/rss-run -e 0 -d 30

# 2. the attack
bin/rss-run -e 1 -u 2 -d 120

# 3. verdict, on the host that owns the gNB CU log
bin/rss-report --since 06:31:00 --until 06:33:10 \
               --jsonl /root/rss-runs/<run_id>/attempts.jsonl
```

`rss-run` prints the run id and the artifact directory. Nothing is interpreted
for you: the verdict comes from the **gNB's own log**, not from the attacker.

---

## Parameters

All three forms work and override in this order:
**command line > environment > `conf/rss.conf` > built-in default.**

### Attack shape

| Option | Env / conf | Default | Meaning |
|---|---|---|---|
| `-e 0\|1` | `ENABLE` | 0 | attack off (normal UE) / on |
| `-u N` | `NUM_UES` | 1 | attacker UE instances sharing one radio |
| `-i MS` | `INTERVAL_MS` | 0 | extra delay between attempts; 0 = as fast as the radio allows |
| `-d SEC` | `MAX_DURATION_S` | 60 | kill switch. **0 = run until stopped** |
| `-o N` | `TARGET_OCCUPANCY` | 0 | hold this many incomplete contexts; 0 = unlimited pressure |
| `-H MS` | `HOLD_MS` | 2000 | your gNB's hold time, used by the occupancy controller |
| `-c PCT` | `COMPLETION_PCT` | 0 | percent of attempts completed normally (mixed traffic) |
| `-r 0\|1` | `HONOR_REJECT` | 1 | obey `RRCReject` waitTime / retry immediately |
| `-g 0\|1` | `ACK_GATE` | 1 | do not restart random access while the Msg4 ACK is pending |
| `-G 0\|1` | `RA_GATE` | 1 | do not restart random access while one is in flight |
| `-M 0\|1` | `MSG4_WAIT` | 1 | **keep 1**, see "rejected optimisations" |
| `-n ID` | `RUN_ID` | auto | run identifier |

**`TARGET_OCCUPANCY` is a closed loop**, not a rate limit. It watches how many
contexts it is currently holding and paces attempts to land on the number you
ask for. Verified on the box: asking for 3, 6 and 12 produced exactly 3, 6 and
12 concurrent incomplete procedures in the gNB log. Use it when you need a
*repeatable* load level for a detector, and `0` when you want maximum pressure.

### Radio efficiency

| Env | Default | Meaning |
|---|---|---|
| `RSS_ZMQ_TX_WAIT_US` | `-2` | how the ZMQ TX thread waits for local samples: `0` upstream blocking 10 ms poll, `>0` usleep(n), `-1` spin, `-2` condition variable |
| `RSS_SHARE_LOCKSTEP` | `1` | hold the per-UE downlink cursors together |
| `RSS_SHARE_WR_MONOTONIC` | `0` | **keep 0**, see "rejected optimisations" |

### Cell, paths, placement

`OAI`, `UE_BIN`, `UE_CFG`, `UECAP`, `LOGDIR`, `BAND`, `DL_FREQ`,
`NUMEROLOGY`, `PRB`, `DEVICE`, `ZMQ_TX`, `ZMQ_RX`, `UE_TASKSET`,
`GNB_TASKSET`, `UE_EXTRA`, `GNB_RESTART_CMD`, `GNB_STOP_CMD`,
`GNB_LOG`, `CAPACITY`. All documented inline in `conf/rss.conf.example`.

**`GNB_RESTART_CMD` matters on a ZMQ testbed.** A ZMQ virtual radio has no
clock of its own — the sample exchange *is* the clock — so the DU and the UE
must start together or their streams never align. Put your DU restart command
there. On a real SDR leave it empty.

---

## Holding saturation

Occupancy is approximately **attempt rate times how long the gNB holds one
context**. That single line decides everything, so measure both before you
expect a result.

```
needed attempt rate  =  cell capacity / hold time
```

### Mode A — default gNB config

Capacity 96, hold about 2 s, so holding capacity needs about 48 attempts/s. One
shared ZMQ radio delivers 33–38/s. **Result: capacity is reached in bursts**
(peak 96 with `RRCReject`), but the longest continuous plateau at 96 measured
0.93 s.

What *is* held at default config: occupancy **>= 48 for 99% of a 120 s run with
a 55.41 s continuous plateau** (2 UE). Use `-o` to hold a chosen level:

```bash
bin/rss-run -e 1 -u 2 -o 48 -H 1900 -d 0     # hold 48 contexts indefinitely
```

### Mode B — reduced capacity, held saturation

`bin/rss-gnb-profile` lowers the cell's capacity through **configuration only**
— it never touches gNB source. It keeps a `.orig` backup and is idempotent.

```bash
# on the host that owns each config file
bin/rss-gnb-profile --role du apply     # capacity 96 -> 12, t300 -> 2000 ms
bin/rss-gnb-profile --role cu apply     # procedure guard -> 5000 ms
# restart your gNB so it reloads the config, then:
bin/rss-run -e 1 -u 2 -r 0 -H 1500 -d 0
...
bin/rss-gnb-profile --role du restore
bin/rss-gnb-profile --role cu restore
```

Capacity 12 with a measured hold of about 1.6 s needs only about 7.5 attempts/s,
which the tool reaches comfortably. Measured over a **200 s window** of a 420 s
run (2 UE, `-r 0`, `-H 1500`):

| | `-r 1` (default) | `-r 0` |
|---|---:|---:|
| attempts/s | 5.6 | 6.5 |
| peak occupancy | 12 / 12 | 12 / 12 |
| `RRCReject` | 388 | **7,551 (61.3/s)** |
| `DU is not able to serve the UE` | 130 | **2,517 (20.4/s)** |
| occupancy >= 6 / 12 | — | **100% of the window, 199.8 s continuous** |
| occupancy >= 9 / 12 | — | 94% of the window, 15.2 s continuous |
| occupancy >= 12 / 12 | — | 33%, 0.87 s continuous |
| longest lapse with no rejection | — | **0.45 s** |
| `rrcSetupComplete` / NGAP | 0 / 0 | **0 / 0** |

Read the two kinds of row separately:

- **Occupancy at or above half capacity was held for the entire window**, in one
  199.8 s unbroken stretch. Nothing in the run was trending toward release, so
  the duration is bounded by how long you let it run, not by the tool.
- **Occupancy exactly at 12 is only 33%** — and that is expected. At capacity the
  gNB refuses the next UE instantly, so the count sits just under the cap and
  bounces. What stays true the whole time is the refusal.
- **Denial was continuous**: 0.02 s ramp-up to the first rejection, then
  123 s+ with no lapse longer than 0.45 s.
- **The scenario stayed clean**: no `rrcSetupComplete`, no `InitialUEMessage`,
  so nothing completed and the core was never reached.

**`-r 0` (`HONOR_REJECT=0`) is what holds it.** With `-r 1` the attacker obeys
the `RRCReject` back-off and spends 95% of the run idle.

> **Verified end-to-end on the testbed through this package.** A `-d 0` run of
> `bin/rss-run -e 1 -u 2 -r 0 -H 1500` was left going for **36.5 min
> continuous**: occupancy held **>= 6 / 12 for 98% of the run (one 426 s
> unbroken plateau)** and the gNB refused service for the **entire 2191 s**
> (longest lapse 2.53 s), with **0 `rrcSetupComplete` and 0 `InitialUEMessage`**.
> The run length was bounded only by when it was stopped. Full numbers in
> [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) §8.

At capacity the gNB refuses the next UE immediately, so occupancy oscillates
just below the cap while service is denied the whole time. "Is denial held" is
therefore answered by the rejection stream, which `bin/rss-report` prints as
**denial continuity**, not by occupancy sitting exactly on the cap.

### Running with no time limit

```bash
bin/rss-run -e 1 -u 2 -r 0 -d 0       # no time limit
pkill -INT -x nr-uesoftmodem          # stop
```

With `-d 0` both kill switches are disarmed on purpose, so **you** are the kill
switch. With `-d N` two independent ones are armed: the in-process timer and an
outer `timeout` at `N+20` seconds.

---

## Choosing NUM_UES

Measured on the reference testbed (OCUDU 26.10, default gNB config, capacity 96,
hold 2000 ms, 60 s runs, one shared ZMQ radio):

| UE | attempts/s | peak occupancy | `RRCReject` | `channel timeout` (sample loss) | gaps >= 200 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 33.8 | 90 / 96 | 0 | 0 | 0 |
| 2 | 38.6 | **96 / 96** | 33 | 5,136 | 3 (5% of run) |
| 3 | 36.2 | 96 / 96 | 198 | 14,718 | 22 (39%) |
| 4 | 37.4 | 96 / 96 | 312 | 39,765 | 25 (45%) |

Read this carefully, because it is not "more UEs is better":

- **The attempt rate does not grow past 2 UE.** All instances share one radio
  and one DU MAC, so the shared layer saturates at 36-38 attempts/s.
- **What grows is sample loss.** The device discards any uplink write whose
  timestamp it has already passed, and more instances means more of that.
- Loss shows up as **1-second stalls**, which drain occupancy. At 4 UE, 45% of
  the run is inside such a gap; at 2 UE, 5%.
- So **2 UE is the recommended setting**: it is the smallest count that reaches
  capacity, and it has the fewest stalls.

Use 1 UE when you want a clean, loss-free attempt stream for detector training
(0 sample loss, but it stops at 90/96 and produces no rejects). Use 3-4 UE only
if you want many `RRCReject` events and do not care about throughput numbers.

---

## Reading the verdict

`bin/rss-report` prints three blocks.

**Occupancy** — concurrent incomplete `RRC Setup Procedure`s, paired by UE id
from the gNB log, plus how long occupancy stayed at each level:

```
peak occupancy 96   at 06:31:24
sustained occupancy
  >=  48   56.4 s of 59 s ( 95%)   longest plateau 50.33 s
  >=  96   12.6 s of 59 s ( 21%)   longest plateau  0.93 s
```

A high *percentage* with a sub-second *longest plateau* is a sawtooth, not held
saturation. Both numbers are printed because the percentage alone is misleading.

**gNB counters** — `RRCReject`, `DU is not able to serve the UE`,
`rrcSetupComplete`, `NGAP InitialUEMessage`.

**UE side** — attempts and the cost breakdown of one attempt cycle.

### What you may claim

| Claim | Evidence needed |
|---|---|
| reached the configured resource limit | peak occupancy at capacity **and** `RRCReject` present |
| saturation held | a long plateau at capacity, not just a high percentage |
| scenario stayed A-type | `rrcSetupComplete` 0 **and** `NGAP InitialUEMessage` 0 |
| normal users were denied service | a separate normal UE measured failing to attach |
| "the gNB was disabled" | the two rows above, together |

The last two cannot be shown with a single ZMQ port pair, because the attacker
and a normal UE cannot both be attached. That is a property of the testbed, not
of this tool.

---

## Optimisations that are in the tool

Each of these was measured, not assumed.

**1. ZMQ TX wake-up (about 3x the attempt rate).** Upstream's TX poll thread
can only be woken by a socket event. Once a sample request has arrived but the
local TX queue is still empty, the peer is blocked waiting for the reply and
sends nothing more, so `zmq_poll` can only return on its own **10 ms** timeout.
UE and DU talk over `127.0.0.1`, where a round trip is tens of microseconds, so
that 10 ms is a timeout constant, not transport latency: a sub-millisecond
lateness cost a whole radio frame. Measured before the fix: 4250 starved
requests x **10.01 ms** = 42.5 s lost in an 80 s run.

| | upstream (`=0`) | fixed (`=-2`) |
|---|---:|---:|
| radio time per wall second | 0.46-0.54 | **2.39-2.46** |
| attempts/s | 6.7 | **19.5-33.8** |
| peak occupancy | 20 / 96 | **90-96 / 96** |

**2. Radio sharing inside one process.** Multiple UE instances share one ZMQ
radio: one instance fetches each slot and the others take a copy, and the uplink
of all instances is summed into a single device write. An external ZMQ broker
was rejected because it would copy the sample stream a second time.

**3. Per-UE read cursors.** A round-robin copy returned a different sample count
than the caller asked for and tripped OAI's `unitTransfer == res` assertion.
Cursors give each instance exactly what it requested, in stream order.

**4. Lockstep cursors (`RSS_SHARE_LOCKSTEP=1`).** Instances join at different
stream positions after cell search and keep a constant offset, which makes every
slot produce one uplink batch per instance instead of one merged batch. The gate
holds them together. Partial effect, measured at 4 UE: out-of-order batches
9.19% -> 7.70%, sample loss 33,144 -> 27,139, radio time 1.12 -> 1.26.

**5. Measurement tools that do not lie.** `analysis/cu_occupancy.py` pairs
procedure start and end by UE id and reports plateaus, not just peaks.
`analysis/cu_count.py` compares only inside the run window. Both exist because
earlier versions silently reported whole-log totals and peak-only numbers.

---

## Rejected optimisations (do not re-try these)

| Idea | Result |
|---|---|
| raise `TRANSMIT_TS_ALIGN_TIMEOUT` | no effect by construction: `align()` returns "timestamp passed" from its first branch, before the timeout is used |
| `sched_yield` spin instead of sleeping (`=-1`) | starved wait 28.5 s -> 0.117 s but radio time 2.15 -> 1.26 and attempts fell. It starves the producer thread it waits on |
| condition variable instead of usleep (`=-2` vs `>0`) | same cost: 237 us vs 240 us. The remaining wait is the producer's real latency, not the wait mechanism. Kept as the default anyway since it burns no CPU |
| `MSG4_WAIT=0` (abandon at Msg3) | UE side looked 5x faster (10878 attempts) but the gNB created **1** context. Without waiting for Msg4 the random access never completes, so Msg3 never reaches the gNB |
| `RSS_SHARE_WR_MONOTONIC=1` | sample loss 21,178 -> 0 but attempts 2387 -> **32**. The clamp advances by one read per flush, which assumes one flush per slot; there are more, so it ran away into the future |
| core pinning (`UE_TASKSET`) | worse: 33.8 -> 24.2 attempts/s, peak 90 -> 51 |
| `ACK_GATE=0` | no change (34.1 vs 33.8 attempts/s) |

---

## Known limits

- **One attempt cycle costs 40 ms of radio time** and 30 ms of that is the
  random access procedure itself. The UE cannot shorten it, so a single
  instance is capped near 35 attempts/s on this testbed.
- **Held saturation is not demonstrated at default gNB config.** Capacity is
  reached (peak 96, rejects present) but the longest continuous plateau at 96
  measured 0.93 s. The cause is quantified: the shared radio discards about
  8-17% of uplink writes, which produces 1-second stalls.
- **Radio time is not real time.** After the TX fix it runs about 2.4x *faster*
  than real time with one instance, because ZMQ has no pacing. Report
  `air_per_wall` from the run log beside any per-second number.
- **Numbers vary between sessions.** Three 4-UE runs gave 2202-2387 attempts but
  sample loss 21k-40k and radio time 0.87-1.63. Compare only within a session.
- **A single ZMQ port pair cannot host the attacker and a normal UE at the same
  time**, so service denial for a normal user cannot be measured on this path.

---

## Files

```
bin/rss-build        apply the patch and build the attacker UE
bin/rss-run          run one experiment
bin/rss-report       verdict from the gNB log plus the UE JSONL
conf/rss.conf.example  every knob, documented inline
patch/rss-ue.patch   the UE-side patch (OAI 2026.w38)
analysis/            occupancy, counters, attempt cost breakdown
```

Every run writes `run.json` (all knobs and the cell), `attempts.jsonl`
(one record per attempt, with both clocks) and `ue.log`.

**`attempts.jsonl` is the label feed for a detection team.** Each record carries
`run_id`, `ue`, `seq`, `t_ns` (wall), `air_ms` (radio), the event, the
transmitted UE identity and the intended versus actual reach of the attempt.
