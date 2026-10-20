#!/usr/bin/env python3
"""Reconstruct observed incomplete RRC Setup procedures from a dated CU log.

usage: cu_occupancy.py [log] [HH:MM:SS or ISO start] [HH:MM:SS or ISO end] [capacity]
The window is [start, end). Prefix events establish observed carry-in state;
initial occupancy and missing lifecycle events remain unknown.
"""
import re
import sys
from collections import Counter
from log_window import read_log, window

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocu.log"
T0 = sys.argv[2] if len(sys.argv) > 2 else None
T1 = sys.argv[3] if len(sys.argv) > 3 else None
EVENT = re.compile(
    r'ue=(\d+).*"RRC Setup Procedure" (started|cancelled|timed out|finished successfully)'
)
try:
    CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 96
    if CAP <= 0:
        raise ValueError("capacity must be positive")
    start, end = window(LOG, T0, T1)
except (OSError, ValueError) as exc:
    sys.exit(f"analysis unavailable: {exc}")

events = []
for stamp, line in read_log(LOG):
    match = EVENT.search(line)
    if match and stamp < end:
        events.append((stamp, match.group(1), match.group(2)))
events.sort(key=lambda event: event[0])

live = {}
holds, starts, series = [], [], []
ends = Counter()
unmatched = duplicates = 0
in_window = 0
carry_in = None
for stamp, ue, kind in events:
    inside = stamp >= start
    if inside and carry_in is None:
        carry_in = len(live)
        series.append((start, carry_in))
    if kind == "started":
        if ue in live:
            duplicates += 1
        live[ue] = stamp
        if inside:
            starts.append(stamp)
    else:
        t0 = live.pop(ue, None)
        if t0 is None:
            unmatched += 1
        elif inside:
            holds.append((stamp - t0).total_seconds())
        if inside:
            ends[kind] += 1
    if inside:
        in_window += 1
        series.append((stamp, len(live)))
if carry_in is None:
    carry_in = len(live)
    series.append((start, carry_in))
if not in_window and not carry_in:
    sys.exit("analysis unavailable: no observed procedure state in the requested window")
series.append((end, len(live)))

span = (end - start).total_seconds()
# Same-timestamp updates do not establish a positive-duration occupancy interval.
peak_at, peak = max(
    (previous for previous, following in zip(series, series[1:])
     if following[0] > previous[0]),
    key=lambda item: item[1],
)
print(f"window [{start.isoformat()}, {end.isoformat()}) ({span:.1f} s)")
print("evidence uncertain: initial occupancy is unknown; reconstructed from available records")
print(f"unmatched endings {unmatched}; repeated live starts {duplicates} (through window end)")
print(f"observed carry-in {carry_in}")
print(f"started        {len(starts)}  ({len(starts) / span:.1f}/s wall)")
print(f"peak occupancy {peak}   at {peak_at.isoformat()} (observed)")
print(f"still live     {len(live)} (observed, just before window end)")
print(f"end reasons    {dict(ends)}")
if holds:
    holds.sort()
    print(f"hold time wall median {holds[len(holds)//2]*1000:.0f} ms"
          f"  p90 {holds[int(len(holds)*0.9)]*1000:.0f} ms (matched endings only)")

levels = sorted({max(1, CAP // 4), max(1, CAP // 2), max(1, (CAP * 3) // 4), CAP})
print(f"observed occupancy (capacity reference {CAP}, requested window {span:.1f} s)")
for level in levels:
    total = run = best = 0.0
    for (previous, occupancy), (following, _) in zip(series, series[1:]):
        dt = (following - previous).total_seconds()
        if occupancy >= level:
            total += dt
            run += dt
            best = max(best, run)
        elif dt:
            run = 0.0
    print(f"  >= {level:3}   {total:6.1f} s of {span:5.1f} s ({total / span * 100:4.0f}%)"
          f"   longest observed plateau {best:6.2f} s")
