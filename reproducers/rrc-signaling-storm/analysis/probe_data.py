#!/usr/bin/env python3
"""probe_data.py — what the probe UE's data plane actually did.

Every availability figure taken before this was a CONNECTION figure. The goal
condition has two halves, "cannot connect" and "cannot communicate", and only
the first was ever measured. This reads the `ping -D` log that bin/rss-probe
writes and reports the second half.

The headline number is max_gap_s: the longest stretch with no reply at all.
That is the duration a normal UE could not communicate.

usage: probe_data.py <run-dir> [<run-dir> ...]
"""
import json, pathlib, re, statistics, sys

LINE = re.compile(r"^\[(\d+\.\d+)\].*icmp_seq=(\d+).*time=([\d.]+) ms")
SUMM = re.compile(r"(\d+) packets transmitted, (\d+) received.*?([\d.]+)% packet loss")


def one(d: pathlib.Path):
    png = d / "probe_ping.txt"
    out = {"run": d.name}
    meta = d / "probe_data.json"
    if meta.exists():
        try:
            out.update(json.loads(meta.read_text()))
        except ValueError:
            pass
    if not png.exists() or not png.stat().st_size:
        out["error"] = "no ping log"
        return out

    ts, rtt, seqs = [], [], []
    txt = png.read_text(errors="replace")
    for ln in txt.splitlines():
        m = LINE.match(ln)
        if m:
            ts.append(float(m.group(1)))
            seqs.append(int(m.group(2)))
            rtt.append(float(m.group(3)))
    m = SUMM.search(txt)
    if m:
        out["sent"], out["recv"] = int(m.group(1)), int(m.group(2))
        out["loss_pct"] = float(m.group(3))
    out["replies"] = len(rtt)
    if not rtt:
        # No reply at all is the strongest possible result, not a parse failure.
        out["max_gap_s"] = None
        out["note"] = "zero replies"
        return out

    out["span_s"] = round(ts[-1] - ts[0], 2)
    rtt_s = sorted(rtt)
    out["rtt_ms"] = {
        "p50": round(statistics.median(rtt_s), 2),
        "p95": round(rtt_s[int(len(rtt_s) * 0.95)], 2),
        "max": round(rtt_s[-1], 2),
    }
    gaps = [(ts[i + 1] - ts[i], ts[i]) for i in range(len(ts) - 1)]
    gaps.sort(reverse=True)
    out["max_gap_s"] = round(gaps[0][0], 3) if gaps else 0.0
    # A gap of 1 s is 50 lost packets at the default 20 ms spacing: long enough
    # that a voice call drops and a TCP flow stalls, so it is the useful bucket.
    out["gaps_over_1s"] = sum(1 for g, _ in gaps if g >= 1.0)
    out["gaps_over_1s_total"] = round(sum(g for g, _ in gaps if g >= 1.0), 2)
    out["top_gaps_s"] = [round(g, 3) for g, _ in gaps[:5]]
    # Seconds in which at least one reply arrived, over seconds in the window:
    # the data-plane twin of the connection-time percentage.
    live = {int(t) for t in ts}
    whole = int(ts[-1]) - int(ts[0]) + 1
    out["seconds_with_traffic_pct"] = round(100.0 * len(live) / whole, 1) if whole else None
    return out


def main(argv):
    if not argv:
        sys.exit(__doc__)
    rows = [one(pathlib.Path(a)) for a in argv]
    print(json.dumps(rows, indent=1))
    print()
    hdr = f"{'run':24} {'loss%':>6} {'p50ms':>7} {'p95ms':>8} {'maxms':>8} {'maxgap':>7} {'>1s':>4} {'live%':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        rt = r.get("rtt_ms") or {}
        print(f"{r['run'][:24]:24} {r.get('loss_pct', '-'):>6} {rt.get('p50', '-'):>7} "
              f"{rt.get('p95', '-'):>8} {rt.get('max', '-'):>8} "
              f"{r.get('max_gap_s', '-'):>7} {r.get('gaps_over_1s', '-'):>4} "
              f"{r.get('seconds_with_traffic_pct', '-'):>6}")


if __name__ == "__main__":
    main(sys.argv[1:])
