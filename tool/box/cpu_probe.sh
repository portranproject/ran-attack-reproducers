#!/usr/bin/env bash
# Measure the attacker UE while the attack is actually running (not during init).
set -u
DUR=${DUR:-50}
PIN=${PIN:-0}
RID="PRB${PIN}-$(date -u +%H%M%SZ)"
echo "### pin=$PIN run=$RID nproc=$(nproc)"

bash /tmp/run_attack.sh -e 1 -i 0 -d "$DUR" -n "$RID" >/tmp/run_$RID.txt 2>&1 &
JOB=$!

# run_attack restarts odu first, so wait for BOTH to be live and for the
# attack to have produced its first events before sampling anything.
J="/root/rss-runs/$RID/attempts.jsonl"
for i in $(seq 1 90); do
  [ -s "$J" ] && break
  sleep 1
done
UE=$(pgrep -x nr-uesoftmodem | head -1 || true)
ODU=$(pgrep -x odu | head -1 || true)
echo "UE=${UE:-none} ODU=${ODU:-none} (attack live after ${i}s)"

if [ "$PIN" = 1 ] && [ -n "${UE:-}" ] && [ -n "${ODU:-}" ]; then
  taskset -apc 0-2 "$ODU" >/dev/null 2>&1 && echo "pinned odu -> 0-2"
  taskset -apc 3-7 "$UE"  >/dev/null 2>&1 && echo "pinned UE  -> 3-7"
  sleep 3
fi

echo "--- steady-state %CPU / threads"
for i in 1 2 3; do
  ps -o pid,comm,pcpu,nlwp -p ${UE:-1} ${ODU:-1} 2>/dev/null | tail -n +2
  sleep 2
done
echo "--- cpu totals"; grep 'cpu ' /proc/stat; uptime

wait $JOB 2>/dev/null || true
python3 - "$J" <<'PY'
import json,sys,statistics,os
p=sys.argv[1]
if not os.path.exists(p): print("  NO JSONL"); raise SystemExit
ev=[json.loads(l) for l in open(p) if l.strip()]
tr=[x['ms_per_tick'] for x in ev if x['event']=='tick_rate']
m4=sum(1 for x in ev if x['event']=='msg4_rx')
t=[x['t_ns'] for x in ev]; span=(max(t)-min(t))/1e9 if len(t)>1 else 0
by={}
for e in ev: by.setdefault(e['seq'],{})[e['event']]=e['t_ns']
a2m=[(v['msg4_rx']-v['attempt_start'])/1e6 for v in by.values() if 'msg4_rx' in v and 'attempt_start' in v]
print(f"  RESULT msg4={m4} span={span:.1f}s msg4_hz={m4/span if span else 0:.2f} "
      f"ms_per_tick={statistics.median(tr) if tr else 0:.1f} RA_cycle_med={statistics.median(a2m) if a2m else 0:.1f}ms")
PY
