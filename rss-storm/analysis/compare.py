#!/usr/bin/env python3
"""compare.py — one line per run: attacker load, gNB response, probe outcome.

usage: compare.py <suite-tag> [run-dir-root]

The probe columns are the goal condition. attach_s is how long a UE with valid
credentials needed before it had a usable PDU session; NONE means it never got
one inside the run. RA/PDU are NAS milestone counts from the probe's own log:
a probe can be RRC-connected in 119 ms and still show RA=0.
"""
import json, pathlib, re, sys

ORDER = ["M1_1", "M2_1", "M3_1", "M1_2", "M2_2", "M3_2",
         "M1_3", "M2_3", "M3_3", "M1_4", "M2_4", "M3_4", "L2_1", "L2_2"]


def read_counts(f: pathlib.Path):
    """Parse the gNB/NAS counts leniently.

    Runs up to 2026-10-26 08:50 wrote this file with `grep -c ... || echo 0`,
    and `grep -c` prints 0 *and* exits 1 when nothing matches, so each zero
    arrived as two lines and the JSON is invalid. The first integer after a key
    is the real count either way.
    """
    if not f.exists():
        return {}
    txt = f.read_text(errors="replace")
    try:
        return json.loads(txt)
    except ValueError:
        return {k: int(v) for k, v in re.findall(r'"(\w+)":\s*(\d+)', txt)}


def row(d: pathlib.Path, name: str):
    att = held = 0
    occ, t = [], []
    for ln in (d / "attempts.jsonl").read_text(errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ev = e.get("event")
        if not ev:
            continue
        if ev == "attempt_start":
            att += 1
        if ev == "msg4_ack_withheld":
            held += 1
        if "occupancy" in e:
            occ.append(e["occupancy"])
        if "t_ns" in e:
            t.append(e["t_ns"])
    span = (max(t) - min(t)) / 1e9 if len(t) > 1 else 0.0
    occ.sort()
    g = read_counts(d / "gnb_nas.json")
    p = json.loads((d / "probe_data.json").read_text()) if (d / "probe_data.json").exists() else {}
    attach = "%.1f" % p["attach_s"] if p.get("attach_s") is not None else "NONE"
    return ("%-7s %6.1f %6d %6.1f %7s %7s %6d %8s %8s %8s %6s %4s %4s" % (
        name, span, att, (att / span if span else 0.0),
        occ[len(occ) // 2] if occ else "-", occ[-1] if occ else "-", held,
        g.get("conres_ce_acked", "-"), g.get("dl_harq_maxretx_discard", "-"),
        attach, p.get("loss_pct", "-") if isinstance(p.get("loss_pct"), (int, float)) else "-",
        g.get("registration_accept", "-"), g.get("pdu_accept", "-")))


def main(a):
    tag = a[0]
    root = pathlib.Path(a[1] if len(a) > 1 else "/root/rss-runs")
    print("%-7s %6s %6s %6s %7s %7s %6s %8s %8s %8s %6s %4s %4s" % (
        "run", "span", "att", "att/s", "occp50", "occmax", "held",
        "conrACK", "dlretx5", "attach_s", "loss%", "RA", "PDU"))
    print("-" * 110)
    for n in ORDER:
        d = root / f"{n}-{tag}"
        if (d / "attempts.jsonl").exists():
            print(row(d, n))


if __name__ == "__main__":
    main(sys.argv[1:])
