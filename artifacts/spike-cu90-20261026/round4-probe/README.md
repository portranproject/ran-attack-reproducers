# Round 4 — probe alone works; concurrent probe still CPU-starved

## Results

- **Probe alone on second DU**: `SSB 0 SINR 59.2 dB RSRP -22 dBm`,
  `RRCSetupComplete`, `Registration Accept`, `PDU Session Establishment Accept`,
  IPv4 `10.45.1.2`, `oaitun_ue1`.
  → the round-2/3 failure was caused by `taskset -c 4-5` on the second DU
  (PHY/ZMQ threads starved). Without taskset the second DU cell is fine.
- **Attack 5 UE alone**: 3,178 attempts, 2,168 `msg5_skip`,
  `ch.timeout` 277 — stable.
- **CU admission limit**: 969 (latest `ue=3092~3094`). CU 90 is being hit
  continuously.
- **Probe during attack**: no SSB, only `[SIM]`/`SA init`; second DU `odu2`
  process still alive. The probe was starved by the first DU + 5-UE attack on
  the same 8-vCPU host.

## Judgment

- CU 90 attack is stable and sustained.
- Probe alone on the second DU works.
- Concurrent probe still fails cell sync due to host CPU contention.
- Goal (sustained normal-UE denial) not yet achieved.

## Next

1. Pin the first DU/attack to cores 0–3 and the second DU/probe to 4–7
   (do NOT taskset the second DU itself; that alone caused the earlier failure).
2. Or move the second DU/probe to the CU host using the DU host's
   `e0db566a` `odu2` (the CU's `ocu` is `e0db566a`; the CU host's own `odu`
   `27871a4` caused the F1AP mismatch) and fix the OAI segfault there.
3. Verify the probe reaches `RRCSetupRequest` on the CU and is rejected by
   `UE admission limit` (no `RRCSetupComplete`, no PDU), then repeat 3×.

## Files

- `cu/cu.yaml`, `cu/admission-count.txt` (969), `cu/ocu-tail.log`
- `du/du2.yaml`, `du/ue2-alone.log` (success), `du/ue2-attack.log` (no SSB),
  `du/attack.log` (3,178 attempts / 2,168 msg5_skip), `du/probe-*.log`
