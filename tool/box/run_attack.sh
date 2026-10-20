#!/usr/bin/env bash
# Start odu + the A-type reproducer UE. Run ON THE DU BOX (as root).
#
# Why this script exists instead of "ctl.sh ue":
#  - the box's ctl.sh hardcodes the UE argument list (no hook for extra args);
#  - its ue_up() waits for "oaitun_ue1 successfully configured", which never
#    happens in A-type (no RRCSetupComplete -> no PDU session) and would make it
#    restart odu+UE twice and report failure.
# It still restarts odu immediately before the UE, which is the ZMQ requirement.
#
# Default is a REGRESSION run (attack off). Team rule: attack only on our own
# p5 set, after user approval, always with a kill switch.
set -euo pipefail

ENABLE=0
INTERVAL_MS=100
MAX_DURATION_S=30
COMPLETION_PCT=0
HONOR_REJECT=1
ACK_GATE=1
TARGET_OCC=0
HOLD_MS=2000
RA_GATE=1
NUM_UES=1          # in-process attacker UE instances sharing the one DU radio
RUN_ID=""
BOX_CTL=${BOX_CTL:-/root/workspace/ctl.sh}
OAI=${OAI:-/root/OAI}
UE_BIN=${UE_BIN:-$OAI/cmake_targets/ran_build/build/nr-uesoftmodem}
UE_CFG=${UE_CFG:-/root/oai_nrue.conf}
UECAP=${UECAP:-$OAI/targets/PROJECTS/GENERIC-NR-5GC/CONF/uecap_ports1.xml}
LOGDIR=${LOGDIR:-/root/rss-runs}
# Real-time tuning (see checklist §11.3: the RRC tick ran 26-36 ms instead of
# 10 ms, so the UE was not keeping up with the air interface).
UE_EXTRA=${UE_EXTRA:-}          # extra nr-uesoftmodem args, e.g. "--num-dl-actors 6"
UE_TASKSET=${UE_TASKSET:-}      # core list for the UE, e.g. "3-7"
ODU_TASKSET=${ODU_TASKSET:-}    # core list for odu, e.g. "0-2"

usage() { echo "usage: $0 [-e 0|1] [-i interval_ms] [-d max_duration_s] [-c completion_pct] [-r honor_reject] [-g ack_gate] [-o target_occupancy] [-H hold_ms] [-n run_id]"; exit 1; }
while getopts "e:i:d:c:r:g:o:H:G:u:n:h" o; do case "$o" in
  e) ENABLE=$OPTARG;; i) INTERVAL_MS=$OPTARG;; d) MAX_DURATION_S=$OPTARG;;
  c) COMPLETION_PCT=$OPTARG;; r) HONOR_REJECT=$OPTARG;; g) ACK_GATE=$OPTARG;;
  o) TARGET_OCC=$OPTARG;; H) HOLD_MS=$OPTARG;; G) RA_GATE=$OPTARG;; u) NUM_UES=$OPTARG;;
  n) RUN_ID=$OPTARG;; *) usage;; esac; done

[[ $ENABLE == 0 || $ENABLE == 1 ]] || usage
(( MAX_DURATION_S >= 1 && MAX_DURATION_S <= 600 )) || { echo "max_duration_s must be 1..600"; exit 1; }
[[ -n "$RUN_ID" ]] || RUN_ID="$([[ $ENABLE == 1 ]] && echo A || echo base)-$(date -u +%Y%m%dT%H%M%SZ)"

# Guard against an upstream OAI config bug (2026.w38,
# common/config/config_load_configmodule.c:232). The -O scan is
#     if (argv[i][1] == 'O' && i < argc - 1) { cfgparam = argv[i+1]; ... }
# with no check for a leading '-', so ANY argument whose second character is
# 'O' is taken as the -O option and the argument after it becomes the config
# file path. A run id like "CONF-043717Z" (C-O-N-F) therefore kills the UE at
# startup with "error: file --rss.log_file does not exist", before a single
# knob is parsed. Box-verified 2026-10-20: CONF-043717Z and CONF2-043950Z both
# segfaulted; ZWA100-043229Z and ZWB60-044132Z (second char 'W') ran fine.
if [[ ${RUN_ID:1:1} == O ]]; then
  echo "!! run_id '$RUN_ID' has 'O' as its second character." >&2
  echo "   OAI would mistake it for the -O config-file option and die at startup." >&2
  exit 1
fi

OUT="$LOGDIR/$RUN_ID"
mkdir -p "$OUT"
JSONL="$OUT/attempts.jsonl"
UE_LOG="$OUT/ue.log"

# per-run record (design.md §8). gnb_cfg values are the box-verified ones.
cat > "$OUT/run.json" <<EOF
{"type":"run","run_id":"$RUN_ID","scenario":"$([[ $ENABLE == 1 ]] && echo A || echo baseline)",
 "rf_path":"zmq","ue_base":"oai-nr $(git -C "$OAI" rev-parse --short HEAD 2>/dev/null)",
 "ue_branch":"$(git -C "$OAI" branch --show-current 2>/dev/null)",
 "cell":{"band":"n78","scs_khz":30,"bw_mhz":20,"prb":51},
 "gnb_cfg":{"t300_ms":1000,"guard_ms":1000,"hold_ms":2000,"rrc_reject_wait_time_s":"unset"},
 "knobs":{"enable":$ENABLE,"interval_ms":$INTERVAL_MS,"completion_pct":$COMPLETION_PCT,
          "honor_reject":$HONOR_REJECT,"ack_gate":$ACK_GATE,"max_duration_s":$MAX_DURATION_S,
          "target_occupancy":$TARGET_OCC,"hold_ms":$HOLD_MS,"ra_gate":$RA_GATE,"num_ues":$NUM_UES,
          "zmq_tx_wait_us":${RSS_ZMQ_TX_WAIT_US:-100}},
 "t_start_utc":"$(date -u +%FT%TZ)"}
EOF

echo "== run_id=$RUN_ID  enable=$ENABLE  num_ues=$NUM_UES  interval=${INTERVAL_MS}ms  target_occ=$TARGET_OCC  hold=${HOLD_MS}ms  kill=${MAX_DURATION_S}s"

# 1. odu must be restarted together with the UE (ZMQ sample stream sync)
echo "== restarting odu"
"$BOX_CTL" stop >/dev/null 2>&1 </dev/null || true
# NOTE (box-verified 2026-10-20): never pipe ctl.sh here. A pipeline blocks
# forever because the pipe's write end stays open after ctl.sh returns, so the
# reader never sees EOF. Redirect to a file and print from the file instead.
"$BOX_CTL" start >"$OUT/odu_boot.txt" 2>&1 </dev/null \
  || { echo "   !! odu start failed"; tail -8 "$OUT/odu_boot.txt"; exit 1; }
sed -n '1,6p' "$OUT/odu_boot.txt"
grep -q 'E2(KPM)→RIC OK' "$OUT/odu_boot.txt" || echo "   (warning: E2 not confirmed)"

# 2. UE. Hard outer kill switch on top of the in-process --rss.max_duration_s.
if [[ -n "$ODU_TASKSET" ]]; then
  for p in $(pgrep -x odu); do taskset -apc "$ODU_TASKSET" "$p" >/dev/null 2>&1 || true; done
  echo "== pinned odu -> cores $ODU_TASKSET"
fi

PIN=()
[[ -n "$UE_TASKSET" ]] && PIN=(taskset -c "$UE_TASKSET") && echo "== pinning UE -> cores $UE_TASKSET"
EXTRA=()
[[ -n "$UE_EXTRA" ]] && read -r -a EXTRA <<< "$UE_EXTRA" && echo "== extra UE args: $UE_EXTRA"

echo "== launching UE (log: $UE_LOG)"
timeout --signal=INT --kill-after=10 "$((MAX_DURATION_S + 20))" \
  "${PIN[@]}" "$UE_BIN" -O "$UE_CFG" --band 78 -C 3489420000 --numerology 1 -r 51 -E --ue-scan-carrier \
  --uecap_file "$UECAP" --device.name oai_zmqdevif \
  '--zmq.[0].tx_channels' tcp://127.0.0.1:4557 '--zmq.[0].rx_channels' tcp://127.0.0.1:4556 \
  --rss.enable "$ENABLE" --rss.interval_ms "$INTERVAL_MS" --rss.max_duration_s "$MAX_DURATION_S" \
  --rss.completion_pct "$COMPLETION_PCT" --rss.honor_reject "$HONOR_REJECT" \
  --num-ues "$NUM_UES" \
  --rss.ack_gate "$ACK_GATE" --rss.ra_gate "$RA_GATE" \
  --rss.target_occupancy "$TARGET_OCC" --rss.hold_ms "$HOLD_MS" \
  --rss.run_id "$RUN_ID" --rss.log_file "$JSONL" "${EXTRA[@]}" \
  >"$UE_LOG" 2>&1 </dev/null || echo "   (UE exited: rc=$? — expected when the kill switch fires)"

pkill -9 -x nr-uesoftmodem 2>/dev/null || true
echo "\"t_stop_utc\":\"$(date -u +%FT%TZ)\"" >> "$OUT/run.json.tail"

# 3. quick self-check
echo "== self-check"
if [[ $ENABLE == 1 ]]; then
  grep -m1 '\[RSS\]' "$UE_LOG" || echo "   !! no [RSS] banner: the knobs were NOT parsed, run is invalid"
fi
printf '   attempts   %s\n' "$(grep -c '"event":"attempt_start"' "$JSONL" 2>/dev/null || echo 0)"
printf '   msg5_skip  %s\n' "$(grep -c 'msg5_skip' "$JSONL" 2>/dev/null || echo 0)"
printf '   ack_wait   %s\n' "$(grep -c 'ack_pending_postpone' "$JSONL" 2>/dev/null || echo 0)"
echo "== artifacts in $OUT"
echo "   next: on the CU box  SINCE=<HH:MM:SS> JSONL=$JSONL bash collect.sh"
