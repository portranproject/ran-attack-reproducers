#!/usr/bin/env python3
"""Count observed CU log occurrences and rejection gaps, not service failures.

usage: cu_count.py [log] [HH:MM:SS or ISO start] [HH:MM:SS or ISO end]
The window is [start, end). Full dated log coverage is required.
"""
import sys
from log_window import read_log, window

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocu.log"
T0 = sys.argv[2] if len(sys.argv) > 2 else None
T1 = sys.argv[3] if len(sys.argv) > 3 else None
PATS = ["rrcReject", "not able to serve", "rrcSetupComplete", "InitialUEMessage"]

try:
    start, end = window(LOG, T0, T1)
except (OSError, ValueError) as exc:
    sys.exit(f"analysis unavailable: {exc}")

n = {p: 0 for p in PATS}
hits = []
observed = 0
for stamp, line in read_log(LOG):
    if not start <= stamp < end:
        continue
    observed += 1
    for pattern in PATS:
        if pattern in line:
            n[pattern] += 1
            if pattern == "rrcReject":
                hits.append(stamp)

span = (end - start).total_seconds()
print(f"window [{start.isoformat()}, {end.isoformat()}) ({span:.1f} s)")
print("counts are matching log lines, not unique messages or service outcomes")
if not observed:
    sys.exit("analysis unavailable: no timestamped log lines inside the requested window")
for pattern in PATS:
    print(f"{pattern:24} {n[pattern]:8} {n[pattern] / span:8.1f}/s")

print()
if hits:
    hits.sort()
    print("observed rejection cadence (rrcReject)")
    print(f"  start to first occurrence    {(hits[0] - start).total_seconds():.2f} s")
    print(f"  last occurrence to end       {(end - hits[-1]).total_seconds():.2f} s")
    if len(hits) > 1:
        gaps = sorted((b - a).total_seconds() for a, b in zip(hits, hits[1:]))
        print(f"  gap between occurrences      p50 {gaps[len(gaps)//2]*1000:.0f} ms"
              f"  p99 {gaps[int(len(gaps)*0.99)]*1000:.0f} ms  max {gaps[-1]*1000:.0f} ms")
    else:
        print("  only one occurrence; no inter-occurrence gap")
else:
    print("no rrcReject observed in this window")
print("service availability and capacity exhaustion cannot be inferred from these counts")
