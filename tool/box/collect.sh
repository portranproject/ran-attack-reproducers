#!/usr/bin/env bash
# Verdict for one A-type run. CU log part must run ON THE CU BOX.
set -euo pipefail

OCU_LOG=${OCU_LOG:-/tmp/ocu.log}
SINCE=${SINCE:-}   # optional "HH:MM:SS" to limit to one run
JSONL=${JSONL:-}

cut_log() { if [[ -n "$SINCE" ]]; then awk -v s="$SINCE" '$0 >= s' "$OCU_LOG"; else cat "$OCU_LOG"; fi; }

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
