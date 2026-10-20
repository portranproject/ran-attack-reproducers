#!/usr/bin/env bash
# Steady-state CPU of odu and the attacker UE process, sampled only while the
# attack is actually running. This decides whether multi-UE scaling flattens
# because the DU box runs out of cores or because of the sharing implementation.
#
#   sudo DUR=40 UES=2 bash cpu_per_ue.sh
set -u
DUR=${DUR:-40}
UES=${UES:-1}
RID="CPU${UES}-$(date -u +%H%M%SZ)"
J="/root/rss-runs/$RID/attempts.jsonl"

echo "### ues=$UES run=$RID nproc=$(nproc)"
bash /home/ubuntu/rss-tools/run_attack.sh -e 1 -i 0 -u "$UES" -d "$DUR" -n "$RID" \
  >/home/ubuntu/rss-tools/cpu_$RID.txt 2>&1 &
JOB=$!

# wait for the attack to produce its first record, then sample
for i in $(seq 1 120); do
  [ -s "$J" ] && break
  sleep 1
done
UE=$(pgrep -x nr-uesoftmodem | head -1 || true)
ODU=$(pgrep -x odu | head -1 || true)
echo "attack live after ${i}s  UE=${UE:-none} ODU=${ODU:-none}"

if [ -n "${UE:-}" ]; then
  for k in 1 2 3 4 5; do
    ps -o comm=,pcpu=,nlwp= -p "${UE}" "${ODU:-1}" 2>/dev/null | awk '{printf "  %-16s cpu=%6s%% threads=%s\n", $1, $2, $3}'
    echo "  ---"
    sleep 3
  done
  echo "idle/total from /proc/loadavg: $(cat /proc/loadavg)"
else
  echo "  UE process not found; attack never started"
fi

wait $JOB 2>/dev/null || true
python3 /home/ubuntu/rss-tools/phase_breakdown.py "$J" 2>&1 | grep -E 'air_per_wall|rate at p50' || true
