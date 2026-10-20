#!/usr/bin/env python3
"""Where the wall-clock cost of one A-type attempt goes.

Reads a run's attempts.jsonl (each event carries both clocks: t_ns wall and
air_ms) and splits the attempt cycle into its phases, so the next optimisation
target is measured instead of guessed.

usage: attempt_phases.py <attempts.jsonl>
"""
import json, sys
from collections import defaultdict

path = sys.argv[1]
by_seq = defaultdict(dict)
order = []
for line in open(path, errors="replace"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        r = json.loads(line)
    except ValueError:
        continue
    ev = r.get("event")
    if ev in ("attempt_start", "msg4_rx", "retrigger", "setup_req_prebuilt"):
        key = (r.get("ue", 0), r.get("seq"))
        if ev not in by_seq[key]:
            by_seq[key][ev] = (r["t_ns"], r.get("air_ms", 0))
            if ev == "attempt_start":
                order.append(key)

def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else float("nan")

phases = {k: ([], []) for k in ("msg3_to_msg4", "msg4_to_retrigger", "retrigger_to_next_msg3")}
cycle_w, cycle_a = [], []
for i, key in enumerate(order):
    e = by_seq[key]
    if "attempt_start" not in e:
        continue
    s_w, s_a = e["attempt_start"]
    if "msg4_rx" in e:
        m_w, m_a = e["msg4_rx"]
        phases["msg3_to_msg4"][0].append((m_w - s_w) / 1e6)
        phases["msg3_to_msg4"][1].append(m_a - s_a)
        if "retrigger" in e:
            r_w, r_a = e["retrigger"]
            phases["msg4_to_retrigger"][0].append((r_w - m_w) / 1e6)
            phases["msg4_to_retrigger"][1].append(r_a - m_a)
    if i + 1 < len(order) and "retrigger" in e:
        n = by_seq[order[i + 1]].get("attempt_start")
        if n:
            r_w, r_a = e["retrigger"]
            phases["retrigger_to_next_msg3"][0].append((n[0] - r_w) / 1e6)
            phases["retrigger_to_next_msg3"][1].append(n[1] - r_a)
    if i + 1 < len(order):
        n = by_seq[order[i + 1]].get("attempt_start")
        if n:
            cycle_w.append((n[0] - s_w) / 1e6)
            cycle_a.append(n[1] - s_a)

cw = med(cycle_w)
print(f"attempts            {len(order)}")
print(f"cycle (wall)        median {cw:.1f} ms   -> {1000 / cw:.1f}/s")
print(f"cycle (air)         median {med(cycle_a):.0f} ms")
print()
print(f"{'phase':26} {'wall ms':>9} {'air ms':>8} {'wall share':>11}")
for name, (w, a) in phases.items():
    mw = med(w)
    print(f"{name:26} {mw:9.1f} {med(a):8.0f} {mw / cw * 100:10.0f}%")
accounted = sum(med(w) for w, _ in phases.values())
print(f"{'(accounted)':26} {accounted:9.1f} {'':8} {accounted / cw * 100:10.0f}%")
