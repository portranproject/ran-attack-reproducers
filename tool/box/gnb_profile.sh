#!/usr/bin/env bash
# gNB SATURATION PROFILE — configuration only, OCUDU source is never touched.
#
# Why this exists: at default settings one attacker UE reaches ~3.8 Msg4/s, so
# N = R * T_hold = ~7.6 incomplete contexts against a measured cell capacity of
# 96. Saturation needs R * T_hold >= N_cap, so the profile moves the two terms
# the operator controls through configuration:
#   - N_cap  : cell_cfg.pucch.nof_cell_sr_res  8 -> 1   (capacity = min(SR,CSI,...))
#   - T_hold : cell_cfg.sib.t300               1000 -> 2000  (DU, 3GPP max)
#              cu_cp.rrc.rrc_procedure_guard_time_ms 1000 -> 5000  (CU)
# Runs on the box that owns the file. Keeps a .orig backup and is idempotent.
#
#   bash gnb_profile.sh --role du  apply|restore|show
#   bash gnb_profile.sh --role cu  apply|restore|show
set -euo pipefail

ROLE=""
SR_RES=${SR_RES:-1}
T300=${T300:-2000}
GUARD_MS=${GUARD_MS:-5000}
CFGDIR=${CFGDIR:-/root/OCUDU/configs}

while [[ $# -gt 0 ]]; do case "$1" in
  --role) ROLE="$2"; shift 2;;
  apply|restore|show) ACTION="$1"; shift;;
  *) echo "usage: $0 --role cu|du apply|restore|show"; exit 1;;
esac; done
[[ -n "$ROLE" && -n "${ACTION:-}" ]] || { echo "usage: $0 --role cu|du apply|restore|show"; exit 1; }

case "$ROLE" in
  du) F="$CFGDIR/du.yaml";;
  cu) F="$CFGDIR/cu.yaml";;
  *)  echo "role must be cu or du"; exit 1;;
esac
[[ -f "$F" ]] || { echo "missing $F"; exit 1; }
[[ -f "$F.orig" ]] || cp -p "$F" "$F.orig"

BEGIN="# RSS-PROFILE BEGIN (saturation, config only - remove to restore)"
END="# RSS-PROFILE END"

strip() { python3 - "$1" <<'PY'
import sys
p=sys.argv[1]; out=[]; skip=False
for l in open(p):
    if 'RSS-PROFILE BEGIN' in l: skip=True; continue
    if 'RSS-PROFILE END' in l: skip=False; continue
    if not skip: out.append(l)
open(p,'w').writelines(out)
PY
}

case "$ACTION" in
  show)
    echo "== $F"; grep -nE 'nof_cell_sr_res|t300|rrc_procedure_guard_time_ms|RSS-PROFILE' "$F" || echo "  (profile not applied)"
    ;;
  restore)
    strip "$F"
    echo "== profile removed from $F (backup kept at $F.orig)"
    diff -u "$F.orig" "$F" && echo "   identical to .orig"
    ;;
  apply)
    strip "$F"
    if [[ "$ROLE" == du ]]; then
      python3 - "$F" "$BEGIN" "$END" "$SR_RES" "$T300" <<'PY'
import sys
p,b,e,sr,t300=sys.argv[1:6]
out=[]
for l in open(p):
    out.append(l)
    if l.startswith('cell_cfg:'):
        out += [b+"\n",
                f"  pucch: {{ nof_cell_sr_res: {sr} }}   # N_cap driver\n",
                f"  sib:   {{ t300: {t300} }}            # T_hold driver (3GPP max 2000)\n",
                e+"\n"]
open(p,'w').writelines(out)
PY
    else
      python3 - "$F" "$BEGIN" "$END" "$GUARD_MS" <<'PY'
import sys
p,b,e,g=sys.argv[1:5]
out=[]
for l in open(p):
    out.append(l)
    if l.startswith('cu_cp:'):
        out += [b+"\n",
                f"  rrc: {{ rrc_procedure_guard_time_ms: {g} }}   # T_hold driver\n",
                e+"\n"]
open(p,'w').writelines(out)
PY
    fi
    echo "== applied to $F"; sed -n '1,30p' "$F"
    ;;
esac
