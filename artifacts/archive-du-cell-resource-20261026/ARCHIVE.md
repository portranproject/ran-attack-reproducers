# Archive — rss-storm v1 (DU cell resource exhaustion)

**Status: archived; development stopped. 2026-10-26.**
This is the A-type RRC signaling storm reproducer as of 2026-10-21/23.
It is preserved as the **DU cell resource exhaustion** line.
It is **not** a CU-CP capacity/CPU exhaustion tool.

## What it is

- OAI `2026.w38` UE patch + shell harness. The gNB (OCUDU 26.10) is unmodified.
- A-type: Msg4 received + HARQ ACK sent, `RRCSetupComplete` (Msg5) omitted,
  new RA repeated in-process.
- Stable knobs: rate, completion, gates, target occupancy, multi-UE.
- Experimental branches (probe/A-NAS/evict/harvest/RO) live in
  `patches/rss-ue-full-20261023.patch`; they are **not** part of the stable
  A-type tool.

## What was verified (with evidence)

- 120 s run, 2 UE: 4,438 attempts (37/s), peak **96/96**,
  `rrcSetupComplete` / `InitialUEMessage` **0**, hold **1,999 ms**,
  `rrcReject` 15. Raw CU log: `../verify-20261021/`.
- 590 s run, 4 UE: 25,095 attempts (42.5/s), occupancy >= 72 for 100%
  (longest 176.7 s), >= 96 only 1.3 s, `rrcReject` 16,227 (27.5/s),
  completion/NGAP 0. Report: `../modeA-sustained-20261021/`.
- Mode B (capacity 12): sustained rejects, >= 6/12 for 98%, longest 426 s.
  Logs: `../midterm-modeb/`.
- Normal UE probe: first attempt connects; connection delay ~75 -> ~180 ms
  (2.4-2.8x). It is not a denial.
- Occupancy/rejection mechanism and the 96 ceiling:
  `findings/gap-metric-mechanism.md`.

## Scope correction (important)

- The scarce resource is the **DU cell's UE context + dedicated SR/CSI**
  (96), not CU-CP.
- CU-CP holds an RRC transaction and a 1,000 ms guard per attempt, and the
  CU F1-C carries the A-type signature. But the CU-CP context limit is
  8,192 (85x the DU's 96), so **the CU-CP is not the bottleneck**.
- Therefore the correct label is: **DU-bound, CU-visible**.
  Do not claim "CU-CP resource exhaustion" from this tool.

## Known limitations

- ZMQ shared radio: sample loss, SSS loss, UE core dumps under heavy runs.
- The normal-UE probe is an in-process instance, not a separate standard UE.
- The 2026-10-22/23 findings and the full experimental patch were not
  committed to git (`findings/` is gitignored). They are copied into this
  archive.
- The full patch contains experimental features (probe/A-NAS/evict/harvest/
  RO arbitration) that are not part of the stable A-type tool.

## Contents

- `findings/` — 8 research records (A-NAS, eviction, normal-UE denial,
  coverage, gap metric, RA pipelining, F1C teardown, security report draft).
- `midterm-rss-draft.md` — midterm draft (2026-10-20).
- `patches/` — `rss-ue-full-20261023.patch`, `rss-ue-anas.patch`,
  `anas-identity.c`.
- `MANIFEST.sha256` — hashes of the files above.

## Git state

- Tag: `du-cell-resource-v1` (created on the archived commit).
- Tracked tool: `rss-storm/` at the tag.
- Local raw artifacts (not in git, relative to `artifacts/`):
  `verify-20261021/`, `modeA-sustained-20261021/`,
  `modeA-peak-6ue-20261021/`, `ro-arbitration-20261022/`,
  `midterm-modeb/`.

## Superseded by

A future CU-targeted design. See the design discussion; the CU target must be
defined operationally (CU-CP processing, CU-CP context table, CU-CP code-path
vulnerability, or CU F1-C observation) before any new tool is built.
