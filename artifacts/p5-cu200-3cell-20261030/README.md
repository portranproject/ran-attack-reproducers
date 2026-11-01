# P5 CU 200 canonical-A hold32 diagnostic (2026-10-30)

## Verdict — diagnostic only, not the default-cleanup success criterion

This run is **not** accepted as attacker-controlled sustained denial. It changed
the incomplete-context lifetime from the roughly 2 s default to about 32 s and
ended before the first expiry wave. It proves the canonical-A path, exact ACK
join, CU-200 reachability, and witness rejection during that artificial hold;
it does not prove that the attack arrival rate beats the default release rate.

Within that diagnostic hold window, `final-v4` recorded:

- the unmodified OCUDU CU used its configured `max_nof_ues: 200`;
- three attacker cells generated canonical A attempts (Msg4 decoded, DU HARQ ACK joined, no Msg5);
- the reconstructed CU RRC-setup occupancy reached exactly 200;
- a normal UE on a separate fourth cell made 17 consecutive on-air attempts over 16.31 s;
- all 17 received `RRCReject`; Msg4, `RRCSetupComplete`, registration, PDU session, and channel timeouts were all zero.

This is an **artificial-hold rejection observation**, not evidence of attacker-controlled denial under the roughly 2 s default cleanup. The attack duration is kept at or below the measured 32 s incomplete-context lifetime so the witness window ends before the first expiry wave. Longer V2/V3 diagnostics crossed that boundary: the witness was initially rejected but eventually won an expiring slot.

## Why the profile has four cells

1. The CU limit is global. Two cells at the default-derived DU capacity 96 can supply at most 192 contexts, so three attack cells are the minimum for CU 200.
2. The fourth cell carries only the normal witness. This separates CU admission failure from same-radio starvation.
3. The three attackers run with `target_occupancy=0` and `honor_reject=0`. The actual ceiling remains the CU's unchanged 200; these knobs only keep every newly opened slot contested.
4. The witness process starts with the radio but delays RRC for 15 s. This avoids the OCUDU ZMQ endpoint's non-reconnect behavior while ensuring the first normal request arrives after saturation.
5. The CU guard and DU cleanup settings produce a measured 32 s incomplete-context lifetime. Capacity values are unchanged; the longer lifetime creates a deterministic witness window on this finite-rate three-cell setup.

## Final run

Run IDs:

- attackers: `C200V4-A0/A1/A2-20261030T041400Z`
- witness: `C200V4-W3-20261030T041400Z`
- normal controls: `H4V2-C0/C1/C2/C3-20261030T040300Z`

| worker | attempts | Msg4 | exact canonical A (`du_ack_state=ack`) | RRCReject | Msg5 |
|---|---:|---:|---:|---:|---:|
| A0 | 211 | 70 | 55 | 140 | 0 |
| A1 | 192 | 65 | 60 | 126 | 0 |
| A2 | 186 | 65 | 61 | 120 | 0 |
| W3 normal witness | 17 | 0 | 0 | 17 | 0 |

All four workers had zero `Error, channel timeout`. Every run manifest verifies locally. The exact canonical total is 176; remaining decoded or rejected attempts are retained as `unknown`, never promoted to ACK evidence.

CU reconstruction for `[04:14:14, 04:14:47)`:

```text
started 200
peak occupancy 200 at 04:14:25.735702
occupancy >= 200: 15.68 s continuous
admission-limit messages: 405
successful RRC Setup procedures: 0
```

The witness's first attempt was 15.083 s after run start; its last of 17 rejects was at 31.393 s. The observed all-failed interval was 16.310 s.

## Control

Before attack load, all four final-binary control workers produced one `RRCSetupComplete` and zero channel timeouts. C3 additionally completed Registration, PDU Session Establishment, and TUN configuration. This proves the witness PCI/port/core path before attributing its hold32-window rejection to CU admission.

## Version and configuration identity

| item | SHA-256 |
|---|---|
| final OAI UE binary | `202934f7d34db2f81763b28d43f2d09f5cdac9175d4146a412d778174f3c4c2b` |
| curated UE patch | `4b822132a73af5777ffe7116be06460f69dfe74aa1619b1f8c5d1bf97c92b751` |
| `rss-run` | `4bb6f256d0ec41198aa32f558d9048ac568f7c1d9bee5cd17f385cab7c28ae9c` |
| P5-smoked `rss-cu200` | `1dade7289f864af624d966aa656b4233aeec2d790e579948c0c13fc4ee5928d9` |
| four-cell DU config | `5e55ca58e10c4f5ce91a358ba5db8badb3e0798eaf6bceecbaa13ef2997c4e77` |
| CU cap200/guard30s config | `cdf0acec7e0bdcf29e183d7b55f403c62630cbe0ef2bf31493a60bc3049d53fe` |
| CU log slice | `382e99f5c926f153497150047968771eb2d6aa37f92e648e2feaee4e0f25b70d` |

`final-v4/cu-base-before-hold.yaml` (`2ab32f...`) is the recovery copy. The p5 hosts were restored to that CU config and the shipped DU config after capture.

The current checkout's wrapper is `fcb258524944f8f0524ec1bca16ce6e19363a922bcd52d71d68bf14671d9997d`.
It differs from the P5-smoked copy only by closing the run-lock file descriptor
at ODU and worker child boundaries; its four local contract tests pass. The
radio arguments and experiment contract are unchanged.

## Reproduce

After starting a fresh four-cell ODU with `du-4cell-hold32.yaml`, run the control and attack through the same wrapper:

```bash
bin/rss-cu200 control -n CU200-control -d 25
bin/rss-cu200 attack  -n CU200-attack  -d 32
```

Set `OAI`, `UE_BIN`, `PATCH`, `UE_CFG`, `UECAP`, `LOGDIR`, and `ODU_LOG` for the deployment. Set `CU200_GNB_STOP_CMD` and `CU200_GNB_RESTART_CMD` together if the wrapper should restart the ODU once before launching the four workers. `CU200_GNB_READY_CMD` must prove F1 and the four-cell ODU are ready.

The wrapper refuses an attack duration longer than `HOLD_MS`; this preserves the exact tested meaning: the witness window ends before context expiry can make the result probabilistic.

## Layout

- `final-v4/runs/` — three attack workers and the normal witness, each with sealed evidence
- `final-v4/control/` — four-cell normal control
- `final-v4/cu/` — immutable CU log slices and capture boundaries
- `final-v4/wrapper-smoke/` — actual P5 execution of `rss-cu200 control`; all four cells completed RRC
- `cap-only-run/` — earlier cap-200 proof without a valid witness
- `default-run/` — diagnostic default-timer run; not success evidence
- `runs/C3S*/` — three-cell normal smoke
