#!/usr/bin/env bash
# Rate sweep for the A-type reproducer. Run ON THE DU BOX (as root).
# Runs the reproducer once per interval value and prints one summary line each,
# so "configured interval" can be compared against "realised rate".
#
#   bash sweep.sh -d 20 -l "0 20 50 100"
set -euo pipefail

DUR=20
LIST="0 20 50 100"
TAG="sweep-$(date -u +%Y%m%dT%H%M%SZ)"
LOGDIR=${LOGDIR:-/root/rss-runs}

while getopts "d:l:n:h" o; do case "$o" in
  d) DUR=$OPTARG;; l) LIST=$OPTARG;; n) TAG=$OPTARG;; *) echo "usage: $0 [-d sec] [-l \"0 20 50\"] [-n tag]"; exit 1;; esac; done

SUM="$LOGDIR/$TAG.tsv"
mkdir -p "$LOGDIR"
printf 'run_id\tinterval_ms\tt_start_utc\tt_stop_utc\tattempts\tmsg4\tretrigger\tno_msg4\treject\tack_wait\tms_per_tick\tattempt_hz\tmsg4_hz\n' > "$SUM"

for IV in $LIST; do
  RID="$TAG-i${IV}"
  T0=$(date -u +%FT%T.%3NZ)
  bash "$(dirname "$0")/run_attack.sh" -e 1 -i "$IV" -d "$DUR" -n "$RID" >"$LOGDIR/$RID.out" 2>&1 || true
  T1=$(date -u +%FT%T.%3NZ)
  J="$LOGDIR/$RID/attempts.jsonl"
  if [[ -f "$J" ]]; then
    python3 - "$J" "$RID" "$IV" "$T0" "$T1" "$SUM" <<'PY'
import json,sys,statistics
j,rid,iv,t0,t1,summ=sys.argv[1:7]
ev=[json.loads(l) for l in open(j) if l.strip()]
def n(e): return sum(1 for x in ev if x['event']==e)
t=[x['t_ns'] for x in ev]
span=(max(t)-min(t))/1e9 if len(t)>1 else 0
att,m4=n('attempt_start'),n('msg4_rx')
tr=[x['ms_per_tick'] for x in ev if x['event']=='tick_rate']
mpt=statistics.median(tr) if tr else float('nan')
row=[rid,iv,t0,t1,att,m4,n('retrigger'),
     sum(1 for x in ev if x.get('actual_reach')=='no_msg4'),n('rrc_reject'),
     n('ack_pending_postpone'),f"{mpt:.2f}",
     f"{att/span:.2f}" if span else "0", f"{m4/span:.2f}" if span else "0"]
open(summ,'a').write("\t".join(str(c) for c in row)+"\n")
print("  ->", " ".join(str(c) for c in row[1:]))
PY
  else
    echo "  -> $RID: no JSONL (run failed, see $LOGDIR/$RID.out)"
  fi
done

echo
echo "== sweep summary ($SUM)"
column -t -s$'\t' "$SUM"
