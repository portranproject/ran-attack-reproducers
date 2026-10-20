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
holds, ends = [], Counter()
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
            first = first or secs(ts)
            last = secs(ts)
            if len(live) > peak:
                peak, peak_at = len(live), hhmmss(ts)
        else:
            ends[e.group(3)] += 1
            t0 = live.pop(ue, None)
            if t0 is not None:
                holds.append(secs(ts) - t0)

span = (last - first) if (first and last and last > first) else 0
holds.sort()
print(f"window         {T0} .. {T1}")
print(f"started        {len(holds) + len(live)}  ({len(holds) / span:.1f}/s wall)" if span else f"started {len(holds)+len(live)}")
print(f"peak occupancy {peak}   at {peak_at}")
print(f"still live     {len(live)}")
print(f"end reasons    {dict(ends)}")
if holds:
    print(f"hold time wall median {holds[len(holds)//2]*1000:.0f} ms  p90 {holds[int(len(holds)*0.9)]*1000:.0f} ms")
