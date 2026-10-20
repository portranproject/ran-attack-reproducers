#!/usr/bin/env bash
# Verdict for one A-type run. CU log part must run ON THE CU BOX.
set -euo pipefail

OCU_LOG=${OCU_LOG:-/tmp/ocu.log}
SINCE=${SINCE:-}   # optional "HH:MM:SS" to limit to one run
JSONL=${JSONL:-}

# Compare SINCE against the time field only. Comparing the whole line is wrong:
# every line starts with "2026-10-20T04:..." which is lexicographically greater
# than any "HH:MM:SS", so the filter passed the entire log and run totals were
# read as whole-log totals (observed 2026-10-20: "timed out 413" for a run that
# had 11). UNTIL bounds the other end.
UNTIL=${UNTIL:-}
cut_log() {
  awk -v s="$SINCE" -v u="$UNTIL" '
    {
      t = $1; sub(/^[^T]*T/, "", t)        # 2026-10-20T04:32:29.123 -> 04:32:29.123
      if (s != "" && t < s) next
      if (u != "" && t > u) next
      print
    }' "$OCU_LOG"
}

echo "== CU side ($OCU_LOG)"
started=$(cut_log | grep -c '"RRC Setup Procedure" started' || true)
timedout=$(cut_log | grep -c '"RRC Setup Procedure" timed out' || true)
finished=$(cut_log | grep -c '"RRC Setup Procedure" finished successfully' || true)
req=$(cut_log | grep -c 'rrcSetupRequest' || true)
comp=$(cut_log | grep -c 'rrcSetupComplete' || true)
# OCUDU 26.10 writes: [NGAP] Tx PDU ue=0 ...: InitialUEMessage (box-verified 2026-10-20)
ngap=$(cut_log | grep -cE 'NGAP.*InitialUEMessage' || true)
printf 'rrcSetupRequest   %s\nprocedure started %s\ntimed out (2000ms) %s\nfinished OK       %s\nrrcSetupComplete  %s\nNGAP InitialUEMsg %s\n' \
  "$req" "$started" "$timedout" "$finished" "$comp" "$ngap"

echo
echo "== M1a verdict"
if (( timedout > 0 && comp == 0 && ngap == 0 )); then
  echo "PASS candidate: incomplete procedures accumulate, no Msg5, core never reached."
elif (( timedout > 0 && comp > 0 )); then
  echo "MIXED: some attempts completed. Check completion_pct and the ~8% ZMQ Msg5 loss baseline."
else
  echo "FAIL/UNCLEAR: no timeouts recorded. Check that the UE really ran with --rss.enable 1."
fi

if [[ -n "$JSONL" && -f "$JSONL" ]]; then
  echo
  echo "== UE side ($JSONL)"
  for e in attempt_start msg4_rx retrigger ack_pending_postpone rrc_reject kill_switch; do
    printf '%-22s %s\n' "$e" "$(grep -c "\"event\":\"$e\"" "$JSONL" || true)"
  done
  echo "msg5_skip attempts    $(grep -c 'msg5_skip' "$JSONL" || true)"
  echo "msg5_sent attempts    $(grep -c 'msg5_sent' "$JSONL" || true)"
fi
