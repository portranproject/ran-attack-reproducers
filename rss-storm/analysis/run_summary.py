#!/usr/bin/env python3
"""run_summary.py — UE-side totals for one or more runs, next to the data plane.

Reads attempts.jsonl, so the figures are the attacker's own ground truth. The
rates are per second of the measured span, not of the configured duration.

usage: run_summary.py <run-dir> [...]
"""
import json, pathlib, sys


def one(d: pathlib.Path):
    r = {"run": d.name}
    try:
        r["knobs"] = json.loads((d / "run.json").read_text())["knobs"]
    except Exception:
        r["knobs"] = {}
    jl = d / "attempts.jsonl"
    if not jl.exists():
        r["error"] = "no attempts.jsonl"
        return r
    counts, occ, t = {}, [], []
    msg4_per_attempt = {}
    for ln in jl.read_text(errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ev = e.get("event")
        if not ev:
            continue
        counts[ev] = counts.get(ev, 0) + 1
        if "t_ns" in e:
            t.append(e["t_ns"])
        if "occupancy" in e:
            occ.append(e["occupancy"])
        # Each withheld ACK is one Msg4 copy the UE decoded, so counting them
        # per attempt counts the gNB's DL HARQ retransmissions.
        if ev == "msg4_ack_withheld":
            k = (e.get("ue"), e.get("seq"))
            msg4_per_attempt[k] = msg4_per_attempt.get(k, 0) + 1
    span = (max(t) - min(t)) / 1e9 if len(t) > 1 else 0.0
    r["span_s"] = round(span, 2)
    r["events"] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    att = counts.get("attempt_start", 0)
    r["attempts"] = att
    r["attempt_rate_s"] = round(att / span, 1) if span else None
    r["msg4_rx"] = counts.get("msg4_rx", 0)
    r["ack_withheld"] = counts.get("msg4_ack_withheld", 0)
    if msg4_per_attempt:
        v = sorted(msg4_per_attempt.values())
        r["msg4_copies_per_attempt"] = {
            "n": len(v), "mean": round(sum(v) / len(v), 2),
            "p50": v[len(v) // 2], "max": v[-1],
        }
    if occ:
        occ_s = sorted(occ)
        r["occupancy"] = {"p50": occ_s[len(occ_s) // 2], "p95": occ_s[int(len(occ_s) * .95)],
                          "max": occ_s[-1], "samples": len(occ_s)}
    return r


def main(a):
    if not a:
        sys.exit(__doc__)
    rows = [one(pathlib.Path(x)) for x in a]
    print(json.dumps(rows, indent=1))
    print()
    hdr = f"{'run':24} {'M':>2} {'A':>2} {'span':>6} {'att':>6} {'att/s':>6} {'msg4rx':>7} {'held':>6} {'cps':>5} {'occ_p50':>8} {'occ_max':>8}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        k, o = r.get("knobs", {}), r.get("occupancy", {})
        c = r.get("msg4_copies_per_attempt", {})
        print(f"{r['run'][:24]:24} {k.get('msg4_wait','-'):>2} {k.get('msg4_ack','-'):>2} "
              f"{r.get('span_s','-'):>6} {r.get('attempts','-'):>6} {r.get('attempt_rate_s','-'):>6} "
              f"{r.get('msg4_rx','-'):>7} {r.get('ack_withheld','-'):>6} {c.get('mean','-'):>5} "
              f"{o.get('p50','-'):>8} {o.get('max','-'):>8}")


if __name__ == "__main__":
    main(sys.argv[1:])
