#!/usr/bin/env python3
"""Per-phase cost of one A-type attempt, in both clocks.

Run on the DU box:  python3 phase_breakdown.py /root/rss-runs/<RUN>/attempts.jsonl
Answers "where do the ~100 ms of air time per attempt go", which decides whether
the remaining headroom is ours (UE side) or the gNB's.
"""
import json, statistics, sys

path = sys.argv[1] if len(sys.argv) > 1 else "/root/rss-runs/CLK3/attempts.jsonl"
ev = [json.loads(l) for l in open(path) if l.strip()]
by = {}
for e in ev:
    by.setdefault(e["seq"], {})[e["event"]] = e

def show(label, pairs):
    w = [p[0] for p in pairs]
    a = [p[1] for p in pairs]
    if w:
        print("  %-22s wall=%7.1f ms  air=%6.0f ms  n=%d"
              % (label, statistics.median(w), statistics.median(a), len(w)))

def within(a, b):
    out = []
    for v in by.values():
        if a in v and b in v:
            out.append(((v[b]["t_ns"] - v[a]["t_ns"]) / 1e6,
                        v[b]["air_ms"] - v[a]["air_ms"]))
    return out

def across(a, b):
    out = []
    seqs = sorted(by)
    for s0, s1 in zip(seqs, seqs[1:]):
        if a in by[s0] and b in by[s1]:
            out.append(((by[s1][b]["t_ns"] - by[s0][a]["t_ns"]) / 1e6,
                        by[s1][b]["air_ms"] - by[s0][a]["air_ms"]))
    return out

print("phase breakdown (median):")
show("Msg3 -> Msg4", within("attempt_start", "msg4_rx"))
show("Msg4 -> retrigger", within("msg4_rx", "retrigger"))
show("retrigger -> next Msg3", across("retrigger", "attempt_start"))
show("FULL CYCLE", across("attempt_start", "attempt_start"))
m4 = sum(1 for x in ev if x["event"] == "msg4_rx")
t = [x["t_ns"] for x in ev]
a = [x["air_ms"] for x in ev]
wall = (max(t) - min(t)) / 1e9
air = (max(a) - min(a)) / 1000.0
print("msg4=%d wall_span=%.1fs air_span=%.1fs air_per_wall=%.3f msg4_hz_wall=%.2f msg4_hz_air=%.2f"
      % (m4, wall, air, air / wall if wall else 0, m4 / wall if wall else 0, m4 / air if air else 0))

# Where the loss is: the median cycle is already at parity with the published
# 40 ms/request, so what costs throughput is the tail of slow cycles.
cyc = sorted(p[1] for p in across("attempt_start", "attempt_start"))
if cyc:
    n = len(cyc)
    mean = sum(cyc) / n
    print("air cycle distribution (ms): n=%d min=%.0f p50=%.0f mean=%.1f p90=%.0f p99=%.0f max=%.0f"
          % (n, cyc[0], cyc[n // 2], mean, cyc[int(n * 0.9)], cyc[int(n * 0.99)], cyc[-1]))
    print("  share of air time spent in cycles > 2x median: %.0f%%"
          % (100.0 * sum(c for c in cyc if c > 2 * cyc[n // 2]) / sum(cyc)))
    print("  rate at p50 cycle = %.1f/s ; actual mean rate = %.1f/s" % (1000.0 / cyc[n // 2] if cyc[n // 2] else 0, 1000.0 / mean if mean else 0))
