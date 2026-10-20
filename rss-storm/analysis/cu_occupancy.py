#!/usr/bin/env python3
"""Peak concurrent incomplete RRC Setup procedures from an OCUDU CU log.

An A-type attempt occupies the gNB from '"RRC Setup Procedure" started' until
that procedure ends. Box-verified 2026-10-20: with the default profile the end
is usually NOT the CU's 2000 ms timeout but '"RRC Setup Procedure" cancelled',
driven by a UeContextReleaseRequest from the DU, so counting only "timed out"
undercounts endings badly (601 starts / 11 timeouts in one run).

usage: cu_occupancy.py [log] [HH:MM:SS from] [HH:MM:SS to]
"""
import re, sys
from collections import Counter

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocu.log"
T0 = sys.argv[2] if len(sys.argv) > 2 else ""
T1 = sys.argv[3] if len(sys.argv) > 3 else "9"

START = re.compile(r'^(\S+) .*ue=(\d+).*"RRC Setup Procedure" started')
END = re.compile(r'^(\S+) .*ue=(\d+).*"RRC Setup Procedure" (cancelled|timed out|finished successfully)')

def hhmmss(ts):
    return ts.split("T")[-1]

def secs(ts):
    h, m, s = hhmmss(ts).split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

live, peak, peak_at = {}, 0, ""
holds, ends, starts, end_times = [], Counter(), [], []
# One source of truth for occupancy: sample len(live) after every change.
# Two separate counters disagreed, because an end whose start was before the
# window still pushed a -1 into the timeline. The result was a reported peak of
# 12 next to "0.0 s above 9", which is impossible.
series = []
first = last = None
with open(LOG, errors="replace") as fh:
    for line in fh:
        m = START.match(line)
        e = None if m else END.match(line)
        if not (m or e):
            continue
        ts = (m or e).group(1)
        if not (T0 <= hhmmss(ts) <= T1):
            continue
        ue = (m or e).group(2)
        if m:
            live[ue] = secs(ts)
            starts.append(secs(ts))
            first = first or secs(ts)
            last = secs(ts)
            if len(live) > peak:
                peak, peak_at = len(live), hhmmss(ts)
            series.append((secs(ts), len(live)))
        else:
            ends[e.group(3)] += 1
            end_times.append(secs(ts))
            last = secs(ts)
            t0 = live.pop(ue, None)
            if t0 is not None:
                holds.append(secs(ts) - t0)
                series.append((secs(ts), len(live)))

span = (last - first) if (first and last and last > first) else 0
holds.sort()
print(f"window         {T0} .. {T1}")
print(f"started        {len(holds) + len(live)}  ({len(holds) / span:.1f}/s wall)" if span else f"started {len(holds)+len(live)}")
print(f"peak occupancy {peak}   at {peak_at}")
print(f"still live     {len(live)}")
print(f"end reasons    {dict(ends)}")
if holds:
    print(f"hold time wall median {holds[len(holds)//2]*1000:.0f} ms  p90 {holds[int(len(holds)*0.9)]*1000:.0f} ms")

# Where the dead time is: the average rate can be far below the burst rate that
# the occupancy peak implies, so print the gap distribution and a per-second
# rate profile instead of guessing.
gaps = sorted(round((b - a) * 1000) for a, b in zip(starts, starts[1:]))
if gaps:
    def q(p):
        return gaps[min(int(len(gaps) * p), len(gaps) - 1)]
    print(f"gap between attempts  p50 {q(.5)} ms  p90 {q(.9)} ms  p99 {q(.99)} ms  max {gaps[-1]} ms")
    big = [g for g in gaps if g >= 200]
    print(f"gaps >= 200 ms        {len(big)}  총 {sum(big) / 1000:.1f} s  (구간 길이의 {sum(big) / 10 / span:.0f}%)")
# Sustained saturation, not just the peak: walk the start/end events in time
# order and measure how long occupancy actually stayed at or above each level.
# A peak of 96 for one instant is not denial; a plateau is.
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 96
# Levels scale with capacity: a fixed "CAP-16" is meaningless when the cell is
# configured for 12. Duplicates and non-positive levels are dropped.
LEVELS = sorted({max(1, CAP // 4), max(1, CAP // 2), max(1, (CAP * 3) // 4), CAP})
# Starts must be applied before ends at the same timestamp. Plain tuple sort
# puts (t, -1) first, and under load an end and the next start share the same
# millisecond often enough that the running count collapsed to zero and every
# plateau was reported as 0.0 s while the peak said 12.
# The window is the whole observed timeline, not just the first-to-last start:
# ends outlive the last start, so using the start span reports >100%.
wall_span = (series[-1][0] - series[0][0]) if len(series) > 1 else 0
time_at = {}
run_at, best_run = {}, {}
for (t_prev, occ), (t_next, _) in zip(series, series[1:]):
    dt = t_next - t_prev
    for lvl in LEVELS:
        if occ >= lvl:
            time_at[lvl] = time_at.get(lvl, 0.0) + dt
            run_at[lvl] = run_at.get(lvl, 0.0) + dt
        else:
            best_run[lvl] = max(best_run.get(lvl, 0.0), run_at.get(lvl, 0.0))
            run_at[lvl] = 0.0
for lvl in LEVELS:
    best_run[lvl] = max(best_run.get(lvl, 0.0), run_at.get(lvl, 0.0))
print(f"sustained occupancy (capacity {CAP}, window {wall_span:.0f} s)")
for lvl in LEVELS:
    ta = time_at.get(lvl, 0.0)
    pct = ta / wall_span * 100 if wall_span else 0
    print(f"  >= {lvl:3}   {ta:6.1f} s of {wall_span:5.1f} s ({pct:4.0f}%)"
          f"   longest plateau {best_run.get(lvl, 0.0):6.2f} s")

per_sec = Counter(int(t - starts[0]) for t in starts)
if per_sec:
    hot = sorted(per_sec.values(), reverse=True)
    print(f"per-second rate       max {hot[0]}/s  p90 {hot[int(len(hot) * .1)]}/s  median {hot[len(hot) // 2]}/s")
