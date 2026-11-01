# rss-storm — RRC signaling storm reproducer (RRCSetupComplete omission)

> 한국어: **[README.md](README.md)** (primary)

> **Frozen on 2026-11-02:** implementation and measurement are closed and the
> tool is documented as a detector-evaluation reproducer. The Korean
> [usage guide](docs/USAGE-GUIDE.ko.md) is authoritative.
> Sustained base-station paralysis under default cleanup was not demonstrated.

A controlled reproducer for an **RRC signaling storm** against a 5G NR base
station **you own**. It drives repeated incomplete initial-access attempts
and observes incomplete UE contexts and rejection logs. Results below are
internal summaries from one OCUDU/ZMQ testbed. A separate-process ordinary UE
was measured, but attack runs split between service failure and service success,
so deterministic normal-user denial is not demonstrated. Sanitized D6 raw
evidence, summaries, and checksums are preserved in the
[default-cleanup evidence set](../artifacts/p5-default-cleanup-rate-v2-20261030/README.md).

The final clean-lineage build also passed the live label-v1 gate. The exporter
failed closed when concurrent MAC/RRC writes interleaved the first ACK-on JSONL;
serializing the shared writer with a mutex made both ACK-on and ACK-off runs end
with `label_export=ok` and `valid=true`. A separate static
`pucch.max_consecutive_kos=20` before/after comparison produced matching aggregate counts of 20 at
each RLF and F1 Release Request/Command/Complete stage in a serial 20-attempt
run, while the attack-off control passed 20/20 pings with zero RLFs. This is not
a per-attempt ID join; it is cell-wide static hardening, not a detector-called
actuator. See the [label/RLF20 evidence](../artifacts/label-v1-rlf20-20261030/README.md).

It is built as a **patch to the OpenAirInterface NR UE**. The base station is
never modified and never patched.

> **Isolated testbeds only.** RF-shielded enclosure or a virtual radio (ZMQ), on
> equipment you own. The attack is off unless you pass `-e 1`. See
> [NOTICE.md](NOTICE.md).

---

## Attack scenario

**RRCSetupComplete-omission = incomplete initial access.** Everything from random access through
receiving Msg4 is exactly what a normal UE does. Only the last message,
`RRCSetupComplete`, is never sent.

| Step | Normal UE | This tool |
|---|---|---|
| PRACH / Msg1-2 | yes | yes |
| `RRCSetupRequest` (Msg3) | yes | yes |
| `RRCSetup` (Msg4) received + HARQ ACK | yes | ACK by default; `MSG4_ACK=0` withholds it |
| `RRCSetupComplete` (Msg5) | **sent** | **skipped** |
| Result at the gNB | UE attaches | context held until the gNB's guard timer expires, then released |

Because Msg5 never arrives, the gNB never sends `InitialUEMessage` to the core.
The core is never touched; the pressure is entirely on the base station's
connection state.

`MSG4_WAIT=0` selects a separate **post-RRCSetupRequest abort** variant. MAC first confirms that
Msg3 was handed to PHY, then RRC resets that UE to idle while keeping it camped;
the attacker therefore does not wait for or accept Msg4. This is not an
RRCSetupComplete-omission attempt and is labelled separately.

**Why this scenario**

- **The detection signal is clean.** Nothing reaches the core, so the pressure
  sits on exactly one thing: the base station's connection state.
  No observed `rrcSetupComplete` or `InitialUEMessage` is consistent with the
  scenario, but zero log matches alone do not prove it.
- **No base station change is needed.** It uses only standard Uu procedures
  (PRACH/RRC). Commercial gNBs and real-SDR OTA operation are unverified.
- **An occupancy target can be set.** `-o` uses local UE records and an assumed
  hold time. Its estimate is not guaranteed to match actual gNB occupancy.

Why it works at all — at which message the gNB commits resources, why no timer
on the network side forces a cleanup, and which config values decide the
outcome — is argued from gNB source in
[docs/MECHANISM.ko.md](docs/MECHANISM.ko.md) (Korean).

> These are descriptive labels based on standard RRC message names, not official
> 3GPP attack classes. An RRC storm is a family of procedures; other variants,
> such as repeated UE restarts, are separate work.

Legacy label-v1 and sealed-evidence machine values remain unchanged for
compatibility: `scenario="A"` and `canonical_a*` mean RRCSetupComplete omission;
`scenario="A_early"` and `canonical_msg3*` mean post-RRCSetupRequest abort; and
`scenario="A_no_ack"` means RRCSetup HARQ-ACK withholding.

---

## Testbed specification

This is the environment the tool **assumes**. Every number in
[docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) came from the setup below.

### Topology

```
   CU host (c6i.xlarge)                   DU host (c6i.2xlarge)
 +-----------------------+   F1 / IP    +--------------------------+
 |  OCUDU CU             |<------------>|  OCUDU DU                |
 |  Open5GS core         |  (VPC, priv) |  attacker UE (this pkg)  |
 |  FlexRIC              |              |   ZMQ virtual radio      |
 |  CU log /tmp/ocu.log  |              |   tcp://127.0.0.1:4556-7 |
 |  bin/rss-report       |              |                          |
 +-----------------------+              +--------------------------+
        verdict                                 attack run
```

- The attacker UE runs **on the same host as the DU**, because the ZMQ virtual
  radio is loopback. The current build, doctor and runners support only
  `oai_zmqdevif`; changing `DEVICE` does not enable OTA and is rejected. A real
  SDR needs a separate hardware-specific backend, arguments and RF-safety gate.
- The verdict is produced **on the CU host**: occupancy and rejection counters
  come from the CU log.
- CU and DU on one host works too; then both steps run in the same place.
- RRCSetupComplete-omission never reaches the core (AMF). **An AMF and a CU-UP must still be
  connected to the CU**, though: without them OCUDU's CU-CP rejects every
  `RRCSetupRequest` and the experiment cannot hold (see Prerequisites).

### Software

| Component | Version / commit | Note |
|---|---|---|
| gNB | OCUDU `release_26_10` (`e0db566a`, srsRAN-derived) | **never modified.** reduced-capacity diagnostic profile changes configuration only |
| attacker UE | OAI `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (tag `2026.w38`) | baseline commit of the default `patch/rss-ue-curated.patch` |
| radio driver | OAI `oai_zmqdevif` | the patch also changes `radio/zmq/` |
| core | Open5GS (Docker) — **must be connected** | RRCSetupComplete-omission attempts never reach NGAP, but with no AMF and no CU-UP connected, OCUDU rejects **every** `RRCSetupRequest` |
| RIC | FlexRIC | part of the testbed, unrelated to this tool |
| analysis | `python3`, standard library only | nothing to install |
| OS | Linux | the scripts use `bash`, `taskset`, `nproc`, `pgrep`, `timeout` |

### Cell

| Item | Value | conf key |
|---|---|---|
| band | n78 (TDD) | `BAND=78` |
| DL centre frequency | 3489.42 MHz (`dl_arfcn` 632628) | `DL_FREQ=3489420000` |
| SCS | 30 kHz (numerology 1) | `NUMEROLOGY=1` |
| bandwidth | 51 PRB (20 MHz channel) | `PRB=51` |
| ZMQ TX / RX | `tcp://127.0.0.1:4557` / `:4556` | `ZMQ_TX`, `ZMQ_RX` |

These **must match the cell your gNB actually broadcasts.** If they do not, the
UE stops at cell search and the run ends with zero attempts.

### gNB configuration and capacity

Capacity and hold time decide the outcome, so read both from the config and
measure both in the log.

| | default gNB profile | reduced-capacity diagnostic profile | config key |
|---|---:|---:|---|
| concurrent UE capacity | 96 | 12 | `cell_cfg.pucch.nof_cell_sr_res` 8 → 1 (DU) |
| `t300` | 1000 ms | 2000 ms | `cell_cfg.sib.t300` (DU, 3GPP max 2000) |
| RRC procedure guard | 1000 ms | 5000 ms | `cu_cp.rrc.rrc_procedure_guard_time_ms` (CU) |
| **measured** context hold | about 1900 ms | about 1460–1850 ms | from the CU log |
| internally recorded attempt rate | 33–38/s | 5.6–6.5/s | raw inputs absent; event definition/window need verification |
| internally recorded result | capacity reached in bursts | repeated rejection logs | see "Occupancy and rejection observations" |

- Capacity is `min(SR resources, CSI resources, ...)`, so lowering
  `nof_cell_sr_res` lowers it.
- **Hold time is not the sum of the configured values.** reduced-capacity diagnostic profile sums to 7000 ms
  on paper, but the DU sometimes releases first and the measured value was about
  1.6 s. Measure it in the log and pass it with `-H`.
- `bin/rss-gnb-profile` applies the profile and **never touches gNB source.** It
  keeps a `.orig` backup and is idempotent.

### Hosts

Measurements were taken on two AWS EC2 instances. These values were read off the
boxes themselves.

| Role | Instance | vCPU | CPU | Memory | OS / kernel |
|---|---|---:|---|---:|---|
| CU (OCUDU CU + core + RIC + verdict) | `c6i.xlarge` | 4 | Intel Xeon Platinum 8375C @ 2.90 GHz (1 socket) | 7.6 GiB | Ubuntu 24.04.5 LTS / `7.0.0-1014-aws` |
| DU + attacker UE | `c6i.2xlarge` | 8 | Intel Xeon Platinum 8375C @ 2.90 GHz (1 socket) | 15.3 GiB | Ubuntu 24.04.5 LTS / `7.0.0-1014-aws` |

**Internal host observations.** On the 8 vCPU DU box, odu
used about 1.7 cores and the attacker UE about 0.3, leaving **6 cores idle**
(observed with `top`/`loadavg` in a separate session, not kept as a run
artifact) —
and the recorded rate was 36–38/s. This does not rule out host bottlenecks or
establish a general performance ceiling. The original interpretation is in
[docs/MECHANISM.ko.md](docs/MECHANISM.ko.md) §6.3–§6.4. The radio was ZMQ, not a
real SDR, so no shielded enclosure or antenna was involved.

**p5 normal-attach retest, 2026-10-20.** The core, RIC and OCUDU CU started,
and the OCUDU DU established F1/E2. The first attempt with a preserved pre-patch
UE ended in a SIGSEGV after generating `RRCSetupComplete`. The kernel fault
address and disassembly identified a `NULL` common PUCCH resource dereference
in the UE scheduler's multiplexing path. We applied the corresponding
[upstream OAI fix](https://github.com/openairinterface/openairinterface5g/commit/3d4b1923b424be974c1dadcc9c48eddbe8428ba0).
Before applying it, `bin/rss-bootstrap` shallow-cloned and built a fresh,
unmodified OAI `2026.w38` without `--deps`; its first normal attach succeeded.
That single success does not remove the intermittent PUCCH crash risk in stock
OAI. With the fix, joint DU/UE restarts produced **10/10 normal attaches** and
**50/50 pings** to the core gateway `10.45.1.1`, with no further UE SIGSEGV.
The old modified OAI source and RSS-patched build were deleted. We then ran
`rss-build` on the fixed OAI branch: UE, ZMQ and static targets compiled and
the knob checks passed. After the build, `rss-doctor` reported zero blockers
and two expected warnings. `rss-run -e 0 -u 1 -d 30` reached
`RRCSetupComplete`, PDU acceptance and `oaitun_ue1` configuration, then its
outer timeout ended it at 50 seconds. Its UE log contained 15 `channel timeout`
events, so this does not establish stable radio operation. A separate normal
attach via the control panel using the same patched build pinged the gateway
**5/5 times**. Afterward, the patched source and build were removed and the
fixed normal UE was rebuilt without RSS binary markers. At the end of that
retest, p5 DU `/root/OAI` was the clean `codex/oai-pucch-null-fix` branch
(`6d6782b`). Its
second joint DU/UE start attached and pinged **5/5 times**, with no subsequent
kernel UE SIGSEGV. Temporary scripts were removed and both EC2 instances were
stopped. This verifies the **normal UE over ZMQ** path. `-e 1` attack execution,
SDR over the air, data beyond the gateway and the fix's effect on suppressed
SR/CSI remain unverified.

**Curated validation, 2026-10-30.** We preserved the subsequently modified
`/root/OAI` tree and used a separate clean `2026.w38` worktree. The official
PUCCH fix plus `patch/rss-ue-curated.patch` applied cleanly and the UE, ZMQ and
static targets built. An attack-off UE attached, accepted registration and a
PDU session, and passed the gateway ping check. We then alternated slow,
single-attacker `MSG4_ACK=1/0` runs three times. The ACK-enabled runs recorded
64-65 DU HARQ ACKs and zero max-retransmission discards; every ACK-withheld run
recorded zero ACKs, 456-477 DTX outcomes and 38-40 max-retransmission discards.
No run sent Msg5 or crashed. This validates the initial and retransmitted Msg4
ACK-withholding path over ZMQ. That campaign did not establish independent
normal-UE impact. The artificial-hold CU200 diagnostic below closes only the
exact-ACK confirmation and admission-observation checks; default-cleanup denial remains
open. Shielded OTA interoperability and the detection-to-response loop remain open.
See [the validation record](docs/CURATED-VALIDATION-20261030.ko.md).

**Label v1 and static RLF validation, 2026-10-30.** The shared JSONL writer in
the final curated build is mutex-serialized, fixing interleaved MAC ACK and RRC
events. Ten ACK-on attempts exported ten UE-side omission candidates; a later p5 run
used the final binary (`202934f7...`) in the CU200 V4 campaign and produced
176 exact `canonical_a=true`, `du_ack_state=ack` attempts across three attacker
cells. Every manifest verifies. Ten ACK-off attempts exported no candidates and
ten final `false` records. Aggregate DU ACK counts are never promoted. With only
`max_consecutive_kos=20` changed, a serial 20-attempt run produced matching
aggregate counts of 20 at every RLF and F1 release stage. A roughly 60-second
attack-off control registered, created
a PDU session, passed 20/20 pings, and recorded zero RLFs. The DU config was
restored to its original SHA-256. Shielded OTA, long or poor-channel normal-UE
safety, and an external detector-triggered actuator remain unverified. See the
[aggregates and remote-source hashes](../artifacts/label-v1-rlf20-20261030/README.md).

**CU 200 hold32 diagnostic on p5, 2026-10-30 — not a success verdict.** Without changing the CU
`max_nof_ues: 200` or per-cell DU capacities, three exact-ACK-confirmed RRCSetupComplete-omission cells
raised reconstructed CU occupancy to exactly 200 and held it there continuously
for 15.68 seconds. An ordinary witness on a separate fourth cell then received
17/17 `RRCReject` responses over 16.31 seconds, with zero Msg4,
`RRCSetupComplete`, registration, PDU session, or channel-timeout events. Before
load, all four control cells completed RRC; one also completed registration,
PDU setup, and TUN configuration. However, this profile extended the roughly
2-second default cleanup to 32 seconds and stopped before the first expiry.
It proves exact-ACK-confirmed RRCSetupComplete omission and CU-200 reachability, not that attack arrivals
beat the default release rate. See the
[CU200 diagnostic](../artifacts/p5-cu200-3cell-20261030/README.md).

**Default-cleanup D6 follow-up, 2026-10-30.** With the gNB cleanup/RLF values,
DU capacity 96, and CU cap 200 unchanged, three 6-process-by-2-UE post-RRCSetupRequest abort runs
all produced primary-witness service failure during load and successful
registration, PDU setup, and ping on a separate prelaunched endpoint after the
attack stopped. In the fastest run, D6F48, Msg3 offered load was 77.408/s and
DU provisional creation was 73.338/s versus 34.209/s cleanup; both exceeded
cleanup in all 12 complete five-second windows. The excess 2,373 arrivals were
rejected before Setup admission, so admitted Setup converged to cleanup and
occupancy peaked at 95/96. An otherwise matched eight-endpoint attack-off control
completed service and passed 303/303 pings. A separate exact-ACK-confirmed
RRCSetupComplete-omission run, D6F50,
confirmed 149 exact current-run DU HARQ-ACK joins and zero attacker Msg5, but its
ordinary UE retained registration, PDU, and ping service during the attack.
Thus post-RRCSetupRequest abort service-level off/on repeated 3/3 and the
exact-ACK-confirmed omission mechanism is confirmed, but 30-second saturation and whole-gNB paralysis
remain unproven. See the
[default-cleanup evidence](../artifacts/p5-default-cleanup-rate-v2-20261030/README.md).

### Prerequisites

- **You do not need an OAI tree in advance.** `bin/rss-bootstrap` clones it from
  the official repository at tag `2026.w38` with a shallow clone and does the
  first build (tens of minutes). An existing tree is reused only if it is clean;
  preserve local changes and use a separate clean OAI path otherwise. Existing
  artifacts with RSS markers are refused; reusing unmarked artifacts does not
  establish stock provenance. A tree with artifacts built at a different commit
  is also refused. Do not rerun `rss-bootstrap` on the current p5 DU fix branch;
  `rss-build` recognizes its existing PUCCH fix.
- `git`, `cmake`, a C/C++ toolchain, `python3`. OAI's system packages are
  installed by `bin/rss-bootstrap --deps`.
- Root on the UE host if the OAI tree and run artifacts live under `/root`;
  likewise for reading the CU log.
- A radio path between gNB and UE: ZMQ virtual radio is the only currently
  runnable path. Shielded real-SDR OTA requires a separately implemented and
  verified hardware inventory, driver, clock, gain, attenuation and leakage gate.
- For OTA G0 preparation, copy `conf/ota-inventory.example.json` to the ignored
  `conf/ota-inventory.json`, then run
  `python3 analysis/validate_ota_inventory.py conf/ota-inventory.json`. Exit 0
  proves manifest completeness only, not the physical cross-check or permission
  to transmit.
- **A core (AMF) and a CU-UP must be connected to the CU.** RRCSetupComplete-omission attempts never
  reach the core, but without those connections OCUDU's CU-CP rejects every
  `RRCSetupRequest` and the experiment cannot start at all.

---

## How to use

This repository is all you need. You do not have to prepare an OAI tree
yourself — step 1 fetches and builds it. The gNB (OCUDU) is assumed to be
already running.

### At a glance

```bash
git clone <this repo> rss-storm && cd rss-storm
bin/rss-bootstrap                        # 1. fetch OAI and build it once
cp conf/rss.conf.example conf/rss.conf   # 2. configure
$EDITOR conf/rss.conf
bin/rss-build                            # 3. apply PUCCH fix + RSS patch, build UE
bin/rss-doctor                           # 4. check build and prerequisites
bin/rss-run -e 0 -u 1 -d 30              # 5. normal-attach regression
bin/rss-run -e 1 -u 2 -d 120             # 6. attack
bin/rss-report --since HH:MM:SS --until HH:MM:SS   # 9. verdict (CU host)
```

**Where to run it**: on the host that will run the attacker UE, normally the
same host as the DU. Only the verdict step runs on the CU host. The default
paths live under `/root`, so **run as root** (`sudo -i`, or prefix every command
with `sudo`).

### 1 — prepare the OAI tree

```bash
bin/rss-bootstrap            # default: fetch + checkout baseline + first build
# Only if missing libraries caused failure: bin/rss-bootstrap --deps
```

What it does:

1. Shallow-clones OAI tag `2026.w38` from the official repository into `$OAI`
   (default `/root/OAI`) if no tree is there.
2. **Checks out the baseline commit `1c2f4d3c…` (tag `2026.w38`)**, which is
   what this patch was made against.
3. With `--deps`, installs OAI's system packages via `build_oai -I`. That
   changes the host, so it is **not done by default**. Pass it once if the build
   fails on a missing library.
4. Builds the stock UE once: `build_oai --nrUE -w ZMQ`. The `-w ZMQ` part also
   builds the radio driver this tool patches (`oai_zmqdevif`). The gNB is not
   built.
5. Verifies that `nr-uesoftmodem` and `liboai_zmqdevif.so` exist.

**This step is slow**: a cold build takes tens of minutes. A clean existing tree
is reused, but one with build artifacts from a different commit is refused. An
existing build at the baseline commit without RSS markers is kept. `--force`
reruns the build, but old artifacts may still be reused. **Only a first build
from a clean baseline source with no existing build artifacts** establishes
stock binary provenance.
The stock UE at the baseline commit can still hit the intermittent PUCCH crash
described above. The next step, `rss-build`, applies the official fix; it is
present even when the resulting UE runs with the attack off (`-e 0`).
On the current p5 DU fix branch, skip this step and proceed to `rss-build` after
configuration.

### 2 — configure

```bash
cp conf/rss.conf.example conf/rss.conf
$EDITOR conf/rss.conf
```

At minimum, match these to your environment. The rest can stay at defaults.

| Key | Why |
|---|---|
| `OAI` | path to the OAI source tree; build and run both read it |
| `UE_CFG` | path to the OAI UE config file |
| `BAND` `DL_FREQ` `NUMEROLOGY` `PRB` | must match the cell your gNB broadcasts |
| `ZMQ_TX` `ZMQ_RX` | the ZMQ port pair your DU exposes |
| `GNB_RESTART_CMD` | **effectively required on a ZMQ path**, see below |
| `LOGDIR` | where run artifacts accumulate |
| `ODU_LOG` | optional single-sector append-only OCUDU DU log; requires `log.fapi_level: debug` and seals this run's FAPI HARQ-ACK slice for final RRCSetupComplete-omission joins |
| `ODU_SECTOR_ID` | OCUDU `Sector#N` used with `ODU_LOG`; missing or other-sector evidence fails closed |
| `GNB_LOG` `CAPACITY` | used by the verdict step on the CU host |

- **Keep `ENABLE=0` as the file default.** An accidental run is then a normal
  UE; the attack turns on only when you pass `-e 1` explicitly.
- To keep the config elsewhere, set `RSS_CONF=/path/to/rss.conf`.
- **A ZMQ virtual radio has no clock of its own** — the sample exchange *is* the
  clock. If the DU and the UE do not start together their streams never align,
  so put your DU restart command in `GNB_RESTART_CMD` and let `rss-run` restart
  the DU for every run.
- **Use a command that starts the DU only.** One that also starts a normal UE
  will take the ZMQ port pair first and the attacker UE will not attach.
- **Never use a pipeline in that command.** The pipe's write end stays open, so
  EOF never arrives and the run can block forever. `bin/rss-doctor` catches this.

### 3 — build

```bash
bin/rss-build
```

What it does:

1. **Refuses any OAI tree with uncommitted changes or untracked files.**
   Changes are never reset automatically; review, preserve and resolve them
   yourself. In a clean tree, creates or checks out `rss-ue-a-type`.
2. Applies the [official OAI PUCCH crash fix](https://github.com/openairinterface/openairinterface5g/commit/3d4b1923b424be974c1dadcc9c48eddbe8428ba0)
   only if absent, then applies the RSS UE patch. The UE binary contains the
   crash fix even when the attack is off.
3. Builds **three targets**: `nr-uesoftmodem`, `oai_zmqdevif` and
   `zmq_radio_static`. The radio driver is a separate shared library
   (`liboai_zmqdevif.so`) that the UE loads at runtime, so building only the UE
   binary leaves `radio/zmq/` changes out of the run.
4. Greps the built artifacts with `strings` for the knobs they must carry
   (`target_occupancy`, `msg4_wait`, `RSS_SHARE_LOCKSTEP`,
   `RSS_ZMQ_TX_WAIT_US`) and **fails if any is missing** — a successful build
   without the knobs produces runs you cannot trust.

Existing binaries are backed up as `.orig`. A previous patch application also
leaves uncommitted changes; review, preserve and resolve them before re-running.

### 4 — run the doctor

```bash
bin/rss-doctor
```

Run this after the build: a stock binary lacks RSS knobs and fails this check.
The doctor is read-only. It checks host commands, the config file, the OAI tree
and its commit, the build artifacts, **whether the knobs actually made it into
the binary**, the UE config, artifact-directory permissions, whether the ZMQ
ports are listening, the restart hook, and access to the CU log.

```
== attacker UE binary
  [ok]   binary: /root/OAI/cmake_targets/ran_build/build/nr-uesoftmodem
  [ok]   knobs present (target_occupancy, msg4_wait, RSS_SHARE_LOCKSTEP)
```

Any `[FAIL]` exits 1, and each line names the command that fixes it. A `[warn]`
can be normal (the DU is down for now; this host has no CU log). **Only move on
when there are no blockers.**

### 5 — regression baseline first

```bash
bin/rss-run -e 0 -u 1 -d 30
```

Prove that a normal attach works on this build with the attack off. **Pass
`-u 1` explicitly**: the shipped config defaults to `NUM_UES=2`, and two normal
UEs on one radio with one subscriber identity is not a meaningful baseline — on
this testbed it crashed the UE (rc=139). `rrcSetupComplete` shows that the RRC
stage was reached, not that attachment completed. Confirm that `oaitun_ue1`
received an address and can reach the core gateway. On p5, `rss-run -e 0` with
the fixed, RSS-patched build reached PDU acceptance and tunnel configuration;
a separate normal attach with that same build pinged the gateway 5/5 times.
Its `rss-run` log had 15 `channel timeout` events, so radio stability is not
established by this test.

Skip this and a zero-attempt attack run is ambiguous: **you cannot tell a cell
misconfiguration from an attack-logic problem.** 30 s is one observation window,
not a guarantee that the first attempt succeeds.

### 6 — run the attack

```bash
bin/rss-run -e 1 -u 2 -d 120              # default gNB profile
bin/rss-run -e 1 -u 2 -o 48 -H 1900 -d 0  # estimated occupancy target 48
```

- `-u 2` is the recommended setting: the smallest count that reaches capacity,
  with the least sample loss (see "Choosing NUM_UES").
- Existing reduced-capacity diagnostic observations are in "Occupancy and rejection observations".
- `-o` is an estimated occupancy target; verify actual load separately in CU logs.
- `-d` is the kill switch. OAI w38 crashed in multi-UE INT and TERM teardown,
  so the runner writes duration and forced-kill markers before sending SIGKILL
  directly. Only that marker-authenticated `rc=137` is a valid controlled
  duration stop; an unmarked SIGKILL remains invalid.

### 7 — stop

```bash
pkill -INT -x nr-uesoftmodem
```

With `-d 0` both kill switches are disarmed on purpose, so **you** are the kill
switch.

The exit code is reported as-is: `130` is SIGINT, `137` is SIGKILL, and `139`
is SIGSEGV. `137` is valid only with the runner's duration and forced-kill
markers; an unmarked `137` and every `139` make the run invalid.

### 8 — artifacts and self-check

Each run lands in `$LOGDIR/<run_id>/`. **An existing file, directory or symlink
at that path is rejected**, so results are not overwritten. A run ID starts
with an ASCII letter or digit and then uses only ASCII letters, digits, `.`,
`_` or `-`. The existing OAI restriction also forbids `O` as its second character.

| File | Contents |
|---|---|
| `run.json` | schema, scenario, every knob, cell, full UE commit, UE binary/RSS patch/runner/exporter/redactor/scanner SHA-256, start time and clock evidence |
| `attempts.jsonl` | immutable UE ground-truth events; multiple events can belong to one attempt. **Do not feed it to the detector.** Written only on `-e 1` runs |
| `ground_truth.jsonl` | one conservative normalized record per `(run_id, ue, seq)`; an unknown ACK never becomes a confirmed RRCSetupComplete-omission attempt |
| `odu.log` | complete DU log lines appended during this run, when `ODU_LOG` capture succeeds |
| `du_log_slice.json` | source inode/offsets, discarded leading/trailing partial bytes and slice SHA-256 |
| `du_log_start.json` `du_log_capture.err` | optional capture boundary and failure diagnostics |
| `ue.log` | UE stdout with subscriber/auth lines removed; run directory mode 0700 and file mode 0600 |
| `ue_redaction.json` `ue_redaction.err` | UE-log sanitation status, redacted-line count, output SHA-256 and diagnostics |
| `sensitive_artifact_check.txt` | successful plaintext-credential scan of the whole run immediately before sealing |
| `gnb_boot.txt` | output of `GNB_RESTART_CMD` |
| `run_stop.json` | exit status, validity, reason, controlled-duration kill/detach state, DU ACK join state (`matched|no_match|capture_*|not_requested`), slice SHA-256 and stop time |
| `evidence_manifest.json` | run ID, size and SHA-256 seal for the core artifacts above |

Read the self-check `rss-run` prints as it exits.

- **No `[RSS]` banner means the run is invalid** — the knobs were not parsed,
  and the script exits non-zero.
- The OAI source patch no longer prints UICC subscriber values or direct Milenage authentication vectors, and the runner checks the
  UE log again immediately after exit. Any unexpected redaction invalidates the
  run; a failed whole-run pre-seal scan suppresses `evidence_manifest.json`.
- `attempts=0` means it never got past cell search or random access. An attack
  run exits non-zero. (In an `-e 0` regression run it is 0 by design: nothing
  is recorded when the attack is off.)
- `RRCSetupComplete omission UE-side` counts candidates where the UE scheduler queued the ACK and Msg5
  was skipped. `RRCSetupComplete omission final` increases only when `ODU_LOG` is enabled and the exact
  FAPI ACK tuple is unique on both the UE and DU sides. Missing, failed or
  ambiguous capture remains `RRCSetupComplete omission unknown`; `du_ack_join=no_match` means the slice
  was captured, not that ACK failure was proven.
- Run `python3 analysis/evidence_manifest.py verify <run-dir>` to check artifact
  hashes and run IDs. Seal and verify also rescan the whole run directory with
  the current scanner in the executing checkout, so that checkout must be
  trusted. A final RRCSetupComplete-omission demonstration must also pass `--require-matched`.
- `--require-matched` also regenerates labels from the sealed raw UE events and
  DU log and requires an exact match with `ground_truth.jsonl`.
- Many `ch.timeout` (`Error, channel timeout`) means heavy sample loss; lower
  `-u`.

### 9 — verdict (on the CU host)

```bash
bin/rss-report --since 2026-10-20T06:31:00 --until 2026-10-20T06:33:10 \
               --jsonl /root/rss-runs/<run_id>/attempts.jsonl
```

- **The time window is required.** Without it you read whole-log totals as one
  run's numbers — that mistake actually happened here.
- Replace the example date and times with the actual analysis window. Windows
  are **start-inclusive, end-exclusive**. Match the **gNB log's time basis and
  timezone notation**; do not confuse them with the UTC in `run.json`.
- `HH:MM:SS` is accepted only when log dates identify one interval. Empty,
  ambiguous or non-overlapping windows are rejected. Analysis stops if the log
  lacks the timestamp coverage needed for full-window metrics.
- `--jsonl` is optional; copy it over from the UE host to add the UE-side view.
  The UE summary reads the **whole supplied JSONL file**; `--since`/`--until`
  filter only the CU log. Matching periods are not enforced, so different
  periods must not be compared directly.
- With the reduced-capacity diagnostic profile pass `--capacity 12`; the default is 96.
- See "Reading the verdict" below for the output. The verdict comes from the
  **gNB's own log**. It does not directly establish user-service denial.

### 10 — restore

```bash
bin/rss-gnb-profile --role du restore     # if you applied the diagnostic profile
bin/rss-gnb-profile --role cu restore
# restart your gNB so it reloads the config
```

The previous UE binary is in the `.orig` copy kept by `bin/rss-build`. Review
and preserve source changes before handling them manually; switching branches
alone does not restore the OAI source tree.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `bin/rss-doctor` reports blockers | each `[FAIL]` line names the fix. Start there |
| no `[RSS]` banner | binary without the patch. Re-run `bin/rss-build` and check that the knob check passes |
| `RSS patch does not apply cleanly` | the OAI source is incompatible with this patch or it was already applied. Check a clean `2026.w38` or verified fix branch; do not force the patch |
| `OAI PUCCH crash fix does not apply cleanly` | the OAI source is neither recognized as fixed nor compatible with this fix. Check for stock `2026.w38` or the verified fix branch; do not force the patch |
| `no build dir ... build stock OAI once first` | run `bin/rss-bootstrap` first |
| the build fails on a missing library | run `bin/rss-bootstrap --deps` once |
| zero attempts, cell search fails | cell parameters do not match, or the DU is not up. On ZMQ, set `GNB_RESTART_CMD` |
| the UE hangs at `Intializing UE Threads` | the DU's and the UE's ZMQ streams are out of step. The DU must be restarted together with the UE via `GNB_RESTART_CMD` |
| `run_id ...: second character must not be 'O'` | OAI's `-O` parsing bug (any argument whose second character is `O` is taken as the config-file option). Rename the run |
| many `Error, channel timeout` | sample loss. Lower `-u` to 2 or less |
| `cannot read /tmp/ocu.log` | wrong host or insufficient permission. Pass `--log`, or use sudo |
| the gNB restart command never returns | you used a pipeline in `GNB_RESTART_CMD`. Make it a single command |
| `gNB did not become ready` | `GNB_READY_CMD` did not succeed before its deadline. Inspect `gnb_ready.txt` for the DU/F1/ZMQ readiness failure. The UE is not launched in this case |
| broker `sync_ues < 5` / `startup.sync_timeout: true` | five-UE GNU Radio startup race, not an attack outcome. The runner stops before the observation window after 30 seconds by default. Use a fresh run ID manually or `bin/rss-broker-witness-retry` to retry only this condition |
| broker `teardown.*` is 137/139 or `forced_kill_count > 0` | diagnostic SIGKILL/SIGSEGV/forced-stop status. The current two-stage UE shutdown should produce five UE exit statuses of 0, broker 0 and no forced kill. The retry wrapper stops on any teardown anomaly |
| occupancy does not rise | measure capacity and hold time first. See "Occupancy and rejection observations" |
| every attach is rejected | no AMF and no CU-UP are connected to the CU. OCUDU rejects every `RRCSetupRequest` in that state |

---

## Parameters

All three forms work and override in this order:
**command line > `conf/rss.conf` > environment > built-in default.**

The scripts source the config file first, so **a key present in the config file
overrides an exported environment variable of the same name.** Comment the key
out of the file if you want the environment to win.

### Attack shape

| Option | Env / conf | Default | Meaning |
|---|---|---|---|
| `-e 0\|1` | `ENABLE` | 0 | attack off (normal UE) / on |
| `-u N` | `NUM_UES` | 1 | attacker UE instances sharing one radio |
| `-i MS` | `INTERVAL_MS` | 0 | extra delay between attempts; 0 = as fast as the radio allows |
| — | `PHASE_MS` | 0 | persistent per-retry stride for non-probe UEs: add `UE ID × PHASE_MS` (0..5000ms) on every retry; probes and attack-off are unchanged |
| `-d SEC` | `MAX_DURATION_S` | 60 | kill switch. **0 = run until stopped** |
| `-o N` | `TARGET_OCCUPANCY` | 0 | UE-side estimated occupancy target; actual gNB occupancy is not guaranteed. 0 = no target limit |
| `-H MS` | `HOLD_MS` | 2000 | your gNB's hold time, used by the occupancy controller |
| `-c PCT` | `COMPLETION_PCT` | 0 | **one-shot check.** Above 0 it completes one attempt normally and **ends the run there.** It does not generate sustained mixed traffic |
| `-r 0\|1` | `HONOR_REJECT` | 1 | obey `RRCReject` waitTime / retry immediately |
| `-g 0\|1` | `ACK_GATE` | 1 | do not restart random access while the Msg4 ACK is pending |
| `-G 0\|1` | `RA_GATE` | 1 | do not restart random access while one is in flight |
| `-M 0\|1` | `MSG4_WAIT` | 1 | 1 = exact-ACK-confirmed RRCSetupComplete-omission; 0 = post-RRCSetupRequest abort reset after MAC-confirmed Msg3. post-RRCSetupRequest abort rejects `-o > 0` because its gNB-observed lifetime controller is not implemented |
| `-p N` | `PROBE_UES` | 0 | instances 0..N-1 are **ordinary UEs**, not storm instances: they connect, register and get a PDU session. This is the "can a normal UE still connect" measurement |
| `-t MS` | `PROBE_DELAY_MS` | 0 | delay the probe's **first** attach: from the first non-probe MAC-confirmed Msg3 in a mixed process, or from process start in an all-probe process |
| — | `PROBE_RA_ONLY` | 0 | repeat RA and skip Msg5. This measures RRC admission, not normal attach or PDU availability |
| — | `PROBE_INTERVAL_MS` | 1000 | minimum interval between RA-only probe attempts, so the measurement does not fill the CU itself |
| `-A 0\|1` | `MSG4_ACK` | 1 | 0 withholds the attacker UE's initial and retransmitted Msg4 HARQ-ACK PUCCH; probes always ACK. Three p5 single-attacker ACK-on/off comparisons measured ACK 64-65→0, DTX 18-20→456-477 and max-retransmission discards 0→38-40. A broker witness measured service impact, but results were non-deterministic and OTA remains unverified. Cannot be combined with `-c > 0` |
| — | `GNB_SETTLE_S` | 4 | wait between the configured gNB stop and restart hooks so F1-U resources can be released |
| — | `GNB_READY_CMD` | empty | deployment-specific read-only readiness check, polled until it returns 0; a failure prevents the UE from starting |
| — | `GNB_READY_TIMEOUT_S` | 30 | total readiness deadline (1–300 seconds) |
| — | `GNB_READY_INTERVAL_S` / `GNB_READY_PROBE_TIMEOUT_S` | 1 / 5 | delay between checks / deadline for one check |
| — | `ODU_LOG` | empty | optional local/mounted single-sector OCUDU DU log; requires `log.fapi_level: debug` and seals only this run's complete lines |
| — | `ODU_SECTOR_ID` | empty | required 0..65535 sector ID with `ODU_LOG`; recorded in run.json and checked against every FAPI candidate prefix |
| — | `GATE_TIMEOUT_MS` | 500 | force the retry if a gate has held it this long (0 = never force). No command-line letter |
| `-n ID` | `RUN_ID` | auto | run identifier |

**`TARGET_OCCUPANCY` uses a UE-side occupancy estimate.** It depends on local
events and the fixed hold-time assumption in `HOLD_MS`, without actual gNB
occupancy feedback. Early release or variable hold times can make it differ
from the gNB. Internal notes report matching targets of 3, 6 and 12, but the
raw evidence is not included. Do not use the estimate as detector ground truth;
keep it separate from occupancy observed in CU logs.

### Radio efficiency

| Env | Default | Meaning |
|---|---|---|
| `RSS_ZMQ_TX_WAIT_US` | `-2` | how the ZMQ TX thread waits for local samples: `0` upstream blocking 10 ms poll, `>0` usleep(n), `-1` spin, `-2` condition variable |
| `RSS_SHARE_LOCKSTEP` | `1` | hold the per-UE downlink cursors together |
| `RSS_SHARE_NUE` | `NUM_UES` | number of PHY instances in the shared-radio batch. `rss-run` rejects partial batches: an attached probe still writes PHY samples, and excluding it causes partial uplink flushes, backwards timestamps, channel timeouts and a crash. Use a separate process/RF path for independent normal-UE evidence |
| `RSS_SHARE_WR_MONOTONIC` | `0` | **keep 0**, see "rejected optimisations" |

### Cell, paths, placement

`OAI`, `UE_BIN`, `UE_CFG`, `UECAP`, `LOGDIR`, `BAND`, `DL_FREQ`,
`NUMEROLOGY`, `PRB`, `DEVICE`, `ZMQ_TX`, `ZMQ_RX`, `UE_TASKSET`,
`GNB_TASKSET`, `UE_EXTRA`, `GNB_RESTART_CMD`, `GNB_STOP_CMD`, `GNB_READY_CMD`, `ODU_LOG`, `ODU_SECTOR_ID`,
`CLOCK_SYNC_METHOD`, `CLOCK_OFFSET_NS`, `CLOCK_UNCERTAINTY_NS`,
`CLOCK_EVIDENCE_SHA256`, `GNB_LOG`, `CAPACITY`. All documented inline in
`conf/rss.conf.example`.
The current runners accept only `DEVICE=oai_zmqdevif`. `UE_EXTRA` is for
logging and thread tuning; it cannot replace runner-owned radio, cell,
`--rss.*`, `-O` or `--num-ues` options.
Keep the clock fields `unmeasured`/`null` until an offset and uncertainty are
actually measured; cross-host detection or response latency is otherwise
unscorable.

**`GNB_RESTART_CMD` matters on a ZMQ testbed.** A ZMQ virtual radio has no
clock of its own — the sample exchange *is* the clock — so the DU and the UE
must start together or their streams never align. Put your DU restart command
there.

A zero exit from `GNB_RESTART_CMD` does not prove service readiness. Set a
deployment-specific `GNB_READY_CMD` that quickly and read-only checks the DU,
F1 association and ZMQ/SDR readiness signal. The command text is deliberately
not copied to `run.json`; only whether the check was enabled and its deadline
are recorded, avoiding accidental credential disclosure.

### Independent five-UE broker witness

`bin/rss-broker-witness` waits up to `BROKER_SYNC_TIMEOUT_S` (30 seconds by
default) for all five UEs to log `Initial sync successful` before it starts the
requested observation window. A miss exits early as
`reason: infrastructure_failure` with `startup.sync_timeout: true`. The default
is an operational value, not a calibrated percentile. A predeclared 15-run
control campaign used a 60-second sync limit and a 60-second observation: five
runs reached 5/5 within 30 seconds, none synchronized in seconds 31-60, and ten
remained at 0/5 through a clean 60-second timeout. This is an observed
fast-success/stuck-0/5 bimodal pattern, so 30 seconds can remain the operational
limit but is not a percentile guarantee. Of the five sync-ready runs, three
were valid controls and two were semantic-invalid.

The result also records `teardown.ue_exit_statuses` and
`teardown.broker_exit_status`. The old r21/r3 teardown faults were OAI UE
`UL__actor` crashes in `init_RA()`, not the broker. OAI w38 treats the first INT
as a NAS deregistration request, so the runner now sends each UE two INTs and
waits up to five seconds. Three live trials ended with all five UEs and the
broker at status 0, no forced kill and no kernel SIGSEGV. All 15 follow-up runs
also had clean teardown and zero segfaults. Observation-boundary
`crash_markers` remain separate from teardown diagnostics.

Use the wrapper below to retry only the startup race. Every attempt is preserved
under a fresh immutable `BASE-tryNN` directory. It never retries a valid service
failure, a semantic-invalid result, corrupt evidence or a teardown anomaly.

```bash
bin/rss-broker-witness-retry control -n bw-control-1030 -a 3 -d 60
bin/rss-broker-witness-retry attack  -n bw-attack-1030  -a 3 -d 60
```

Fail-fast and bounded retries do not solve the `sync=0` race or control-ping
variation. Live and regression evidence for the shutdown fix and retry policy
is in [`artifacts/broker-stability-20261030/`](../artifacts/broker-stability-20261030/).
The valid c04/c07/c13 controls attached in 1/3/36 seconds and had ping loss of
93.3333%/93.5484%/0.833333%, respectively. Raw-evidence hashes and
classification are in
[`artifacts/broker-sync-sampling-20261030/README.md`](../artifacts/broker-sync-sampling-20261030/README.md).
This sample does not support a stable denial or service-preservation claim.

---

## Occupancy and rejection observations

In a steady state, mean occupancy can be approximated by **context creation
rate times mean hold time**. Attempt rate, acceptance rate and log occurrence
rate differ; this approximation alone does not establish saturation or service
denial. The following internal summaries do not include raw evidence.

```
approximate mean occupancy  =  context creation rate × mean hold time
```

### default gNB profile — default gNB config

Internal notes report capacity 96, hold about 2 s and 33–38 attempts/s.
**Recorded result: capacity was reached in bursts**
(peak 96 with `RRCReject`), but the longest continuous plateau at 96 measured
0.93 s.

What *is* held at default config: occupancy **>= 48 for 99% of a 120 s run with
a 55.41 s continuous plateau** (2 UE). `-o` sets an estimated occupancy target:

```bash
bin/rss-run -e 1 -u 2 -o 48 -H 1900 -d 0     # estimated target 48, no time limit
```

### reduced-capacity diagnostic profile — observations with reduced capacity

`bin/rss-gnb-profile` lowers the cell's capacity through **configuration only**
— it never touches gNB source. It keeps a `.orig` backup and is idempotent.

```bash
# on the host that owns each config file
bin/rss-gnb-profile --role du apply     # capacity 96 -> 12, t300 -> 2000 ms
bin/rss-gnb-profile --role du show      # confirm it landed (apply fails if the anchor key is absent)
bin/rss-gnb-profile --role cu apply     # procedure guard -> 5000 ms
bin/rss-gnb-profile --role cu show
# restart your gNB so it reloads the config, then:
bin/rss-run -e 1 -u 2 -r 0 -H 1500 -d 0
...
bin/rss-gnb-profile --role du restore
bin/rss-gnb-profile --role cu restore
```

Internal notes compare two runs at capacity 12. Occupancy uses a reported
**200 s window** of a 420 s run, while rejection counts use a reported
**123.2 s window**. Exact boundaries and raw logs are absent. Do not combine
these periods or interpret log counts as unique UEs or messages.

| | `-r 1` (reported 102 s window) | `-r 0` (occupancy: reported 200 s window) |
|---|---:|---:|
| internally recorded attempts/s | 5.6 | 6.5 |
| peak occupancy | 12 / 12 | 12 / 12 |
| log lines containing `RRCReject` | 388 | 7,551 (reported 123.2 s window) |
| log lines containing `DU is not able to serve the UE` | 130 | 2,517 (reported 123.2 s window) |
| occupancy >= 6 / 12 | — | rounded to 100%, longest continuous 199.8 s |
| occupancy >= 9 / 12 | — | 94%, longest continuous 15.2 s |
| occupancy >= 12 / 12 | — | 33%, longest continuous 0.87 s |
| longest gap between rejection logs | — | 0.45 s |
| log lines containing `rrcSetupComplete` / `InitialUEMessage` | 0 / 0 | 0 / 0 |

These are internal observations of occupancy changes and recurring rejection
logs. Without the raw log and analysis version, values, windows and duplicates
cannot be rechecked. Later separate-process witness runs were non-deterministic,
so these are **not evidence of sustained user-service denial or full-capacity
occupancy**.

> **Internal longer-run record:** a run of about **36.5 min** reported occupancy
> >= 6 / 12 for **98%, with a longest continuous interval of 426.1 s**. The
> longest rejection-log gap was **2.53 s**. The relationship between the 2191 s
> window and 25.2 s ramp-up is unclear, so full-window continuity is unverified.
> Stability over longer durations is also unverified. See
> [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) §9.

`bin/rss-report` reports reconstructed occupancy, log-pattern occurrences and
gaps. Repeated rejection logs are distinct from measuring a normal user's
inability to obtain service.

### Running with no time limit

```bash
bin/rss-run -e 1 -u 2 -r 0 -d 0       # no time limit
pkill -INT -x nr-uesoftmodem          # stop
```

With `-d 0` both kill switches are disarmed on purpose, so **you** are the kill
switch. With `-d N`, the in-process timer and the runner's
marker-authenticated forced kill use the same declared deadline.

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
from the gNB log, plus how long observed occupancy stayed at each level.
Current output labels it `observed occupancy` and warns when initial occupancy
is unknown or events cannot be matched. The following is a **historical,
unverified excerpt**, not output rerun by the current parser:

```
(historical excerpt)
peak occupancy 96   at 06:31:24
sustained occupancy
  >=  48   56.4 s of 59 s ( 95%)   longest plateau 50.33 s
  >=  96   12.6 s of 59 s ( 21%)   longest plateau  0.93 s
```

A high *percentage* with a sub-second *longest plateau* is a sawtooth, not held
saturation. Both numbers are printed because the percentage alone is misleading.

**gNB log-pattern occurrences** — `RRCReject`, `DU is not able to serve the UE`,
`rrcSetupComplete`, `NGAP InitialUEMessage`. These are not unique messages or
UEs and depend on duplicate logging and coverage. Occupancy is also an
observation reconstructed from logs.

**UE side** — attempts and the cost breakdown of one attempt cycle.

### What you may claim

| Claim | Evidence needed |
|---|---|
| reached the configured resource limit | peak occupancy at capacity **and** `RRCReject` present |
| saturation held | a long plateau at capacity, not just a high percentage |
| observations are consistent with RRCSetupComplete-omission | neither `rrcSetupComplete` nor `NGAP InitialUEMessage` observed with adequate log coverage; zero matches alone are not proof |
| normal users were denied service | a separate normal UE measured failing to attach |
| "the gNB was disabled" | the two rows above, together |

A direct single ZMQ port pair cannot show the last two. A five-UE GNU Radio
broker enabled a separate ordinary witness, but start races, high baseline loss
and opposing attack outcomes keep it from being stable denial evidence.

---

## Current p5 post-RRCSetupRequest abort result (2026-10-30)

The old pre-PHY reset did erase Msg3 before transmission. The current
implementation instead records `msg3_tx` in the MAC scheduler after handoff to
PHY, bridges that confirmation to RRC, and only then performs the camped-idle
reset.

- `G2-msg3-0140`: 10/10 UE `msg3_tx` TC-RNTIs matched exactly one current-run
  CU `Rx ... rrcSetupRequest`; attacker Msg4 was zero.
- `G4-u1-i0-clean`: 661 MAC-confirmed Msg3 transmissions produced 661 CU
  requests, 55 accepted RRC procedure starts and 606 `DU is not able to serve`
  rejections. A later configuration audit found `nof_cell_sr_res: 1`, so this
  was a capacity-12 profile. It is valid procedure/rejection evidence, not a
  hidden pool or a capacity-96 result.
- `G13-pair-attack-valid`: a marker-authenticated duration SIGKILL made the run
  valid. It recorded 1,029 total MAC-confirmed Msg3 transmissions and zero
  attacker or probe Msg4. The CU recorded 921 requests, 84 starts and 837 DU
  resource rejections, with no `InitialUEMessage` or PDU setup. All ten probe
  TC-RNTIs matched one request and one resource rejection.
- `G14-pair-recovery-control`: after a clean DU restart, the same final build
  and topology, with only the attacker interval raised to 10 s, connected the probe on its first attempt
  and completed Registration, PDU setup and TUN configuration; the CU recorded
  the corresponding RRC and PDU procedures.

This is a controlled **same-process, shared-ZMQ witness** result. It shows that
the probe reached the gNB and was rejected at the observed resource bottleneck,
plus service availability after a clean-restart matched low-rate control. It
does not measure spontaneous recovery without a restart, and it is not evidence
from an independent physical UE; that claim still requires the separate broker
to become stable or a shielded OTA witness.

The corrected capacity-96 campaign found that the default CSI-DTX RLF path
released Msg3-only contexts after about 2.86 seconds, allowing the normal probe
to connect. With capacity unchanged and only the experiment cleanup window
extended (`max_consecutive_kos=2000`, `t300=2000`, CU guard 30000 ms), the G34
control completed Registration/PDU/TUN. In G35, all 11 normal-probe TC-RNTIs
reached the CU and were rejected with `DU is not able to serve`; no Msg4, Msg5,
or connection occurred during the 10.13-second probe window. See the
[capacity-96 artifact](../artifacts/p5-msg3-cap96-20261030/README.md) for the
profiles, failed intermediate runs, hashes, and limitations.

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
requests with 42,555 ms accumulated wait, or about **10.01 ms** each.
The recorded run/process durations are inconsistent, so no lifetime percentage
is stated.

| | upstream (`=0`) | fixed (`=-2`) |
|---|---:|---:|
| radio time per wall second | 0.46-0.54 | **2.39-2.46** |
| attempts/s | 6.7 | **19.5-33.8** |
| peak occupancy | 20 / 96 | **90-96 / 96** |

**2. Radio sharing inside one process.** Multiple UE instances share one ZMQ
radio: one instance fetches each slot and the others take a copy, and the uplink
of all instances is summed into a single device write. A custom C ZMQ broker
was rejected; an expanded srsRAN GNU Radio flowgraph is retained only for
separate-process witness experiments.

**3. Per-UE read cursors.** A round-robin copy returned a different sample count
than the caller asked for and tripped OAI's `unitTransfer == res` assertion.
Cursors give each instance exactly what it requested, in stream order.

**4. Lockstep cursors (`RSS_SHARE_LOCKSTEP=1`).** Instances join at different
stream positions after cell search and keep a constant offset, which makes every
slot produce one uplink batch per instance instead of one merged batch. The gate
holds them together. Partial effect, measured at 4 UE: out-of-order batches
9.19% -> 7.70%, sample loss 33,144 -> 27,139, radio time 1.12 -> 1.26.

**5. Offline log analysis.** `analysis/cu_occupancy.py` pairs
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
| old pre-PHY `MSG4_WAIT=0` hook | the UE logged 10,878 attempts but the gNB created **1** context because the reset erased queued Msg3 before PHY transmission. Superseded by the MAC-confirmed post-RRCSetupRequest abort path above |
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
  about 17% of uplink writes (measured at 4 UE), which produces 1-second stalls.
- **Radio time is not real time.** After the TX fix it runs about 2.4x *faster*
  than real time with one instance, because ZMQ has no pacing. Report
  `air_per_wall` from the run log beside any per-second number.
- **Numbers vary between sessions.** Three 4-UE runs gave 2202-2387 attempts but
  sample loss 21k-40k and radio time 0.87-1.63. Compare only within a session.
- **A same-process mixed probe is not independent normal-UE evidence.** It can
  share one ZMQ radio with the attacker, but the corrected run still produced
  157,990 channel timeouts and about 10.5% out-of-order shared TX. Measure
  service preservation with a separate process/RF path or shielded OTA UE.
- **The five-UE broker witness is not stable denial evidence.** A valid control
  attached and completed Registration/PDU, one valid attack run failed service,
  and another with 294 attack attempts attached after 50 s. The predeclared
  control campaign's three valid runs still ranged from 0.833333% to 93.5484%
  ping loss. `sync=0` races and service variation prevent a stable denial or
  service-preservation claim. The teardown SIGSEGV was traced to the OAI UE and
  fixed with two-stage shutdown.

---

## Files

```
bin/rss-bootstrap    clone OAI, land on the baseline commit, first stock build
bin/rss-doctor       prerequisite check (read-only, exit 1 on a blocker)
bin/rss-build        apply OAI PUCCH fix + RSS patch, build the UE
bin/rss-run          run one experiment
bin/rss-cu200        diagnose CU 200 under artificial hold32 with 3 RRCSetupComplete-omission cells + 1 witness
bin/rss-broker-witness  run 4 load/attack UEs plus one separate ordinary witness
bin/rss-broker-witness-retry  retry only a clean 5/5 sync timeout under fresh IDs
bin/rss-report       verdict from the gNB log plus the UE JSONL
bin/rss-gnb-profile  apply/restore the reduced-capacity diagnostic profile (config only)
conf/rss.conf.example  every knob, documented inline
conf/ota-inventory.example.json  secret-free shielded-OTA G0 inventory template
patch/rss-ue-curated.patch  default UE patch (OAI 2026.w38, RRCSetupComplete-omission+post-RRCSetupRequest abort+probe+Msg4 ACK)
patch/rss-ue.patch   archived 2026-10-20 RRCSetupComplete-omission baseline (not used by default)
patch/oai-pucch-null-fix.patch  upstream OAI PUCCH crash fix (for 2026.w38)
analysis/            occupancy, counters, attempt cost breakdown
analysis/check_sensitive_artifacts.py  reject subscriber/auth plaintext in files and archives
analysis/sanitize_ue_log.py  atomically sanitize the UE log and record its hash before sealing
analysis/capture_du_log.py  seal this run's byte slice from an append-only DU log
analysis/evidence_manifest.py  seal run artifacts and verify matched DU evidence
analysis/check_sensitive_history.py  scan reachable Git blobs on every local ref for credentials
analysis/export_labels.py  conservative per-attempt truth with exact DU-ACK or CU-RRC joins
analysis/validate_ota_inventory.py  fail-closed G0 completeness check without RF probing
tools/multi_ue_5ue.py  five-UE expansion of the srsRAN GNU Radio flowgraph
tests/test_broker_witness.py  broker role, lifecycle and lock regression tests
tests/test_broker_witness_retry.py  bounded-retry and immutable-ID policy tests
tests/test_sensitive_artifacts.py  plaintext and archive credential scanner tests
tests/test_du_log_capture.py  DU-log rotation, truncation and complete-line boundary tests
tests/test_label_export.py  label-v1 and exact FAPI ACK join tests
tests/test_ota_inventory.py  OTA G0 manifest safety and completeness regression tests
docs/MECHANISM.ko.md why the attack works, argued from gNB source (Korean)
docs/MEASUREMENTS.md internal measurement summary and evidence limits
docs/LABEL-CONTRACT.ko.md truth, detection, response, effect and clock contract
docs/P5-DU-ACK-JOIN.ko.md approval, verification and rollback gate for one live p5 DU ACK join
docs/RESPONSE-PATH-AUDIT.ko.md RRCSetupComplete-omission actuation audit and CSI-DTX RLF hardening comparison
docs/OTA-SMOKE.ko.md fail-closed shielded-OTA bring-up gates
NOTICE.md            use restrictions, attribution, licensing
```

Every run writes `run.json` (all knobs and the cell) and `ue.log`; an attack run
(`-e 1`) additionally writes `attempts.jsonl`, one record per event with both
clocks.

**`attempts.jsonl` is an event feed.** Common fields are `type`, `run_id`, `ue`,
`seq`, `t_ns` (wall), `air_ms` (radio) and `event`. Identity and intended/actual
reach are event-specific optional fields, not present on every row. Multiple
events can belong to one attempt, and run-status events also occur; row count
is not attempt count.

## Private GitHub publication scope

The current reviewed **`rss-storm/` directory** is the source of truth; inspect
its final file list before publication. The old `rss-publish` branch is stale
and must be regenerated only after final changes are committed. Do not include
parent-directory experiment logs, source materials or personal configuration.

Run offline analysis checks from this directory with
`python3 -m unittest discover -s tests`. These checks do not verify builds,
hardware operation or historical measurements.
