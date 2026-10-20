#!/usr/bin/env python3
"""gNB-side latency of one attempt, from the CU log. Run on the CU box.

Splits "Msg3 reached the CU over F1" -> "RRC decoded it" -> "Msg4 sent", so the
report can say how much of the per-attempt cost is the gNB's own processing
rather than the attacker's loop.
"""
import re, statistics, sys

log = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocu.log"

def ts(line):
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+)", line)
    if not m:
        return None
    hms = m.group(1).split("T")[1]
    h, mi, s = hms.split(":")
    return int(h) * 3600 + int(mi) * 60 + float(s)

f1, req, setup = [], [], []
for line in open(log, errors="ignore").read().splitlines()[-40000:]:
    if "Rx InitialULRRCMessageTransfer" in line:
        f1.append(ts(line))
    elif "CCCH UL rrcSetupRequest" in line:
        req.append(ts(line))
    elif "CCCH DL rrcSetup " in line:
        setup.append(ts(line))

print("counts  f1=%d  rrcSetupRequest=%d  rrcSetup=%d" % (len(f1), len(req), len(setup)))
n = min(len(f1), len(req), len(setup))
if n > 5:
    d1 = [(req[i] - f1[i]) * 1000 for i in range(n) if req[i] and f1[i]]
    d2 = [(setup[i] - req[i]) * 1000 for i in range(n) if setup[i] and req[i]]
    d1 = [x for x in d1 if 0 <= x < 5000]
    d2 = [x for x in d2 if 0 <= x < 5000]
    if d1:
        print("  F1 InitialUL -> RRC sees Msg3 : median %7.1f ms  n=%d" % (statistics.median(d1), len(d1)))
    if d2:
        print("  RRC Msg3 -> Tx Msg4          : median %7.1f ms  n=%d" % (statistics.median(d2), len(d2)))
