#!/usr/bin/env bash
# Start odu + UE with the A-type reproducer. Run ON THE DU BOX.
# Default is a REGRESSION run (attack off). Pass -e 1 to enable the attack.
# Team rule: attack runs only on the team's own p5 set, after user approval.
set -euo pipefail

ENABLE=0
INTERVAL_MS=100
MAX_DURATION_S=30
COMPLETION_PCT=0
HONOR_REJECT=1
ACK_GATE=1
RUN_ID="rss-$(date -u +%Y%m%dT%H%M%SZ)"
CTL=${CTL:-/root/workspace/ctl.sh}
LOGDIR=${LOGDIR:-/root/rss-runs}

usage() { echo "usage: $0 [-e 0|1] [-i interval_ms] [-d max_duration_s] [-c completion_pct] [-r honor_reject] [-g ack_gate] [-n run_id]"; exit 1; }
while getopts "e:i:d:c:r:g:n:h" o; do case "$o" in
  e) ENABLE=$OPTARG;; i) INTERVAL_MS=$OPTARG;; d) MAX_DURATION_S=$OPTARG;;
  c) COMPLETION_PCT=$OPTARG;; r) HONOR_REJECT=$OPTARG;; g) ACK_GATE=$OPTARG;;
  n) RUN_ID=$OPTARG;; *) usage;; esac; done

mkdir -p "$LOGDIR/$RUN_ID"
JSONL="$LOGDIR/$RUN_ID/attempts.jsonl"

RSS_ARGS="--rss.enable $ENABLE --rss.interval_ms $INTERVAL_MS --rss.max_duration_s $MAX_DURATION_S \
 --rss.completion_pct $COMPLETION_PCT --rss.honor_reject $HONOR_REJECT --rss.ack_gate $ACK_GATE \
 --rss.run_id $RUN_ID --rss.log_file $JSONL"

cat > "$LOGDIR/$RUN_ID/run.json" <<EOF
{"run_id":"$RUN_ID","scenario":"$([[ $ENABLE == 1 ]] && echo A || echo baseline)","rf_path":"zmq",
 "knobs":{"enable":$ENABLE,"interval_ms":$INTERVAL_MS,"completion_pct":$COMPLETION_PCT,
 "honor_reject":$HONOR_REJECT,"ack_gate":$ACK_GATE,"max_duration_s":$MAX_DURATION_S},
 "ue_commit":"$(git -C ${OAI:-/root/OAI} rev-parse --short HEAD)","t_start_utc":"$(date -u +%FT%TZ)"}
EOF

echo "== run_id=$RUN_ID enable=$ENABLE interval=${INTERVAL_MS}ms kill=${MAX_DURATION_S}s"
echo "== odu+UE must restart together (UE-only restart desyncs the ZMQ stream)"
echo "== extra UE args: $RSS_ARGS"
echo
echo "Pass these to the UE launched by $CTL (see tool/README.md: UE_EXTRA_ARGS)."
echo "Hard kill switch beyond the in-process one:"
echo "  timeout $((MAX_DURATION_S + 15)) <ue command> $RSS_ARGS"
echo
echo "JSONL ground truth: $JSONL"
