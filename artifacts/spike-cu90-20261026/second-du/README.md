# Second-DU probe split — 2026-10-26

## Setup

- CU `max_nof_ues=90` (temporary; restored after the run).
- Second DU `odu2`: `du2.yaml` — `pci: 2`, `sector_id: 1`, ZMQ 4558/4559,
  F1-U port 2153, `gnb_du_id 2`. F1 + E2 connected.
- Probe: stock OAI normal UE, ZMQ 4559/4558, `uicc0`, no RSS options.
- Attack: 6 UEs on the first DU, ZMQ 4556/4557.

## Results

- **Probe alone** (second DU): `RRCSetupComplete`, `Registration Accept`,
  `PDU Session Establishment Accept`, IPv4 `10.45.1.2`, `oaitun_ue1`.
  → the second-DU/probe path is valid.
- **Attack alone 30 s**: 1,716 attempts, 1,084 `msg5_skip`,
  `ch.timeout` 127 → stable.
- **Attack 60 s + probe**: 137 attempts, 89 `msg5_skip`,
  `ch.timeout` 1,082, shared-TX late-drop 55,990. The probe produced only the
  SIM line; no `RRCSetupRequest`/`RRCSetupComplete`/PDU. The probe did not
  sync to the second cell.
- CU `UE admission limit reached` count: 668 (cumulative over the runs).
  The CU cap 90 was the first limit in the earlier 6-UE run
  (peak occupancy 90, DU `not able to serve` 0).

## Judgment

- CU 90 is the first admission limit (confirmed in the earlier spike).
- The second-DU/probe separation is valid **alone**.
- Concurrent attack + probe on the same DU host is unstable: the first DU's
  shared TX collapses (`ch.timeout` 1,082, late-drop 55,990) and the probe
  fails cell sync. This is resource contention on one 8-vCPU DU host
  (two DUs + two UEs), not a CU-cap effect.
- **Goal (sustained normal-UE denial) is not achieved in this round.**

## Next

1. Move the second DU/probe to the CU host (4 vCPU), leaving the first DU and
   attack on the DU host; or pin the two DUs/UEs to disjoint cores.
2. Reduce the attack to 5 UEs and retest; the CU cap must be filled while the
   probe attempts.
3. Verify the probe's `RRCSetupRequest` reaches the CU and is rejected by the
   `UE admission limit` path (no `RRCSetupComplete`, no PDU), then repeat 3×.

## Files

- `cu/cu.yaml` — CU 90 config snapshot
- `cu/ocu-window.log` — CU window (admission/RRC)
- `cu/admission-count.txt` — 668
- `du/du2.yaml` — second DU config
- `du/odu2.boot.log`, `du/odu2-window.log` — second DU F1/E2/probe traces
- `du/ue2-alone.log` — probe alone (success)
- `du/ue2-attack.log` — probe under attack (no RRC)
- `du/attack2.log` — attack 60 s self-check (collapse)
- `cu/cu.tar.gz`, `du/du.tar.gz` — raw bundles
