#!/usr/bin/env python3
"""What the normal-UE probe saw in one run.

The probe (`-p N`) is the measurement for "can an ordinary UE still connect".
It logs one probe_attempt per try, one probe_connected when it reaches
RRC_CONNECTED, and probe_lost when the gNB drops it again.

usage: probe_summary.py <attempts.jsonl>
"""
import json
import sys

path = sys.argv[1]
tries = 0
first = None
last = None
connected = []
lost = 0
for line in open(path, errors="replace"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        r = json.loads(line)
    except ValueError:
        continue
    ev = r.get("event")
    if ev == "probe_attempt":
        tries += 1
        if first is None:
            first = r.get("t_ns")
    elif ev == "probe_connected":
        connected.append(r)
    elif ev == "probe_lost":
        lost += 1
    else:
        continue
    last = r.get("t_ns")

print(f"probe attempts      {tries}")
if connected:
    c = connected[-1]
    print(f"probe connected     yes   tries={c.get('tries', 0)}  {c.get('ms', 0)} ms"
          f"  ({len(connected)} probe_connected)")
else:
    print("probe connected     no    (no probe_connected in this run)")
print(f"probe lost          {lost}")
if first and last and last > first:
    print(f"probe window        {(last - first) / 1e9:.1f} s")

if not tries and not connected:
    print("\nverdict             this run has no probe events (run it with -p)")
elif tries and not connected:
    print("\nverdict             the normal UE never connected")
elif lost:
    print(f"\nverdict             the normal UE connected and was dropped {lost} time(s)")
else:
    print("\nverdict             the normal UE connected and stayed connected")
