#!/usr/bin/env python3
"""Verify that every JSONL record carries its UE instance and a per-UE seq.

With --num-ues > 1 the attempt streams interleave, so a single global seq makes
per-attempt joins impossible. Run on the DU box:
  python3 check_ue_labels.py /root/rss-runs/<RUN>/attempts.jsonl
"""
import collections, json, sys

path = sys.argv[1]
ev = [json.loads(l) for l in open(path) if l.strip()]
per = collections.Counter(e.get("ue") for e in ev)
print("records per ue:", dict(per))
if None in per:
    print("  !! records without a 'ue' field: labels are not per-UE")
for u in sorted(k for k in per if k is not None):
    seqs = [e["seq"] for e in ev if e.get("ue") == u]
    starts = [e for e in ev if e.get("ue") == u and e["event"] == "attempt_start"]
    m4 = [e for e in ev if e.get("ue") == u and e["event"] == "msg4_rx"]
    print("  ue=%s records=%d max_seq=%d attempts=%d msg4=%d"
          % (u, len(seqs), max(seqs), len(starts), len(m4)))
