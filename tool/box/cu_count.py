#!/usr/bin/env python3
import sys
log, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3]
pats = ["rrcReject", "not able to serve", "rrcSetupComplete", "InitialUEMessage"]
n = {p: 0 for p in pats}
for line in open(log, errors="replace"):
    t = line.split(" ", 1)[0]
    t = t.split("T")[-1]
    if not (t0 <= t <= t1):
        continue
    for p in pats:
        if p in line:
            n[p] += 1
for p in pats:
    print(f"{p:24} {n[p]}")
