#!/usr/bin/env bash
# A/B the RA-in-flight gate at whatever gNB config is currently loaded.
# Run ON THE DU BOX. Samples CPU of odu and the UE to tell a logic problem
# apart from the UE simply not running in real time.
set -euo pipefail
DUR=${DUR:-25}
IV=${IV:-0}
LIST=${LIST:-"0 1"}

for G in $LIST; do
  RID="GATE${G}-$(date -u +%H%M%SZ)"
  echo "##### ra_gate=$G run_id=$RID start=$(date -u +%FT%T.%3NZ)"
  ( for i in $(seq 1 20); do
      top -b -n1 -o %CPU 2>/dev/null | grep -E 'odu|nr-uesoftmodem' >> "/tmp/cpu_$RID.txt" || true
      sleep 2
    done ) >/dev/null 2>&1 &
  SAMP=$!
  bash /tmp/run_attack.sh -e 1 -i "$IV" -G "$G" -d "$DUR" -n "$RID" > "/tmp/run_$RID.txt" 2>&1 || true
  kill $SAMP 2>/dev/null || true
  wait $SAMP 2>/dev/null || true

  python3 - "/root/rss-runs/$RID/attempts.jsonl" <<'PY'
import json,sys,statistics,os
p=sys.argv[1]
if not os.path.exists(p):
    print("   NO JSONL"); raise SystemExit
ev=[json.loads(l) for l in open(p) if l.strip()]
def n(e): return sum(1 for x in ev if x['event']==e)
t=[x['t_ns'] for x in ev]; span=(max(t)-min(t))/1e9 if len(t)>1 else 0
att,m4=n('attempt_start'),n('msg4_rx')
tr=[x['ms_per_tick'] for x in ev if x['event']=='tick_rate']
by={}
for e in ev: by.setdefault(e['seq'],{})[e['event']]=e['t_ns']
a2m=[(v['msg4_rx']-v['attempt_start'])/1e6 for v in by.values() if 'msg4_rx' in v and 'attempt_start' in v]
m2r=[(v['retrigger']-v['msg4_rx'])/1e6 for v in by.values() if 'msg4_rx' in v and 'retrigger' in v]
print(f"   span={span:5.1f}s attempts={att:4d} msg4={m4:4d} wasted={1-m4/max(att,1):5.1%} "
      f"msg4_hz={m4/span if span else 0:5.2f} ms_per_tick={statistics.median(tr) if tr else 0:5.1f}")
print(f"   gate_hold={n('gate_hold'):4d} gate_forced={n('gate_forced'):3d} ack_wait={n('ack_pending_postpone'):3d} "
      f"RA_cycle_med={statistics.median(a2m) if a2m else 0:6.1f}ms retrig_lat_med={statistics.median(m2r) if m2r else 0:6.1f}ms")
PY
  echo "   --- CPU% (odu / UE), last 4 samples"
  tail -4 "/tmp/cpu_$RID.txt" 2>/dev/null | awk '{printf "   %s %s%%  %s\n", $1, $9, $12}' || echo "   (none)"
  echo "##### stop=$(date -u +%FT%T.%3NZ)"
done
echo "=== nproc=$(nproc)"
