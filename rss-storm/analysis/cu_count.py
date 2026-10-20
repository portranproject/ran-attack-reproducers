#!/usr/bin/env python3
"""Count gNB log events inside one run window, and measure denial continuity.

Held saturation is not "occupancy equals N". At capacity the gNB immediately
refuses the next UE, so occupancy oscillates just below the cap while service
is being denied the whole time. The number that answers "is denial held" is
therefore the rejection stream: how often, and what is the longest silent gap.

usage: cu_count.py <log> <HH:MM:SS from> <HH:MM:SS to>
"""
import sys

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocu.log"
T0 = sys.argv[2] if len(sys.argv) > 2 else ""
T1 = sys.argv[3] if len(sys.argv) > 3 else "9"

PATS = ["rrcReject", "not able to serve", "rrcSetupComplete", "InitialUEMessage"]
# Continuity is only meaningful for the denial signal.
CONTINUITY = "rrcReject"

def secs(hhmmss):
    h, m, s = hhmmss.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

n = {p: 0 for p in PATS}
hits = []
first = last = None
for line in open(LOG, errors="replace"):
    stamp = line.split(" ", 1)[0]
    t = stamp.split("T")[-1]
    if not (T0 <= t <= T1):
        continue
    try:
        ts = secs(t)
    except ValueError:
        continue
    first = ts if first is None else first
    last = ts
    for p in PATS:
        if p in line:
            n[p] += 1
            if p == CONTINUITY:
                hits.append(ts)

span = (last - first) if (first is not None and last is not None) else 0.0
for p in PATS:
    rate = f"{n[p] / span:8.1f}/s" if span else "        -"
    print(f"{p:24} {n[p]:8} {rate}")

print()
if len(hits) > 1:
    gaps = [b - a for a, b in zip(hits, hits[1:])]
    gaps.sort()
    # Separate the ramp-up from the steady state. The interval before the first
    # rejection is the time the attacker needed to fill the cell, not a lapse in
    # denial; counting it as a gap made a healthy run look discontinuous.
    ramp = hits[0] - first
    held = last - hits[0]
    tail = last - hits[-1]
    worst = max(gaps[-1], tail)
    print(f"denial continuity ({CONTINUITY}, window {span:.1f} s)")
    print(f"  ramp-up to first rejection   {ramp:.2f} s")
    print(f"  denial held for              {held:.2f} s")
    print(f"  gap between rejections       p50 {gaps[len(gaps)//2]*1000:.0f} ms"
          f"  p99 {gaps[int(len(gaps)*0.99)]*1000:.0f} ms  max {gaps[-1]*1000:.0f} ms")
    print(f"  longest lapse once held      {worst:.2f} s")
    print()
    if worst < 1.0:
        print(f"  -> denial was CONTINUOUS for {held:.0f} s: after the ramp, no full second")
        print(f"     passed without the gNB refusing a UE (worst lapse {worst * 1000:.0f} ms).")
    else:
        print(f"  -> denial LAPSED: a {worst:.2f} s interval had no rejection.")
elif n[CONTINUITY] == 0:
    print(f"no {CONTINUITY} in this window: the cell never hit its capacity limit.")
