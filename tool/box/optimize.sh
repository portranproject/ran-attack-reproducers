#!/usr/bin/env bash
# Real-time optimisation sweep for the attacker UE. Run ON THE DU BOX.
# Each variant answers one question: does the RRC tick get closer to 10 ms,
# and does the realised Msg4 rate rise? gNB config is never touched here.
set -u
DUR=${DUR:-30}

run() {
  local tag="$1"; shift
  local rid="OPT-${tag}-$(date -u +%H%M%SZ)"
  echo "### $tag"
  env "$@" bash /tmp/run_attack.sh -e 1 -i 0 -d "$DUR" -n "$rid" >/tmp/opt_$tag.txt 2>&1 || true
  python3 - "/root/rss-runs/$rid/attempts.jsonl" "$tag" <<'PY'
import json,sys,statistics,os
p,tag=sys.argv[1],sys.argv[2]
if not os.path.exists(p):
    print(f"   {tag}: NO JSONL"); raise SystemExit
ev=[json.loads(l) for l in open(p) if l.strip()]
tr=[x['ms_per_tick'] for x in ev if x['event']=='tick_rate']
att=sum(1 for x in ev if x['event']=='attempt_start')
pre=sum(1 for x in ev if x['event']=='setup_req_prebuilt')
m4=sum(1 for x in ev if x['event']=='msg4_rx')
t=[x['t_ns'] for x in ev]; span=(max(t)-min(t))/1e9 if len(t)>1 else 0
by={}
for e in ev: by.setdefault(e['seq'],{})[e['event']]=e['t_ns']
a2m=[(v['msg4_rx']-v['attempt_start'])/1e6 for v in by.values() if 'msg4_rx' in v and 'attempt_start' in v]
tick=statistics.median(tr) if tr else 0
hz=m4/span if span else 0
print(f"   {tag:16s} span={span:5.1f}s attempts={att:4d} prebuilt={pre:4d} msg4={m4:4d} "
      f"msg4_hz={hz:5.2f} tick={tick:5.1f}ms RA={statistics.median(a2m) if a2m else 0:6.1f}ms "
      f"=> N@2s={hz*2:5.1f} / 96")
PY
}

run baseline
run loglevel        UE_EXTRA="--log_config.global_log_level error"
run pinned          UE_TASKSET=3-7 ODU_TASKSET=0-2
run log+pin         UE_EXTRA="--log_config.global_log_level error" UE_TASKSET=3-7 ODU_TASKSET=0-2
run log+pin+actors  UE_EXTRA="--log_config.global_log_level error --num-dl-actors 0 --num-ul-actors 0" UE_TASKSET=3-7 ODU_TASKSET=0-2
